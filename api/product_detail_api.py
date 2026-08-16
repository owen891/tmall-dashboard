import csv
import io
from datetime import date

from flask import Blueprint, request, Response

from api.api_response import evidence_level_for, failure, limitations_for, success
from db import get_db, get_shop_id
from repos.actions_repo import ActionsRepo
from services.lifecycle_service import lifecycle_service
from services.metric_definitions import derive_metrics
from services.source_resolution_service import lineage_for_product_day
from services.shop_scope_service import reject_legacy_shop_scope


product_detail_bp = Blueprint('product_detail', __name__)


def _validate_range(start, end):
    try:
        parsed_start = date.fromisoformat(start) if start else None
        parsed_end = date.fromisoformat(end) if end else None
    except ValueError:
        return '日期必须使用 YYYY-MM-DD 格式'
    if parsed_start and parsed_end and parsed_start > parsed_end:
        return '开始日期不能晚于结束日期'
    return None


def _monthly_analysis(connection, product_id, start=None, end=None):
    shop_id = get_shop_id()
    date_filters = []
    date_params = [shop_id, product_id]
    if start:
        date_filters.append('date >= ?')
        date_params.append(start)
    if end:
        date_filters.append('date <= ?')
        date_params.append(end)
    date_where = f" AND {' AND '.join(date_filters)}" if date_filters else ''
    rows = connection.execute(
        f'''SELECT substr(date, 1, 7) AS month,
                  SUM(payment_amount) AS payment_amount,
                  SUM(refund_amount) AS refund_amount,
                  SUM(payment_amount - refund_amount) AS net_sales,
                  SUM(ipv) AS product_visitors,
                  SUM(buyers) AS payment_buyers,
                  SUM(ad_spend) AS ad_spend,
                  COUNT(*) AS covered_days,
                  MIN(date) AS coverage_start,
                  MAX(date) AS coverage_end
           FROM daily_data WHERE shop_id = ? AND product_id = ?{date_where} GROUP BY substr(date, 1, 7) ORDER BY month''',
        tuple(date_params),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        payment = item.get('payment_amount')
        visitors = item.get('product_visitors')
        item['payment_conversion_rate'] = (item['payment_buyers'] / visitors) if payment is not None and visitors else None
        item['expense_ratio'] = (item['ad_spend'] / payment) if payment not in (None, 0) and item.get('ad_spend') is not None else None
        item['average_order_value'] = (payment / item['payment_buyers']) if payment is not None and item['payment_buyers'] else None
        result.append(item)
    comparisons = []
    contributions = []
    for index, current in enumerate(result):
        previous = result[index - 1] if index else None
        deltas = {}
        for key in ('payment_amount', 'net_sales', 'product_visitors', 'ad_spend', 'payment_conversion_rate', 'expense_ratio'):
            current_value = current.get(key)
            previous_value = previous.get(key) if previous else None
            delta = current_value - previous_value if current_value is not None and previous_value is not None else None
            pct = (delta / previous_value * 100) if delta is not None and previous_value else None
            deltas[key] = {'current': current_value, 'previous': previous_value, 'delta': delta, 'change_pct': pct}
        comparisons.append({'month': current['month'], 'previous_month': previous['month'] if previous else None,
                            'metrics': deltas,
                            'anomalies': [key for key, value in deltas.items() if value['change_pct'] is not None and abs(value['change_pct']) >= 20]})
        if previous:
            contributions.append({'month': current['month'], 'drivers': [
                {'metric': '净销售额', 'delta': deltas['net_sales']['delta'], 'direction': 'up' if (deltas['net_sales']['delta'] or 0) > 0 else 'down'},
                {'metric': '推广花费', 'delta': deltas['ad_spend']['delta'], 'direction': 'up' if (deltas['ad_spend']['delta'] or 0) > 0 else 'down'},
                {'metric': '商品访客数', 'delta': deltas['product_visitors']['delta'], 'direction': 'up' if (deltas['product_visitors']['delta'] or 0) > 0 else 'down'},
            ], 'method': '环比变化拆解，不代表因果归因'})
    return result, comparisons, contributions


@product_detail_bp.route('/api/products/<product_id>/detail')
def product_detail(product_id):
    if (denied := reject_legacy_shop_scope('商品详情')):
        return denied
    shop_id = get_shop_id()
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    invalid_range = _validate_range(start, end)
    if invalid_range:
        return failure('VALIDATION_ERROR', invalid_range, status=422)
    date_filters = []
    date_params = [shop_id]
    if start:
        date_filters.append('date >= ?')
        date_params.append(start)
    if end:
        date_filters.append('date <= ?')
        date_params.append(end)
    date_where = f" AND {' AND '.join(date_filters)}" if date_filters else ''
    with get_db() as connection:
        product = connection.execute('SELECT * FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if not product:
            return failure('NOT_FOUND', '商品不存在', status=404)
        trend = connection.execute(
            f'''SELECT date, payment_amount, refund_amount, payment_amount - refund_amount AS net_sales,
                      ipv AS product_visitors, buyers AS payment_buyers, ad_spend
               FROM daily_data WHERE shop_id = ? AND product_id = ?{date_where} ORDER BY date''', (shop_id, product_id, *date_params[1:])
        ).fetchall()
        summary = connection.execute(
            f'''SELECT SUM(payment_amount) AS payment_amount, SUM(refund_amount) AS refund_amount,
                      SUM(payment_amount - refund_amount) AS net_sales,
                      SUM(ipv) AS product_visitors, SUM(buyers) AS payment_buyers,
                      SUM(ad_spend) AS ad_spend, MAX(date) AS data_cutoff_date
               FROM daily_data WHERE shop_id = ? AND product_id = ?{date_where}''', (shop_id, product_id, *date_params[1:])
        ).fetchone()
        monthly_rows, period_comparison, contribution_analysis = _monthly_analysis(connection, product_id, start, end)
    product_data = dict(product)
    lifecycle = lifecycle_service.get(product_id)
    summary = dict(summary)
    derived = derive_metrics({
        'payment_amount': summary['payment_amount'],
        'successful_refund_amount': summary['refund_amount'],
        'product_visitors': summary['product_visitors'],
        'payment_buyers': summary['payment_buyers'],
        'ad_spend': summary['ad_spend'],
    }, names=(
        'net_sales', 'refund_rate', 'payment_conversion_rate',
        'average_order_value', 'expense_ratio',
    ))
    summary.update({
        **derived['values'],
        'metric_availability': derived['metric_availability'],
    })
    missing_inputs = derived['missing_fields']
    availability = 'no-data' if not trend else ('missing-fields' if missing_inputs else 'available')
    from repos.lifecycle_repo import LifecycleRepo
    lifecycle_history = LifecycleRepo.history(product_id)
    actions = ActionsRepo.list_actions(product_id)
    source_batches = [item for item in ({'source': 'daily_data', 'row_count': len(trend), 'coverage_start': trend[0]['date'] if trend else None, 'coverage_end': trend[-1]['date'] if trend else None},
                                        {'source': 'lifecycle_history', 'row_count': len(lifecycle_history)},
                                        {'source': 'product_actions', 'row_count': len(actions)})]
    evidence_summary = {
        'level': evidence_level_for(availability, missing_inputs=missing_inputs),
        'coverage': {'start': trend[0]['date'] if trend else None, 'end': trend[-1]['date'] if trend else None, 'days': len(trend)},
        'sources': source_batches,
        'missing_fields': missing_inputs,
        'unknowns': ['严格因果归因'] if contribution_analysis else [],
    }
    if not evidence_summary.get('unknowns'):
        evidence_summary['unknowns'] = ['strict causal attribution is unavailable']
    daily_trend = []
    for row in trend:
        item = dict(row)
        item['field_lineage'] = {}
        daily_trend.append(item)
    # The database connection is closed above; load lineage in one short read
    # transaction so legacy detail queries retain their existing shape.
    with get_db() as lineage_connection:
        for item in daily_trend:
            item['field_lineage'] = lineage_for_product_day(lineage_connection, product_id, item['date'], shop_id=shop_id)
    return success({'product': product_data, 'summary': summary,
                    'daily_trend': daily_trend,
                    'lifecycle': lifecycle, 'lifecycle_history': lifecycle_history,
                    'actions': actions, 'monthly_analysis': monthly_rows,
                    'period_comparison': period_comparison,
                    'contribution_analysis': contribution_analysis,
                    'evidence_summary': evidence_summary},
                   availability=availability,
                   capabilities={
                       'can_view': True,
                       'can_create_action': bool(trend),
                       'can_review_action': any(item.get('status') == 'pending_review' for item in actions),
                       'can_export': bool(trend),
                   },
                   evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
                   missing_inputs=missing_inputs,
                   limitations=limitations_for(availability, missing_inputs=missing_inputs),
                   freshness={'end': summary.get('data_cutoff_date')},
                   source_batches=source_batches,
                   evidence=[{'source': 'daily_data', 'row_count': len(trend), 'data_cutoff_date': summary.get('data_cutoff_date')}])


@product_detail_bp.route('/api/products/<product_id>/lineage')
def product_lineage(product_id):
    shop_id = get_shop_id()
    stat_date = (request.args.get('date') or '').strip()
    if stat_date:
        invalid_range = _validate_range(stat_date, stat_date)
        if invalid_range:
            return failure('VALIDATION_ERROR', invalid_range, status=422)
    with get_db() as connection:
        exists = connection.execute('SELECT 1 FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if not exists:
            return failure('NOT_FOUND', '商品不存在', status=404)
        if stat_date:
            lineage = lineage_for_product_day(connection, product_id, stat_date, shop_id=shop_id)
        else:
            rows = connection.execute(
                'SELECT DISTINCT date FROM daily_data WHERE shop_id = ? AND product_id = ? ORDER BY date', (shop_id, product_id)
            ).fetchall()
            lineage = {row['date']: lineage_for_product_day(connection, product_id, row['date'], shop_id=shop_id) for row in rows}
    return success({'product_id': product_id, 'date': stat_date or None, 'lineage': lineage},
                   availability='available' if lineage else 'no-data',
                   capabilities={'can_view': True},
                   evidence=[{'source': 'fact_field_lineage', 'product_id': product_id, 'date': stat_date or None}])


@product_detail_bp.route('/api/products/<product_id>/detail/export')
def export_product_detail(product_id):
    """Export the same detail evidence shown by the workbench as UTF-8 CSV."""
    capability = (request.args.get('capability_key') or request.headers.get('X-Capability-Key'))
    if capability is not None and capability != 'product-detail.export':
        return failure('FORBIDDEN', 'capability mismatch', {'capability': capability}, status=403)
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    invalid_range = _validate_range(start, end)
    if invalid_range:
        return failure('VALIDATION_ERROR', invalid_range, status=422)
    date_filters = []
    shop_id = get_shop_id()
    date_params = [shop_id, product_id]
    if start:
        date_filters.append('date >= ?')
        date_params.append(start)
    if end:
        date_filters.append('date <= ?')
        date_params.append(end)
    date_where = f" AND {' AND '.join(date_filters)}" if date_filters else ''
    with get_db() as connection:
        product = connection.execute('SELECT product_id, title FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if not product:
            return failure('NOT_FOUND', '商品不存在', status=404)
        rows = connection.execute(
            f'''SELECT date, payment_amount, refund_amount, payment_amount - refund_amount AS net_sales,
                      ipv AS product_visitors, buyers AS payment_buyers, ad_spend
               FROM daily_data WHERE shop_id = ? AND product_id = ?{date_where} ORDER BY date''', tuple(date_params)
        ).fetchall()
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['product_id', 'title', 'date', 'payment_amount', 'refund_amount', 'net_sales', 'product_visitors', 'payment_buyers', 'ad_spend'])
    for row in rows:
        writer.writerow([product['product_id'], product['title'], row['date'], row['payment_amount'], row['refund_amount'], row['net_sales'], row['product_visitors'], row['payment_buyers'], row['ad_spend']])
    response = Response('\ufeff' + output.getvalue(), mimetype='text/csv; charset=utf-8')
    response.headers['Content-Disposition'] = f'attachment; filename="product-detail-{product_id}.csv"'
    return response

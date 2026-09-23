import csv
import io
from datetime import date

from flask import Blueprint, request, Response

from api.api_response import evidence_level_for, failure, limitations_for, success
from db import get_db, get_shop_id
from repos.actions_repo import ActionsRepo
from services.lifecycle_service import lifecycle_service
from services.metric_definitions import derive_metrics
from services.category_mode_service import mode_to_label
from services.product_rules_service import evaluate_rule, get_rule
from services.promotion_service import PromotionValidationError, promotion_service
from services.source_resolution_service import lineage_for_product_day
from services.shop_scope_service import reject_legacy_shop_scope


product_detail_bp = Blueprint('product_detail', __name__)


GRANULAR_THEME_DEFINITIONS = (
    {
        'key': 'sku',
        'label': '\u5546\u54c1 SKU',
        'table': 'product_sku_daily',
        'grain': ['product_id', 'sku_id', 'date'],
        'required_columns': ['product_id', 'sku_id', 'date'],
        'dimension_column': 'sku_id',
        'display_columns': ['sku_name', 'sku_properties'],
        'measure_columns': ['payment_amount', 'payment_quantity', 'buyers', 'refund_amount'],
        'capability_requirements': {
            'sku_ranking': ['payment_amount', 'payment_quantity'],
            'sku_contribution': ['payment_amount', 'payment_quantity'],
            'export': ['product_id', 'sku_id', 'date'],
        },
        'capabilities': ['sku_ranking', 'sku_contribution', 'export'],
        'limitations': ['\u672a\u5efa\u7acb SKU \u65e5\u4e8b\u5b9e\u8868\uff0c\u5546\u54c1\u65e5\u5ea6\u603b\u8ba1\u4e0d\u80fd\u62c6\u5206\u4e3a SKU \u6570\u636e'],
    },
    {
        'key': 'region',
        'label': '\u5730\u57df',
        'table': 'product_region_daily',
        'grain': ['product_id', 'region_code', 'date'],
        'required_columns': ['product_id', 'region_code', 'date'],
        'dimension_column': 'region_code',
        'display_columns': ['region_name'],
        'measure_columns': ['visitors', 'buyers', 'payment_amount'],
        'capability_requirements': {
            'region_ranking': ['payment_amount', 'visitors'],
            'region_conversion': ['visitors', 'buyers'],
            'export': ['product_id', 'region_code', 'date'],
        },
        'capabilities': ['region_ranking', 'region_conversion', 'export'],
        'limitations': ['\u672a\u53d1\u73b0\u53ef\u7528\u5546\u54c1\u5730\u57df\u4e8b\u5b9e\uff0c\u5546\u54c1\u65e5\u5ea6\u603b\u8ba1\u4e0d\u80fd\u62c6\u5206\u4e3a\u5730\u57df\u6570\u636e'],
    },
    {
        'key': 'hour',
        'label': '\u5546\u54c1\u5c0f\u65f6',
        'table': 'product_hourly',
        'grain': ['product_id', 'date', 'hour'],
        'required_columns': ['product_id', 'date', 'hour'],
        'dimension_column': 'hour',
        'display_columns': [],
        'measure_columns': ['visitors', 'buyers', 'payment_amount', 'ad_spend'],
        'capability_requirements': {
            'hourly_trend': ['payment_amount', 'visitors'],
            'peak_periods': ['payment_amount', 'visitors'],
            'export': ['product_id', 'date', 'hour'],
        },
        'capabilities': ['hourly_trend', 'peak_periods', 'export'],
        'limitations': ['\u672a\u5efa\u7acb\u5546\u54c1\u5c0f\u65f6\u4e8b\u5b9e\u8868\uff0c\u4e0d\u4f7f\u7528\u5546\u54c1\u65e5\u5ea6\u603b\u8ba1\u62c6\u5206\u4e3a\u5c0f\u65f6\u6570\u636e'],
    },
)


def _granular_theme_status(connection, product_id, definition, start=None, end=None):
    table = definition['table']
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    base = {
        'key': definition['key'],
        'label': definition['label'],
        'grain': definition['grain'],
        'source_table': table,
        'capabilities': [],
        'capability_readiness': [],
        'required_columns': list(definition['required_columns']),
        'available_columns': [],
        'coverage': {'row_count': 0, 'start': None, 'end': None, 'latest_update': None, 'dimension_count': 0},
        'missing_inputs': [table],
        'limitations': list(definition['limitations']),
    }
    if not exists:
        base['availability'] = 'source-unavailable'
        base['evidence_level'] = 'insufficient'
        base['limitations'].append(f'\u6570\u636e\u8868\u4e0d\u53ef\u7528: {table}')
        return base

    columns = {row['name'] for row in connection.execute(f'PRAGMA table_info("{table}")')}
    base['available_columns'] = sorted(columns)
    missing = [field for field in definition['required_columns'] if field not in columns]
    base['missing_inputs'] = missing
    if missing:
        base['availability'] = 'missing-fields'
        base['evidence_level'] = 'partial'
        base['limitations'].append(f'\u7f3a\u5c11\u5fc5\u8981\u5b57\u6bb5: {", ".join(missing)}')
        return base

    filters = ['product_id = ?']
    params = [product_id]
    if start and 'date' in columns:
        filters.append('date >= ?')
        params.append(start)
    if end and 'date' in columns:
        filters.append('date <= ?')
        params.append(end)
    where = ' AND '.join(filters)
    selections = [
        'COUNT(*) AS row_count',
        'MIN(date) AS start_date',
        'MAX(date) AS end_date',
    ]
    if 'updated_at' in columns:
        selections.append('MAX(updated_at) AS latest_update')
    elif 'imported_at' in columns:
        selections.append('MAX(imported_at) AS latest_update')
    else:
        selections.append('NULL AS latest_update')
    dimension_column = definition.get('dimension_column')
    if dimension_column in columns:
        selections.append(f'COUNT(DISTINCT "{dimension_column}") AS dimension_count')
    else:
        selections.append('0 AS dimension_count')
    row = connection.execute(
        f'SELECT {", ".join(selections)} FROM "{table}" WHERE {where}',
        params,
    ).fetchone()
    base['coverage'] = {
        'row_count': int(row['row_count'] or 0),
        'start': row['start_date'],
        'end': row['end_date'],
        'latest_update': row['latest_update'],
        'dimension_count': int(row['dimension_count'] or 0),
    }
    if not base['coverage']['row_count']:
        base['availability'] = 'no-data'
        base['evidence_level'] = 'insufficient'
        return base
    readiness = []
    enabled = []
    missing_analysis_fields = set()
    for capability in definition['capabilities']:
        required = list(definition.get('capability_requirements', {}).get(capability, definition['required_columns']))
        missing_for_capability = sorted(set(required) - columns)
        readiness.append({
            'key': capability,
            'required_columns': required,
            'missing_columns': missing_for_capability,
            'available': not missing_for_capability,
        })
        if missing_for_capability:
            missing_analysis_fields.update(missing_for_capability)
        else:
            enabled.append(capability)
    base['capability_readiness'] = readiness
    base['capabilities'] = enabled
    base['missing_inputs'] = sorted(missing_analysis_fields)
    if missing_analysis_fields:
        base['availability'] = 'partial'
        base['evidence_level'] = 'partial'
        base['limitations'].append(f'\u5206\u6790\u6307\u6807\u7f3a\u5c11\u5b57\u6bb5: {", ".join(sorted(missing_analysis_fields))}')
    else:
        base['availability'] = 'available'
        base['evidence_level'] = 'full'
    return base


def _granular_analysis_theme(connection, product_id, definition, start=None, end=None, limit=100):
    """Return grouped rows only when the corresponding fact table proves them."""
    status = _granular_theme_status(connection, product_id, definition, start, end)
    status['rows'] = []
    status['row_count'] = 0
    if status['availability'] not in {'available', 'partial'}:
        return status

    columns = set(status['available_columns'])
    dimension = definition['dimension_column']
    if dimension not in columns:
        return status
    display_columns = [field for field in definition.get('display_columns', ()) if field in columns]
    measure_columns = [field for field in definition.get('measure_columns', ()) if field in columns]
    select_parts = [f'"{dimension}" AS dimension_value']
    group_parts = [f'"{dimension}"']
    for field in display_columns:
        select_parts.append(f'MAX("{field}") AS "{field}"')
    for field in measure_columns:
        select_parts.append(f'SUM(COALESCE("{field}", 0)) AS "{field}"')
    filters = ['product_id = ?']
    params = [product_id]
    if start:
        filters.append('date >= ?')
        params.append(start)
    if end:
        filters.append('date <= ?')
        params.append(end)
    order_field = 'payment_amount' if 'payment_amount' in measure_columns else dimension
    order_sql = f'"{order_field}" DESC' if order_field != dimension else f'"{dimension}" ASC'
    rows = connection.execute(
        f'''SELECT {", ".join(select_parts)}
            FROM "{definition['table']}"
            WHERE {' AND '.join(filters)}
            GROUP BY {", ".join(group_parts)}
            ORDER BY {order_sql}
            LIMIT ?''',
        [*params, limit],
    ).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        if 'visitors' in item and 'buyers' in item and item['visitors']:
            item['conversion_rate'] = item['buyers'] / item['visitors']
        else:
            item['conversion_rate'] = None
        output.append(item)
    status['rows'] = output
    status['row_count'] = len(output)
    status['analysis_fields'] = [*display_columns, *measure_columns]
    status['capability_readiness'] = [
        item for item in status.get('capability_readiness', [])
        if item['available']
    ]
    return status


def _validate_range(start, end):
    try:
        parsed_start = date.fromisoformat(start) if start else None
        parsed_end = date.fromisoformat(end) if end else None
    except ValueError:
        return '日期必须使用 YYYY-MM-DD 格式'
    if parsed_start and parsed_end and parsed_start > parsed_end:
        return '开始日期不能晚于结束日期'
    return None


DETAIL_FIELD_DEFINITIONS = (
    ('payment_amount', '支付金额', 'currency', 'sum'),
    ('refund_amount', '退款金额', 'currency', 'sum'),
    ('payment_qty', '支付件数', 'number', 'sum'),
    ('buyers', '支付买家数', 'number', 'sum'),
    ('product_visitors', '商品访客数', 'number', 'sum'),
    ('pv', '页面浏览量', 'number', 'sum'),
    ('search_visitors', '搜索访客', 'number', 'sum'),
    ('search_conversion', '搜索转化率', 'ratio', 'avg'),
    ('paid_ipv', '付费访客', 'number', 'sum'),
    ('organic_ipv', '自然访客', 'number', 'sum'),
    ('search_ipv', '搜索 IPV', 'number', 'sum'),
    ('recommend_ipv', '推荐 IPV', 'number', 'sum'),
    ('cart_qty', '加购件数', 'number', 'sum'),
    ('cart_users', '加购人数', 'number', 'sum'),
    ('cart_rate', '加购率', 'ratio', 'avg'),
    ('fav_users', '收藏人数', 'number', 'sum'),
    ('fav_rate', '收藏率', 'ratio', 'avg'),
    ('repurchase_users', '复购人数', 'number', 'sum'),
    ('repurchase_rate', '复购率', 'ratio', 'avg'),
    ('presale_amount', '预售支付金额', 'currency', 'sum'),
    ('presale_qty', '预售件数', 'number', 'sum'),
    ('ad_spend', '推广花费', 'currency', 'sum'),
    ('ad_roi', '推广 ROI', 'ratio', 'weighted_ad_roi'),
    ('search_click_rate', '搜索点击率', 'ratio', 'avg'),
    ('cross_sell_qty', '关联销售件数', 'number', 'sum'),
    ('cross_sell_rate', '关联销售率', 'ratio', 'avg'),
    ('cross_sell_categories', '关联类目数', 'number', 'sum'),
    ('order_buyers', '下单买家数', 'number', 'sum'),
    ('order_items', '下单件数', 'number', 'sum'),
    ('order_amount', '下单金额', 'currency', 'sum'),
    ('order_conversion', '下单转化率', 'ratio', 'avg'),
    ('new_payment_buyers', '新客支付买家', 'number', 'sum'),
    ('returning_payment_buyers', '老客支付买家', 'number', 'sum'),
    ('returning_payment_amount', '老客支付金额', 'currency', 'sum'),
    ('data_source', '数据来源', 'text', 'latest'),
    ('imported_at', '最后导入时间', 'text', 'latest'),
)


def _aggregate_detail_rows(rows):
    records = [dict(row) for row in rows]
    summary = {}
    for key, _label, _unit, aggregation in DETAIL_FIELD_DEFINITIONS:
        values = [record.get(key) for record in records if record.get(key) is not None]
        if not values:
            summary[key] = None
        elif aggregation == 'sum':
            summary[key] = sum(values)
        elif aggregation == 'avg':
            summary[key] = sum(float(value) for value in values) / len(values)
        elif aggregation == 'latest':
            summary[key] = values[-1]
        elif aggregation == 'weighted_ad_roi':
            spend = summary.get('ad_spend')
            payment = summary.get('payment_amount')
            summary[key] = (payment / spend) if spend not in (None, 0) and payment is not None else None
    payment = summary.get('payment_amount')
    refund = summary.get('refund_amount')
    visitors = summary.get('product_visitors')
    buyers = summary.get('buyers')
    summary['net_sales'] = payment - refund if payment is not None and refund is not None else None
    summary['refund_rate'] = refund / payment if payment not in (None, 0) and refund is not None else None
    summary['payment_conversion_rate'] = buyers / visitors if visitors not in (None, 0) and buyers is not None else None
    summary['average_order_value'] = payment / buyers if buyers not in (None, 0) and payment is not None else None
    summary['expense_ratio'] = summary['ad_spend'] / payment if payment not in (None, 0) and summary.get('ad_spend') is not None else None
    summary['search_ratio'] = summary['search_visitors'] / visitors if visitors not in (None, 0) and summary.get('search_visitors') is not None else None
    summary['data_cutoff_date'] = records[-1].get('date') if records else None
    return summary


def _detail_metrics(summary):
    return [
        {
            'key': key,
            'label': label,
            'unit': unit,
            'value': summary.get(key),
            'availability': 'available' if summary.get(key) is not None else 'missing-fields',
        }
        for key, label, unit, _aggregation in DETAIL_FIELD_DEFINITIONS
    ]


RULE_ACTIONS = {
    'high_refund': ['定位退款来源和退款原因', '检查商品详情与售后承诺', '创建退款风险观察动作'],
    'high_paid_high_refund': ['检查推广计划费比', '定位退款来源与高退款 SKU', '创建投放与售后联动观察动作'],
    'high_expense': ['拆解推广渠道与计划花费', '检查低效计划和搜索词', '创建费比优化观察动作'],
    'low_conversion': ['拆解流量来源与落地页', '检查主图、价格和详情承接', '创建转化率优化观察动作'],
    'high_cart_zero_paid': ['检查加购用户未支付原因', '补充自然流量承接动作', '创建加购转支付观察动作'],
    'high_aov': ['沉淀高客单价卖点', '检查高价值人群和连带购买', '创建高客单价放量观察动作'],
    'low_aov': ['检查价格带和组合装数', '评估连带销售与客单提升空间', '创建客单价优化观察动作'],
    'all_products': ['确认当前经营事实覆盖范围', '查看日度趋势和流量来源', '创建下一步验证动作'],
}


def _period_label(start, end, explicit=None, cutoff=None):
    if explicit:
        return explicit
    if start and end and start[:7] == end[:7]:
        return start[:7]
    return (cutoff or end or start or '')[:7]


def _problem_context(rule_key, summary, *, start=None, end=None, period=None, category_mode=None, product=None, has_facts=False):
    if not rule_key:
        return None
    rule = get_rule(rule_key)
    if not rule:
        return None
    metrics = {
        'payment_amount': summary.get('payment_amount'),
        'refund_amount': summary.get('refund_amount'),
        'ad_spend': summary.get('ad_spend'),
        'product_visitors': summary.get('product_visitors'),
        'payment_buyers': summary.get('payment_buyers'),
        'cart_rate': summary.get('cart_rate'),
        'refund_rate': summary.get('refund_rate'),
        'expense_ratio': summary.get('expense_ratio'),
        'payment_conversion_rate': summary.get('payment_conversion_rate'),
        'average_order_value': summary.get('average_order_value'),
    }
    evaluation = evaluate_rule(rule_key, metrics, has_facts=has_facts)
    scope_label = mode_to_label(category_mode)
    product_labels = [item.strip() for item in str((product or {}).get('shop_label') or '').split(',') if item.strip()]
    scope_match = not scope_label or scope_label in product_labels
    if not scope_match:
        evaluation = {**evaluation, 'status': 'not-computable', 'matched': False, 'missing_fields': ['category_scope'], 'matched_fields': []}
    return {
        'rule_key': rule_key,
        'rule_name': rule['name'],
        'group': rule['group'],
        'description': rule['description'],
        'severity': rule['severity'],
        'period': _period_label(start, end, period, summary.get('data_cutoff_date')),
        'category_mode': category_mode or 'all',
        'scope_match': scope_match,
        'status': evaluation['status'],
        'matched': evaluation['matched'],
        'missing_fields': evaluation.get('missing_fields', []),
        'matched_fields': evaluation.get('matched_fields', []),
        'checks': evaluation.get('checks', []),
        'suggested_actions': RULE_ACTIONS.get(rule_key, []),
        'evidence': {
            'coverage_start': start or None,
            'coverage_end': end or summary.get('data_cutoff_date'),
            'fact_days': int(summary.get('_fact_days') or 0),
            'level': 'full' if evaluation['status'] in {'matched', 'not-matched'} else 'partial',
        },
    }


def _promotion_catalog_fallback(connection, product_id, shop_id):
    """Build a display-only identity for a promotion fact without a catalog row."""
    identity = None
    identity_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'product_identity_map'"
    ).fetchone()
    if identity_table:
        identity = connection.execute(
            '''SELECT display_title, image_url, fact_row_count, first_seen_date, last_seen_date
               FROM product_identity_map
               WHERE shop_id = ? AND source_system = 'promotion' AND external_product_id = ?''',
            (shop_id, product_id),
        ).fetchone()
    evidence = connection.execute(
        '''SELECT COUNT(*) AS fact_count, MIN(date) AS first_date, MAX(date) AS last_date
           FROM promotion_daily_facts
           WHERE shop_id = ? AND product_id = ? AND grain = 'product' ''',
        (shop_id, product_id),
    ).fetchone()
    if not evidence or not evidence['fact_count']:
        return None
    edge_identity = connection.execute(
        '''SELECT MAX(NULLIF(product_name, '')) AS product_name,
                  MAX(NULLIF(image_url, '')) AS image_url
           FROM promotion_campaign_items
           WHERE shop_id = ? AND product_id = ?''',
        (shop_id, product_id),
    ).fetchone()
    creative = connection.execute(
        '''SELECT MAX(NULLIF(product_name, '')) AS product_name,
                  MAX(NULLIF(image_url, '')) AS image_url
           FROM promotion_creatives
           WHERE shop_id = ? AND product_id = ?''',
        (shop_id, product_id),
    ).fetchone()
    return {
        'product_id': product_id,
        'title': (identity['display_title'] if identity else None) or (edge_identity['product_name'] if edge_identity else None) or (creative['product_name'] if creative else None) or product_id,
        'category': '', 'tier': '', 'style': '', 'scene': '', 'list_date': None,
        'status': 'external_only',
        'remark': '推广事实存在，但商品主档尚未回溯',
        'image_url': (identity['image_url'] if identity else None) or (edge_identity['image_url'] if edge_identity else None) or (creative['image_url'] if creative else None) or '',
        'manager': '',
        'source_status': 'promotion_fact_only',
        'catalog_status': 'missing',
        'promotion_fact_count': int(identity['fact_row_count'] if identity and identity['fact_row_count'] is not None else evidence['fact_count']),
        'promotion_first_date': (identity['first_seen_date'] if identity else None) or evidence['first_date'],
        'promotion_last_date': (identity['last_seen_date'] if identity else None) or evidence['last_date'],
    }


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
    rule_key = (request.args.get('rule_key') or '').strip()
    category_mode = (request.args.get('category_mode') or '').strip() or 'all'
    period = (request.args.get('period') or '').strip()
    if rule_key and not get_rule(rule_key):
        return failure('VALIDATION_ERROR', 'invalid product rule', {'rule_key': rule_key}, status=422)
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
        catalog_fallback = False
        if not product:
            fallback = _promotion_catalog_fallback(connection, product_id, shop_id)
            if fallback:
                product = fallback
                catalog_fallback = True
        if not product:
            return failure('NOT_FOUND', '商品不存在', status=404)
        trend = connection.execute(
            f'''SELECT *, ipv AS product_visitors, buyers AS payment_buyers
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
    trend_records = []
    for row in trend:
        item = dict(row)
        payment = item.get('payment_amount')
        refund = item.get('refund_amount')
        item['net_sales'] = payment - refund if payment is not None and refund is not None else None
        trend_records.append(item)
    summary = dict(summary)
    summary.update(_aggregate_detail_rows(trend_records))
    summary['_fact_days'] = len(trend_records)
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
    if catalog_fallback:
        availability = 'partial'
    from repos.lifecycle_repo import LifecycleRepo
    lifecycle_history = LifecycleRepo.history(product_id)
    actions = ActionsRepo.list_actions(product_id)
    source_batches = [item for item in ({'source': 'daily_data', 'row_count': len(trend), 'coverage_start': trend[0]['date'] if trend else None, 'coverage_end': trend[-1]['date'] if trend else None},
                                        {'source': 'lifecycle_history', 'row_count': len(lifecycle_history)},
                                        {'source': 'product_actions', 'row_count': len(actions)})]
    if catalog_fallback:
        source_batches.append({
            'source': 'promotion_daily_facts',
            'row_count': product_data.get('promotion_fact_count', 0),
            'coverage_start': product_data.get('promotion_first_date'),
            'coverage_end': product_data.get('promotion_last_date'),
        })
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
    for item in trend_records:
        item['field_lineage'] = {}
        daily_trend.append(item)
    # The database connection is closed above; load lineage in one short read
    # transaction so legacy detail queries retain their existing shape.
    with get_db() as lineage_connection:
        for item in daily_trend:
            item['field_lineage'] = lineage_for_product_day(lineage_connection, product_id, item['date'], shop_id=shop_id)
    problem_context = _problem_context(
        rule_key,
        summary,
        start=start,
        end=end,
        period=period,
        category_mode=category_mode,
        product=product_data,
        has_facts=bool(trend_records),
    )
    summary.pop('_fact_days', None)
    return success({'product': product_data, 'summary': summary,
                    'detail_metrics': _detail_metrics(summary),
                    'daily_trend': daily_trend,
                    'lifecycle': lifecycle, 'lifecycle_history': lifecycle_history,
                    'actions': actions, 'monthly_analysis': monthly_rows,
                    'period_comparison': period_comparison,
                    'contribution_analysis': contribution_analysis,
                    'evidence_summary': evidence_summary,
                    'problem_context': problem_context},
                   availability=availability,
                   capabilities={
                       'can_view': True,
                       'can_create_action': bool(trend) and not catalog_fallback,
                       'can_review_action': any(item.get('status') == 'pending_review' for item in actions),
                       'can_export': bool(trend) and not catalog_fallback,
                   },
                   evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
                   missing_inputs=missing_inputs,
                   limitations=limitations_for(availability, missing_inputs=missing_inputs) + ([
                       '商品主档缺失，仅展示推广事实身份和推广详情；商品分类、生命周期和日度经营数据不可用'
                   ] if catalog_fallback else []),
                   freshness={'end': summary.get('data_cutoff_date')},
                   source_batches=source_batches,
                   evidence=[{'source': 'daily_data', 'row_count': len(trend), 'data_cutoff_date': summary.get('data_cutoff_date')}])


@product_detail_bp.route('/api/products/<product_id>/granular-capabilities')
def product_granular_capabilities(product_id):
    """Expose SKU, region and hourly capability boundaries for one product.

    This endpoint is intentionally capability-first: it only reads verified
    fact tables and never derives granular values from product-day totals.
    """
    if (denied := reject_legacy_shop_scope('\u5546\u54c1\u7c92\u5ea6\u5206\u6790')):
        return denied
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    theme_key = (request.args.get('theme') or '').strip()
    if theme_key and theme_key not in {item['key'] for item in GRANULAR_THEME_DEFINITIONS}:
        return failure('VALIDATION_ERROR', 'invalid granular theme', {'theme': theme_key}, status=422)
    try:
        limit = int(request.args.get('limit') or 100)
    except ValueError:
        return failure('VALIDATION_ERROR', 'limit must be an integer', status=422)
    if not 1 <= limit <= 500:
        return failure('VALIDATION_ERROR', 'limit must be between 1 and 500', status=422)
    invalid_range = _validate_range(start, end)
    if invalid_range:
        return failure('VALIDATION_ERROR', invalid_range, status=422)

    with get_db() as connection:
        exists = connection.execute(
            'SELECT 1 FROM products WHERE product_id = ?', (product_id,)
        ).fetchone()
        if not exists:
            return failure('NOT_FOUND', '\u5546\u54c1\u4e0d\u5b58\u5728', status=404)
        themes = []
        analysis = None
        for definition in GRANULAR_THEME_DEFINITIONS:
            if definition['key'] == theme_key:
                analysis = _granular_analysis_theme(connection, product_id, definition, start, end, limit)
                themes.append(analysis)
            else:
                themes.append(_granular_theme_status(connection, product_id, definition, start, end))

    missing_inputs = sorted({item for theme in themes for item in theme['missing_inputs']})
    availability = 'available' if all(theme['availability'] == 'available' for theme in themes) else 'partial'
    if all(theme['availability'] == 'source-unavailable' for theme in themes):
        availability = 'source-unavailable'
    can_view_theme = {
        theme['key']: theme['availability'] in {'available', 'partial'} and bool(theme.get('capabilities'))
        for theme in themes
    }
    return success(
        {'product_id': product_id, 'themes': themes, 'analysis': analysis},
        availability=availability,
        capabilities={
            'can_view': True,
            'can_view_sku': can_view_theme['sku'],
            'can_view_region': can_view_theme['region'],
            'can_view_hour': can_view_theme['hour'],
        },
        filters={'product_id': product_id, 'start': start or None, 'end': end or None},
        missing_inputs=missing_inputs,
        limitations=sorted({item for theme in themes for item in theme['limitations']}),
        evidence_level='full' if availability == 'available' else 'insufficient',
        freshness={'start': start or None, 'end': end or None},
        evidence=[
            {
                'source': theme['source_table'],
                'grain': theme['grain'],
                'availability': theme['availability'],
                'row_count': theme['coverage']['row_count'],
            }
            for theme in themes
        ],
    )


@product_detail_bp.route('/api/products/<product_id>/lineage')
def product_lineage(product_id):
    if (denied := reject_legacy_shop_scope('商品详情')):
        return denied
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


@product_detail_bp.route('/api/products/<product_id>/promotion')
def product_promotion_analysis(product_id):
    """Return the promotion theme for the product workbench.

    This deliberately delegates to the existing promotion service so the
    workbench and cross-product promotion page share one aggregation contract.
    """
    if (denied := reject_legacy_shop_scope('商品推广分析')):
        return denied
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    invalid_range = _validate_range(start, end)
    if invalid_range:
        return failure('VALIDATION_ERROR', invalid_range, status=422)
    if not start or not end:
        return failure('VALIDATION_ERROR', '推广分析必须提供 start 和 end', status=422)
    try:
        result = promotion_service.product_detail(start, end, product_id)
    except PromotionValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    rows_available = bool(result.get('campaigns') or result.get('channel_mix'))
    availability = 'available' if rows_available else 'no-data'
    missing_inputs = [] if rows_available else ['promotion_daily']
    return success(
        result,
        availability=availability,
        capabilities={
            'can_view': True,
            'can_drill_campaign': bool(result.get('campaigns')),
            'can_export': False,
        },
        filters={'product_id': product_id, 'start': start, 'end': end},
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs) + list(result.get('limitations') or []),
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        freshness={'start': start, 'end': end},
        evidence=[
            {'source': 'promotion_campaign_items', 'row_count': len(result.get('campaigns') or [])},
            {'source': 'promotion_daily_facts', 'row_count': len(result.get('channel_mix') or [])},
        ],
    )


@product_detail_bp.route('/api/products/<product_id>/trade')
def product_trade_analysis(product_id):
    """Return the transaction and after-sales theme for the product workbench.

    This theme deliberately uses the same daily product fact table as the
    detail summary, so the page can explain payment, refund and net-sales
    changes without inventing an order-level source that is not available.
    """
    if (denied := reject_legacy_shop_scope('鍟嗗搧浜ゆ槗鍒嗘瀽')):
        return denied
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    invalid_range = _validate_range(start, end)
    if invalid_range:
        return failure('VALIDATION_ERROR', invalid_range, status=422)
    shop_id = get_shop_id()
    date_filters = []
    params = [shop_id, product_id]
    if start:
        date_filters.append('date >= ?')
        params.append(start)
    if end:
        date_filters.append('date <= ?')
        params.append(end)
    date_where = f" AND {' AND '.join(date_filters)}" if date_filters else ''
    with get_db() as connection:
        product = connection.execute(
            'SELECT product_id FROM products WHERE product_id = ?', (product_id,)
        ).fetchone()
        if not product:
            return failure('NOT_FOUND', '鍟嗗搧涓嶅瓨鍦?', status=404)
        rows = connection.execute(
            f'''SELECT date, payment_amount, refund_amount, payment_qty,
                       buyers, order_amount, order_buyers, presale_amount,
                       cart_qty, cart_users, fav_users
                FROM daily_data
                WHERE shop_id = ? AND product_id = ?{date_where}
                ORDER BY date''',
            tuple(params),
        ).fetchall()

    trend = []
    for row in rows:
        item = dict(row)
        payment = item.get('payment_amount')
        refund = item.get('refund_amount')
        buyers = item.get('buyers')
        item['net_sales'] = payment - refund if payment is not None and refund is not None else None
        item['refund_rate'] = refund / payment if payment not in (None, 0) and refund is not None else None
        item['payment_conversion_rate'] = buyers / item['order_buyers'] if buyers is not None and item.get('order_buyers') not in (None, 0) else None
        trend.append(item)

    def _sum(key):
        values = [row.get(key) for row in trend if row.get(key) is not None]
        return sum(values) if values else None

    payment = _sum('payment_amount')
    refund = _sum('refund_amount')
    buyers = _sum('buyers')
    summary = {
        'payment_amount': payment,
        'refund_amount': refund,
        'net_sales': payment - refund if payment is not None and refund is not None else None,
        'payment_qty': _sum('payment_qty'),
        'buyers': buyers,
        'order_amount': _sum('order_amount'),
        'order_buyers': _sum('order_buyers'),
        'presale_amount': _sum('presale_amount'),
        'cart_qty': _sum('cart_qty'),
        'cart_users': _sum('cart_users'),
        'fav_users': _sum('fav_users'),
        'refund_rate': refund / payment if payment not in (None, 0) and refund is not None else None,
        'average_order_value': payment / buyers if payment is not None and buyers not in (None, 0) else None,
        'data_cutoff_date': trend[-1]['date'] if trend else None,
    }
    availability = 'available' if trend else 'no-data'
    missing_inputs = [] if trend else ['daily_data']
    return success(
        {'product_id': product_id, 'summary': summary, 'trend': trend},
        availability=availability,
        capabilities={'can_view': True, 'can_drill': bool(trend)},
        filters={'product_id': product_id, 'start': start or None, 'end': end or None},
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        freshness={'start': trend[0]['date'] if trend else start or None,
                   'end': trend[-1]['date'] if trend else end or None},
        source_batches=[{'source': 'daily_data', 'row_count': len(trend),
                         'coverage_start': trend[0]['date'] if trend else None,
                         'coverage_end': trend[-1]['date'] if trend else None}],
        evidence=[{'source': 'daily_data', 'row_count': len(trend),
                   'data_cutoff_date': summary['data_cutoff_date']}],
    )


@product_detail_bp.route('/api/products/<product_id>/detail/export')
def export_product_detail(product_id):
    if (denied := reject_legacy_shop_scope('商品详情')):
        return denied
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
            f'''SELECT *, ipv AS product_visitors, buyers AS payment_buyers
               FROM daily_data WHERE shop_id = ? AND product_id = ?{date_where} ORDER BY date''', tuple(date_params)
        ).fetchall()
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    field_keys = [key for key, _label, _unit, _aggregation in DETAIL_FIELD_DEFINITIONS if key not in {'data_source', 'imported_at'}]
    headers = ['product_id', 'title', 'date', *field_keys, 'data_source', 'imported_at']
    writer.writerow(headers)
    for row in rows:
        values = dict(row)
        payment = values.get('payment_amount')
        refund = values.get('refund_amount')
        values['net_sales'] = payment - refund if payment is not None and refund is not None else None
        writer.writerow([product['product_id'], product['title'], values.get('date'), *(values.get(key) for key in field_keys), values.get('data_source'), values.get('imported_at')])
    response = Response('\ufeff' + output.getvalue(), mimetype='text/csv; charset=utf-8')
    response.headers['Content-Disposition'] = f'attachment; filename="product-detail-{product_id}.csv"'
    return response

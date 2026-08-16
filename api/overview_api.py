from datetime import date

import csv
import io

from flask import Blueprint, Response, request

from api.api_response import evidence_level_for, failure, limitations_for, success
from repos.metrics_repo import MetricsRepo
from services.metrics_service import build_overview
from services.shop_scope_service import reject_legacy_shop_scope


overview_bp = Blueprint('overview', __name__)
FILTER_KEYS = ('product_id', 'tier', 'lifecycle_stage', 'promotion_channel')


def _filters():
    return {key: request.args.get(key) for key in FILTER_KEYS if request.args.get(key)}


def _date_argument(name):
    raw_value = request.args.get(name)
    if not raw_value:
        raise ValueError(f'缺少参数 {name}')
    return date.fromisoformat(raw_value).isoformat()


@overview_bp.route('/api/overview', methods=['GET'])
def get_overview():
    try:
        start_date = _date_argument('start')
        end_date = _date_argument('end')
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)

    if start_date > end_date:
        return failure('VALIDATION_ERROR', '开始日期不能晚于结束日期', status=422)

    filters = _filters()
    if filters.get('lifecycle_stage') and (denied := reject_legacy_shop_scope('经营总览生命周期筛选')):
        return denied
    result = build_overview(
        MetricsRepo.get_product_daily_totals(start_date, end_date, filters),
        start_date,
        end_date,
    )
    matrix = MetricsRepo.get_daily_matrix(start_date, end_date, filters)
    context = MetricsRepo.overview_context()
    latest_import = context.get('latest_import')
    result['data']['context'] = context
    result['data']['action_todos'] = MetricsRepo.action_todos()
    result['data']['missing_fields'] = result['data'].get('missing_fields', [])
    missing_inputs = result['data']['missing_fields']
    missing_ranges = matrix.get('missing_date_ranges', [])
    source_batches = matrix.get('source_batches', []) or ([latest_import] if latest_import else [])
    evidence_level = evidence_level_for(
        result['availability'], missing_inputs=missing_inputs, missing_ranges=missing_ranges,
    )
    if result['availability'] == 'no-data' and source_batches:
        evidence_level = 'partial'
    return success(
        result['data'],
        availability=result['availability'],
        capabilities={
            'can_export': True,
            'can_drilldown': True,
            'can_edit': False,
            'can_create_action': True,
        },
        filters={**filters, 'start': start_date, 'end': end_date},
        missing_fields=missing_inputs,
        missing_ranges=missing_ranges,
        source_batches=source_batches,
        evidence_level=evidence_level,
        missing_inputs=missing_inputs,
        limitations=limitations_for(result['availability'], missing_inputs=missing_inputs, missing_ranges=missing_ranges),
        freshness={'start': start_date, 'end': result['data'].get('data_cutoff_date')},
        evidence=[{
            'source': 'store_daily_facts',
            'row_count': len(matrix.get('rows', [])),
            'start': start_date,
            'end': result['data'].get('data_cutoff_date'),
        }],
    )


@overview_bp.route('/api/overview/daily-matrix', methods=['GET'])
def daily_matrix():
    if _filters().get('lifecycle_stage') and (denied := reject_legacy_shop_scope('经营总览生命周期筛选')):
        return denied
    try:
        start_date = _date_argument('start')
        end_date = _date_argument('end')
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    if start_date > end_date:
        return failure('VALIDATION_ERROR', '开始日期不能晚于结束日期', status=422)
    matrix = MetricsRepo.get_daily_matrix(start_date, end_date, _filters())
    rows = matrix['rows']
    if not rows:
        return success({'start_date': start_date, 'end_date': end_date, 'rows': []}, availability='no-data')
    return success({'start_date': start_date, 'end_date': end_date, **matrix})


@overview_bp.route('/api/overview/daily-matrix/export', methods=['GET'])
def export_daily_matrix():
    if _filters().get('lifecycle_stage') and (denied := reject_legacy_shop_scope('经营总览生命周期筛选')):
        return denied
    try:
        start_date = _date_argument('start')
        end_date = _date_argument('end')
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    if start_date > end_date:
        return failure('VALIDATION_ERROR', '开始日期不能晚于结束日期', status=422)

    rows = MetricsRepo.get_daily_matrix(start_date, end_date, _filters())['rows']
    columns = [
        'date', 'net_sales', 'payment_amount', 'successful_refund_amount', 'refund_rate',
        'visitors', 'buyers', 'payment_conversion_rate', 'ad_spend', 'expense_ratio',
        'average_order_value', 'returning_buyer_ratio', 'source_batch_id', 'data_source',
    ]
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    filename = f'overview-daily-matrix-{start_date}-{end_date}.csv'
    return Response(
        '\ufeff' + output.getvalue(),
        content_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )

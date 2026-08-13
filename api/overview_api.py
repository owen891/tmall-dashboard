from datetime import date

from flask import Blueprint, request

from api.api_response import failure, success
from repos.metrics_repo import MetricsRepo
from services.metrics_service import build_overview


overview_bp = Blueprint('overview', __name__)


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

    result = build_overview(
        MetricsRepo.get_product_daily_totals(start_date, end_date),
        start_date,
        end_date,
    )
    result['data']['context'] = MetricsRepo.overview_context()
    result['data']['action_todos'] = MetricsRepo.action_todos()
    return success(result['data'], availability=result['availability'])


@overview_bp.route('/api/overview/daily-matrix', methods=['GET'])
def daily_matrix():
    try:
        start_date = _date_argument('start')
        end_date = _date_argument('end')
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    if start_date > end_date:
        return failure('VALIDATION_ERROR', '开始日期不能晚于结束日期', status=422)
    rows = MetricsRepo.get_daily_matrix(start_date, end_date)
    if not rows:
        return success({'start_date': start_date, 'end_date': end_date, 'rows': []}, availability='no-data')
    return success({'start_date': start_date, 'end_date': end_date, 'rows': rows})

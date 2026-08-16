from flask import Blueprint, request
from api.api_response import evidence_level_for, failure, limitations_for, success
from repos.period_reviews_repo import PeriodReviewsRepo


period_reviews_bp = Blueprint('period_reviews', __name__)

@period_reviews_bp.route('/api/period-reviews')
def list_period_reviews():
    rows = PeriodReviewsRepo.list(request.args.get('period_type'))
    availability = 'available' if rows else 'no-data'
    missing_inputs = [] if rows else ['period_reviews']
    return success(
        rows,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        evidence=[{'source': 'period_reviews', 'row_count': len(rows)}],
    )

@period_reviews_bp.route('/api/period-reviews/<period_type>/<period_key>', methods=['PUT'])
def save_period_review(period_type, period_key):
    if period_type not in {'day', 'week', 'month'}:
        return failure('VALIDATION_ERROR', '周期类型必须为 day、week 或 month', status=422)
    payload = request.get_json(silent=True) or {}
    if any(not payload.get(key) for key in ('summary','conclusions','next_actions','reviewer')):
        return failure('VALIDATION_ERROR', '周期复盘字段不完整', status=422)
    PeriodReviewsRepo.upsert(period_type, period_key, payload)
    return success(
        {'period_type': period_type, 'period_key': period_key},
        evidence_level='full',
        freshness={'period_type': period_type, 'period_key': period_key},
        evidence=[{'source': 'period_reviews', 'period_type': period_type, 'period_key': period_key,
                   'row_count': 1, 'action': 'upsert'}],
        assumptions=['复盘内容是人工结论，不替代经营事实和指标证据'],
    )

from flask import Blueprint, request

from api.api_response import evidence_level_for, failure, limitations_for, success
from services.promotion_service import PromotionValidationError, promotion_service


promotion_bp = Blueprint('promotion_domain', __name__)


@promotion_bp.route('/api/promotion')
def promotion():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    if not start_date or not end_date:
        return failure('VALIDATION_ERROR', '必须提供 start 和 end', status=422)
    filters = {
        **{key: request.args.get(key) for key in ('channel', 'campaign_id', 'unit_id', 'product_id')},
        'channel': request.args.get('channel') or request.args.get('promotionChannel'),
    }
    group_by = request.args.get('group_by', 'channel')
    try:
        result = promotion_service.list(start_date, end_date, group_by, filters)
    except PromotionValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    missing_ranges = result['missing_ranges']
    availability = 'available' if result['rows'] else 'no-data'
    missing_inputs = ['promotion_daily'] if not result['rows'] else []
    return success(
        result,
        availability=availability,
        capabilities=result['capabilities'],
        filters={**{key: value for key, value in filters.items() if value},
                 'start': start_date, 'end': end_date, 'group_by': group_by},
        missing_ranges=missing_ranges,
        source_batches=result['source_batches'],
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs, missing_ranges=missing_ranges),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs, missing_ranges=missing_ranges) + result.get('limitations', []),
        freshness={'start': start_date, 'end': end_date},
        evidence=[{'source': 'promotion_daily_facts', 'row_count': len(result['rows'])}],
    )

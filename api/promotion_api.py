from flask import Blueprint, request

from api.api_response import failure, success
from services.promotion_service import PromotionValidationError, promotion_service


promotion_bp = Blueprint('promotion_domain', __name__)


@promotion_bp.route('/api/promotion')
def promotion():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    if not start_date or not end_date:
        return failure('VALIDATION_ERROR', '必须提供 start 和 end', status=422)
    try:
        result = promotion_service.list(start_date, end_date, request.args.get('group_by', 'channel'), {
            key: request.args.get(key) for key in ('channel', 'campaign_id', 'unit_id', 'product_id')
        })
    except PromotionValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(result, availability='available' if result['rows'] else 'no-data')

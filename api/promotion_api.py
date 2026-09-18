from flask import Blueprint, request

from api.api_response import evidence_level_for, failure, limitations_for, success
from services.category_mode_service import category_filters_from_request
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
    filters.update(category_filters_from_request())
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


@promotion_bp.route('/api/promotion/creatives')
def promotion_creatives():
    """素材看板：创意维度汇总（CTR/CVR/加购/花费）。"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    if not start_date or not end_date:
        return failure('VALIDATION_ERROR', '必须提供 start 和 end', status=422)
    product_id = request.args.get('product_id')
    channel = request.args.get('channel')
    sort = request.args.get('sort', 'clicks')
    result = promotion_service.creatives(start_date, end_date, product_id, channel, sort)
    availability = result['availability']
    missing_inputs = ['promotion_creatives'] if not result['rows'] else []
    return success(
        result,
        availability=availability,
        filters={'start': start_date, 'end': end_date,
                 'product_id': product_id, 'channel': channel, 'sort': sort},
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs) + result.get('limitations', []),
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        evidence=[{'source': 'promotion_creative_daily', 'row_count': len(result['rows'])}],
    )


@promotion_bp.route('/api/promotion/plan-types')
def promotion_plan_types():
    """投放方式效果对比：计划名解析投放方式后聚合。"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    if not start_date or not end_date:
        return failure('VALIDATION_ERROR', '必须提供 start 和 end', status=422)
    filters = {
        **{key: request.args.get(key) for key in ('channel', 'campaign_id', 'unit_id', 'product_id')},
    }
    filters.update(category_filters_from_request())
    result = promotion_service.plan_types(start_date, end_date, filters)
    availability = result['availability']
    missing_inputs = ['promotion_daily'] if not result['rows'] else []
    return success(
        result,
        availability=availability,
        filters={'start': start_date, 'end': end_date},
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        evidence=[{'source': 'promotion_daily_facts', 'row_count': len(result['rows'])}],
    )


@promotion_bp.route('/api/promotion/campaign-detail')
def promotion_campaign_detail():
    """计划看板行展开：计划汇总 + 投放商品列表。"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    campaign_id = request.args.get('campaign_id')
    if not start_date or not end_date or not campaign_id:
        return failure('VALIDATION_ERROR', '必须提供 start、end 和 campaign_id', status=422)
    try:
        result = promotion_service.campaign_detail(start_date, end_date, campaign_id)
    except PromotionValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    availability = 'available' if (result['products'] or result['summary'].get('ad_spend')) else 'no-data'
    missing_inputs = ['promotion_daily'] if availability == 'no-data' else []
    return success(
        result,
        availability=availability,
        filters={'start': start_date, 'end': end_date, 'campaign_id': campaign_id},
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        evidence=[{'source': 'promotion_campaign_items', 'row_count': len(result['products'])}],
    )


@promotion_bp.route('/api/promotion/product-detail')
def promotion_product_detail():
    """商品推广详情抽屉：该商品的计划列表 + 渠道花费结构。"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    product_id = request.args.get('product_id')
    if not start_date or not end_date or not product_id:
        return failure('VALIDATION_ERROR', '必须提供 start、end 和 product_id', status=422)
    try:
        result = promotion_service.product_detail(start_date, end_date, product_id)
    except PromotionValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    availability = 'available' if (result['campaigns'] or result['channel_mix']) else 'no-data'
    missing_inputs = ['promotion_daily'] if availability == 'no-data' else []
    return success(
        result,
        availability=availability,
        filters={'start': start_date, 'end': end_date, 'product_id': product_id},
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs) + result.get('limitations', []),
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        evidence=[{'source': 'promotion_campaign_items', 'row_count': len(result['campaigns'])}],
    )

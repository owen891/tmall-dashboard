from flask import Blueprint, request

from api.api_response import failure, success
from repos.keyword_promotion_repo import KeywordPromotionRepo
from services.keyword_promotion_service import KeywordPromotionValidationError, keyword_promotion_service


keyword_promotion_bp = Blueprint('keyword_promotion_domain', __name__)


@keyword_promotion_bp.route('/api/keyword-promotion/products')
def list_products():
    """关键词推广商品列表，支持属性筛选、排序、分页"""
    filters = {
        key: request.args.get(key)
        for key in ('gender', 'season', 'category', 'material', 'scene',
                    'thickness', 'style', 'score_grade', 'suggested_action',
                    'keyword', 'min_spend', 'min_roi', 'shop_label')
    }
    filters['start'] = request.args.get('start')
    filters['end'] = request.args.get('end')
    filters = {k: v for k, v in filters.items() if v}

    sort_by = request.args.get('sort_by', 'total_score')
    sort_order = request.args.get('sort_order', 'desc')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 50))

    try:
        result = keyword_promotion_service.list_products(filters, sort_by, sort_order, page, page_size)
    except KeywordPromotionValidationError as e:
        return failure('VALIDATION_ERROR', str(e), status=422)

    availability = 'available' if result['rows'] else 'no-data'
    return success(
        result,
        availability=availability,
        filters={**filters, 'sort_by': sort_by, 'sort_order': sort_order, 'page': page, 'page_size': page_size},
        capabilities={
            'can_filter': True,
            'can_sort': True,
            'can_paginate': True,
            'sort_columns': list(KeywordPromotionRepo.SORT_COLUMNS.keys()) if hasattr(KeywordPromotionRepo, 'SORT_COLUMNS') else [],
        },
        evidence=[{'source': 'keyword_promotion_products', 'row_count': result['total']}],
    )


@keyword_promotion_bp.route('/api/keyword-promotion/summary')
def summary():
    """关键词推广汇总统计"""
    filters = {
        key: request.args.get(key)
        for key in ('gender', 'season', 'category', 'material', 'scene',
                    'thickness', 'style', 'score_grade', 'suggested_action',
                    'keyword', 'min_spend', 'min_roi', 'shop_label')
    }
    filters['start'] = request.args.get('start')
    filters['end'] = request.args.get('end')
    filters = {k: v for k, v in filters.items() if v}

    result = keyword_promotion_service.summary(filters)
    return success(
        result,
        filters=filters,
        evidence=[{'source': 'keyword_promotion_products_summary', 'row_count': result.get('product_count', 0)}],
    )


@keyword_promotion_bp.route('/api/keyword-promotion/filters')
def filter_options():
    """获取筛选器选项（各属性分布）"""
    result = keyword_promotion_service.filter_options()
    return success(
        result,
        evidence=[{'source': 'keyword_promotion_products_filters'}],
    )


@keyword_promotion_bp.route('/api/keyword-promotion/grade-distribution')
def grade_distribution():
    """推广评级分布"""
    result = keyword_promotion_service.grade_distribution()
    return success(
        {'grades': result},
        evidence=[{'source': 'keyword_promotion_products_grades', 'row_count': len(result)}],
    )

from datetime import datetime
"""Products Legacy API - 商品和推广相关接口（旧版）

从 data_api.py 拆分出来的独立模块，包含：
- 商品列表/详情/更新
- 商品标签 CRUD
- 广告告警/趋势
"""

import io
import json
from api.data_api import DIMENSION_MAP, _reject_legacy_shop_scope, _validate_period_arg, calc_score, get_prev_period

import pandas as pd
from flask import Blueprint, current_app, g, jsonify, request

from db import get_db, get_shop_id
from api.api_response import evidence_level_for, failure, json_object, limitations_for, success
from services.category_mode_service import category_filters_from_request
from services.shop_scope_service import reject_legacy_shop_scope


products_legacy_bp = Blueprint('products_legacy', __name__)


def _request_cache_key(prefix):
    params = sorted(request.args.items())
    param_str = "&".join(f"{k}={v}" for k, v in params)
    from flask import g
    shop_id = getattr(getattr(g, 'shop_id', None), '__str__', lambda: 'default')()
    return f"{prefix}:{request.path}:{shop_id}:{param_str}"


def cached_api(prefix, ttl=60):
    from utils.cache import cache as _ttl_cache
    def decorator(f):
        def wrapped(*args, **kwargs):
            key = _request_cache_key(prefix)
            cached = _ttl_cache.get(key)
            if cached is not None:
                return jsonify(cached)
            result = f(*args, **kwargs)
            try:
                if hasattr(result, 'status_code') and result.status_code == 200 and hasattr(result, 'get_json'):
                    data = result.get_json()
                    if data is not None:
                        _ttl_cache.set(key, data, ttl)
            except Exception:
                pass
            return result
        wrapped.__name__ = getattr(f, '__name__', 'wrapped')
        wrapped.__doc__ = getattr(f, '__doc__', '')
        return wrapped
    return decorator


@products_legacy_bp.route('/api/products', methods=['GET'])
@cached_api('products', 30)
def get_products():
    """商品列表"""
    dimension = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    sort_by = request.args.get('sort', 'payment_amount')
    order = request.args.get('order', 'desc')
    limit = max(1, min(request.args.get('limit', 20, type=int) or 20, 200))
    offset = max(0, request.args.get('offset', 0, type=int) or 0)
    tier = request.args.get('tier', '')
    style = request.args.get('style', '')
    product_type = request.args.get('product_type', '')
    product_time_node = request.args.get('product_time_node', '')
    product_growth_stage = request.args.get('product_growth_stage', '')
    search = request.args.get('search', '')
    product_id = request.args.get('product_id', '')
    status_filter = request.args.get('status', '')
    lifecycle_stage = request.args.get('lifecycle_stage', '')
    seasonality = request.args.get('seasonality', '')
    has_pending_action = request.args.get('has_pending_action', '')
    unsupported = _reject_legacy_shop_scope(dimension)
    if unsupported:
        return unsupported

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dimension}, status=422)
    invalid = _validate_period_arg(dimension, period)
    if invalid:
        return invalid
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']
    shop_id = get_shop_id()

    if shop_id != 'default' and (lifecycle_stage or seasonality or has_pending_action not in ('', None, False, 'false', '0', 0)):
        return failure('UNSUPPORTED_SCOPE', '非 default 店铺暂不支持生命周期/动作旧表筛选', status=422)
    legacy_lifecycle_join = (
        'LEFT JOIN lifecycle_profiles lp ON lp.product_id = p.product_id'
        if shop_id == 'default' else
        'LEFT JOIN (SELECT NULL AS product_id, NULL AS manual_stage, NULL AS recommended_stage, NULL AS seasonal_attribute) lp ON 1=0'
    )
    legacy_paid_join = (
        '''LEFT JOIN (
            SELECT pd.* FROM paid_detail pd
            INNER JOIN (
                SELECT product_id, MAX(imported_at) as max_imported
                FROM paid_detail GROUP BY product_id
            ) pd_max ON pd.product_id = pd_max.product_id AND pd.imported_at = pd_max.max_imported
        ) pd_latest ON p.product_id = pd_latest.product_id'''
        if shop_id == 'default' else
        'LEFT JOIN paid_detail pd_latest ON 1=0'
    )
    legacy_pending_action_expr = (
        "CASE WHEN EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked')) THEN 1 ELSE 0 END"
        if shop_id == 'default' else '0'
    )

    requested_period = period
    with get_db() as conn:
        # 当前月度数据源提供的是月度事实。未指定月份时，使用最新可用月。
        # 对于当前月或历史月份，若该月尚未导入，则回退到不晚于请求月份的最新可用月；
        # 对明显未来的月份不回退，保留无事实数据的 partial 语义，避免把旧数据伪装成未来数据。
        if dimension == 'monthly':
            latest_period_row = conn.execute('SELECT MAX(month) AS latest_period FROM monthly_data').fetchone()
            latest_period = (latest_period_row['latest_period'] if latest_period_row else '') or ''
            if not period:
                period = latest_period
            elif not conn.execute('SELECT 1 FROM monthly_data WHERE month = ? LIMIT 1', (period,)).fetchone():
                try:
                    requested_month = datetime.strptime(period, '%Y-%m')
                    current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                except (TypeError, ValueError):
                    requested_month = None
                    current_month = None
                if requested_month is not None and requested_month <= current_month:
                    fallback_row = conn.execute(
                        'SELECT MAX(month) AS latest_period FROM monthly_data WHERE month <= ?',
                        (period,),
                    ).fetchone()
                    fallback_period = (fallback_row['latest_period'] if fallback_row else '') or ''
                    if fallback_period:
                        period = fallback_period

        # monthly_data 独有的列（daily/weekly表不存在）
        _monthly_ad_cols = '''COALESCE(d.overall_roi, 0) as overall_roi,
                   COALESCE(d.paid_ratio, 0) as paid_ratio,
                   COALESCE(d.refund_paid_ratio, 0) as refund_paid_ratio,
                   COALESCE(d.keyword_spend, 0) as keyword_spend,
                   COALESCE(d.keyword_sales, 0) as keyword_sales,
                   COALESCE(d.keyword_roi, 0) as keyword_roi,
                   COALESCE(d.keyword_visitors, 0) as keyword_visitors,
                   COALESCE(d.keyword_ppc, 0) as keyword_ppc,
                   COALESCE(d.crowd_spend, 0) as crowd_spend,
                   COALESCE(d.crowd_sales, 0) as crowd_sales,
                   COALESCE(d.crowd_roi, 0) as crowd_roi,
                   COALESCE(d.crowd_visitors, 0) as crowd_visitors,
                   COALESCE(d.crowd_ppc, 0) as crowd_ppc,
                   COALESCE(d.site_spend, 0) as site_spend,
                   COALESCE(d.site_sales, 0) as site_sales,
                   COALESCE(d.site_roi, 0) as site_roi,
                   COALESCE(d.site_visitors, 0) as site_visitors,
                   COALESCE(d.site_ppc, 0) as site_ppc,'''

        _monthly_traffic_cols = '''COALESCE(d.paid_ipv, 0) as paid_ipv,
                   COALESCE(d.organic_ipv, 0) as organic_ipv,
                   COALESCE(d.search_ipv, 0) as search_ipv,
                   COALESCE(d.recommend_ipv, 0) as recommend_ipv,'''

        _monthly_extra_cols = '''COALESCE(d.industry_ctr, 0) as industry_ctr,
                   COALESCE(d.cross_sell_qty, 0) as cross_sell_qty,
                   COALESCE(d.cross_sell_categories, 0) as cross_sell_categories,
                   COALESCE(d.repurchase_users, 0) as repurchase_users,
                   COALESCE(d.guide_visits, 0) as guide_visits,
                   COALESCE(d.guide_visitors, 0) as guide_visitors,
                   COALESCE(d.guide_potential, 0) as guide_potential,
                   COALESCE(d.guide_potential_ratio, 0) as guide_potential_ratio,
                   COALESCE(d.new_buyers, 0) as new_buyers,
                   COALESCE(d.new_buyer_ratio, 0) as new_buyer_ratio,'''

        _zero_ad = ',\n               '.join([f'0 as {c}' for c in ['overall_roi','paid_ratio','refund_paid_ratio','keyword_spend','keyword_sales','keyword_roi','keyword_visitors','keyword_ppc','crowd_spend','crowd_sales','crowd_roi','crowd_visitors','crowd_ppc','site_spend','site_sales','site_roi','site_visitors','site_ppc']]) + ','
        _zero_traffic = ',\n               '.join([f'0 as {c}' for c in ['paid_ipv','organic_ipv','search_ipv','recommend_ipv']]) + ','
        _zero_extra = ',\n               '.join([f'0 as {c}' for c in ['industry_ctr','cross_sell_categories','guide_visits','guide_visitors','guide_potential','guide_potential_ratio','new_buyers','new_buyer_ratio']]) + ','

        monthly_only_cols = _monthly_ad_cols if dimension == 'monthly' else _zero_ad
        monthly_traffic_cols = _monthly_traffic_cols if dimension in {'monthly', 'daily', 'weekly'} else _zero_traffic
        monthly_extra_cols = _monthly_extra_cols if dimension == 'monthly' else _zero_extra
        dmp_cols = '''COALESCE(d.repurchase_users, 0) as repurchase_users,
                   COALESCE(d.presale_amount, 0) as presale_amount,
                   COALESCE(d.presale_qty, 0) as presale_qty,
                   COALESCE(d.search_click_rate, 0) as search_click_rate,
                   COALESCE(d.cross_sell_qty, 0) as cross_sell_qty,
                   COALESCE(d.category_width, 0) as category_width,'''
        dmp_zero_cols = '''0 as presale_amount, 0 as presale_qty,
                   0 as search_click_rate, 0 as category_width,'''
        dmp_metric_cols = dmp_cols if dimension in {'daily', 'weekly'} else dmp_zero_cols
        repurchase_cross_cols = "COALESCE(d.repurchase_rate, 0) as repurchase_rate,\n               COALESCE(d.cross_sell_rate, 0) as cross_sell_rate," if dimension in {'monthly', 'daily', 'weekly'} else "0 as repurchase_rate,\n               0 as cross_sell_rate,"
        click_score_cols = "COALESCE(d.click_rate, 0) as click_rate,\n               COALESCE(d.score, 0) as score," if dimension == 'monthly' else "0 as click_rate,\n               0 as score,"
        # Imported BI-only fields remain in a JSON payload so source schema changes do not
        # require adding hundreds of SQLite columns. The catalog controls which are exposed.
        bi_payload_select = ', bsp.payload_json AS bi_payload_json' if dimension == 'monthly' else ''
        bi_payload_join = (
            'LEFT JOIN monthly_source_payload bsp ON bsp.product_id = p.product_id AND bsp.month = d.month'
            if dimension == 'monthly' else ''
        )

        data_relation = table
        join_clause = f'p.product_id = d.product_id AND d.{date_col} = ?'
        params = [period]
        if dimension == 'daily':
            join_clause = f'p.product_id = d.product_id AND d.shop_id = ? AND d.{date_col} = ?'
            params = [shop_id, period]
        if dimension == 'daily' and start and end:
            data_relation = '''(
                SELECT current.product_id,
                       current.payment_amount,
                       current.refund_amount,
                       current.net_sales,
                       current.ipv,
                       current.pv,
                       current.payment_conversion,
                       current.cart_rate,
                       current.fav_rate,
                       current.bounce_rate,
                       current.avg_stay_duration,
                       current.ad_spend,
                       current.ad_roi,
                       current.buyers,
                       current.avg_order_value,
                       current.paid_ipv,
                       current.organic_ipv,
                       current.search_ipv,
                       current.recommend_ipv,
                       current.repurchase_rate,
                       current.repurchase_users,
                       current.presale_amount,
                       current.presale_qty,
                       current.search_click_rate,
                       current.cross_sell_qty,
                       current.cross_sell_rate,
                       current.category_width,
                       CASE WHEN previous.payment_amount != 0
                            THEN (current.payment_amount - previous.payment_amount) * 1.0 / previous.payment_amount
                            ELSE NULL END AS trend_change
                FROM (
                    SELECT product_id,
                           SUM(payment_amount) AS payment_amount,
                           SUM(refund_amount) AS refund_amount,
                           SUM(net_sales) AS net_sales,
                           SUM(ipv) AS ipv,
                           SUM(pv) AS pv,
                           AVG(payment_conversion) AS payment_conversion,
                           AVG(cart_rate) AS cart_rate,
                           AVG(fav_rate) AS fav_rate,
                           AVG(bounce_rate) AS bounce_rate,
                           AVG(avg_stay_duration) AS avg_stay_duration,
                           SUM(ad_spend) AS ad_spend,
                           CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) / SUM(ad_spend) ELSE 0 END AS ad_roi,
                           SUM(buyers) AS buyers,
                           CASE WHEN SUM(buyers) > 0 THEN SUM(payment_amount) / SUM(buyers) ELSE AVG(avg_order_value) END AS avg_order_value,
                           SUM(paid_ipv) AS paid_ipv,
                           SUM(organic_ipv) AS organic_ipv,
                           SUM(search_ipv) AS search_ipv,
                           SUM(recommend_ipv) AS recommend_ipv,
                           AVG(repurchase_rate) AS repurchase_rate,
                           SUM(repurchase_users) AS repurchase_users,
                           SUM(presale_amount) AS presale_amount,
                           SUM(presale_qty) AS presale_qty,
                           AVG(search_click_rate) AS search_click_rate,
                           SUM(cross_sell_qty) AS cross_sell_qty,
                           AVG(cross_sell_rate) AS cross_sell_rate,
                           AVG(category_width) AS category_width
                     FROM daily_data
                     WHERE shop_id = ? AND date BETWEEN ? AND ?
                    GROUP BY product_id
                ) current
                LEFT JOIN (
                    SELECT product_id, SUM(payment_amount) AS payment_amount
                     FROM daily_data
                     WHERE shop_id = ? AND date BETWEEN date(?, '-' || CAST((julianday(?) - julianday(?) + 1) AS INTEGER) || ' days') AND date(?, '-1 day')
                    GROUP BY product_id
                ) previous ON previous.product_id = current.product_id
            )'''
            join_clause = 'p.product_id = d.product_id'
            params = [shop_id, start, end, shop_id, start, end, start, start]

        where_clauses = []
        where_params = []
        if status_filter and status_filter != 'all':
            where_clauses.append('p.status = ?')
            where_params.append(status_filter)
        elif status_filter != 'all':
            where_clauses.append("p.status = 'active'")
        if tier:
            where_clauses.append('p.tier = ?')
            where_params.append(tier)
        if style:
            where_clauses.append('p.style = ?')
            where_params.append(style)
        if product_type:
            where_clauses.append('p.product_type = ?')
            where_params.append(product_type)
        _category_filters = category_filters_from_request()
        if _category_filters.get('shop_label'):
            _label = _category_filters['shop_label']
            where_clauses.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
            where_params.extend([_label, _label])
        if product_time_node:
            where_clauses.append('p.product_time_node = ?')
            where_params.append(product_time_node)
        if product_growth_stage:
            where_clauses.append('p.product_growth_stage = ?')
            where_params.append(product_growth_stage)
        if lifecycle_stage:
            where_clauses.append("COALESCE(lp.manual_stage, lp.recommended_stage, '') = ?")
            where_params.append(lifecycle_stage)
        if seasonality:
            where_clauses.append("COALESCE(lp.seasonal_attribute, '') = ?")
            where_params.append(seasonality)
        if has_pending_action.lower() in {'true', '1', 'yes'}:
            where_clauses.append("EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked'))")
        elif has_pending_action.lower() in {'false', '0', 'no'}:
            where_clauses.append("NOT EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked'))")
        if search:
            search_safe = search.replace('%', '\\%').replace('_', '\\_')
            where_clauses.append("(p.title LIKE ? ESCAPE '\\' OR p.product_id LIKE ? ESCAPE '\\')")
            where_params.append(f'%{search_safe}%')
            where_params.append(f'%{search_safe}%')
        if product_id:
            where_clauses.append('p.product_id = ?')
            where_params.append(product_id)
        where_sql = ' AND '.join(where_clauses) or '1=1'

        query = f'''
            SELECT p.product_id, p.title, p.tier, p.style, p.scene, p.status, p.image_url,
                   p.category, p.list_date, p.remark, p.manager,
                   p.product_type, p.product_tags, p.product_growth_stage, p.product_time_node,
                   CASE WHEN d.product_id IS NOT NULL THEN 1 ELSE 0 END as has_data,
                   COALESCE(p.starred, 0) as starred,
                   COALESCE(lp.manual_stage, lp.recommended_stage) as lifecycle_stage,
                   lp.seasonal_attribute as seasonality,
                       {legacy_pending_action_expr} as has_pending_action,
                   COALESCE(d.payment_amount, 0) as payment_amount,
                   COALESCE(d.refund_amount, 0) as refund_amount,
                   COALESCE(d.payment_conversion, 0) as conversion,
                   COALESCE(d.ad_spend, 0) as ad_spend,
                   COALESCE(d.ad_roi, 0) as roi,
                   COALESCE(d.{('visitors' if dimension=='monthly' else 'ipv')}, 0) as visitors,
                   {('COALESCE(d.payment_qty, 0)' if dimension=='monthly' else '0')} as payment_count,
                   CASE WHEN COALESCE(d.payment_amount, 0) > 0 THEN COALESCE(d.refund_amount, 0) * 1.0 / d.payment_amount ELSE 0 END as refund_rate,
                   {('COALESCE(d.page_views, 0)' if dimension=='monthly' else ('COALESCE(d.pv, 0)' if dimension=='daily' else '0'))} as page_views,
                   {('COALESCE(d.uv_value, 0)' if dimension=='monthly' else '0')} as uv_value,
                   {('COALESCE(d.search_visitors, 0)' if dimension=='monthly' else '0')} as search_visitors,
                   {('COALESCE(d.search_ratio, 0)' if dimension=='monthly' else '0')} as search_ratio,
                   {('COALESCE(d.search_conversion, 0)' if dimension=='monthly' else '0')} as search_conversion,
                   COALESCE(d.cart_rate, 0) as cart_rate,
                   COALESCE(d.fav_rate, 0) as fav_rate,
                   COALESCE(d.bounce_rate, 0) as bounce_rate,
                   COALESCE(d.avg_stay_duration, 0) as avg_stay_duration,
                   {monthly_only_cols}
                   {repurchase_cross_cols}
                   {('COALESCE(d.buyers, 0)' if dimension!='weekly' else '0')} as buyers,
                   COALESCE(d.avg_order_value, 0) as avg_order_value,
                   {('COALESCE(d.cart_qty, 0)' if dimension=='monthly' else '0')} as cart_qty,
                   {('COALESCE(d.fav_users, 0)' if dimension=='monthly' else '0')} as fav_users,
                   {click_score_cols}
                   COALESCE(d.net_sales, 0) as net_sales,
                   CASE WHEN COALESCE(d.payment_amount, 0) > 0 THEN COALESCE(d.ad_spend, 0) * 1.0 / d.payment_amount ELSE NULL END as expense_ratio,
                   {('d.trend_change' if dimension == 'daily' and start and end else 'NULL')} as trend_change,
                   {monthly_traffic_cols}
                   {dmp_metric_cols}
                   {('COALESCE(d.cart_users, 0)' if dimension=='monthly' else '0')} as cart_users,
                   {monthly_extra_cols}
                   COALESCE(pd_latest.impressions, 0) as impressions,
                   COALESCE(pd_latest.clicks, 0) as clicks,
                   COALESCE(pd_latest.cost, 0) as cost,
                   COALESCE(pd_latest.ctr, 0) as ctr,
                   COALESCE(pd_latest.cpc, 0) as cpc,
                   COALESCE(pd_latest.cpm, 0) as cpm,
                   COALESCE(pd_latest.direct_gmv, 0) as direct_gmv,
                   COALESCE(pd_latest.indirect_gmv, 0) as indirect_gmv,
                   COALESCE(pd_latest.total_gmv, 0) as total_gmv,
                   COALESCE(pd_latest.total_orders, 0) as total_orders,
                   COALESCE(pd_latest.direct_orders, 0) as direct_orders,
                   COALESCE(pd_latest.indirect_orders, 0) as indirect_orders,
                   COALESCE(pd_latest.click_conversion, 0) as click_conversion,
                   COALESCE(pd_latest.presale_roi, 0) as presale_roi,
                   COALESCE(pd_latest.total_cost, 0) as total_cost,
                   COALESCE(pd_latest.cart_adds, 0) as cart_adds,
                   COALESCE(pd_latest.direct_cart_adds, 0) as direct_cart_adds,
                   COALESCE(pd_latest.indirect_cart_adds, 0) as indirect_cart_adds,
                   COALESCE(pd_latest.favs, 0) as favs,
                   COALESCE(pd_latest.store_favs, 0) as store_favs,
                   COALESCE(pd_latest.store_fav_cost, 0) as store_fav_cost,
                   COALESCE(pd_latest.total_fav_cart, 0) as total_fav_cart,
                   COALESCE(pd_latest.total_fav_cart_cost, 0) as total_fav_cart_cost,
                   COALESCE(pd_latest.item_fav_cart, 0) as item_fav_cart,
                   COALESCE(pd_latest.item_fav_cart_cost, 0) as item_fav_cart_cost,
                   COALESCE(pd_latest.total_favs, 0) as total_favs,
                   COALESCE(pd_latest.item_fav_cost, 0) as item_fav_cost,
                   COALESCE(pd_latest.item_fav_rate, 0) as item_fav_rate,
                   COALESCE(pd_latest.cart_cost, 0) as cart_cost
                   {bi_payload_select}
            FROM products p
            {legacy_lifecycle_join}
            LEFT JOIN {data_relation} d ON {join_clause}
            {bi_payload_join}
            {legacy_paid_join}
            WHERE {where_sql}
        '''
        params.extend(where_params)

        sort_whitelist = [
            'payment_amount','payment_count','refund_amount','refund_rate','conversion',
            'ad_spend','roi','visitors','title','tier','style','scene',
            'page_views','uv_value','search_visitors','search_ratio','search_conversion',
            'cart_rate','fav_rate','bounce_rate','avg_stay_duration',
            'overall_roi','paid_ratio','refund_paid_ratio',
            'keyword_spend','keyword_sales','keyword_roi','keyword_visitors','keyword_ppc',
            'crowd_spend','crowd_sales','crowd_roi','crowd_visitors','crowd_ppc',
            'site_spend','site_sales','site_roi','site_visitors','site_ppc',
            'repurchase_rate','cross_sell_rate','buyers','avg_order_value',
            'cart_qty','fav_users','click_rate','score','net_sales',
            'category','list_date','product_id',
            'presale_amount','presale_qty','search_click_rate','category_width',
            'paid_ipv','organic_ipv','search_ipv','recommend_ipv',
            'cart_users','industry_ctr','cross_sell_qty','cross_sell_categories',
            'repurchase_users','guide_visits','guide_visitors','guide_potential',
            'guide_potential_ratio','new_buyers','new_buyer_ratio',
            'impressions','clicks','cost','ctr','cpc','cpm',
            'direct_gmv','indirect_gmv','total_gmv','total_orders',
            'direct_orders','indirect_orders','click_conversion','presale_roi',
            'total_cost','cart_adds','direct_cart_adds','indirect_cart_adds',
            'favs','store_favs','store_fav_cost','total_fav_cart','total_fav_cart_cost',
            'item_fav_cart','item_fav_cart_cost','total_favs','item_fav_cost',
            'item_fav_rate','cart_cost','manager',
            'expense_ratio','trend_change','lifecycle_stage','seasonality','has_pending_action',
        ]
        sort_col = sort_by if sort_by in sort_whitelist else 'payment_amount'
        # product_id exists on both products and the daily/monthly relation.
        # Qualify it so the public sort option cannot produce an ambiguous SQL error.
        sort_expression = 'p.product_id' if sort_col == 'product_id' else sort_col
        query += f' ORDER BY {sort_expression} {"DESC" if order=="desc" else "ASC"} LIMIT ? OFFSET ?'
        params.append(limit)
        params.append(offset)

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        if dimension == 'monthly' and rows:
            # Resolve only catalogued fields. Missing source values stay absent/None rather
            # than being synthesized as zero, while existing legacy metrics retain compatibility.
            bi_catalog = conn.execute(
                "SELECT field_key, source_column FROM source_field_catalog WHERE source_type = 'bi_monthly_overview'"
            ).fetchall()
            if bi_catalog:
                field_map = {item['field_key']: item['source_column'] for item in bi_catalog}
                for row in rows:
                    raw_payload = row.pop('bi_payload_json', None)
                    try:
                        payload = json.loads(raw_payload) if raw_payload else {}
                    except (TypeError, ValueError):
                        payload = {}
                    for field_key, source_column in field_map.items():
                        row[field_key] = payload.get(source_column)

        # 获取总数（用于服务端分页）- 与主查询使用完全相同的WHERE条件
        count_query = f'''SELECT COUNT(*) as total FROM products p
            LEFT JOIN lifecycle_profiles lp ON lp.product_id = p.product_id
            WHERE {where_sql}'''
        count_params = list(where_params)
        total_row = conn.execute(count_query, count_params).fetchone()
        total_count = total_row['total'] if total_row else 0

        facets = {}
        for facet_name, column in [
            ('tiers', 'tier'), ('styles', 'style'), ('statuses', 'status'),
            ('product_types', 'product_type'), ('product_time_nodes', 'product_time_node'),
            ('product_growth_stages', 'product_growth_stage'),
        ]:
            facets[facet_name] = [
                r[column] for r in conn.execute(
                    f"SELECT DISTINCT {column} FROM products WHERE {column} IS NOT NULL AND TRIM({column}) != '' ORDER BY {column}"
                ).fetchall()
            ]

        # 计算综合评分
        for row in rows:
            row['score'] = calc_score(row)

        # 月度维度下计算环比变化（批量查询上期数据）
        if dimension == 'monthly' and period:
            prev_period = get_prev_period(period, dimension)
            if prev_period != period:
                product_ids = [r['product_id'] for r in rows]
                if product_ids:
                    placeholders = ','.join(['?'] * len(product_ids))
                    prev_rows = conn.execute(f'''
                        SELECT product_id,
                               COALESCE(payment_amount, 0) as payment_amount,
                               COALESCE({visitors_col}, 0) as visitors,
                               COALESCE(payment_conversion, 0) as payment_conversion,
                               CASE WHEN COALESCE(payment_amount, 0) > 0 THEN COALESCE(refund_amount, 0) * 1.0 / payment_amount ELSE 0 END as refund_rate,
                               COALESCE(uv_value, 0) as uv_value
                        FROM {table}
                        WHERE {date_col} = ? AND product_id IN ({placeholders})
                    ''', [prev_period] + product_ids).fetchall()
                    prev_map = {r['product_id']: dict(r) for r in prev_rows}

                    for row in rows:
                        prev_data = prev_map.get(row['product_id'], {})
                        changes = {}
                        for metric in ['payment_amount', 'visitors', 'payment_conversion', 'refund_rate', 'uv_value']:
                            curr_val = row.get(metric, 0) or 0
                            prev_val = prev_data.get(metric, 0) or 0
                            if prev_val > 0:
                                changes[metric] = round((curr_val - prev_val) / prev_val * 100, 1)
                            else:
                                changes[metric] = None
                        row['changes'] = changes
            else:
                for row in rows:
                    row['changes'] = {m: None for m in ['payment_amount', 'visitors', 'payment_conversion', 'refund_rate', 'uv_value']}
        else:
            for row in rows:
                    row['changes'] = {}

    result = {'rows': rows, 'total': total_count, 'limit': limit, 'offset': offset, 'facets': facets, 'period': period or None, 'requested_period': requested_period or None}
    observed_rows = sum(int(row.get('has_data') or 0) for row in rows)
    availability = 'no-data' if not rows else 'available' if observed_rows == len(rows) else 'partial'
    missing_inputs = [] if observed_rows == len(rows) else ['product_daily']
    return success(
        result,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        freshness={'period': period or None, 'start': start or None, 'end': end or None},
        evidence=[{'source': 'products', 'row_count': len(rows), 'observed_fact_rows': observed_rows, 'total': total_count}],
    )

#

@products_legacy_bp.route('/api/product_tags', methods=['GET'])
def get_product_tags():
    """商品自动画像标签 + 自定义标签"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dim}, status=422)
    invalid = _validate_period_arg(dim, period)
    if invalid:
        return invalid
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    with get_db() as conn:
        # 获取当期所有活跃商品数据
        payment_qty_col = 'd.payment_qty' if dim == 'monthly' else '0'
        refund_rate_expr = 'd.refund_rate' if dim == 'monthly' else 'CASE WHEN d.payment_amount > 0 THEN d.refund_amount * 1.0 / d.payment_amount ELSE 0 END'
        overall_roi_expr = 'd.overall_roi' if dim == 'monthly' else '0'
        rows = conn.execute(f'''
            SELECT d.product_id, d.payment_amount, d.payment_conversion,
                   {refund_rate_expr} as refund_rate, d.ad_roi, {overall_roi_expr} as overall_roi, {payment_qty_col} as payment_qty
            FROM {table} d
            JOIN products p ON d.product_id = p.product_id
            WHERE d.{date_col} = ? AND p.status = 'active'
        ''', (period,)).fetchall()

        if not rows:
            return jsonify([])

        data_list = [dict(r) for r in rows]

        # 获取上期数据用于环比计算
        prev_period = get_prev_period(period, dim)
        prev_map = {}
        if prev_period:
            prev_rows = conn.execute(f'''
                SELECT product_id, payment_amount
                FROM {table}
                WHERE {date_col} = ?
            ''', (prev_period,)).fetchall()
            for r in prev_rows:
                prev_map[r['product_id']] = r['payment_amount'] or 0

        # 计算百分位
        amounts = sorted([d['payment_amount'] or 0 for d in data_list])
        n = len(amounts)
        p90 = amounts[int(n * 0.9)] if n > 0 else 0
        p10 = amounts[int(n * 0.1)] if n > 0 else 0

        # 批量查询所有自定义标签（避免N+1查询）
        all_pids = [d['product_id'] for d in data_list]
        if all_pids:
            placeholders = ','.join(['?'] * len(all_pids))
            custom_all = conn.execute(
                f'SELECT product_id, tag FROM product_tags WHERE product_id IN ({placeholders}) AND is_auto = 0',
                all_pids
            ).fetchall()
            custom_map = {}
            for cr in custom_all:
                custom_map.setdefault(cr['product_id'], []).append(cr['tag'])
        else:
            custom_map = {}

        # 自动标签规则
        results = []
        for d in data_list:
            pid = d['product_id']
            tags = []
            amt = d['payment_amount'] or 0
            conv = d['payment_conversion'] or 0
            refund = d['refund_rate'] or 0
            roi = d['overall_roi'] or d['ad_roi'] or 0
            prev_amt = prev_map.get(pid, 0)

            # 爆款：支付金额 >= 90th 百分位 AND 转化率 >= 3%
            if amt >= p90 and conv >= 0.03:
                tags.append('爆款')
            # 潜力款：转化率 >= 5% AND 支付金额环比增长 > 20%
            if conv >= 0.05 and prev_amt > 0 and (amt - prev_amt) / prev_amt > 0.20:
                tags.append('潜力款')
            # 衰退款：支付金额环比下降 > 30%
            if prev_amt > 0 and (amt - prev_amt) / prev_amt < -0.30:
                tags.append('衰退款')
            # 滞销款：支付金额 < 10th 百分位
            if amt <= p10:
                tags.append('滞销款')
            # 高退款：退款率 > 20%
            if refund > 0.20:
                tags.append('高退款')
            # 高ROI：综合ROI > 15
            if roi > 15:
                tags.append('高ROI')

            # 从预查询的map中获取自定义标签
            for ct in custom_map.get(pid, []):
                if ct not in tags:
                    tags.append(ct)

            results.append({
                'product_id': pid,
                'tags': tags,
            })

    return jsonify(results)

@products_legacy_bp.route('/api/product_tags', methods=['POST'])
def add_product_tag():
    """添加自定义标签"""
    data = json_object(request)
    product_id = str(data.get('product_id') or '').strip()
    tag = str(data.get('tag') or '').strip()
    if not product_id or not tag:
        return failure('VALIDATION_ERROR', '缺少参数', status=422)

    with get_db() as conn:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO product_tags (product_id, tag, is_auto) VALUES (?, ?, 0)',
                (product_id, tag)
            )
            conn.commit()
        except Exception:
            current_app.logger.exception('Product tag write failed: %s', product_id)
            return jsonify({'error': '标签保存失败，请稍后重试'}), 500

    return jsonify({'success': True})

@products_legacy_bp.route('/api/product_tags/<int:tag_id>', methods=['DELETE'])
def delete_product_tag(tag_id):
    """删除标签"""
    with get_db() as conn:
        conn.execute('DELETE FROM product_tags WHERE id = ?', (tag_id,))
        conn.commit()
    return jsonify({'success': True})

@products_legacy_bp.route('/api/ad_alerts', methods=['GET'])
@cached_api('get_ad_alerts', ttl=30)
def get_ad_alerts():
    """推广效果预警"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    
    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dim}, status=422)
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    if period:
        period_format = '%Y-%m' if dim == 'monthly' else '%Y-%m-%d'
        try:
            parsed_period = datetime.strptime(period, period_format)
        except (TypeError, ValueError):
            return failure('VALIDATION_ERROR', 'invalid period format', {'dim': dim, 'period': period}, status=422)
        if parsed_period.strftime(period_format) != period:
            return failure('VALIDATION_ERROR', 'invalid period format', {'dim': dim, 'period': period}, status=422)
    
    with get_db() as conn:
        # Auto-detect latest period if not provided
        if not period:
            row = conn.execute(f'SELECT MAX({date_col}) as p FROM {table}').fetchone()
            period = row['p'] if row and row['p'] else ''
            if not period:
                return jsonify([])

        # Get current period ad data per product
        if dim == 'monthly':
            ad_select = 'd.ad_spend, d.ad_roi, d.overall_roi, d.payment_amount, d.keyword_spend, d.keyword_roi, d.crowd_spend, d.crowd_roi'
        else:
            # daily/weekly tables don't have overall_roi, keyword_*, crowd_* columns
            ad_select = 'd.ad_spend, d.ad_roi, d.payment_amount / NULLIF(d.ad_spend, 0) as overall_roi, d.payment_amount, 0 as keyword_spend, 0 as keyword_roi, 0 as crowd_spend, 0 as crowd_roi'
        
        rows = [dict(r) for r in conn.execute(f'''
            SELECT p.product_id, p.title, {ad_select}
            FROM products p
            JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
            WHERE p.status = 'active' AND d.ad_spend > 0
        ''', (period,)).fetchall()]
        
        alerts = []
        for r in rows:
            roi = r.get('overall_roi') or r.get('ad_roi') or 0
            spend = r.get('ad_spend') or 0
            gmv = r.get('payment_amount') or 0
            
            # Alert 1: ROI < 3 (投产比过低)
            if roi > 0 and roi < 3:
                alerts.append({
                    'product_id': r['product_id'],
                    'title': r['title'],
                    'alert_type': 'low_roi',
                    'severity': 'danger' if roi < 1.5 else 'warning',
                    'message': f'投产比仅 {roi:.2f}，低于安全线3.0',
                    'metric': 'ROI',
                    'value': roi,
                    'threshold': 3.0,
                })
            
            # Alert 2: 高花费低产出 (花费>5000 but ROI<5)
            if spend > 5000 and roi > 0 and roi < 5:
                alerts.append({
                    'product_id': r['product_id'],
                    'title': r['title'],
                    'alert_type': 'high_cost_low_return',
                    'severity': 'warning',
                    'message': f'花费¥{spend:.0f}但投产比仅{roi:.2f}',
                    'metric': '花费/ROI',
                    'value': f'¥{spend:.0f}/{roi:.2f}',
                    'threshold': 'ROI≥5',
                })
            
            # Alert 3: 关键词推广ROI过低
            kw_roi = r.get('keyword_roi') or 0
            kw_spend = r.get('keyword_spend') or 0
            if kw_spend > 1000 and kw_roi > 0 and kw_roi < 2:
                alerts.append({
                    'product_id': r['product_id'],
                    'title': r['title'],
                    'alert_type': 'keyword_low_roi',
                    'severity': 'warning',
                    'message': f'直通车投产比仅{kw_roi:.2f}，花费¥{kw_spend:.0f}',
                    'metric': '直通车ROI',
                    'value': kw_roi,
                    'threshold': 2.0,
                })
            
            # Alert 4: 人群推广ROI过低
            cr_roi = r.get('crowd_roi') or 0
            cr_spend = r.get('crowd_spend') or 0
            if cr_spend > 1000 and cr_roi > 0 and cr_roi < 2:
                alerts.append({
                    'product_id': r['product_id'],
                    'title': r['title'],
                    'alert_type': 'crowd_low_roi',
                    'severity': 'warning',
                    'message': f'人群推广投产比仅{cr_roi:.2f}，花费¥{cr_spend:.0f}',
                    'metric': '人群ROI',
                    'value': cr_roi,
                    'threshold': 2.0,
                })
    
    # Sort by severity
    severity_order = {'danger': 0, 'warning': 1, 'info': 2}
    alerts.sort(key=lambda x: severity_order.get(x['severity'], 99))
    
    return jsonify(alerts)

@products_legacy_bp.route('/api/ad_trend', methods=['GET'])
@cached_api('get_ad_trend', ttl=30)
def get_ad_trend():
    """推广趋势分析 — 最近N个周期的推广核心指标"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')
    raw_count = request.args.get('count')
    try:
        periods_count = 6 if raw_count is None else int(raw_count)
    except (TypeError, ValueError):
        return failure('VALIDATION_ERROR', 'count 必须是 1-24 的整数', status=422)
    if not 1 <= periods_count <= 24:
        return failure('VALIDATION_ERROR', 'count 必须是 1-24 的整数', status=422)
    
    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dim}, status=422)
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    if period:
        period_format = '%Y-%m' if dim == 'monthly' else '%Y-%m-%d'
        try:
            parsed_period = datetime.strptime(period, period_format)
        except (TypeError, ValueError):
            return failure(
                'VALIDATION_ERROR',
                f'period must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dim, 'period': period},
                status=422,
            )
        if parsed_period.strftime(period_format) != period:
            return failure(
                'VALIDATION_ERROR',
                f'period must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dim, 'period': period},
                status=422,
            )

    with get_db() as conn:
        # Auto-detect latest period if not provided
        if not period:
            row = conn.execute(f'SELECT MAX({date_col}) as p FROM {table}').fetchone()
            period = row['p'] if row and row['p'] else ''
            if not period:
                return jsonify([])

        # Get recent periods
        if dim == 'monthly':
            rows = [dict(r) for r in conn.execute(f'''
                SELECT {date_col} as period,
                       SUM(ad_spend) as ad_spend,
                       SUM(payment_amount) as gmv,
                       SUM(ad_spend) / NULLIF(SUM(payment_amount), 0) as ad_ratio,
                       SUM(payment_amount) / NULLIF(SUM(ad_spend), 0) as overall_roi,
                       AVG(payment_conversion) as conversion,
                       COUNT(DISTINCT d.product_id) as product_count
                FROM {table} d
                JOIN products p ON p.product_id = d.product_id
                WHERE d.{date_col} <= ? AND p.status = 'active' AND d.ad_spend > 0
                GROUP BY d.{date_col}
                ORDER BY d.{date_col} DESC
                LIMIT ?
            ''', (period, periods_count)).fetchall()]
        elif dim == 'weekly':
            from datetime import timedelta, date
            try:
                base = datetime.strptime(period, '%Y-%m-%d')
                periods = [(base - timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(periods_count)]
                placeholders = ','.join(['?' for _ in periods])
                rows = [dict(r) for r in conn.execute(f'''
                    SELECT {date_col} as period,
                           SUM(ad_spend) as ad_spend,
                           SUM(payment_amount) as gmv,
                           SUM(ad_spend) / NULLIF(SUM(payment_amount), 0) as ad_ratio,
                           SUM(payment_amount) / NULLIF(SUM(ad_spend), 0) as overall_roi,
                           AVG(payment_conversion) as conversion,
                           COUNT(DISTINCT product_id) as product_count
                    FROM {table}
                    WHERE {date_col} IN ({placeholders})
                    GROUP BY {date_col}
                    ORDER BY {date_col} DESC
                ''', periods).fetchall()]
            except ValueError:
                rows = []
        else:  # daily
            from datetime import timedelta, date
            try:
                base = datetime.strptime(period, '%Y-%m-%d')
                periods = [(base - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(min(periods_count, 30))]
                placeholders = ','.join(['?' for _ in periods])
                rows = [dict(r) for r in conn.execute(f'''
                    SELECT {date_col} as period,
                           SUM(ad_spend) as ad_spend,
                           SUM(payment_amount) as gmv,
                           SUM(ad_spend) / NULLIF(SUM(payment_amount), 0) as ad_ratio,
                           SUM(payment_amount) / NULLIF(SUM(ad_spend), 0) as overall_roi,
                           AVG(payment_conversion) as conversion,
                           COUNT(DISTINCT product_id) as product_count
                    FROM {table}
                    WHERE {date_col} IN ({placeholders})
                    GROUP BY {date_col}
                    ORDER BY {date_col} DESC
                ''', periods).fetchall()]
            except ValueError:
                rows = []
        
        # Reverse to chronological order
        rows.reverse()
        
        # Calculate MoM changes
        for i in range(1, len(rows)):
            prev = rows[i-1]
            curr = rows[i]
            for key in ['ad_spend', 'gmv', 'overall_roi', 'conversion']:
                prev_val = prev.get(key) or 0
                curr_val = curr.get(key) or 0
                if prev_val != 0:
                    curr[f'{key}_change'] = round((curr_val - prev_val) / abs(prev_val) * 100, 1)
                else:
                    curr[f'{key}_change'] = None
        
        return jsonify(rows)


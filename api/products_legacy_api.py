from datetime import datetime, timedelta
"""Products Legacy API - 商品和推广相关接口（旧版）

从 data_api.py 拆分出来的独立模块，包含：
- 商品列表/详情/更新
- 商品标签 CRUD
- 广告告警/趋势
"""

import io
import json
import re
from api.data_api import DIMENSION_MAP, _reject_legacy_shop_scope, _validate_period_arg, calc_score, cached_api, get_prev_period

import pandas as pd
from flask import Blueprint, current_app, g, jsonify, request

from db import get_db, get_shop_id
from api.api_response import evidence_level_for, failure, json_object, limitations_for, success
from services.category_mode_service import category_filters_from_request
from services.shop_scope_service import reject_legacy_shop_scope
from services.product_rules_service import condition_for_dimension, get_rule
from services.dmp_item_metrics_enrichment import enrich_rows, snapshot_metadata
from services.promotion_item_metrics_enrichment import (
    enrich_rows as promotion_enrich_rows,
    source_metadata as promotion_source_metadata,
)
from services.lead_item_metrics_enrichment import (
    enrich_rows as lead_enrich_rows,
    source_metadata as lead_source_metadata,
)


products_legacy_bp = Blueprint('products_legacy', __name__)


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
    rule_key = request.args.get('rule_key', '')
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

        # 2026-10-19 零值审计结论（data/dashboard.db 全表扫描，见 tests/test_products_null_semantics.py）：
        # 下列列在源表里从来没有出现过非零值——monthly_data 80192 行、daily_data 153618 行
        # 全是 0 或 NULL，paid_detail 是 0 行。这说明采集链路没把这些字段落库，
        # 而不是业务上真的为 0。对它们不再 COALESCE(..., 0)，让 NULL 直通；
        # 前端 products-live.js:156-161 的 money/number/percent/decimal 会把 NULL 渲染成 `--`。
        # 只对“从未有过非零值”的列这样做。ad_spend / ad_roi / visitors / uv_value /
        # payment_qty / cart_qty / fav_users / cart_users / search_visitors / search_ratio /
        # search_conversion / search_ipv(daily) 等确有数据的列保持 COALESCE，因为它们的 0 是真值。
        #
        # 第二层：这些列在 SQLite 建表时带 `DEFAULT 0`（见 db_migrations.py 的
        # new_monthly_cols / new_daily_cols），导入链路根本没写它们时落库就是 0 而不是 NULL。
        # 所以光去掉 COALESCE 还不够，必须用 NULLIF(x, 0) 把这种“没采到的 0”还原成 NULL。
        # 依据仍是同一次全表扫描：这些列 nz=0，历史数据里不存在真正的非零值。
        # ⚠️ 等采集链路真的开始回填这些字段后，应把 NULLIF 去掉，否则真实的 0 也会被显示成 `--`。
        # monthly_data 独有的列（daily/weekly表不存在）
        _monthly_ad_cols = '''NULLIF(d.overall_roi, 0) as overall_roi,
                   NULLIF(d.paid_ratio, 0) as paid_ratio,
                   NULLIF(d.refund_paid_ratio, 0) as refund_paid_ratio,
                   NULLIF(d.keyword_spend, 0) as keyword_spend,
                   NULLIF(d.keyword_sales, 0) as keyword_sales,
                   NULLIF(d.keyword_roi, 0) as keyword_roi,
                   NULLIF(d.keyword_visitors, 0) as keyword_visitors,
                   NULLIF(d.keyword_ppc, 0) as keyword_ppc,
                   NULLIF(d.crowd_spend, 0) as crowd_spend,
                   NULLIF(d.crowd_sales, 0) as crowd_sales,
                   NULLIF(d.crowd_roi, 0) as crowd_roi,
                   NULLIF(d.crowd_visitors, 0) as crowd_visitors,
                   NULLIF(d.crowd_ppc, 0) as crowd_ppc,
                   NULLIF(d.site_spend, 0) as site_spend,
                   NULLIF(d.site_sales, 0) as site_sales,
                   NULLIF(d.site_roi, 0) as site_roi,
                   NULLIF(d.site_visitors, 0) as site_visitors,
                   NULLIF(d.site_ppc, 0) as site_ppc,'''

        _monthly_traffic_cols = '''NULLIF(d.paid_ipv, 0) as paid_ipv,
                   NULLIF(d.organic_ipv, 0) as organic_ipv,
                   NULLIF(d.search_ipv, 0) as search_ipv,
                   NULLIF(d.recommend_ipv, 0) as recommend_ipv,'''

        _monthly_extra_cols = '''NULLIF(d.industry_ctr, 0) as industry_ctr,
                   NULLIF(d.cross_sell_qty, 0) as cross_sell_qty,
                   NULLIF(d.cross_sell_categories, 0) as cross_sell_categories,
                   NULLIF(d.repurchase_users, 0) as repurchase_users,
                   NULLIF(d.guide_visits, 0) as guide_visits,
                   NULLIF(d.guide_visitors, 0) as guide_visitors,
                   NULLIF(d.guide_potential, 0) as guide_potential,
                   NULLIF(d.guide_potential_ratio, 0) as guide_potential_ratio,
                   NULLIF(d.new_buyers, 0) as new_buyers,
                   NULLIF(d.new_buyer_ratio, 0) as new_buyer_ratio,'''

        # weekly 维度没有这些源列，只能给 NULL 字面量；给 0 会让前端把“不可得”画成真实 0。
        _zero_ad = ',\n               '.join([f'NULL as {c}' for c in ['overall_roi','paid_ratio','refund_paid_ratio','keyword_spend','keyword_sales','keyword_roi','keyword_visitors','keyword_ppc','crowd_spend','crowd_sales','crowd_roi','crowd_visitors','crowd_ppc','site_spend','site_sales','site_roi','site_visitors','site_ppc']]) + ','
        _zero_traffic = ',\n               '.join([f'NULL as {c}' for c in ['paid_ipv','organic_ipv','search_ipv','recommend_ipv']]) + ','
        _zero_extra = ',\n               '.join([f'NULL as {c}' for c in ['industry_ctr','cross_sell_categories','guide_visits','guide_visitors','guide_potential','guide_potential_ratio','new_buyers','new_buyer_ratio']]) + ','

        monthly_only_cols = _monthly_ad_cols if dimension == 'monthly' else _zero_ad
        # Daily BI facts carry the traffic split columns only when the source
        # actually provides them. Keep NULL for unavailable paid/organic/
        # recommendation traffic instead of manufacturing a real-looking 0.
        if dimension == 'daily':
            monthly_traffic_cols = '''NULLIF(d.paid_ipv, 0) as paid_ipv,
                   NULLIF(d.organic_ipv, 0) as organic_ipv,
                   COALESCE(d.search_ipv, 0) as search_ipv,
                   NULLIF(d.recommend_ipv, 0) as recommend_ipv,'''
        else:
            monthly_traffic_cols = _monthly_traffic_cols if dimension == 'monthly' else _zero_traffic

        payment_count_expr = 'COALESCE(d.payment_qty, 0)' if dimension in {'monthly', 'daily'} else 'NULL'
        uv_value_expr = 'COALESCE(d.uv_value, 0)' if dimension in {'monthly', 'daily'} else 'NULL'
        search_visitors_expr = (
            'COALESCE(d.search_visitors, 0)' if dimension == 'monthly'
            else ('COALESCE(d.search_ipv, 0)' if dimension == 'daily' else 'NULL')
        )
        search_ratio_expr = (
            'COALESCE(d.search_ratio, 0)' if dimension == 'monthly'
            else ("CASE WHEN COALESCE(d.ipv, 0) > 0 THEN COALESCE(d.search_ipv, 0) * 1.0 / d.ipv ELSE NULL END" if dimension == 'daily' else 'NULL')
        )
        search_conversion_expr = 'COALESCE(d.search_conversion, 0)' if dimension in {'monthly', 'daily'} else 'NULL'
        cart_qty_expr = 'COALESCE(d.cart_qty, 0)' if dimension in {'monthly', 'daily'} else 'NULL'
        fav_users_expr = 'COALESCE(d.fav_users, 0)' if dimension in {'monthly', 'daily'} else 'NULL'
        cart_users_expr = 'COALESCE(d.cart_users, 0)' if dimension in {'monthly', 'daily'} else 'NULL'
        monthly_extra_cols = _monthly_extra_cols if dimension == 'monthly' else _zero_extra
        dmp_cols = '''NULLIF(d.repurchase_users, 0) as repurchase_users,
                   NULLIF(d.presale_amount, 0) as presale_amount,
                   NULLIF(d.presale_qty, 0) as presale_qty,
                   NULLIF(d.search_click_rate, 0) as search_click_rate,
                   NULLIF(d.cross_sell_qty, 0) as cross_sell_qty,
                   NULLIF(d.category_width, 0) as category_width,
                   NULL as industry_ctr,'''
        dmp_zero_cols = '''NULL as presale_amount, NULL as presale_qty,
                   NULL as search_click_rate, NULL as category_width,'''
        dmp_metric_cols = dmp_cols if dimension in {'daily', 'weekly'} else dmp_zero_cols
        repurchase_cross_cols = "NULLIF(d.repurchase_rate, 0) as repurchase_rate,\n               NULLIF(d.cross_sell_rate, 0) as cross_sell_rate," if dimension in {'monthly', 'daily', 'weekly'} else "NULL as repurchase_rate,\n               NULL as cross_sell_rate,"
        click_score_cols = "NULLIF(d.click_rate, 0) as click_rate,\n               NULLIF(d.score, 0) as score," if dimension == 'monthly' else "NULL as click_rate,\n               NULL as score,"
        # 利润三列：daily/monthly 直取源列（2026-10-24 实测 operating_profit 近期全非空，
        # 且利润为 0 是真值——盈亏平衡，不做 NULLIF 也不 COALESCE 成 0，无事实行保持 NULL→前端 `--`）。
        # profit_rate 必须"先聚合再相除"：daily 区间分支的 d.net_sales/d.operating_profit 已是区间 SUM。
        # weekly_data 无利润列，给 NULL 字面量（weekly 分支的其余 NULL 列同因）。
        if dimension == 'weekly':
            profit_cols = 'NULL as operating_profit,\n                   NULL as product_cost,\n                   NULL as profit_rate,'
        else:
            _net_base = 'COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0)'
            profit_cols = f'''d.operating_profit as operating_profit,
                   d.product_cost as product_cost,
                   CASE WHEN {_net_base} > 0 THEN d.operating_profit * 1.0 / {_net_base} ELSE NULL END as profit_rate,'''
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
                       current.payment_qty,
                       current.uv_value,
                       current.search_visitors,
                       current.search_conversion,
                       current.cart_qty,
                       current.fav_users,
                       current.cart_users,
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
                       current.operating_profit,
                       current.product_cost,
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
                            CASE WHEN SUM(ipv) > 0 THEN SUM(buyers) * 1.0 / SUM(ipv) ELSE NULL END AS payment_conversion,
                            CASE WHEN SUM(ipv) > 0 THEN SUM(cart_users) * 1.0 / SUM(ipv) ELSE NULL END AS cart_rate,
                            CASE WHEN SUM(ipv) > 0 THEN SUM(fav_users) * 1.0 / SUM(ipv) ELSE NULL END AS fav_rate,
                           AVG(bounce_rate) AS bounce_rate,
                           AVG(avg_stay_duration) AS avg_stay_duration,
                           SUM(ad_spend) AS ad_spend,
                            CASE WHEN SUM(ad_spend) > 0 THEN SUM(net_sales) / SUM(ad_spend) ELSE NULL END AS ad_roi,
                            SUM(buyers) AS buyers,
                            CASE WHEN SUM(buyers) > 0 THEN SUM(payment_amount) / SUM(buyers) ELSE AVG(avg_order_value) END AS avg_order_value,
                            SUM(payment_qty) AS payment_qty,
                            AVG(uv_value) AS uv_value,
                            SUM(search_ipv) AS search_visitors,
                            CASE WHEN SUM(search_ipv) > 0 THEN SUM(search_payment_buyers) * 1.0 / SUM(search_ipv) ELSE NULL END AS search_conversion,
                            SUM(cart_qty) AS cart_qty,
                            SUM(fav_users) AS fav_users,
                            SUM(cart_users) AS cart_users,
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
                           AVG(category_width) AS category_width,
                           SUM(operating_profit) AS operating_profit,
                           SUM(product_cost) AS product_cost
                     FROM daily_data
                     WHERE shop_id = ? AND date BETWEEN ? AND ?
                    GROUP BY product_id
                ) current
                LEFT JOIN (
                    SELECT product_id,
                           SUM(payment_amount) AS payment_amount,
                           SUM(refund_amount) AS refund_amount,
                           SUM(net_sales) AS net_sales,
                           SUM(ad_spend) AS ad_spend,
                           SUM(operating_profit) AS operating_profit
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
        # 经营分群和品类范围都代表“当前周期可审计的商品集合”。在这两种
        # 场景下没有事实行的商品不能进入列表，否则卡片命中数与列表总数会漂移。
        # 未带范围的旧调用继续保留 LEFT JOIN，以维持主档 partial 兼容语义。
        require_period_facts = (
            (dimension == 'daily' and bool(start and end and start == end))
            or (dimension == 'monthly' and bool(_category_filters.get('shop_label') or rule_key))
        )
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
        if rule_key:
            if not get_rule(rule_key):
                return failure('VALIDATION_ERROR', 'invalid product rule', {'rule_key': rule_key}, status=422)
            where_clauses.append(condition_for_dimension(rule_key, dimension))
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
                   d.ad_roi as roi,
                   COALESCE(d.{('visitors' if dimension=='monthly' else 'ipv')}, 0) as visitors,
                    {payment_count_expr} as payment_count,
                   -- 分母为 0 时比率无定义，返回 NULL（前端渲染 `--`），不再伪造成 0%
                   CASE WHEN COALESCE(d.payment_amount, 0) > 0 THEN COALESCE(d.refund_amount, 0) * 1.0 / d.payment_amount ELSE NULL END as refund_rate,
                   {('COALESCE(d.page_views, 0)' if dimension=='monthly' else ('COALESCE(d.pv, 0)' if dimension=='daily' else 'NULL'))} as page_views,
                    {uv_value_expr} as uv_value,
                    {search_visitors_expr} as search_visitors,
                    {search_ratio_expr} as search_ratio,
                    {search_conversion_expr} as search_conversion,
                   COALESCE(d.cart_rate, 0) as cart_rate,
                   COALESCE(d.fav_rate, 0) as fav_rate,
                   COALESCE(d.bounce_rate, 0) as bounce_rate,
                   COALESCE(d.avg_stay_duration, 0) as avg_stay_duration,
                   {monthly_only_cols}
                   {repurchase_cross_cols}
                   {('COALESCE(d.buyers, 0)' if dimension!='weekly' else 'NULL')} as buyers,
                   COALESCE(d.avg_order_value, 0) as avg_order_value,
                    {cart_qty_expr} as cart_qty,
                    {fav_users_expr} as fav_users,
                   {click_score_cols}
                   COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0) as net_sales,
                   CASE WHEN COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0) > 0
                        THEN COALESCE(d.ad_spend, 0) * 1.0 / COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0) ELSE NULL END as expense_ratio,
                   {profit_cols}
                   {('d.trend_change' if dimension == 'daily' and start and end else 'NULL')} as trend_change,
                   {monthly_traffic_cols}
                   {dmp_metric_cols}
                    {cart_users_expr} as cart_users,
                   {monthly_extra_cols}
                   pd_latest.impressions as impressions,
                   pd_latest.clicks as clicks,
                   pd_latest.cost as cost,
                   pd_latest.ctr as ctr,
                   pd_latest.cpc as cpc,
                   pd_latest.cpm as cpm,
                   pd_latest.direct_gmv as direct_gmv,
                   pd_latest.indirect_gmv as indirect_gmv,
                   pd_latest.total_gmv as total_gmv,
                   pd_latest.total_orders as total_orders,
                   pd_latest.direct_orders as direct_orders,
                   pd_latest.indirect_orders as indirect_orders,
                   pd_latest.click_conversion as click_conversion,
                   pd_latest.presale_roi as presale_roi,
                   pd_latest.total_cost as total_cost,
                   pd_latest.cart_adds as cart_adds,
                   pd_latest.direct_cart_adds as direct_cart_adds,
                   pd_latest.indirect_cart_adds as indirect_cart_adds,
                   pd_latest.favs as favs,
                   pd_latest.store_favs as store_favs,
                   pd_latest.store_fav_cost as store_fav_cost,
                   pd_latest.total_fav_cart as total_fav_cart,
                   pd_latest.total_fav_cart_cost as total_fav_cart_cost,
                   pd_latest.item_fav_cart as item_fav_cart,
                   pd_latest.item_fav_cart_cost as item_fav_cart_cost,
                   pd_latest.total_favs as total_favs,
                   pd_latest.item_fav_cost as item_fav_cost,
                   pd_latest.item_fav_rate as item_fav_rate,
                   pd_latest.cart_cost as cart_cost
                   {bi_payload_select}
            FROM products p
            {legacy_lifecycle_join}
            {'JOIN' if require_period_facts else 'LEFT JOIN'} {data_relation} d ON {join_clause}
            {bi_payload_join}
            {legacy_paid_join}
            WHERE {where_sql}
        '''
        params.extend(where_params)

        sort_whitelist = [            'payment_amount','payment_count','refund_amount','refund_rate','conversion',
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
            'operating_profit','product_cost','profit_rate',
        ]
        sort_col = sort_by if sort_by in sort_whitelist else 'payment_amount'
        # 区间筛选（min_<field>/max_<field>）：只接受白名单内的**外层别名**，数值解析失败静默忽略。
        # 白名单即主 SELECT 的输出别名，包一层子查询后天然不可注入（字段名走白名单，值走参数绑定）。
        # 区间作用于聚合后的行级值（例如退款率是“先聚合再相除”的结果），与列显示口径一致。
        _RANGE_FIELDS = {
            'payment_amount', 'refund_amount', 'net_sales', 'ad_spend',
            'operating_profit', 'product_cost',
            'refund_rate', 'expense_ratio', 'profit_rate', 'conversion',
            'visitors', 'payment_count', 'buyers', 'search_visitors',
            'search_ratio', 'cart_users', 'cart_rate', 'uv_value', 'roi',
        }
        range_clauses = []
        range_params = []
        for arg_key, arg_value in request.args.items(multi=False):
            match = re.fullmatch(r'(min|max)_([a-z_]+)', arg_key)
            if not match:
                continue
            field = match.group(2)
            if field not in _RANGE_FIELDS:
                continue
            try:
                bound = float(arg_value)
            except (TypeError, ValueError):
                continue
            op = '>=' if match.group(1) == 'min' else '<='
            range_clauses.append(f'filtered.{field} {op} ?')
            range_params.append(bound)
        range_sql = ' AND '.join(range_clauses)
        base_params = list(params)

        # 汇总行（BI 的「汇总：全部」档）：按当前全部筛选条件（含区间、不含分页）服务端聚合。
        # 不抄 BI「切换全部/当前页数值不变」的缺陷——全部档必须来自独立聚合查询。
        summary_query = f'''SELECT COUNT(*) AS rows_count,
               COALESCE(SUM(payment_amount), 0) AS payment_amount,
               COALESCE(SUM(refund_amount), 0) AS refund_amount,
               COALESCE(SUM(net_sales), 0) AS net_sales,
               COALESCE(SUM(ad_spend), 0) AS ad_spend,
               SUM(operating_profit) AS operating_profit,
               SUM(product_cost) AS product_cost,
               COALESCE(SUM(buyers), 0) AS buyers,
               COALESCE(SUM(visitors), 0) AS visitors
            FROM ({query}) filtered'''
        summary_exec = base_params + range_params
        if range_sql:
            summary_query += f' WHERE {range_sql}'
        summary_row = conn.execute(summary_query, summary_exec).fetchone()
        _summary = dict(summary_row) if summary_row else {}

        if range_sql:
            count_query = f'SELECT COUNT(*) AS total FROM ({query}) filtered WHERE {range_sql}'
            count_params = base_params + range_params
            # 包裹后外层没有 p. 前缀，全部按别名排序（白名单里都是主 SELECT 别名）
            page_query = (
                f'SELECT * FROM ({query}) filtered WHERE {range_sql} '
                f'ORDER BY {sort_col} {"DESC" if order=="desc" else "ASC"} LIMIT ? OFFSET ?'
            )
            page_params = base_params + range_params + [limit, offset]
        else:
            count_query = f'''SELECT COUNT(*) as total FROM products p
                {legacy_lifecycle_join}
                {'JOIN' if require_period_facts else 'LEFT JOIN'} {data_relation} d ON {join_clause}
                {bi_payload_join}
                {legacy_paid_join}
                WHERE {where_sql}'''
            count_params = base_params
            # product_id exists on both products and the daily/monthly relation.
            # Qualify it so the public sort option cannot produce an ambiguous SQL error.
            sort_expression = 'p.product_id' if sort_col == 'product_id' else sort_col
            page_query = query + f' ORDER BY {sort_expression} {"DESC" if order=="desc" else "ASC"} LIMIT ? OFFSET ?'
            page_params = base_params + [limit, offset]

        rows = [dict(r) for r in conn.execute(page_query, page_params).fetchall()]

        # 达摩盘单品指标回填：daily_data 里这几列从未采到过非零值（search_click_rate /
        # category_width / repurchase_* / cross_sell_* / presale_*），唯一真实源是
        # dmp_shop_item_indicators。这里只补当前页为 NULL 的字段，且只在窗口天数与
        # 快照 period 对齐时生效；快照窗口会通过 source_batches/limitations 披露。
        dmp_enrichment = None
        if dimension == 'daily' and rows and start and end:
            dmp_enrichment = enrich_rows(conn, rows, start, end)

        # 万相台推广事实回填：「推广与付费」分组里展现量/点击量/点击率/点击单价/
        # 千次展现花费/直接与归因成交/加购次数/加购成本/新买家/点击转化率这些列
        # 在 SQL 里取自 paid_detail，而 paid_detail 实测是 0 行（从未采集）。
        # 真实数据在 promotion_daily_facts（grain='product' + channel='全部'）。
        # 同样只填当前页为 NULL 的字段。
        promotion_enrichment = None
        if dimension == 'daily' and rows and start and end:
            promotion_enrichment = promotion_enrich_rows(conn, rows, start, end)

        # 万相台潜客回填：guide_visitors / guide_potential / guide_potential_ratio 在
        # monthly_data 里从未写过非零值（nz=0），真实源是 promotion_lead_daily
        # （万相台 item_promotion 报表，商品×日粒度）。口径：占比 = 潜客数 ÷ 入店访客数。
        # 该表是滚动窗口，这里取与请求区间的交集，并通过 source_batches/limitations 披露。
        lead_enrichment = None
        if dimension == 'daily' and rows and start and end:
            lead_enrichment = lead_enrich_rows(conn, rows, start, end)

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

        # 总数已在上方（含区间筛选语义一致）计算
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
                               COALESCE(uv_value, 0) as uv_value,
                               COALESCE(operating_profit, 0) as operating_profit,
                               COALESCE(ad_spend, 0) as ad_spend,
                               COALESCE(NULLIF(net_sales, 0), payment_amount - refund_amount, 0) as net_sales
                        FROM {table}
                        WHERE {date_col} = ? AND product_id IN ({placeholders})
                    ''', [prev_period] + product_ids).fetchall()
                    prev_map = {r['product_id']: dict(r) for r in prev_rows}

                    for row in rows:
                        prev_data = prev_map.get(row['product_id'], {})
                        changes = {}
                        for metric in ['payment_amount', 'visitors', 'payment_conversion', 'refund_rate', 'uv_value', 'operating_profit']:
                            curr_val = row.get(metric, 0) or 0
                            prev_val = prev_data.get(metric, 0) or 0
                            if prev_val > 0:
                                changes[metric] = round((curr_val - prev_val) / prev_val * 100, 1)
                            else:
                                changes[metric] = None
                        # 费比与利润率是"先聚合再相除"的派生口径，环比要对比两侧各自的比率
                        prev_net = prev_data.get('net_sales') or 0
                        prev_expense = (prev_data.get('ad_spend') or 0) / prev_net if prev_net > 0 else None
                        for metric, prev_rate in (('expense_ratio', prev_expense), ('profit_rate', (prev_data.get('operating_profit') or 0) / prev_net if prev_net > 0 else None)):
                            curr_rate = row.get(metric)
                            if curr_rate is not None and prev_rate:
                                changes[metric] = round((curr_rate - prev_rate) / prev_rate * 100, 1)
                            else:
                                changes[metric] = None
                        row['changes'] = changes
            else:
                for row in rows:
                    row['changes'] = {m: None for m in ['payment_amount', 'visitors', 'payment_conversion', 'refund_rate', 'uv_value', 'operating_profit', 'expense_ratio', 'profit_rate']}
        else:
            for row in rows:
                    row['changes'] = {}

        # daily 维度环比：上一等长窗口（与 SQL 里 trend_change 的窗口口径一致）。
        # 单日视图（start==end，页面默认）也补前一日对比；率类指标两侧各自"先聚合再相除"。
        if dimension == 'daily' and rows:
            eff_start = start or period
            eff_end = end or period
            if eff_start and eff_end:
                try:
                    start_day = datetime.strptime(eff_start, '%Y-%m-%d')
                    end_day = datetime.strptime(eff_end, '%Y-%m-%d')
                except (TypeError, ValueError):
                    start_day = end_day = None
                if start_day and end_day and end_day >= start_day:
                    span_days = (end_day - start_day).days + 1
                    prev_end_day = start_day - timedelta(days=1)
                    prev_start_day = prev_end_day - timedelta(days=span_days - 1)
                    product_ids = [r['product_id'] for r in rows]
                    if product_ids:
                        placeholders = ','.join(['?'] * len(product_ids))
                        prev_rows = conn.execute(f'''
                            SELECT product_id,
                                   COALESCE(SUM(payment_amount), 0) AS payment_amount,
                                   COALESCE(SUM(refund_amount), 0) AS refund_amount,
                                   COALESCE(SUM(net_sales), 0) AS net_sales,
                                   COALESCE(SUM(ad_spend), 0) AS ad_spend,
                                   SUM(operating_profit) AS operating_profit
                            FROM daily_data
                            WHERE shop_id = ? AND date BETWEEN ? AND ?
                              AND product_id IN ({placeholders})
                            GROUP BY product_id
                        ''', [shop_id, prev_start_day.strftime('%Y-%m-%d'), prev_end_day.strftime('%Y-%m-%d')] + product_ids).fetchall()
                        prev_map = {r['product_id']: dict(r) for r in prev_rows}

                        def _ratio(num, den):
                            return (num / den) if (num is not None and den and den > 0) else None

                        for row in rows:
                            prev_data = prev_map.get(row['product_id'], {})
                            prev_net = prev_data.get('net_sales') or 0
                            prev = {
                                'payment_amount': prev_data.get('payment_amount') or 0,
                                'refund_rate': _ratio(prev_data.get('refund_amount'), prev_data.get('payment_amount')),
                                'expense_ratio': _ratio(prev_data.get('ad_spend'), prev_net),
                                'operating_profit': prev_data.get('operating_profit'),
                                'profit_rate': _ratio(prev_data.get('operating_profit'), prev_net),
                            }
                            curr_net = row.get('net_sales') or 0
                            curr = {
                                'payment_amount': row.get('payment_amount') or 0,
                                'refund_rate': row.get('refund_rate'),
                                'expense_ratio': row.get('expense_ratio'),
                                'operating_profit': row.get('operating_profit'),
                                'profit_rate': row.get('profit_rate') if row.get('profit_rate') is not None else _ratio(row.get('operating_profit'), curr_net),
                            }
                            changes = {}
                            for metric in prev:
                                c_val, p_val = curr.get(metric), prev.get(metric)
                                changes[metric] = round((c_val - p_val) / p_val * 100, 1) if (c_val is not None and p_val not in (None, 0)) else None
                            row['changes'] = changes

    def _safe_ratio(num, den):
        return (num / den) if (num is not None and den and den > 0) else None

    _s_pay = _summary.get('payment_amount') or 0
    _s_net = _summary.get('net_sales') or 0
    _s_op = _summary.get('operating_profit')
    summary = {
        'rows_count': _summary.get('rows_count') or 0,
        'payment_amount': _s_pay,
        'net_sales': _s_net,
        'refund_amount': _summary.get('refund_amount') or 0,
        'refund_rate': _safe_ratio(_summary.get('refund_amount') or 0, _s_pay),
        'ad_spend': _summary.get('ad_spend') or 0,
        'expense_ratio': _safe_ratio(_summary.get('ad_spend') or 0, _s_net),
        'operating_profit': _s_op,
        'profit_rate': _safe_ratio(_s_op, _s_net),
        'buyers': _summary.get('buyers') or 0,
        'visitors': _summary.get('visitors') or 0,
        'conversion': _safe_ratio(_summary.get('buyers') or 0, _summary.get('visitors') or 0),
    }

    result = {'rows': rows, 'total': total_count, 'limit': limit, 'offset': offset, 'facets': facets, 'summary': summary, 'period': period or None, 'requested_period': requested_period or None}
    observed_rows = sum(int(row.get('has_data') or 0) for row in rows)
    availability = 'no-data' if not rows else 'available' if observed_rows == len(rows) else 'partial'
    missing_inputs = [] if observed_rows == len(rows) else ['product_daily']

    # 达摩盘快照披露：让调用方知道哪几列不是来自本期日粒度事实表。
    dmp_snapshot = snapshot_metadata((dmp_enrichment or {}).get('snapshot'))
    source_batches = None
    if dmp_snapshot:
        source_batches = [dmp_snapshot]
    response_limitations = limitations_for(availability, missing_inputs=missing_inputs)
    if dmp_snapshot:
        window = f"{dmp_snapshot['snapshot_start_date']}~{dmp_snapshot['snapshot_end_date']}"
        note = f"达摩盘单品指标（{'/'.join(dmp_snapshot['fields'])}）取自 {dmp_snapshot['period_days']} 天窗口 {window}"
        if not dmp_snapshot['exact_window']:
            note += f"，与请求区间相差 {dmp_snapshot['aligned_days']} 天"
        response_limitations = list(response_limitations) + [note]

    # 万相台推广事实披露：这些列不来自 paid_detail（该表 0 行），而是
    # promotion_daily_facts 的 grain='product' + channel='全部' 聚合。
    if promotion_enrichment and promotion_enrichment.get('applied'):
        promotion_meta = promotion_source_metadata(promotion_enrichment.get('matched_items') or 0)
        source_batches = list(source_batches or []) + [promotion_meta]
        response_limitations = list(response_limitations) + [
            "推广转化指标（展现/点击/点击率/点击单价/千次展现花费/直接与归因成交/加购次数/"
            "加购成本/新买家/点击转化率）取自万相台 promotion_daily_facts 商品粒度汇总；"
            "归因成交不含间接成交，与账单口径花费不同源，二者不可相减"
        ]

    # 万相台潜客披露：占比 = 潜客数 ÷ 入店访客数，且单品口径不可相加。
    if lead_enrichment and lead_enrichment.get('applied'):
        lead_meta = lead_source_metadata(lead_enrichment)
        source_batches = list(source_batches or []) + [lead_meta]
        window_note = f"{lead_meta['covered_start']}~{lead_meta['covered_end']}"
        note = (f"引导潜客指标（引导访客/引导潜客/引导潜客占比）取自万相台 "
                f"promotion_lead_daily 商品日粒度汇总，覆盖 {window_note} 共 "
                f"{lead_meta['covered_days']} 天")
        if not lead_meta['full_window']:
            note += (f"（请求 {lead_meta['requested_days']} 天，该表仅覆盖 "
                     f"{lead_meta['table_start']}~{lead_meta['table_end']}）")
        note += "；占比 = 潜客数 ÷ 入店访客数；单品口径不可相加，同一用户逛多个商品会重复计数"
        response_limitations = list(response_limitations) + [note]

    return success(
        result,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        source_batches=source_batches,
        limitations=response_limitations,
        freshness={'period': period or None, 'start': start or None, 'end': end or None},
        evidence=[{'source': 'products', 'row_count': len(rows), 'observed_fact_rows': observed_rows, 'total': total_count}],
    )

#

@products_legacy_bp.route('/api/products/timeline', methods=['GET'])
@cached_api('products-timeline', 30)
def get_products_timeline():
    """Return period-grain rows for the products currently shown in the list."""
    dimension = request.args.get('dim', 'daily')
    if dimension not in {'daily', 'weekly', 'monthly'}:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dimension}, status=422)
    product_ids = [value.strip() for value in request.args.get('product_ids', '').split(',') if value.strip()]
    if not product_ids:
        return success({'rows': [], 'dimension': dimension, 'start': None, 'end': None}, availability='no-data')
    if len(product_ids) > 200:
        return failure('VALIDATION_ERROR', 'too many product_ids', status=422)
    start = request.args.get('start', '').strip()
    end = request.args.get('end', '').strip()
    period = request.args.get('period', '').strip()
    limit_periods = max(0, min(request.args.get('limit_periods', 0, type=int) or 0, 24))
    invalid = _validate_period_arg(dimension, period) if period else None
    if invalid:
        return invalid
    table = {'daily': 'daily_data', 'weekly': 'weekly_data', 'monthly': 'monthly_data'}[dimension]
    date_col = {'daily': 'date', 'weekly': 'week_start', 'monthly': 'month'}[dimension]
    visitors_col = {'daily': 'ipv', 'weekly': 'ipv', 'monthly': 'visitors'}[dimension]
    paid_ipv_expr = 'd.paid_ipv' if dimension == 'daily' else ('COALESCE(d.paid_ipv, 0)' if dimension == 'weekly' else '0')
    organic_ipv_expr = 'd.organic_ipv' if dimension == 'daily' else ('COALESCE(d.organic_ipv, 0)' if dimension == 'weekly' else '0')
    search_ipv_expr = 'COALESCE(d.search_ipv, 0)' if dimension in {'daily', 'weekly'} else '0'
    recommend_ipv_expr = 'd.recommend_ipv' if dimension == 'daily' else ('COALESCE(d.recommend_ipv, 0)' if dimension == 'weekly' else '0')
    buyers_expr = 'COALESCE(d.buyers, 0)' if dimension in {'daily', 'monthly'} else '0'
    shop_id = get_shop_id()
    placeholders = ','.join('?' for _ in product_ids)
    clauses = [f'd.product_id IN ({placeholders})']
    params = list(product_ids)
    if dimension == 'daily':
        clauses.append('d.shop_id = ?')
        params.append(shop_id)
        if start:
            clauses.append('d.date >= ?')
            params.append(start)
        if end:
            clauses.append('d.date <= ?')
            params.append(end)
    elif dimension == 'weekly':
        if start:
            clauses.append('d.week_start >= ?')
            params.append(start)
        if end:
            clauses.append('d.week_start <= ?')
            params.append(end)
    elif period:
        clauses.append('d.month = ?')
        params.append(period[:7])
    elif start or end:
        if start:
            if not limit_periods:
                clauses.append('d.month >= ?')
                params.append(start[:7])
        if end:
            clauses.append('d.month <= ?')
            params.append(end[:7])
    with get_db() as conn:
        rows = conn.execute(
            f'''SELECT d.product_id, d.{date_col} AS period,
                       COALESCE(d.payment_amount, 0) AS payment_amount,
                       COALESCE(d.refund_amount, 0) AS refund_amount,
                       COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0) AS net_sales,
                       COALESCE(d.{visitors_col}, 0) AS visitors,
                       COALESCE(d.payment_conversion, 0) AS conversion,
                       COALESCE(d.ad_spend, 0) AS ad_spend,
                       COALESCE(d.ad_roi, 0) AS roi,
                       CASE WHEN COALESCE(d.payment_amount, 0) > 0
                            THEN COALESCE(d.refund_amount, 0) * 1.0 / d.payment_amount ELSE 0 END AS refund_rate,
                   CASE WHEN COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0) > 0
                        THEN COALESCE(d.ad_spend, 0) * 1.0 / COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0) ELSE NULL END AS expense_ratio,
                       {paid_ipv_expr} AS paid_ipv,
                       {organic_ipv_expr} AS organic_ipv,
                       {search_ipv_expr} AS search_ipv,
                       {recommend_ipv_expr} AS recommend_ipv,
                       COALESCE(d.repurchase_rate, 0) AS repurchase_rate,
                       {buyers_expr} AS buyers,
                       COALESCE(d.avg_order_value, 0) AS avg_order_value
                FROM {table} d
                WHERE {' AND '.join(clauses)}
                ORDER BY d.product_id, d.{date_col} DESC''',
            params,
        ).fetchall()
        if dimension == 'weekly' and not rows:
            daily_clauses = [f'd.product_id IN ({placeholders})', 'd.shop_id = ?']
            daily_params = list(product_ids) + [shop_id]
            if start:
                daily_clauses.append('d.date >= ?')
                daily_params.append(start)
            if end:
                daily_clauses.append('d.date <= ?')
                daily_params.append(end)
            rows = conn.execute(
                f'''SELECT d.product_id,
                           date(d.date, '-' || ((CAST(strftime('%w', d.date) AS INTEGER) + 6) % 7) || ' days') AS period,
                           SUM(COALESCE(d.payment_amount, 0)) AS payment_amount,
                           SUM(COALESCE(d.refund_amount, 0)) AS refund_amount,
                           SUM(COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0)) AS net_sales,
                           SUM(COALESCE(d.ipv, 0)) AS visitors,
                           AVG(COALESCE(d.payment_conversion, 0)) AS conversion,
                           SUM(COALESCE(d.ad_spend, 0)) AS ad_spend,
                           CASE WHEN SUM(COALESCE(d.ad_spend, 0)) > 0
                                THEN SUM(COALESCE(d.payment_amount, 0)) / SUM(COALESCE(d.ad_spend, 0)) ELSE 0 END AS roi,
                           CASE WHEN SUM(COALESCE(d.payment_amount, 0)) > 0
                                THEN SUM(COALESCE(d.refund_amount, 0)) * 1.0 / SUM(COALESCE(d.payment_amount, 0)) ELSE 0 END AS refund_rate,
                           CASE WHEN SUM(COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0)) > 0
                                THEN SUM(COALESCE(d.ad_spend, 0)) * 1.0 / SUM(COALESCE(NULLIF(d.net_sales, 0), d.payment_amount - d.refund_amount, 0)) ELSE NULL END AS expense_ratio,
                           SUM(COALESCE(d.paid_ipv, 0)) AS paid_ipv,
                           SUM(COALESCE(d.organic_ipv, 0)) AS organic_ipv,
                           SUM(COALESCE(d.search_ipv, 0)) AS search_ipv,
                           SUM(COALESCE(d.recommend_ipv, 0)) AS recommend_ipv,
                           AVG(COALESCE(d.repurchase_rate, 0)) AS repurchase_rate,
                           SUM(COALESCE(d.buyers, 0)) AS buyers,
                           CASE WHEN SUM(COALESCE(d.buyers, 0)) > 0
                                THEN SUM(COALESCE(d.payment_amount, 0)) / SUM(COALESCE(d.buyers, 0)) ELSE 0 END AS avg_order_value
                    FROM daily_data d
                    WHERE {' AND '.join(daily_clauses)}
                    GROUP BY d.product_id, period
                    ORDER BY d.product_id, period DESC''',
                daily_params,
            ).fetchall()
    payload_rows = [dict(row) for row in rows]
    by_product = {}
    for row in payload_rows:
        by_product.setdefault(str(row.get('product_id') or ''), []).append(row)
    for product_rows in by_product.values():
        for index, row in enumerate(product_rows):
            previous = product_rows[index + 1].get('payment_amount') if index + 1 < len(product_rows) else None
            current = row.get('payment_amount')
            row['trend_change'] = ((float(current or 0) - float(previous)) / float(previous)) if previous not in (None, 0) else None
        if limit_periods:
            product_rows[:] = product_rows[:limit_periods]
    if limit_periods:
        payload_rows = [row for product_rows in by_product.values() for row in product_rows]
    return success(
        {'rows': payload_rows, 'dimension': dimension,
         'start': payload_rows[-1]['period'] if payload_rows else None,
         'end': payload_rows[0]['period'] if payload_rows else None},
        availability='available' if payload_rows else 'no-data',
        evidence=[{'source': table, 'row_count': len(payload_rows)}],
    )

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

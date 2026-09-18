import os
import calendar
from datetime import datetime, date, timedelta
from services.shop_scope_service import reject_legacy_shop_scope
from services.category_mode_service import category_filters_from_request, shop_label_filter
"""Data Legacy API - 核心数据分析相关接口（旧版）

从 data_api.py 拆分出来的独立模块，包含：
- 数据比较/导出/周期
- 流量结构/多趋势/广告表现
- 异常检测/生命周期/客户分析/漏斗
- 商品目标进度
"""

import io

import openpyxl
from api.data_api import DIMENSION_MAP, _aov_expression, _reject_legacy_shop_scope, _validate_period_arg, get_prev_period, _get_prev_month
from services.category_mode_service import mode_to_label

from flask import Blueprint, current_app, g, jsonify, request, send_file

from db import get_db, get_shop_id, load_config
from api.api_response import failure, json_object, success


data_legacy_bp = Blueprint('data_legacy', __name__)


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


@data_legacy_bp.route('/api/compare', methods=['GET'])
@cached_api('compare_periods', ttl=30)
def compare_periods():
    """周期对比分析"""
    dim = request.args.get('dim', 'monthly')
    period_a = request.args.get('period_a', '')
    period_b = request.args.get('period_b', '')
    unsupported = _reject_legacy_shop_scope(dim)
    if unsupported:
        return unsupported

    if not period_a or not period_b:
        return jsonify({'error': 'period_a and period_b are required'}), 400

    if dim == 'monthly':
        table, date_col = 'monthly_data', 'month'
        visitors_col = 'visitors'
    elif dim == 'daily':
        table, date_col = 'daily_data', 'date'
        visitors_col = 'ipv'
    elif dim == 'weekly':
        table, date_col = 'weekly_data', 'week_start'
        visitors_col = 'ipv'
    else:
        return failure('VALIDATION_ERROR', 'dim must be monthly, weekly, or daily', status=400)

    period_format = '%Y-%m' if dim == 'monthly' else '%Y-%m-%d'
    for period_name, period_value in (('period_a', period_a), ('period_b', period_b)):
        try:
            parsed_period = datetime.strptime(period_value, period_format)
        except (TypeError, ValueError):
            return failure(
                'VALIDATION_ERROR',
                f'{period_name} must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dim, period_name: period_value},
                status=422,
            )
        if parsed_period.strftime(period_format) != period_value:
            return failure(
                'VALIDATION_ERROR',
                f'{period_name} must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dim, period_name: period_value},
                status=422,
            )

    shop_id = get_shop_id()
    scope_sql = 'shop_id = ? AND ' if table == 'daily_data' else ''
    scope_params = (shop_id,) if table == 'daily_data' else ()

    with get_db() as conn:
        _label_clause, _label_params = shop_label_filter(category_filters_from_request())
        _join_sql = f' JOIN products p ON p.product_id = {table}.product_id' if _label_clause else ''
        _kpi_where = (' AND ' + _label_clause) if _label_clause else ''

        def query_kpi(p):
            if not p:
                return None
            row = conn.execute(f'''
                SELECT
                    COUNT(*) as row_count,
                    COALESCE(SUM(payment_amount),0) as gmv,
                    COALESCE(SUM(refund_amount),0) as refund,
                    COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                    COALESCE(SUM({visitors_col}),0) as visitors,
                    {_aov_expression(dim)} as aov,
                    CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                    COALESCE(SUM(ad_spend),0) as ad_spend,
                    CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi,
                    AVG(payment_conversion) as conversion
                FROM {table}{_join_sql} WHERE {scope_sql}{date_col} = ?{_kpi_where}
            ''', (*scope_params, p, *_label_params)).fetchone()
            result = dict(row) if row else None
            if result and not result.pop('row_count', 0):
                return None
            return result

        def query_products(p):
            if not p:
                return []
            payment_qty_col = 'd.payment_qty' if dim == 'monthly' else '0'
            rows = conn.execute(f'''
                SELECT p.product_id, p.title, p.style,
                       COALESCE(d.payment_amount, 0) as payment_amount,
                       COALESCE({payment_qty_col}, 0) as payment_count,
                       COALESCE(d.ad_spend, 0) as ad_spend
                FROM products p
                LEFT JOIN {table} d ON p.product_id = d.product_id
                    AND {scope_sql.replace('shop_id', 'd.shop_id') if table == 'daily_data' else ''}d.{date_col} = ?
                WHERE p.status = 'active'{_kpi_where}
                ORDER BY d.payment_amount DESC
            ''', (*scope_params, p, *_label_params)).fetchall()
            return [dict(r) for r in rows]

        kpi_a = query_kpi(period_a)
        kpi_b = query_kpi(period_b)
        products_a = query_products(period_a)
        products_b = query_products(period_b)

        # KPI对比
        kpi_compare = {}
        if kpi_a and kpi_b:
            for key in ['gmv', 'net_sales', 'visitors', 'aov', 'ad_spend', 'roi', 'conversion']:
                va = kpi_a.get(key, 0) or 0
                vb = kpi_b.get(key, 0) or 0
                change = round((vb - va) / va * 100, 1) if va > 0 else None
                kpi_compare[key] = {
                    'period_a': va,
                    'period_b': vb,
                    'change_pct': change,
                }
            # 退款率特殊处理
            ra = kpi_a.get('refund_rate', 0) or 0
            rb = kpi_b.get('refund_rate', 0) or 0
            kpi_compare['refund_rate'] = {
                'period_a': ra,
                'period_b': rb,
                'change_pct': round((rb - ra) * 100, 1),
            }

        # 商品排名变化
        rank_a = {p['product_id']: i + 1 for i, p in enumerate(products_a) if p.get('payment_amount', 0) > 0}
        rank_b = {p['product_id']: i + 1 for i, p in enumerate(products_b) if p.get('payment_amount', 0) > 0}
        amount_a = {p['product_id']: p.get('payment_amount', 0) for p in products_a}
        amount_b = {p['product_id']: p.get('payment_amount', 0) for p in products_b}
        title_map = {p['product_id']: p.get('title', '') for p in products_a}
        style_map = {p['product_id']: p.get('style', '') for p in products_a}
        # 补充B中独有的商品
        for p in products_b:
            if p['product_id'] not in title_map:
                title_map[p['product_id']] = p.get('title', '')
                style_map[p['product_id']] = p.get('style', '')

        product_changes = []
        all_ids = set(rank_a.keys()) | set(rank_b.keys())
        for pid in all_ids:
            r_a = rank_a.get(pid)
            r_b = rank_b.get(pid)
            if r_a and r_b:
                diff = r_a - r_b  # 正数=排名上升
                if diff > 0:
                    status = 'up'
                elif diff < 0:
                    status = 'down'
                else:
                    status = 'flat'
                product_changes.append({
                    'product_id': pid,
                    'title': title_map.get(pid, ''),
                    'style': style_map.get(pid, ''),
                    'rank_a': r_a,
                    'rank_b': r_b,
                    'rank_diff': diff,
                    'amount_a': amount_a.get(pid, 0),
                    'amount_b': amount_b.get(pid, 0),
                    'status': status,
                })
            elif r_a and not r_b:
                product_changes.append({
                    'product_id': pid,
                    'title': title_map.get(pid, ''),
                    'style': style_map.get(pid, ''),
                    'rank_a': r_a,
                    'rank_b': None,
                    'rank_diff': None,
                    'amount_a': amount_a.get(pid, 0),
                    'amount_b': 0,
                    'status': 'exit',
                })
            else:
                product_changes.append({
                    'product_id': pid,
                    'title': title_map.get(pid, ''),
                    'style': style_map.get(pid, ''),
                    'rank_a': None,
                    'rank_b': r_b,
                    'rank_diff': None,
                    'amount_a': 0,
                    'amount_b': amount_b.get(pid, 0),
                    'status': 'new',
                })

        if not (kpi_a and kpi_b):
            # A missing period is unknown, not a zero-sales period.
            product_changes = []
        else:
            product_changes.sort(key=lambda x: x.get('rank_diff') or 0, reverse=True)

        # 获取两个周期各自的趋势数据
        trend_rows_a = conn.execute(f'''
            SELECT {date_col} as period, SUM(payment_amount) as gmv, SUM(refund_amount) as refund,
                   SUM(payment_amount) - SUM(refund_amount) as net_sales, SUM({visitors_col}) as visitors
            FROM {table}
            WHERE {scope_sql}{date_col} = ?
            GROUP BY product_id ORDER BY product_id
        ''', (*scope_params, period_a)).fetchall()

        trend_rows_b = conn.execute(f'''
            SELECT {date_col} as period, SUM(payment_amount) as gmv, SUM(refund_amount) as refund,
                   SUM(payment_amount) - SUM(refund_amount) as net_sales, SUM({visitors_col}) as visitors
            FROM {table}
            WHERE {scope_sql}{date_col} = ?
            GROUP BY product_id ORDER BY product_id
        ''', (*scope_params, period_b)).fetchall()

        trend_compare = {
            'labels': [period_a, period_b],
            'series_a': [sum(dict(r).get('gmv', 0) for r in trend_rows_a) if trend_rows_a else None],
            'series_b': [sum(dict(r).get('gmv', 0) for r in trend_rows_b) if trend_rows_b else None],
        }

    return jsonify({
        'period_a': period_a,
        'period_b': period_b,
        'availability': 'available' if kpi_a and kpi_b else 'partial' if kpi_a or kpi_b else 'no-data',
        'kpi_compare': kpi_compare,
        'product_changes': product_changes,
        'trend_compare': trend_compare,
    })

# ==================== 数据导出 API ====================

@data_legacy_bp.route('/api/export', methods=['POST'])
def export_data():
    """导出数据为Excel"""
    data = json_object(request)
    export_type = str(data.get('type') or 'products').strip()
    period = str(data.get('period') or '').strip()
    dim = str(data.get('dim') or 'monthly').strip()
    export_shop = str(request.args.get('shop_id') or current_app.config.get('SHOP_ID') or os.environ.get('TMALL_SHOP_ID') or '').strip()
    if dim in {'weekly', 'monthly'} and export_shop and export_shop != 'default':
        return failure(
            'UNSUPPORTED_SCOPE',
            f'{dim} 维度当前不支持 shop_id；请先完成周/月表店铺迁移',
            status=422,
        )
    shop_id = get_shop_id()

    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active

    if export_type == 'products':
        ws.title = '商品数据'
        dim_cfg = DIMENSION_MAP.get(dim)
        if not dim_cfg:
            return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dim}, status=422)
        table, date_col = dim_cfg['table'], dim_cfg['date_col']

        # 筛选参数
        search = data.get('search', '')
        tier = data.get('tier', '')
        style = data.get('style', '')
        status = data.get('status', '')
        lifecycle_stage = data.get('lifecycle_stage', '')
        seasonality = data.get('seasonality', '')
        has_pending_action = data.get('has_pending_action', '')
        product_id = data.get('product_id', '')
        star_only = data.get('star_only', False)
        export_cols = data.get('columns', [])
        start = data.get('start', '')
        end = data.get('end', '')
        sort_by = data.get('sort', 'payment_amount')
        order = data.get('order', 'desc')

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

        where_clauses = []
        params = []
        if search:
            search_safe = search.replace('%', '\\%').replace('_', '\\_')
            where_clauses.append("(p.title LIKE ? ESCAPE '\\' OR p.product_id LIKE ? ESCAPE '\\')")
            params.extend([f'%{search_safe}%', f'%{search_safe}%'])
        if tier:
            where_clauses.append("p.tier = ?")
            params.append(tier)
        if style:
            where_clauses.append("p.style = ?")
            params.append(style)
        if status and status != 'all':
            where_clauses.append("p.status = ?")
            params.append(status)
        if star_only:
            where_clauses.append("p.starred = 1")
        if lifecycle_stage:
            where_clauses.append("COALESCE(lp.manual_stage, lp.recommended_stage, '') = ?")
            params.append(lifecycle_stage)
        if seasonality:
            where_clauses.append("COALESCE(lp.seasonal_attribute, '') = ?")
            params.append(seasonality)
        if has_pending_action in (True, 'true', '1', 1):
            where_clauses.append("EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked'))")
        elif has_pending_action in (False, 'false', '0', 0):
            where_clauses.append("NOT EXISTS (SELECT 1 FROM product_actions pa WHERE pa.product_id = p.product_id AND pa.status IN ('pending_execution','executing','observing','pending_review','blocked'))")
        if product_id:
            where_clauses.append("p.product_id = ?")
            params.append(product_id)
        export_category_mode = data.get('category_mode') or request.args.get('category_mode')
        export_label = mode_to_label(export_category_mode)
        if export_label:
            where_clauses.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
            params.extend([export_label, export_label])
        where_sql = (' AND ' + ' AND '.join(where_clauses)) if where_clauses else ''

        data_relation = table
        join_clause = f'p.product_id = d.product_id AND d.{date_col} = ?'
        join_params = [period]
        if dim == 'daily':
            join_clause = f'p.product_id = d.product_id AND d.shop_id = ? AND d.{date_col} = ?'
            join_params = [shop_id, period]
        if dim == 'daily' and start and end:
            data_relation = '''(
                SELECT current.product_id,
                       current.payment_amount,
                       current.refund_amount,
                       current.net_sales,
                       current.ipv,
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
            join_params = [shop_id, start, end, shop_id, start, end, start, start]

        # 如果指定了导出列，动态构建SELECT
        if export_cols:
            # 安全：只允许已知列名
            safe_cols = []
            base_cols = {
                'product_id': 'p.product_id', 'title': 'p.title', 'tier': 'p.tier',
                'style': 'p.style', 'scene': 'p.scene', 'status': 'p.status',
                'list_date': 'p.list_date', 'manager': 'p.manager', 'remark': 'p.remark',
                'lifecycle_stage': 'COALESCE(lp.manual_stage, lp.recommended_stage)',
                'seasonality': 'lp.seasonal_attribute',
                'has_pending_action': legacy_pending_action_expr,
            }
            visitors_col = dim_cfg['visitors_col']
            _monthly_only = dim == 'monthly'
            data_cols = {
                'payment_amount': 'COALESCE(d.payment_amount,0)', 'refund_amount': 'COALESCE(d.refund_amount,0)',
                'net_sales': 'COALESCE(d.net_sales,0)', 'visitors': f'COALESCE(d.{visitors_col},0)',
                'uv_value': 'COALESCE(d.uv_value,0)' if _monthly_only else '0',
                'search_visitors': 'COALESCE(d.search_visitors,0)' if _monthly_only else '0',
                'search_ratio': 'COALESCE(d.search_ratio,0)' if _monthly_only else '0',
                'search_conversion': 'COALESCE(d.search_conversion,0)' if _monthly_only else '0',
                'paid_ipv': 'COALESCE(d.paid_ipv,0)', 'organic_ipv': 'COALESCE(d.organic_ipv,0)',
                'search_ipv': 'COALESCE(d.search_ipv,0)', 'recommend_ipv': 'COALESCE(d.recommend_ipv,0)',
                'payment_conversion': 'COALESCE(d.payment_conversion,0)',
                'conversion': 'COALESCE(d.payment_conversion,0)',
                'cart_rate': 'COALESCE(d.cart_rate,0)',
                'fav_rate': 'COALESCE(d.fav_rate,0)',
                'bounce_rate': 'COALESCE(d.bounce_rate,0)', 'avg_stay_duration': 'COALESCE(d.avg_stay_duration,0)',
                'ad_spend': 'COALESCE(d.ad_spend,0)', 'ad_roi': 'COALESCE(d.ad_roi,0)',
                'roi': 'COALESCE(d.ad_roi,0)',
                'overall_roi': 'COALESCE(d.overall_roi,0)' if _monthly_only else '0',
                'paid_ratio': 'COALESCE(d.paid_ratio,0)' if _monthly_only else '0',
                'expense_ratio': 'CASE WHEN COALESCE(d.payment_amount,0) > 0 THEN COALESCE(d.ad_spend,0) * 1.0 / d.payment_amount ELSE NULL END',
                'refund_rate': 'COALESCE(d.refund_rate,0)' if _monthly_only else '0',
                'repurchase_rate': 'COALESCE(d.repurchase_rate,0)', 'repurchase_users': 'COALESCE(d.repurchase_users,0)',
                'presale_amount': 'COALESCE(d.presale_amount,0)' if not _monthly_only else '0',
                'presale_qty': 'COALESCE(d.presale_qty,0)' if not _monthly_only else '0',
                'search_click_rate': 'COALESCE(d.search_click_rate,0)' if not _monthly_only else '0',
                'cross_sell_qty': 'COALESCE(d.cross_sell_qty,0)', 'cross_sell_rate': 'COALESCE(d.cross_sell_rate,0)',
                'category_width': 'COALESCE(d.category_width,0)' if not _monthly_only else '0',
                'buyers': f"COALESCE(d.buyers,0)" if dim != 'weekly' else '0',
                'avg_order_value': 'COALESCE(d.avg_order_value,0)',
                'payment_qty': f"COALESCE(d.payment_qty,0)" if dim == 'monthly' else '0',
                'payment_count': f"COALESCE(d.payment_qty,0)" if dim == 'monthly' else '0',
                'cart_qty': f"COALESCE(d.cart_qty,0)" if _monthly_only else '0',
                'fav_users': f"COALESCE(d.fav_users,0)" if _monthly_only else '0',
                'score': f"COALESCE(d.score,0)" if _monthly_only else '0',
                'keyword_spend': 'COALESCE(d.keyword_spend,0)' if _monthly_only else '0',
                'keyword_roi': 'COALESCE(d.keyword_roi,0)' if _monthly_only else '0',
                'crowd_spend': 'COALESCE(d.crowd_spend,0)' if _monthly_only else '0',
                'crowd_roi': 'COALESCE(d.crowd_roi,0)' if _monthly_only else '0',
                'impressions': 'COALESCE(pd_latest.impressions,0)',
                'ctr': 'COALESCE(pd_latest.ctr,0)',
                'trend_change': 'd.trend_change' if dim == 'daily' and start and end else 'NULL',
            }
            col_labels = {
                'product_id': '商品ID', 'title': '商品名称', 'tier': '分层', 'style': '风格',
                'scene': '场景', 'status': '状态', 'list_date': '上架时间',
                'manager': '负责人', 'remark': '备注', 'lifecycle_stage': '生命周期阶段',
                'seasonality': '季节属性', 'has_pending_action': '待办动作',
                'payment_amount': '销售额', 'refund_amount': '退款金额', 'net_sales': '净销售额',
                'visitors': '访客数', 'uv_value': '客单价值', 'search_visitors': '搜索访客',
                'search_ratio': '搜索占比', 'payment_conversion': '转化率', 'bounce_rate': '跳出率',
                'conversion': '转化率',
                'avg_stay_duration': '停留时长', 'ad_spend': '推广花费', 'ad_roi': 'ROI',
                'roi': 'ROI',
                'overall_roi': '综合ROI', 'refund_rate': '退款率', 'buyers': '买家数',
                'avg_order_value': '客单价', 'payment_qty': '支付件数', 'payment_count': '支付件数', 'cart_qty': '加购件数',
                'fav_users': '收藏人数', 'score': '综合评分',
                'trend_change': '销售趋势变化',
            }
            col_labels.update({
                'paid_ipv': '\u4ed8\u8d39 IPV', 'organic_ipv': '\u81ea\u7136 IPV',
                'search_ipv': '\u641c\u7d22 IPV', 'recommend_ipv': '\u63a8\u8350 IPV',
                'repurchase_rate': '\u590d\u8d2d\u7387', 'repurchase_users': '\u590d\u8d2d\u7528\u6237\u6570',
                'presale_amount': '\u9884\u552e\u652f\u4ed8\u91d1\u989d', 'presale_qty': '\u9884\u552e\u9500\u91cf',
                'search_click_rate': '\u514d\u8d39\u641c\u7d22\u70b9\u51fb\u7387',
                'cross_sell_qty': '\u8fde\u5e26\u8d2d\u4e70\u91cf', 'cross_sell_rate': '\u8fde\u5e26\u8d2d\u4e70\u7387',
                'category_width': '\u8fde\u5e26\u8d2d\u4e70\u53f6\u5b50\u7c7b\u76ee\u5bbd\u5ea6',
            })
            for c in export_cols:
                if c in base_cols:
                    safe_cols.append(f"{base_cols[c]} as {c}")
                elif c in data_cols:
                    safe_cols.append(f"{data_cols[c]} as {c}")
            if not safe_cols:
                safe_cols = ['p.product_id', 'p.title', 'p.tier', 'p.style']
            select_clause = ', '.join(safe_cols)
            headers = [col_labels.get(c, c) for c in export_cols if c in base_cols or c in data_cols]
            if not headers:
                headers = ['商品ID', '商品名称', '分层', '风格']
        else:
            payment_qty_col = 'd.payment_qty' if dim == 'monthly' else '0'
            select_clause = f"""p.product_id, p.title, p.tier, p.style, p.scene, p.status,
                       COALESCE(d.payment_amount, 0) as payment_amount,
                       COALESCE(d.refund_amount, 0) as refund_amount,
                       COALESCE({payment_qty_col}, 0) as payment_count,
                       CASE WHEN COALESCE(d.payment_amount, 0) > 0 THEN COALESCE(d.refund_amount, 0) * 1.0 / d.payment_amount ELSE 0 END as refund_rate,
                       COALESCE(d.ad_spend, 0) as ad_spend,
                       COALESCE(d.ad_roi, 0) as roi"""
            headers = ['商品ID', '商品名称', '分层', '风格', '场景', '状态',
                       '销售额', '退款金额', '支付件数', '退款率', '推广花费', 'ROI']

        with get_db() as conn:
            sort_whitelist = {
                'product_id', 'title', 'tier', 'style', 'scene', 'status',
                'payment_amount', 'refund_amount', 'payment_count', 'refund_rate',
                'ad_spend', 'roi',
            }
            if export_cols:
                sort_whitelist.update(base_cols.keys())
                sort_whitelist.update(data_cols.keys())
            sort_col = sort_by if sort_by in sort_whitelist else 'payment_amount'
            order_sql = 'DESC' if order == 'desc' else 'ASC'
            sort_expression = 'p.product_id' if sort_col == 'product_id' else sort_col
            rows = conn.execute(f'''
            SELECT {select_clause}
                FROM products p
                {legacy_lifecycle_join}
                LEFT JOIN {data_relation} d ON {join_clause}
                {legacy_paid_join}
                WHERE 1=1{where_sql}
                ORDER BY {sort_expression} {order_sql}
            ''', join_params + params).fetchall()
        ws.append(headers)
        for r in rows:
            ws.append(list(r))

    elif export_type == 'refund':
        ws.title = '退款数据'
        with get_db() as conn:
            if dim == 'monthly':
                table, date_col = 'monthly_data', 'month'
                refund_rate_expr = 'd.refund_rate'
            else:
                table, date_col = 'weekly_data', 'week_start'
                refund_rate_expr = 'CASE WHEN d.payment_amount > 0 THEN d.refund_amount * 1.0 / d.payment_amount ELSE 0 END'

            rows = conn.execute(f'''
                SELECT p.product_id, p.title, p.style,
                       d.payment_amount, d.refund_amount, {refund_rate_expr} as refund_rate
                FROM products p
                JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
                WHERE p.status = 'active' AND d.refund_amount > 0
                ORDER BY d.refund_amount DESC
            ''', (period,)).fetchall()

        headers = ['商品ID', '商品名称', '风格', '销售额', '退款金额', '退款率']
        ws.append(headers)
        for r in rows:
            ws.append(list(r))

    elif export_type == 'reviews':
        ws.title = '评价数据'
        with get_db() as conn:
            rows = conn.execute('''
                SELECT r.product_id, p.title, r.rating, r.sentiment, r.content, r.is_effective, r.has_image, r.imported_at
                FROM reviews r
                LEFT JOIN products p ON r.product_id = p.product_id
                ORDER BY r.imported_at DESC
            ''').fetchall()

        headers = ['商品ID', '商品名称', '评分', '情感', '评价内容', '有效评价', '带图', '导入时间']
        ws.append(headers)
        for r in rows:
            ws.append(list(r))

    wb.save(output)
    output.seek(0)

    filename = f'{export_type}_{period or "all"}.xlsx'
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=filename)

def calc_score(row):
    """计算商品综合评分（0-100分）"""
    score = 50  # 基础分
    # 转化率加分（越高越好，上限+20）
    conv = row.get('conversion') or 0
    score += min(conv * 5, 20)
    # ROI加分（越高越好，上限+15）
    roi = row.get('overall_roi') or 0
    score += min(roi * 1.5, 15)
    # 退款率扣分（越低越好，上限-20）
    refund = row.get('refund_rate') or 0
    score -= min(refund * 1.5, 20)
    # UV价值加分（越高越好，上限+10）
    uv = row.get('uv_value') or 0
    score += min(uv * 0.5, 10)
    # 搜索占比加分（上限+5）
    search = row.get('search_ratio') or 0
    score += min(search * 5, 5)
    return round(max(0, min(100, score)), 1)

#

@data_legacy_bp.route('/api/periods', methods=['GET'])
@cached_api('get_periods', ttl=60)
def get_periods():
    """获取可选的时间周期列表"""
    dimension = request.args.get('dim', 'weekly')
    unsupported = _reject_legacy_shop_scope(dimension)
    if unsupported:
        return unsupported
    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dimension}, status=422)
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    with get_db() as conn:
        if dimension == 'daily':
            rows = [dict(r) for r in conn.execute(
                f'SELECT DISTINCT {date_col} as period FROM {table} WHERE shop_id = ? ORDER BY {date_col} DESC LIMIT 90',
                (get_shop_id(),)).fetchall()]
        else:
            rows = [dict(r) for r in conn.execute(
                f'SELECT DISTINCT {date_col} as period FROM {table} ORDER BY {date_col} DESC').fetchall()]

    return jsonify(rows)

# 预留接口：数据备份（前端暂未调用）
#

@data_legacy_bp.route('/api/traffic_structure', methods=['GET'])
@cached_api('traffic', 60)
def get_traffic_structure():
    """流量结构分析"""
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
                return jsonify({
                    'structure': {},
                    'trend': [],
                    'period': None,
                    'dim': dim,
                    'availability': 'no-data',
                })

        # Current period traffic breakdown
        if dim == 'monthly':
            traffic_cols = 'SUM(search_ipv) as search, SUM(recommend_ipv) as recommend, SUM(paid_ipv) as paid, SUM(organic_ipv) as organic, SUM(visitors) as total'
        else:
            traffic_cols = 'SUM(search_ipv) as search, SUM(recommend_ipv) as recommend, SUM(paid_ipv) as paid, SUM(organic_ipv) as organic, SUM(ipv) as total'
        
        current = conn.execute(
            f'SELECT COUNT(*) AS row_count, {traffic_cols} FROM {table} WHERE {date_col} = ?',
            (period,),
        ).fetchone()
        current = dict(current) if current else {}
        current_has_rows = bool(current.pop('row_count', 0))
        
        total = current.get('total') or 0
        if total > 0:
            structure = {
                'search': round((current.get('search') or 0) / total * 100, 1),
                'recommend': round((current.get('recommend') or 0) / total * 100, 1),
                'paid': round((current.get('paid') or 0) / total * 100, 1),
                'organic': round((current.get('organic') or 0) / total * 100, 1),
                'free': round(((current.get('search') or 0) + (current.get('recommend') or 0)) / total * 100, 1),
            }
            structure['search_val'] = current.get('search') or 0
            structure['recommend_val'] = current.get('recommend') or 0
            structure['paid_val'] = current.get('paid') or 0
            structure['organic_val'] = current.get('organic') or 0
            structure['total_val'] = total
        else:
            structure = {}
        
        # Trend (last 6 periods)
        trend = []
        if not current_has_rows:
            rows = []
        elif dim == 'monthly':
            rows = conn.execute(f'''
                SELECT {date_col} as period,
                       SUM(search_ipv) as search, SUM(recommend_ipv) as recommend,
                       SUM(paid_ipv) as paid, SUM(organic_ipv) as organic, SUM(visitors) as total
                FROM {table}
                WHERE {date_col} <= ?
                GROUP BY {date_col} ORDER BY {date_col} DESC LIMIT 6
            ''', (period,)).fetchall()
        elif dim == 'weekly':
            try:
                base = datetime.strptime(period, '%Y-%m-%d')
                periods = [(base - timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(6)]
                placeholders = ','.join(['?' for _ in periods])
                rows = conn.execute(f'''
                    SELECT {date_col} as period,
                           SUM(search_ipv) as search, SUM(recommend_ipv) as recommend,
                           SUM(paid_ipv) as paid, SUM(organic_ipv) as organic, SUM(ipv) as total
                    FROM {table} WHERE {date_col} IN ({placeholders})
                    GROUP BY {date_col} ORDER BY {date_col} DESC
                ''', periods).fetchall()
            except ValueError:
                rows = []
        else:
            rows = []
        
        for r in rows:
            r = dict(r)
            t = r.get('total') or 0
            if t > 0:
                r['search_pct'] = round((r.get('search') or 0) / t * 100, 1)
                r['recommend_pct'] = round((r.get('recommend') or 0) / t * 100, 1)
                r['paid_pct'] = round((r.get('paid') or 0) / t * 100, 1)
                r['organic_pct'] = round((r.get('organic') or 0) / t * 100, 1)
            trend.append(r)
        trend.reverse()
    
    return jsonify({
        'structure': structure,
        'trend': trend,
        'period': period,
        'dim': dim,
        'availability': 'available' if current_has_rows else 'no-data',
    })

# ==================== 任务看板 API ====================

def _legacy_task_payload(row):
    item = dict(row)
    if item.get('status') == 'in_progress':
        item['status'] = 'doing'
    return item


#

@data_legacy_bp.route('/api/multi_trend', methods=['GET'])
@cached_api('get_multi_trend', ttl=30)
def get_multi_trend():
    """多周期趋势叠加数据"""
    dim = request.args.get('dim', 'monthly')
    periods_str = request.args.get('periods', '')
    metric = request.args.get('metric', 'payment_amount')
    shop_id = get_shop_id()

    if not periods_str:
        return failure('VALIDATION_ERROR', '请选择至少一个周期', status=422)

    periods = [p.strip() for p in periods_str.split(',') if p.strip()]
    if not periods:
        return failure('VALIDATION_ERROR', '请选择至少一个周期', status=422)

    period_format = {'monthly': '%Y-%m', 'weekly': '%Y-%m-%d', 'daily': '%Y-%m-%d'}.get(dim)
    if not period_format:
        return failure('VALIDATION_ERROR', 'dim must be monthly, weekly, or daily', {'dim': dim}, status=422)
    for period in periods:
        try:
            parsed_period = datetime.strptime(period, period_format)
        except (TypeError, ValueError):
            return failure(
                'VALIDATION_ERROR',
                f'periods must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dim, 'period': period},
                status=422,
            )
        if parsed_period.strftime(period_format) != period:
            return failure(
                'VALIDATION_ERROR',
                f'periods must use {period_format.replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")}',
                {'dim': dim, 'period': period},
                status=422,
            )

    # 指标白名单
    metric_whitelist = {
        'payment_amount': 'payment_amount',
        'visitors': 'visitors',
        'conversion': 'payment_conversion',
        'refund_rate': None,  # 需要计算
    }
    if metric not in metric_whitelist:
        return failure(
            'VALIDATION_ERROR',
            '不支持的指标',
            {'metric': metric, 'accepted': sorted(metric_whitelist)},
            status=422,
        )

    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return failure(
            'VALIDATION_ERROR',
            '不支持的维度',
            {'dim': dim, 'accepted': sorted(DIMENSION_MAP)},
            status=422,
        )

    result = {'periods': []}

    with get_db() as conn:
        for period in periods:
            if dim == 'monthly':
                # 月度维度：查询该月每日数据，按周聚合
                year, month = period.split('-')
                month_start = f"{period}-01"
                # 计算月末
                last_day = calendar.monthrange(int(year), int(month))[1]
                month_end = f"{period}-{last_day:02d}"

                rows = conn.execute('''
                    SELECT date, SUM(payment_amount) as payment_amount,
                           SUM(ipv) as visitors,
                           AVG(payment_conversion) as payment_conversion,
                           CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate
                    FROM daily_data
                     WHERE shop_id = ? AND date >= ? AND date <= ?
                    GROUP BY date ORDER BY date
                ''', (shop_id, month_start, month_end)).fetchall()

                # 按周聚合
                weekly_data = {}
                for row in rows:
                    d = datetime.strptime(row['date'], '%Y-%m-%d')
                    # 计算周偏移（该月第几周）
                    week_num = (d.day - 1) // 7 + 1
                    week_key = f"W{week_num}"
                    if week_key not in weekly_data:
                        weekly_data[week_key] = {'date': week_key, 'payment_amount': 0, 'visitors': 0, 'conversion': [], 'refund_rate': []}
                    weekly_data[week_key]['payment_amount'] += row['payment_amount'] or 0
                    weekly_data[week_key]['visitors'] += row['visitors'] or 0
                    if row['payment_conversion'] is not None:
                        weekly_data[week_key]['conversion'].append(row['payment_conversion'])
                    if row['refund_rate'] is not None:
                        weekly_data[week_key]['refund_rate'].append(row['refund_rate'])

                data = []
                for wk in sorted(weekly_data.keys()):
                    wd = weekly_data[wk]
                    if metric == 'conversion':
                        val = sum(wd['conversion']) / len(wd['conversion']) if wd['conversion'] else 0
                    elif metric == 'refund_rate':
                        val = sum(wd['refund_rate']) / len(wd['refund_rate']) if wd['refund_rate'] else 0
                    else:
                        val = wd[metric] or 0
                    data.append({'date': wd['date'], 'value': round(val, 4)})

            elif dim == 'weekly':
                # 周度维度：查询该周每日数据
                try:
                    week_start = period
                    week_end_dt = datetime.strptime(period, '%Y-%m-%d') + timedelta(days=6)
                    week_end = week_end_dt.strftime('%Y-%m-%d')
                except ValueError:
                    data = []
                else:
                    rows = conn.execute('''
                        SELECT date, SUM(payment_amount) as payment_amount,
                               SUM(ipv) as visitors,
                               AVG(payment_conversion) as payment_conversion,
                               CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate
                        FROM daily_data
                         WHERE shop_id = ? AND date >= ? AND date <= ?
                        GROUP BY date ORDER BY date
                    ''', (shop_id, week_start, week_end)).fetchall()

                    data = []
                    for row in rows:
                        val = row[metric] if metric != 'refund_rate' else row['refund_rate']
                        data.append({'date': row['date'], 'value': round(val or 0, 4)})

            else:
                # 日度维度：直接查询当天数据
                rows = conn.execute('''
                    SELECT date, SUM(payment_amount) as payment_amount,
                           SUM(ipv) as visitors,
                           AVG(payment_conversion) as payment_conversion,
                           CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate
                    FROM daily_data
                     WHERE shop_id = ? AND date = ?
                    GROUP BY date
                ''', (shop_id, period)).fetchall()
                data = []
                for row in rows:
                    val = row[metric] if metric != 'refund_rate' else row['refund_rate']
                    data.append({'date': row['date'], 'value': round(val or 0, 4)})

            result['periods'].append({'period': period, 'data': data})

    return jsonify(result)


# ==================== Feature 7: 数据异常事件标注 ====================
#

@data_legacy_bp.route('/api/ad_performance', methods=['GET'])
@cached_api('get_ad_performance', ttl=30)
def get_ad_performance():
    """推广效果数据"""
    dimension = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dimension}, status=422)
    invalid = _validate_period_arg(dimension, period)
    if invalid:
        return invalid
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']

    with get_db() as conn:
        if dimension == 'monthly':
            ad_select = '''d.ad_spend, d.ad_roi, d.overall_roi, d.paid_ratio,
                   d.keyword_spend, d.keyword_roi, d.keyword_ppc,
                   d.crowd_spend, d.crowd_roi, d.crowd_ppc,
                   d.site_spend, d.site_roi, d.site_ppc,
                   d.payment_amount, d.refund_paid_ratio'''
        else:
            ad_select = '''d.ad_spend, d.ad_roi,
                   0 as overall_roi, 0 as paid_ratio,
                   0 as keyword_spend, 0 as keyword_roi, 0 as keyword_ppc,
                   0 as crowd_spend, 0 as crowd_roi, 0 as crowd_ppc,
                   0 as site_spend, 0 as site_roi, 0 as site_ppc,
                   d.payment_amount, 0 as refund_paid_ratio'''
        rows = [dict(r) for r in conn.execute(f'''
            SELECT p.product_id, p.title,
                   {ad_select}
            FROM products p
            JOIN {table} d ON p.product_id = d.product_id AND d.{date_col} = ?
            WHERE p.status = 'active' AND d.ad_spend > 0
            ORDER BY d.ad_spend DESC
        ''', (period,)).fetchall()]
    return jsonify(rows)

#

@data_legacy_bp.route('/api/anomalies', methods=['GET'])
@cached_api('get_anomalies', ttl=60)
def get_anomalies():
    """获取当前周期的异常指标"""
    dimension = request.args.get('dim', 'weekly')
    period = request.args.get('period', '')
    prev_period = request.args.get('prev_period', '')

    dim_cfg = DIMENSION_MAP.get(dimension)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dimension}, status=422)
    for field, value in (('period', period), ('prev_period', prev_period)):
        invalid = _validate_period_arg(dimension, value, field)
        if invalid:
            return invalid
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    with get_db() as conn:
        _label_clause, _label_params = shop_label_filter(category_filters_from_request())
        _join_sql = f' JOIN products p ON p.product_id = {table}.product_id' if _label_clause else ''
        _kpi_where = (' AND ' + _label_clause) if _label_clause else ''

        def query_period(p):
            if not p:
                return None
            row = conn.execute(f'''
                SELECT
                    COUNT(*) as row_count,
                    COALESCE(SUM(payment_amount),0) as gmv,
                    COALESCE(SUM(refund_amount),0) as refund,
                    COALESCE(SUM(payment_amount),0) - COALESCE(SUM(refund_amount),0) as net_sales,
                    COALESCE(SUM({visitors_col}),0) as visitors,
                    {_aov_expression(dimension)} as aov,
                    CASE WHEN SUM(payment_amount) > 0 THEN SUM(refund_amount) * 1.0 / SUM(payment_amount) ELSE 0 END as refund_rate,
                    COALESCE(SUM(ad_spend),0) as ad_spend,
                    CASE WHEN SUM(ad_spend) > 0 THEN SUM(payment_amount) * 1.0 / SUM(ad_spend) ELSE 0 END as roi
                FROM {table}{_join_sql} WHERE {date_col} = ?{_kpi_where}
            ''', (p, *_label_params)).fetchone()
            result = dict(row) if row else None
            if result and not result.pop('row_count', 0):
                return None
            return result

        current = query_period(period)
        previous = query_period(prev_period)

        anomalies = []
        config = load_config()
        anomaly_decline = config.get('thresholds', {}).get('anomaly_decline', 0.20)

        if current and previous:
            metric_labels = {
                'gmv': '支付金额',
                'net_sales': '净销售额',
                'visitors': '访客数',
                'aov': '客单价'
            }
            for key, label in metric_labels.items():
                prev_val = previous.get(key) or 0
                curr_val = current.get(key) or 0
                if prev_val > 0:
                    change = round((curr_val - prev_val) / prev_val * 100, 1)
                    if change < 0 and abs(change) > anomaly_decline * 100:
                        anomalies.append({
                            'metric': key,
                            'label': label,
                            'change': change,
                            'current': curr_val,
                            'previous': prev_val,
                            'direction': 'decline',
                            'severity': 'high' if abs(change) > anomaly_decline * 200 else 'warning'
                        })

    availability = 'no-data' if current is None else ('partial' if previous is None else 'available')
    return jsonify({
        'period': period,
        'prev_period': prev_period,
        'anomaly_threshold': anomaly_decline,
        'availability': availability,
        'anomalies': anomalies,
        'has_anomalies': len(anomalies) > 0
    })

# ==================== 目标管理 API ====================

def _get_prev_month(period):
    """获取上一个自然月"""
    try:
        parts = period.split('-')
        year, month = int(parts[0]), int(parts[1])
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        return f"{year}-{month:02d}"
    except (ValueError, IndexError, TypeError):
        return None

def generate_alerts(conn, period):
    """生成预警"""

    # 获取目标
    target = conn.execute('SELECT * FROM shop_targets WHERE period = ?', (period,)).fetchone()
    if not target:
        return

    target = dict(target)
    actual = conn.execute('''
        SELECT COUNT(*) as row_count,
               SUM(payment_amount) as gsv,
               SUM(ad_spend) as ad_spend,
               AVG(payment_conversion) as conversion
        FROM monthly_data WHERE month = ?
    ''', (period,)).fetchone()
    actual = dict(actual) if actual else {}
    if not actual.get('row_count'):
        return
    actual.pop('row_count', None)

    gsv_actual = actual.get('gsv', 0) or 0
    ad_actual = actual.get('ad_spend', 0) or 0
    gsv_target = target.get('target_gsv', 0) or 0
    ad_target = target.get('target_ad_spend', 0) or 0
    target_ad_ratio = target.get('target_ad_ratio', 0) or 0

    today = datetime.now()
    try:
        month_end = datetime.strptime(period + '-01', '%Y-%m-%d')
        _, days_in_month = calendar.monthrange(month_end.year, month_end.month)
        if today.year == month_end.year and today.month == month_end.month:
            time_progress = today.day / days_in_month
        else:
            time_progress = 1.0
    except (ValueError, IndexError, TypeError):
        time_progress = 1.0

    # 预警1：进度落后
    if gsv_target > 0 and time_progress > 0 and time_progress < 1:
        gsv_progress = gsv_actual / gsv_target
        if gsv_progress < time_progress * 0.7:
            severity = 'critical' if gsv_progress < time_progress * 0.5 else 'high'
            conn.execute('''
                INSERT INTO alerts (alert_date, alert_type, severity, title, detail, metric_name, current_value, target_value, period)
                VALUES (date('now'), 'progress_behind', ?, ?, ?, ?, ?, ?, ?)
            ''', (severity, 'GSV进度严重落后',
                  f'当前完成{gsv_progress*100:.1f}%，时间进度{time_progress*100:.1f}%，缺口¥{(gsv_target-gsv_actual)/10000:.1f}万',
                  'gsv', gsv_actual, gsv_target, period))

    # 预警2：费比超标
    if gsv_actual > 0 and target_ad_ratio > 0:
        actual_ad_ratio = ad_actual / gsv_actual
        if actual_ad_ratio > target_ad_ratio * 1.3:
            severity = 'critical' if actual_ad_ratio > target_ad_ratio * 1.5 else 'high'
            conn.execute('''
                INSERT INTO alerts (alert_date, alert_type, severity, title, detail, metric_name, current_value, target_value, period)
                VALUES (date('now'), 'ad_ratio_exceed', ?, ?, ?, ?, ?, ?, ?)
            ''', (severity, '费比超标',
                  f'实际费比{actual_ad_ratio*100:.1f}%，目标{target_ad_ratio*100:.1f}%，超{(actual_ad_ratio-target_ad_ratio)*100:.1f}个百分点',
                  'ad_ratio', actual_ad_ratio, target_ad_ratio, period))

    # 预警3：智能预测不达标
    if gsv_target > 0 and time_progress > 0.1 and time_progress < 0.9:
        forecast = gsv_actual / time_progress
        if forecast < gsv_target * 0.9:
            severity = 'high' if forecast < gsv_target * 0.7 else 'warning'
            conn.execute('''
                INSERT INTO alerts (alert_date, alert_type, severity, title, detail, metric_name, current_value, target_value, period)
                VALUES (date('now'), 'forecast_miss', ?, ?, ?, ?, ?, ?, ?)
            ''', (severity, '月底GSV可能不达标',
                  f'预测月底GSV ¥{forecast/10000:.1f}万，目标 ¥{gsv_target/10000:.1f}万，缺口 ¥{(gsv_target-forecast)/10000:.1f}万',
                  'gsv_forecast', forecast, gsv_target, period))

    # 预警4：同比异常
    prev_period = _get_prev_month(period)
    if prev_period:
        prev = conn.execute('SELECT SUM(payment_amount) as gsv FROM monthly_data WHERE month = ?', (prev_period,)).fetchone()
        prev = dict(prev) if prev else {}
        prev_gsv = prev.get('gsv', 0) or 0
        if prev_gsv > 0:
            yoy = (gsv_actual - prev_gsv) / prev_gsv
            if yoy < -0.3:
                severity = 'critical' if yoy < -0.5 else 'high'
                conn.execute('''
                    INSERT INTO alerts (alert_date, alert_type, severity, title, detail, metric_name, current_value, target_value, period)
                    VALUES (date('now'), 'yoy_anomaly', ?, ?, ?, ?, ?, ?, ?)
                ''', (severity, '同比大幅下降',
                      f'GSV同比{yoy*100:.1f}%，上月 ¥{prev_gsv/10000:.1f}万，本月 ¥{gsv_actual/10000:.1f}万',
                      'gsv_yoy', gsv_actual, prev_gsv, period))

    conn.commit()

#

@data_legacy_bp.route('/api/lifecycle', methods=['GET'])
@cached_api('get_lifecycle', ttl=30)
def get_lifecycle():
    """Get product lifecycle data - monthly GSV for each product"""
    if (denied := reject_legacy_shop_scope('生命周期')):
        return denied
    product_id = request.args.get('product_id', '')
    limit = request.args.get('limit', 500, type=int)
    limit = max(1, min(limit or 500, 2000))

    with get_db() as conn:
        if product_id:
            # Single product lifecycle
            rows = conn.execute('''
                SELECT p.product_id, p.title, p.image_url, p.tier, p.style,
                       d.month, d.payment_amount as gsv, d.payment_qty, d.refund_amount,
                       d.visitors, d.ad_spend, d.ad_roi, d.payment_conversion,
                       d.cart_rate, d.fav_rate, d.bounce_rate, d.avg_stay_duration,
                       d.uv_value, d.search_visitors, d.search_ratio, d.net_sales,
                       d.buyers, d.avg_order_value, d.repurchase_rate, d.cross_sell_rate
                FROM products p
                JOIN monthly_data d ON p.product_id = d.product_id
                WHERE p.product_id = ?
                ORDER BY d.month
            ''', (product_id,)).fetchall()
        else:
            # Top products lifecycle summary
            _label_clause, _label_params = shop_label_filter(category_filters_from_request())
            _lifecycle_where = (' WHERE ' + _label_clause) if _label_clause else ''
            rows = conn.execute('''
                SELECT p.product_id, p.title, p.image_url, p.tier, p.style,
                       GROUP_CONCAT(d.month || ':' || COALESCE(d.payment_amount,0)) as gsv_series,
                       SUM(d.payment_amount) as total_gsv,
                       COUNT(DISTINCT d.month) as active_months,
                       MIN(d.month) as first_month,
                       MAX(d.month) as last_month
                FROM products p
                JOIN monthly_data d ON p.product_id = d.product_id
                ''' + _lifecycle_where + '''
                GROUP BY p.product_id
                ORDER BY total_gsv DESC
                LIMIT ?
            ''', (*_label_params, limit)).fetchall()

    return jsonify([dict(r) for r in rows])

# ==================== 商品健康度 API ====================

#

@data_legacy_bp.route('/api/customer_analysis', methods=['GET'])
@cached_api('get_customer_analysis', ttl=60)
def get_customer_analysis():
    """新老客分析：新客数、老客数、占比及趋势"""
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

    # Customer mix is a store-level distinct-buyer metric. Product tables
    # cannot be summed here because one buyer may purchase multiple products.
    shop_id = get_shop_id()

    def period_bounds(period_value):
        try:
            if dim == 'monthly':
                start = datetime.strptime(period_value, '%Y-%m')
                end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            elif dim == 'weekly':
                start = datetime.strptime(period_value, '%Y-%m-%d')
                end = start + timedelta(days=7)
            else:
                start = datetime.strptime(period_value, '%Y-%m-%d')
                end = start + timedelta(days=1)
            return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
        except (TypeError, ValueError):
            return None, None

    def period_key(date_value):
        if dim == 'monthly':
            return date_value[:7]
        if dim == 'daily':
            return date_value
        try:
            current_date = datetime.strptime(date_value, '%Y-%m-%d')
            return (current_date - timedelta(days=current_date.weekday())).strftime('%Y-%m-%d')
        except (TypeError, ValueError):
            return None

    def query_customer(period_value, conn):
        start, end = period_bounds(period_value)
        if not start:
            return None
        row = conn.execute(
            '''SELECT COUNT(*) AS row_count,
                      COUNT(product_visitors) AS visitor_count,
                      COUNT(payment_buyers) AS buyer_count,
                      COUNT(returning_payment_buyers) AS returning_count,
                      COALESCE(SUM(product_visitors), 0) AS visitors,
                      COALESCE(SUM(payment_buyers), 0) AS buyers,
                      COALESCE(SUM(returning_payment_buyers), 0) AS returning_buyers
               FROM store_daily_facts
               WHERE shop_id = ? AND date >= ? AND date < ?''',
            (shop_id, start, end),
        ).fetchone()
        if not row or not row['row_count']:
            return None
        result = dict(row)
        result['visitors'] = result['visitors'] or 0
        result['buyers'] = result['buyers'] or 0
        result['returning_buyers'] = result['returning_buyers'] or 0
        result['visitors_available'] = result['visitor_count'] == result['row_count']
        result['split_available'] = (
            result['buyer_count'] == result['row_count']
            and result['returning_count'] == result['row_count']
        )
        if result['split_available']:
            result['returning_buyers'] = min(result['returning_buyers'], result['buyers'])
            result['new_buyers'] = result['buyers'] - result['returning_buyers']
        else:
            result['new_buyers'] = None
            result['returning_buyers'] = None
        return result

    def ratios(result):
        if not result or not result.get('split_available') or result['buyers'] <= 0:
            return None, None
        return result['new_buyers'] / result['buyers'], result['returning_buyers'] / result['buyers']

    with get_db() as conn:
        current = query_customer(period, conn)
        current_new_ratio, current_returning_ratio = ratios(current)
        previous = query_customer(get_prev_period(period, dim), conn)
        prev_new_ratio, prev_returning_ratio = ratios(previous)

        periods = set()
        end_period = period_bounds(period)[1]
        if end_period:
            rows = conn.execute(
                'SELECT DISTINCT date FROM store_daily_facts WHERE shop_id = ? AND date < ?',
                (shop_id, end_period),
            ).fetchall()
            periods = {period_key(row['date']) for row in rows if period_key(row['date'])}
        trend = []
        for trend_period in sorted(periods, reverse=True)[:6][::-1]:
            item = query_customer(trend_period, conn)
            trend.append({
                'period': trend_period,
                'new_buyers': item['new_buyers'] if item and item['split_available'] else None,
                'returning_buyers': item['returning_buyers'] if item and item['split_available'] else None,
            })

    missing_fields = []
    limitations = []
    availability = 'available'
    if current is None:
        availability = 'no-data'
        limitations.append('当前周期没有店铺级新老客事实')
        legacy_start, legacy_end = period_bounds(period)
        with get_db() as conn:
            if dim == 'monthly':
                legacy_exists = conn.execute(
                    f'SELECT 1 FROM {table} WHERE {date_col} = ? LIMIT 1',
                    (period,),
                ).fetchone()
            else:
                legacy_exists = conn.execute(
                    f'SELECT 1 FROM {table} WHERE {date_col} >= ? AND {date_col} < ? LIMIT 1',
                    (legacy_start, legacy_end),
                ).fetchone() if legacy_start else None
        if legacy_exists:
            availability = 'missing-fields'
            missing_fields = ['store_daily_facts.product_visitors', 'store_daily_facts.payment_buyers', 'store_daily_facts.returning_payment_buyers']
            limitations.append('已有商品或周月汇总数据不能替代店铺级去重买家事实')
    elif not current.get('split_available'):
        availability = 'missing-fields'
        missing_fields = ['store_daily_facts.product_visitors', 'store_daily_facts.payment_buyers', 'store_daily_facts.returning_payment_buyers']
        limitations.append('店铺级事实缺少完整客户字段，无法计算新老客构成')
    else:
        if not current.get('visitors_available'):
            availability = 'partial'
            missing_fields.append('store_daily_facts.product_visitors')
            limitations.append('店铺级事实缺少访客字段，访客数不可计算')
        if dim in {'monthly', 'weekly'}:
            availability = 'partial'
            limitations.append('当前仅按日事实汇总，未提供用户 ID，月/周买家数不保证跨日去重')

    return jsonify({
        'source': 'store_daily_facts',
        'availability': availability,
        'missing_fields': missing_fields,
        'limitations': limitations,
        'new_buyers': current['new_buyers'] if current else None,
        'returning_buyers': current['returning_buyers'] if current else None,
        'total_visitors': current['visitors'] if current and current.get('visitors_available') else None,
        'new_ratio': round(current_new_ratio, 4) if current_new_ratio is not None else None,
        'returning_ratio': round(current_returning_ratio, 4) if current_returning_ratio is not None else None,
        'prev_new_ratio': round(prev_new_ratio, 4) if prev_new_ratio is not None else None,
        'prev_returning_ratio': round(prev_returning_ratio, 4) if prev_returning_ratio is not None else None,
        'trend': trend,
    })


# ==================== 加购→支付漏斗分析 API ====================

@data_legacy_bp.route('/api/funnel', methods=['GET'])
@cached_api('get_funnel_analysis', ttl=60)
def get_funnel_analysis():
    """漏斗分析：曝光→浏览→加购→收藏→支付"""
    dim = request.args.get('dim', 'monthly')
    period = request.args.get('period', '')

    dim_cfg = DIMENSION_MAP.get(dim)
    if not dim_cfg:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dim}, status=422)
    table = dim_cfg['table']
    date_col = dim_cfg['date_col']
    visitors_col = dim_cfg['visitors_col']

    if period:
        period_format = '%Y-%m' if dim == 'monthly' else '%Y-%m-%d'
        try:
            parsed_period = datetime.strptime(period, period_format)
        except (TypeError, ValueError):
            return failure('VALIDATION_ERROR', 'invalid period format', {'dim': dim, 'period': period}, status=422)
        if parsed_period.strftime(period_format) != period:
            return failure('VALIDATION_ERROR', 'invalid period format', {'dim': dim, 'period': period}, status=422)

    funnel_fields = {
        'monthly': {
            'visitors': 'visitors', 'page_views': 'page_views',
            'cart_qty': 'cart_qty', 'fav_users': 'fav_users', 'payment_qty': 'payment_qty',
        },
        'daily': {
            'visitors': 'ipv', 'page_views': 'pv',
            'cart_qty': 'cart_qty', 'fav_users': 'fav_users', 'payment_qty': 'payment_qty',
        },
        'weekly': {
            'visitors': 'ipv', 'page_views': 'pv',
            'cart_qty': None, 'fav_users': None, 'payment_qty': None,
        },
    }
    field_map = funnel_fields[dim]
    step_units = {'visitors': 'users', 'page_views': 'views', 'cart_qty': 'items',
                  'fav_users': 'users', 'payment_qty': 'items'}

    def query_funnel(p, conn):
        if not p:
            return None
        select_fields = ['COUNT(*) AS row_count']
        for alias, column in field_map.items():
            if column:
                select_fields.append(f'COALESCE(SUM({column}), 0) AS {alias}')
        row = conn.execute(
            f'SELECT {", ".join(select_fields)} FROM {table} WHERE {date_col} = ?',
            (p,),
        ).fetchone()
        if not row or not row['row_count']:
            return None
        rd = dict(row)
        steps = [
            {'name': '曝光', 'key': 'visitors', 'value': rd.get('visitors'), 'unit': step_units['visitors']},
            {'name': '浏览', 'key': 'page_views', 'value': rd.get('page_views'), 'unit': step_units['page_views']},
            {'name': '加购', 'key': 'cart_qty', 'value': rd.get('cart_qty'), 'unit': step_units['cart_qty']},
            {'name': '收藏', 'key': 'fav_users', 'value': rd.get('fav_users'), 'unit': step_units['fav_users']},
            {'name': '支付', 'key': 'payment_qty', 'value': rd.get('payment_qty'), 'unit': step_units['payment_qty']},
        ]
        for i, step in enumerate(steps):
            if i == 0:
                step['rate'] = 1.0 if step['value'] is not None else None
                step['volume_ratio'] = None
                continue
            previous = steps[i - 1]
            current_value = step['value']
            previous_value = previous['value']
            step['rate_basis'] = f"{previous['unit'] or 'unknown'}_to_{step['unit'] or 'unknown'}"
            if current_value is None or previous_value is None or previous_value <= 0:
                step['rate'] = None
                step['volume_ratio'] = None
            else:
                step['volume_ratio'] = current_value / previous_value
                # A count ratio across different units is not a conversion rate.
                step['rate'] = (
                    step['volume_ratio']
                    if previous['unit'] == step['unit'] else None
                )
        return steps

    with get_db() as conn:
        steps = query_funnel(period, conn)
        prev_period = get_prev_period(period, dim)
        prev_steps = query_funnel(prev_period, conn)

    missing_fields = [alias for alias, column in field_map.items() if not column]
    availability = 'missing-fields' if missing_fields else ('available' if steps else 'no-data')
    limitations = []
    if missing_fields:
        limitations.append('当前维度缺少完整漏斗字段，缺失步骤不会用 0 填充')
    limitations.append('不同统计单位之间仅提供 volume_ratio，不将其标记为转化率')

    return jsonify({
        'availability': availability,
        'missing_fields': missing_fields,
        'limitations': limitations,
        'steps': steps or [],
        'prev_steps': prev_steps or [],
    })


# ==================== 行业基准对比 API ====================

#

@data_legacy_bp.route('/api/product_target_progress', methods=['GET'])
def get_product_target_progress():
    """商品/分层目标进度"""
    if (denied := reject_legacy_shop_scope('商品目标')):
        return denied
    period = request.args.get('period', '')
    invalid = _validate_period_arg('monthly', period)
    if invalid:
        return invalid
    target_shop = (request.args.get('shop_id') or '').strip() or str(current_app.config.get('SHOP_ID') or os.environ.get('TMALL_SHOP_ID') or '').strip()
    if target_shop and target_shop != 'default':
        return failure('UNSUPPORTED_SCOPE', '商品目标当前不支持 shop_id；请先完成目标表店铺迁移', status=422)
    with get_db() as conn:

        rows = [dict(r) for r in conn.execute('''
            SELECT pt.*,
                   m.payment_amount as actual_gsv,
                   m.ad_spend as actual_ad_spend,
                   p.title, p.tier, p.image_url
            FROM product_targets pt
            LEFT JOIN monthly_data m ON pt.product_id = m.product_id AND m.month = pt.period
            LEFT JOIN products p ON pt.product_id = p.product_id
            WHERE pt.period = ?
            ORDER BY (pt.target_gsv - COALESCE(m.payment_amount, 0)) DESC
        ''', (period,)).fetchall()]

        # 计算进度
        for r in rows:
            if r['actual_gsv'] is not None and r['target_gsv'] and r['target_gsv'] > 0:
                r['gsv_progress'] = round(r['actual_gsv'] / r['target_gsv'] * 100, 1)
            if r['actual_ad_spend'] is not None and r['target_ad_spend'] and r['target_ad_spend'] > 0:
                r['ad_progress'] = round(r['actual_ad_spend'] / r['target_ad_spend'] * 100, 1)

    return jsonify(rows)

#


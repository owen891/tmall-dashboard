import calendar
from datetime import datetime

from services.category_mode_service import category_filters_from_request
from services.shop_scope_service import reject_legacy_shop_scope
"""Goals Legacy API - 经营目标相关接口（旧版）

从 data_api.py 拆分出来的独立模块，现仅保留：
- 目标进度查询（/api/target_progress）
"""

from flask import Blueprint, jsonify, request
from api.data_api import DIMENSION_MAP, _get_prev_month, _reject_legacy_shop_scope, _validate_period_arg

from db import get_db, get_shop_id
from services.category_mode_service import shop_label_filter
from api.api_response import failure


goals_legacy_bp = Blueprint('goals_legacy', __name__)

@goals_legacy_bp.route('/api/target_progress', methods=['GET'])
def get_target_progress():
    if request.args.get('dim', 'monthly') == 'daily' and (denied := reject_legacy_shop_scope('店铺目标')):
        return denied
    """目标完成进度 — 支持日/周/月维度"""
    period = request.args.get('period', '')
    dim = request.args.get('dim', 'monthly')
    if dim not in DIMENSION_MAP:
        return failure('VALIDATION_ERROR', 'invalid dimension', {'dim': dim}, status=422)
    invalid = _validate_period_arg(dim, period)
    if invalid:
        return invalid
    unsupported = _reject_legacy_shop_scope(dim)
    if unsupported:
        return unsupported
    shop_id = get_shop_id()
    _t_label, _t_label_params = shop_label_filter(category_filters_from_request())
    _t_table = 'daily_data' if dim == 'daily' else 'weekly_data' if dim == 'weekly' else 'monthly_data'
    _t_alias = 'd' if dim == 'daily' else 'w' if dim == 'weekly' else 'm'
    _t_join = f' JOIN products p ON p.product_id = {_t_alias}.product_id' if _t_label else ''
    _t_where = (' AND ' + _t_label) if _t_label else ''
    with get_db() as conn:

        # 获取店铺目标（period字段兼容月/周/日格式）
        target = conn.execute('SELECT * FROM shop_targets WHERE period = ?', (period,)).fetchone()
        target = dict(target) if target else None

        # 根据维度查询实际数据（品类模式过滤 actual，target 保持店铺目标）
        if dim == 'daily':
            actual = conn.execute(f'''
                SELECT
                    COUNT(*) as row_count,
                    SUM(payment_amount) as gsv,
                    SUM(refund_amount) as refund,
                    SUM(payment_amount) - SUM(refund_amount) as net_sales,
                    SUM(ipv) as visitors,
                    AVG(payment_conversion) as conversion,
                    SUM(ad_spend) as ad_spend,
                    COUNT(DISTINCT d.product_id) as product_count
                FROM daily_data d{_t_join} WHERE d.shop_id = ? AND d.date = ?{_t_where}
            ''', (shop_id, period, *_t_label_params)).fetchone()
        elif dim == 'weekly':
            actual = conn.execute(f'''
                SELECT
                    COUNT(*) as row_count,
                    SUM(payment_amount) as gsv,
                    SUM(refund_amount) as refund,
                    SUM(payment_amount) - SUM(refund_amount) as net_sales,
                    SUM(ipv) as visitors,
                    AVG(payment_conversion) as conversion,
                    SUM(ad_spend) as ad_spend,
                    COUNT(DISTINCT w.product_id) as product_count
                FROM weekly_data w{_t_join} WHERE w.week_start = ?{_t_where}
            ''', (period, *_t_label_params)).fetchone()
        else:
            actual = conn.execute(f'''
                SELECT
                    COUNT(*) as row_count,
                    SUM(payment_amount) as gsv,
                    SUM(refund_amount) as refund,
                    SUM(payment_amount) - SUM(refund_amount) as net_sales,
                    SUM(visitors) as visitors,
                    AVG(payment_conversion) as conversion,
                    SUM(ad_spend) as ad_spend,
                    COUNT(DISTINCT m.product_id) as product_count
                FROM monthly_data m{_t_join} WHERE m.month = ?{_t_where}
            ''', (period, *_t_label_params)).fetchone()
            # 月度数据未覆盖该月时（如当前月只有日度导出），从日度数据聚合
            if not actual or not actual['row_count']:
                _fallback_join = f' JOIN products p ON p.product_id = d.product_id' if _t_label else ''
                actual = conn.execute(f'''
                    SELECT
                        COUNT(*) as row_count,
                        SUM(payment_amount) as gsv,
                        SUM(refund_amount) as refund,
                        SUM(payment_amount) - SUM(refund_amount) as net_sales,
                        SUM(ipv) as visitors,
                        AVG(payment_conversion) as conversion,
                        SUM(ad_spend) as ad_spend,
                        COUNT(DISTINCT d.product_id) as product_count
                    FROM daily_data d{_fallback_join} WHERE d.shop_id = ? AND d.date LIKE ?{_t_where}
                ''', (shop_id, period + '%', *_t_label_params)).fetchone()
        actual = dict(actual) if actual else None
        if actual and not actual.pop('row_count', 0):
            actual = None

        result = {'target': target, 'actual': actual, 'period': period, 'dim': dim}

        if target and actual:
            gsv_target = target['target_gsv'] or 0
            gsv_actual = actual['gsv'] or 0
            ad_target = target['target_ad_spend'] or 0
            ad_actual = actual['ad_spend'] or 0

            result['gsv_progress'] = round(gsv_actual / gsv_target * 100, 1) if gsv_target > 0 else None
            result['gsv_gap'] = gsv_target - gsv_actual
            result['ad_progress'] = round(ad_actual / ad_target * 100, 1) if ad_target > 0 else None
            result['ad_gap'] = ad_target - ad_actual
            result['actual_ad_ratio'] = round(ad_actual / gsv_actual, 4) if gsv_actual > 0 else None
            result['target_ad_ratio'] = target['target_ad_ratio']

            # 净销售额目标进度（target_net_sales 为新增字段，旧记录可能为 NULL）
            net_target = target.get('target_net_sales') or 0
            net_actual = actual.get('net_sales') or 0
            if net_target > 0:
                result['net_sales_progress'] = round(net_actual / net_target * 100, 1)
                result['net_sales_gap'] = net_target - net_actual
            else:
                result['net_sales_progress'] = None
                result['net_sales_gap'] = None

            # 时间进度估算
            try:
                today = datetime.now()
                if dim == 'daily':
                    # 日维度：当月已过天数 / 当月总天数
                    try:
                        month_str = period[:7]  # 从 "2026-04-25" 提取 "2026-04"
                        month_end = datetime.strptime(month_str + '-01', '%Y-%m-%d')
                        _, days_in_month = calendar.monthrange(month_end.year, month_end.month)
                    except (ValueError, IndexError):
                        month_end = today
                        _, days_in_month = calendar.monthrange(today.year, today.month)
                    if today.year == month_end.year and today.month == month_end.month:
                        time_progress = round(today.day / days_in_month * 100, 1)
                    elif (today.year > month_end.year) or (today.year == month_end.year and today.month > month_end.month):
                        time_progress = 100
                    else:
                        time_progress = 0
                elif dim == 'weekly':
                    # 周维度：当前周已过天数 / 7
                    try:
                        week_start = datetime.strptime(period, '%Y-%m-%d')
                        days_elapsed = (today - week_start).days + 1
                        time_progress = round(min(max(days_elapsed, 0) / 7 * 100, 100), 1)
                    except (ValueError, IndexError):
                        time_progress = round(today.weekday() / 7 * 100, 1) + 14.3  # 近似
                else:
                    # 月维度：自然月进度
                    month_end = datetime.strptime(period + '-01', '%Y-%m-%d')
                    _, days_in_month = calendar.monthrange(month_end.year, month_end.month)
                    if today.year == month_end.year and today.month == month_end.month:
                        time_progress = round(today.day / days_in_month * 100, 1)
                    elif (today.year > month_end.year) or (today.year == month_end.year and today.month > month_end.month):
                        time_progress = 100
                    else:
                        time_progress = 0
                result['time_progress'] = time_progress
            except (ValueError, IndexError, TypeError):
                result['time_progress'] = None

            # 智能预测
            if result.get('time_progress') and result.get('time_progress', 0) > 0 and result.get('time_progress', 0) < 100:
                speed = gsv_actual / (result['time_progress'] / 100)
                if dim == 'daily':
                    # 日维度：日均 × 当月总天数
                    try:
                        month_str = period[:7]
                        month_end = datetime.strptime(month_str + '-01', '%Y-%m-%d')
                        _, days_in_month = calendar.monthrange(month_end.year, month_end.month)
                    except (ValueError, IndexError):
                        days_in_month = 30
                    result['gsv_forecast'] = round(speed * days_in_month, 0)
                    result['forecast_label'] = f'预计本月GSV'
                elif dim == 'weekly':
                    # 周维度：日均 × 7
                    result['gsv_forecast'] = round(speed * 7, 0)
                    result['forecast_label'] = f'预计本周GSV'
                else:
                    result['gsv_forecast'] = round(speed, 0)
                    result['forecast_label'] = f'预计月底GSV'
                result['forecast_gap'] = round(gsv_target - result['gsv_forecast'], 0)

            # 同比数据
            def add_yoy(previous):
                if not previous or not previous.pop('row_count', 0):
                    return
                previous_gsv = previous.get('gsv')
                previous_ad = previous.get('ad_spend')
                if previous_gsv not in (None, 0):
                    result['yoy_gsv'] = round((gsv_actual - previous_gsv) / previous_gsv * 100, 1)
                if previous_ad not in (None, 0):
                    result['yoy_ad'] = round((ad_actual - previous_ad) / previous_ad * 100, 1)

            if dim == 'monthly':
                prev_period = _get_prev_month(period)
                if prev_period:
                    prev = conn.execute('''
                        SELECT COUNT(*) as row_count, SUM(payment_amount) as gsv, SUM(ad_spend) as ad_spend
                        FROM monthly_data WHERE month = ?
                    ''', (prev_period,)).fetchone()
                    prev = dict(prev) if prev else None
                    add_yoy(prev)
            elif dim == 'daily':
                # 日维度：取前一天对比
                try:
                    from datetime import timedelta, date
                    prev_date = (datetime.strptime(period, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
                    prev = conn.execute('''
                        SELECT COUNT(*) as row_count, SUM(payment_amount) as gsv, SUM(ad_spend) as ad_spend
                        FROM daily_data WHERE shop_id = ? AND date = ?
                    ''', (shop_id, prev_date)).fetchone()
                    prev = dict(prev) if prev else None
                    add_yoy(prev)
                except (ValueError, IndexError):
                    # 同比日期解析失败时跳过年同比计算
                    pass
            elif dim == 'weekly':
                # 周维度：取上一周对比
                try:
                    from datetime import timedelta, date
                    prev_week = (datetime.strptime(period, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
                    prev = conn.execute('''
                        SELECT COUNT(*) as row_count, SUM(payment_amount) as gsv, SUM(ad_spend) as ad_spend
                        FROM weekly_data WHERE week_start = ?
                    ''', (prev_week,)).fetchone()
                    prev = dict(prev) if prev else None
                    add_yoy(prev)
                except (ValueError, IndexError):
                    # 周同比日期解析失败时跳过
                    pass

    return jsonify(result)

# 预留接口：商品分层目标进度（前端暂未调用）

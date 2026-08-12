"""
周期计算工具 — 从 data_api.py 提取。

处理月/周/日的上一期计算，用于环比对比。
"""
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def get_prev_period(dim, period):
    """
    获取上一期周期值。
    替代原 data_api.py 中的 get_prev_period() 函数。

    参数:
        dim: 'monthly' | 'weekly' | 'daily'
        period: 当前周期值（字符串）

    返回:
        上一期周期值（字符串）

    示例:
        get_prev_period('monthly', '2026-07') → '2026-06'
        get_prev_period('weekly', '2026-08-04') → '2026-07-28'
        get_prev_period('daily', '2026-08-10') → '2026-08-09'
    """
    if dim == 'monthly':
        dt = datetime.strptime(period, '%Y-%m')
        prev = dt - relativedelta(months=1)
        return prev.strftime('%Y-%m')

    elif dim == 'weekly':
        dt = datetime.strptime(period, '%Y-%m-%d')
        prev = dt - timedelta(weeks=1)
        return prev.strftime('%Y-%m-%d')

    elif dim == 'daily':
        dt = datetime.strptime(period, '%Y-%m-%d')
        prev = dt - timedelta(days=1)
        return prev.strftime('%Y-%m-%d')

    return period


def get_period_range(dim, period):
    """
    获取周期的起止日期。
    用于查询时过滤日期范围。
    """
    if dim == 'monthly':
        dt = datetime.strptime(period, '%Y-%m')
        start = dt
        end = dt + relativedelta(months=1) - timedelta(days=1)
        return start, end

    elif dim == 'weekly':
        start = datetime.strptime(period, '%Y-%m-%d')
        end = start + timedelta(days=6)
        return start, end

    elif dim == 'daily':
        dt = datetime.strptime(period, '%Y-%m-%d')
        return dt, dt

    return None, None


def get_recent_periods(dim, count=6, end_period=None):
    """获取最近 N 个周期列表"""
    if end_period is None:
        end_period = datetime.now().strftime('%Y-%m')

    periods = []
    current = end_period
    for _ in range(count):
        periods.insert(0, current)
        current = get_prev_period(dim, current)
    return periods

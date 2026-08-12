"""
格式化工具函数 — 从 data_api.py 提取。

这些函数在多个路由中被调用，提取到 utils 后可复用。
"""

def fmt_wan(value):
    """
    金额格式化：万为单位，保留 1 位小数。
    替代原 data_api.py 中的 _fmt_wan() 函数。
    """
    if value is None or value == 0:
        return '0'
    if abs(value) >= 10000:
        return f'{value / 10000:.1f}万'
    return f'{value:.0f}'


def fmt_percent(value, decimals=1):
    """百分比格式化"""
    if value is None:
        return '0%'
    return f'{value * 100:.{decimals}f}%'


def fmt_number(value, decimals=0):
    """数字格式化"""
    if value is None:
        return '0'
    return f'{value:,.{decimals}f}'


def calc_change_rate(current, previous):
    """
    计算环比变化率。
    替代原 data_api.py 中各路由重复的计算逻辑。
    """
    if not previous or previous == 0:
        return 0 if not current else 1.0
    return (current - previous) / abs(previous)

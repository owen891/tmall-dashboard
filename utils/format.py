def calc_change_rate(current, previous):
    current = current or 0
    previous = previous or 0
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def fmt_wan(value):
    if value is None:
        return '--'
    value = float(value)
    if value == 0:
        return '0'
    return f'{value:,.0f}' if abs(value) < 10000 else f'{value / 10000:.1f}万'


def fmt_percent(value, digits=1):
    if value is None:
        return '--'
    return f'{float(value) * 100:.{digits}f}%'


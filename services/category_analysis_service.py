"""Category period analysis backed by daily product facts."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any

from db import get_db, get_shop_id
from services.category_mode_service import mode_to_label

BASE_METRICS = {
    'payment_amount': 'payment_amount', 'net_sales': 'net_sales',
    'payment_qty': 'payment_qty', 'visitors': 'ipv', 'buyers': 'buyers',
    'ad_spend': 'ad_spend', 'refund_amount': 'refund_amount',
}
DERIVED = {'payment_conversion_rate', 'average_order_value', 'refund_rate', 'expense_ratio',
           'gross_profit', 'operating_profit', 'profit_rate'}

# 经营利润（支付预估口径）的扣减项。
# 该式在 2025-09-01 / 2025-09-15 / 2026-08-15 / 2026-09-10 四个日期上对 BI 的
# 「利润(支付预估)」列做逐商品回归，聚合误差 < 0.1 元、±1 元命中 100%：
#   利润 = 净销售额(支付) − 销售费用(支付预估) − 自定义费用
#          − 净货品成本(支付) − 发货费用(支付) − 其他费用(支付)
PROFIT_DEDUCTION_COLUMNS = ('sales_cost', 'custom_cost', 'product_cost', 'logistics_cost', 'other_cost')
# BI 直接给出的权威利润列。存在时优先采用；缺失时才回落到上面的公式。
PROFIT_SOURCE_COLUMN = 'operating_profit'
# 仅供拆解下钻参考，不参与利润公式，避免与 BI 口径打架。
SUPPLEMENTARY_COST_COLUMNS = ('platform_fee', 'after_sales_loss')
COST_COLUMNS = PROFIT_DEDUCTION_COLUMNS + SUPPLEMENTARY_COST_COLUMNS
COST_LABELS = {
    'product_cost': '净货品成本', 'sales_cost': '销售费用', 'custom_cost': '自定义费用',
    'logistics_cost': '发货费用', 'other_cost': '其他费用',
    'platform_fee': '平台花费', 'after_sales_loss': '退款货品成本',
}


def _period_dates(start: date, end: date, grain: str):
    cur = start
    while cur <= end:
        if grain == 'day':
            nxt = cur
        elif grain == 'week':
            nxt = cur + timedelta(days=(6 - cur.weekday()))
        else:
            nxt = cur.replace(day=monthrange(cur.year, cur.month)[1])
        yield cur, min(nxt, end)
        cur = nxt + timedelta(days=1)


def _rate(numerator, denominator):
    # 分子也可能为 None（例如成本缺失时的经营利润），必须一并挡掉，
    # 否则 None / float 会抛 TypeError 并被 API 包装成 422。
    return None if numerator is None or denominator in (None, 0) else numerator / denominator


def _parse_period(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'invalid {name}') from exc


def _aggregate(conn, start: date, end: date, category_mode: str | None, shop_id: str):
    label = mode_to_label(category_mode)
    # daily_data 是多店表（唯一键含 shop_id），漏掉店铺条件就会把其他店铺的
    # 经营数据聚合进当前请求的店铺口径里。店铺条件必须显式且不可省略。
    clauses = ['d.shop_id = ?', 'd.date >= ?', 'd.date <= ?']
    params: list[Any] = [shop_id, start.isoformat(), end.isoformat()]
    if label:
        clauses.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
        params.extend([label, label])
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(daily_data)').fetchall()}
    select = ['d.date', 'd.product_id', 'p.title'] + [f'd.{c}' for c in BASE_METRICS.values() if c in columns]
    for c in COST_COLUMNS + (PROFIT_SOURCE_COLUMN,):
        if c in columns and c not in BASE_METRICS.values():
            select.append(f'd.{c}')
    query = f"SELECT {', '.join(select)} FROM daily_data d LEFT JOIN products p ON p.product_id=d.product_id WHERE {' AND '.join(clauses)} ORDER BY d.date"
    rows = [dict(row) for row in conn.execute(query, params).fetchall()]
    return rows, label, columns


def _summarize(rows):
    """Aggregate rows into totals and per-field presence flags.

    Returns ``(totals, seen, profit_basis)``.  ``profit_basis`` is ``'bi'`` when
    BI's own 利润(支付预估) column supplied the profit, ``'derived'`` when it was
    reconstructed from the verified deduction formula, and ``None`` when neither
    is possible.  When it is ``None``, ``operating_profit`` is ``None`` and must
    never be rendered as a number.

    Missing cost fields stay ``None``; they are never silently defaulted to 0.
    Otherwise 「经营利润」 collapses into 净销售额 − 推广花费 and looks wildly
    profitable for a category that is actually losing money.
    """
    metric_keys = set(BASE_METRICS) | set(COST_COLUMNS) | {PROFIT_SOURCE_COLUMN}
    totals = {key: 0.0 for key in metric_keys}
    seen = {key: False for key in metric_keys}
    derived_keys = ('gross_profit', 'payment_conversion_rate', 'average_order_value',
                    'refund_rate', 'expense_ratio', 'profit_rate')
    if not rows:
        empty = {key: None for key in metric_keys}
        empty.update({key: None for key in derived_keys})
        return empty, seen, None
    for row in rows:
        for key, column in BASE_METRICS.items():
            if column in row and row[column] is not None:
                totals[key] += float(row[column] or 0); seen[key] = True
        for key in COST_COLUMNS + (PROFIT_SOURCE_COLUMN,):
            if key in row and row[key] is not None:
                totals[key] += float(row[key] or 0); seen[key] = True
    missing = [key for key in PROFIT_DEDUCTION_COLUMNS if not seen[key]]
    if seen[PROFIT_SOURCE_COLUMN]:
        operating_profit, basis = totals[PROFIT_SOURCE_COLUMN], 'bi'
    elif not missing and seen['net_sales']:
        operating_profit = totals['net_sales'] - sum(totals[key] for key in PROFIT_DEDUCTION_COLUMNS)
        basis = 'derived'
    else:
        operating_profit, basis = None, None
    totals['operating_profit'] = operating_profit
    totals['gross_profit'] = (totals['net_sales'] - totals['product_cost']
                              if seen['net_sales'] and seen['product_cost'] else None)
    totals['payment_conversion_rate'] = _rate(totals['buyers'], totals['visitors'])
    totals['average_order_value'] = _rate(totals['payment_amount'], totals['buyers'])
    totals['refund_rate'] = _rate(totals['refund_amount'], totals['payment_amount'])
    totals['expense_ratio'] = _rate(totals['ad_spend'], totals['net_sales'])
    totals['profit_rate'] = _rate(operating_profit, totals['net_sales'])
    return totals, seen, basis


def _compare(current, previous):
    amount = None if current is None or previous is None else current - previous
    return {'amount': amount, 'rate': None if amount is None or previous in (None, 0) else amount / previous}


def _contributors(rows, previous_rows, metric, top_n):
    """Per-product growth/shrink ranking for the category.

    Titles are resolved through a single map instead of a linear scan per
    product (the old form was O(n²)), and products that fell to zero are kept:
    iterating only the current period silently dropped every discontinued SKU
    from the 「下滑拖累」 board, which is exactly the set worth looking at.
    """
    column = BASE_METRICS.get(metric, metric)
    titles: dict[str, str | None] = {}

    def by_product(items):
        result: dict[str, float] = {}
        for row in items:
            key = row.get('product_id') or ''
            if titles.get(key) is None and row.get('title'):
                titles[key] = row['title']
            value = row.get(column)
            if value is not None:
                result[key] = result.get(key, 0.0) + float(value or 0)
        return result

    current, previous = by_product(rows), by_product(previous_rows)
    changes = []
    for key in set(current) | set(previous):
        cur, prev = current.get(key), previous.get(key)
        if cur is None and prev is None:
            continue
        delta = (cur or 0.0) - (prev or 0.0)
        changes.append({
            'product_id': key,
            'title': titles.get(key),
            'current_value': cur,
            'compare_value': prev,
            'change': delta,
            'amount': delta,
            'value': delta,
        })
    return {'up': sorted((item for item in changes if item['change'] > 0), key=lambda item: item['change'], reverse=True)[:top_n],
            'down': sorted((item for item in changes if item['change'] < 0), key=lambda item: item['change'])[:top_n]}


def analyze(*, start: date, end: date, compare_start: date | None, compare_end: date | None,
            grain: str, category_mode: str | None, metric: str, top_n: int = 20,
            shop_id: str | None = None):
    if grain not in {'day', 'week', 'month'}: raise ValueError('grain must be day, week, or month')
    if metric not in BASE_METRICS and metric not in DERIVED: raise ValueError('unsupported metric')
    shop_id = str(shop_id or get_shop_id())
    with get_db() as conn:
        rows, label, columns = _aggregate(conn, start, end, category_mode, shop_id)
        current, seen, profit_basis = _summarize(rows)
        previous = prev_seen = None
        previous_rows = []
        if compare_start and compare_end:
            previous_rows, _, _ = _aggregate(conn, compare_start, compare_end, category_mode, shop_id)
            previous, prev_seen, _ = _summarize(previous_rows)
        latest = conn.execute(
            'SELECT MAX(date) AS latest FROM daily_data WHERE shop_id = ?', (shop_id,)
        ).fetchone()
    coverage_end = min(end, date.fromisoformat(latest['latest'])) if latest and latest['latest'] else None

    def build_trend(source_rows, range_start, range_end):
        series = []
        for bucket_start, bucket_end in _period_dates(range_start, range_end, grain):
            bucket_rows = [r for r in source_rows
                           if bucket_start.isoformat() <= r['date'] <= bucket_end.isoformat()]
            values, _, _ = _summarize(bucket_rows)
            series.append({
                'period': bucket_start.isoformat() if bucket_start == bucket_end
                else f'{bucket_start.isoformat()}~{bucket_end.isoformat()}',
                'start': bucket_start.isoformat(),
                'end': bucket_end.isoformat(),
                'value': values.get(metric),
            })
        return series

    trend = build_trend(rows, start, end)
    compare_trend = (build_trend(previous_rows, compare_start, compare_end)
                     if compare_start and compare_end else [])
    cur_value, prev_value = current.get(metric), previous.get(metric) if previous else None
    days, prev_days = (end - start).days + 1, ((compare_end - compare_start).days + 1 if compare_start and compare_end else None)
    breakdown_keys = (('net_sales', 'ad_spend') + PROFIT_DEDUCTION_COLUMNS
                      + SUPPLEMENTARY_COST_COLUMNS + ('gross_profit', 'operating_profit'))
    # gross_profit / operating_profit 是 _summarize 里推导出来的，不对应任何单一
    # 源列，seen 里没有它们的标记；只按 seen 过滤会把推导出的利润误清成 None。
    computed_keys = {'gross_profit', 'operating_profit'}
    breakdown = {key: (current.get(key) if (seen.get(key) or key in computed_keys) else None)
                 for key in breakdown_keys}
    missing_costs = [key for key in COST_COLUMNS if not seen.get(key)]
    missing_profit = [key for key in PROFIT_DEDUCTION_COLUMNS if not seen.get(key)]
    breakdown['operating_profit_rate'] = _rate(breakdown.get('operating_profit'), breakdown.get('net_sales'))
    breakdown['basis'] = profit_basis
    breakdown['missing_fields'] = missing_profit
    breakdown['is_complete'] = bool(profit_basis) and not missing_profit
    availability = 'no-data' if not rows and not previous_rows else 'partial' if not rows or missing_costs else 'available'
    return {'category': {'value': category_mode or 'all', 'label': label or '全部品类'}, 'grain': grain, 'metric': metric,
            'current_period': {'start': start.isoformat(), 'end': end.isoformat(), 'days': days, 'value': cur_value, 'daily_average': None if cur_value is None else cur_value / days},
            'compare_period': None if previous is None else {'start': compare_start.isoformat(), 'end': compare_end.isoformat(), 'days': prev_days, 'value': prev_value, 'daily_average': None if prev_value is None else prev_value / prev_days},
            'change': _compare(cur_value, prev_value), 'trend': trend, 'compare_trend': compare_trend,
            'contributors': _contributors(rows, previous_rows, metric, top_n), 'profit_breakdown': breakdown,
            'cost_labels': COST_LABELS,
            'data_quality': {'availability': availability, 'is_partial_period': end >= date.today(),
                             'missing_fields': missing_costs, 'profit_basis': profit_basis,
                             'source_tables': ['daily_data'],
                             'coverage_end': coverage_end.isoformat() if coverage_end else None,
                             'requested_end': end.isoformat(),
                             # 前端一律用这个基准，不要再本地硬编码日期。
                             'server_today': date.today().isoformat()}}


def analyze_matrix(*, years: list[int], category_mode: str | None, metric: str = 'net_sales',
                   metrics: list[str] | None = None, shop_id: str | None = None):
    """Return a calendar-month matrix for multi-year category management."""
    if not years or len(years) > 5 or any(year < 2000 or year > 2100 for year in years):
        raise ValueError('years must contain one to five valid years')
    selected_metrics = list(dict.fromkeys(metrics or [metric]))
    if not selected_metrics or any(item not in BASE_METRICS and item not in DERIVED for item in selected_metrics):
        raise ValueError('unsupported metric')
    shop_id = str(shop_id or get_shop_id())
    years = sorted(set(years))
    start, end = date(years[0], 1, 1), date(years[-1], 12, 31)
    with get_db() as conn:
        rows, label, _ = _aggregate(conn, start, end, category_mode, shop_id)
    def build_metric(metric_name):
        values = {year: {} for year in years}
        for year in years:
            for month in range(1, 13):
                month_rows = [row for row in rows if row['date'].startswith(f'{year:04d}-{month:02d}-')]
                summary, _, _ = _summarize(month_rows)
                values[year][month] = summary.get(metric_name)
        matrix = []
        for month in range(1, 13):
            current = values[years[-1]][month]
            previous_year = values.get(years[-1] - 1, {}).get(month)
            previous_month = values[years[-1]].get(month - 1) if month > 1 else None
            matrix.append({
                'month': month,
                'label': f'{month}月',
                'values': {str(year): values[year][month] for year in years},
                'yoy': _compare(current, previous_year),
                'mom': _compare(current, previous_month),
            })
        annual = {}
        for year in years:
            summary, _, _ = _summarize([row for row in rows if row['date'].startswith(f'{year:04d}-')])
            annual[str(year)] = summary.get(metric_name)
        return {'metric': metric_name, 'matrix': matrix, 'annual': annual}

    metric_data = {item: build_metric(item) for item in selected_metrics}
    primary = metric_data[selected_metrics[0]]
    focus_year = years[-1]
    missing_costs = [key for key in COST_COLUMNS if not any(row.get(key) is not None for row in rows)]
    coverage_end = min(end, date.today()).isoformat() if start <= date.today() else None
    return {
        'category': {'value': category_mode or 'all', 'label': label or '全部品类'},
        'years': years, 'focus_year': focus_year, 'metric': selected_metrics[0],
        'metrics': selected_metrics, 'matrix': primary['matrix'], 'annual': primary['annual'],
        'series': metric_data,
        'data_quality': {
            'availability': 'no-data' if not rows else 'partial' if missing_costs else 'available',
            'missing_fields': missing_costs, 'source_tables': ['daily_data'], 'coverage_end': coverage_end,
            'server_today': date.today().isoformat(),
        },
    }

# -*- coding: utf-8 -*-
"""指标矩阵 / 类目拆解：最近 N 个周期的矩阵与类目分解视图。"""

from __future__ import annotations

from db import get_db
from services.category_mode_service import mode_to_label
from services import category_analysis_service as category_service
from services.period_parsing import resolve_period, _period_label
from services.period_context import _daily_scope

# ---------------------------------------------------------------------------
# 指标矩阵 / 类目拆解（新增）
# ---------------------------------------------------------------------------

# 矩阵表暴露的字段。value 为 None 表示该列在当前数据里不存在或无值。
MATRIX_METRICS = [
    ('net_sales', '净销售额', 'money', False),
    ('payment_conversion_rate', '转化率', 'percent', False),
    ('cart_rate', '加购率', 'percent', False),
    ('ad_spend', '推广花费', 'money', False),
    ('expense_ratio', '净费比', 'percent', True),
    ('ad_roi', '投产比', 'decimal', False),
    ('refund_rate', '退款率', 'percent', True),
    ('operating_profit', '利润(支付预估)', 'money', False),
    ('profit_rate', '利润率', 'percent', False),
]

# 来自 BI「商品总览」的推广平台明细原始列，需要单独求和。
# 注意：无界花费/无界成交不在这里——BI 导出的「万相台」列在近两年整列为
# '--' 或 0，真实无界数据来自万相台后台采集表 promotion_daily_facts，
# 见 _wujie_totals()。
PROMO_DETAIL_COLUMNS = (
    'product_sitewide_spend', 'product_sitewide_payment',
    'gift_cost', 'brand_marketing_spend',
)

# 推广平台明细列。口径与来源列一一对应，缺数据时值为 None（前端显示 --）。
# 「商品营销托管花费」= 品牌新享营销托管软件服务费；
# 「礼金总费用」= 首单礼金 / 品牌新享首单礼金。
MATRIX_PROMO_METRICS = [
    ('wujie_spend', '无界花费', 'money', False),
    ('wujie_roi', '无界总ROI', 'decimal', False),
    ('wujie_expense_ratio', '无界净费比', 'percent', True),
    ('brand_marketing_spend', '商品营销托管花费', 'money', False),
    ('gift_cost', '礼金总费用', 'money', False),
    ('product_sitewide_spend', '货品全站推花费', 'money', False),
]


def _metric_item(key, label, fmt, lower_better, current, previous):
    value = current.get(key)
    prev_value = previous.get(key) if previous else None
    item = {
        'key': key, 'label': label, 'format': fmt, 'lower_better': lower_better,
        'value': value, 'prev_value': prev_value,
    }
    if value is not None and prev_value not in (None, 0):
        item['change_rate'] = round((value - prev_value) / abs(prev_value), 6)
    return item


def _row_status(metrics):
    """根据关键指标给出行状态（success / warning / danger / normal）。

    规则可按业务调整；当前默认：
    - 本期与上期都没有净销售额 -> unknown（无数据）
    - 利润率为负 -> danger
    - 净销售额环比降幅 >= 20% -> danger
    - 净销售额环比增幅 >= 20% -> success
    - 费比环比上升 >= 5pt -> warning
    """
    net_sales = metrics.get('net_sales') or {}
    profit_rate = metrics.get('profit_rate') or {}
    expense_ratio = metrics.get('expense_ratio') or {}

    # 两期都没有净销售额 => 这个周期压根没有数据。
    # 不能落到 'normal'（正常），否则表格会出现「显示正常但整行是 --」的误导。
    if net_sales.get('value') is None and net_sales.get('prev_value') is None:
        return 'unknown'

    if (profit_rate.get('value') is not None and profit_rate['value'] < 0):
        return 'danger'
    change = net_sales.get('change_rate')
    if change is not None and change <= -0.20:
        return 'danger'
    if change is not None and change >= 0.20:
        return 'success'
    expense_change = expense_ratio.get('change_rate')
    if expense_change is not None and expense_change >= 0.05:
        return 'warning'
    return 'normal'


# 无界数据来源：万相台后台采集的推广域事实表。
# 商品维度 channel='全部' 的行即该商品当日的无界总消耗与总成交。
WUJIE_SOURCE_TABLE = 'promotion_daily_facts'


def _wujie_totals(conn, start, end, category_mode, group_by_category=False):
    """从万相台后台事实表取「无界」花费与成交。

    BI 日度导出的「万相台」列在近两年整列为 '--' 或 0（平台侧没把无界
    消耗拆到商品），因此无界花费只能走推广域采集表。该表覆盖
    2025-09、2026-08、2026-09 等周期；缺覆盖的周期返回 None，
    前端显示 '--' 而不是 0。

    过滤条件说明：
    - grain='product' + channel='全部'：避免与计划/单元维度重复计数；
    - product_id 以 '-' 开头的是账户级汇总哨兵行（-998/-999），不是商品；
    - source_batch_id 为空的历史行是月度汇总被塞进月末日期，不是日度事实。
    """
    if group_by_category:
        empty: object = {}
    else:
        empty = (None, None)
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (WUJIE_SOURCE_TABLE,),
    ).fetchone()
    if not table:
        return empty

    label = mode_to_label(category_mode)
    clauses = [
        'f.date >= ?', 'f.date <= ?',
        "f.grain = 'product'", "f.channel = '全部'",
        "f.product_id NOT LIKE '-%'",
        'f.source_batch_id IS NOT NULL',
    ]
    params = [start.isoformat(), end.isoformat()]
    if label:
        clauses.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
        params.extend([label, label])

    if group_by_category:
        select = "COALESCE(p.category, '未分类') AS grp, SUM(f.ad_spend) AS spend, SUM(f.attributed_payment_amount) AS pay"
        tail = 'GROUP BY grp'
    else:
        select = 'SUM(f.ad_spend) AS spend, SUM(f.attributed_payment_amount) AS pay'
        tail = ''

    query = (f'SELECT {select} FROM {WUJIE_SOURCE_TABLE} f '
             f'LEFT JOIN products p ON p.product_id = f.product_id '
             f"WHERE {' AND '.join(clauses)} {tail}")
    rows = conn.execute(query, params).fetchall()

    def pair(row):
        spend = row['spend']
        pay = row['pay']
        return (float(spend) if spend is not None else None,
                float(pay) if pay is not None else None)

    if group_by_category:
        return {row['grp']: pair(row) for row in rows}
    if not rows:
        return empty
    return pair(rows[0])


def _matrix_aggregate(conn, start, end, category_mode, group_by_category=False):
    """聚合日事实，并补齐 category_analysis_service 未覆盖的加购率 / 投产比。

    category_service.BASE_METRICS 不含 cart_rate / ad_roi，直接复用 _summarize
    会让这两列永远为空。这里在它的基础上补算：
    - cart_rate：按行取非零日均值（与复盘服务的口径一致）
    - ad_roi：支付金额 / 推广花费（费用为 0 时返回 None，不臆造）
    """
    label = mode_to_label(category_mode)
    clauses = ['d.date >= ?', 'd.date <= ?']
    params = [start.isoformat(), end.isoformat()]
    if label:
        clauses.append("(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)")
        params.extend([label, label])

    columns = {row['name'] for row in conn.execute('PRAGMA table_info(daily_data)').fetchall()}
    select = ['d.date', 'd.product_id']
    if group_by_category:
        select.append('p.category')
    select += [f'd.{c}' for c in category_service.BASE_METRICS.values() if c in columns]
    for c in category_service.COST_COLUMNS + (category_service.PROFIT_SOURCE_COLUMN,):
        if c in columns and c not in category_service.BASE_METRICS.values():
            select.append(f'd.{c}')
    if 'cart_rate' in columns:
        select.append('d.cart_rate')
    for c in PROMO_DETAIL_COLUMNS:
        if c in columns:
            select.append(f'd.{c}')

    query = (f"SELECT {', '.join(select)} FROM daily_data d "
             f"LEFT JOIN products p ON p.product_id=d.product_id "
             f"WHERE {' AND '.join(clauses)} ORDER BY d.date")
    rows = [dict(row) for row in conn.execute(query, params).fetchall()]

    wujie_total = _wujie_totals(conn, start, end, category_mode)
    wujie_groups = _wujie_totals(conn, start, end, category_mode, group_by_category=True)

    def apply_wujie(totals, wujie):
        """写入无界花费/成交，并据此推导无界 ROI 与无界净费比。"""
        spend, pay = wujie if wujie else (None, None)
        totals['wujie_spend'] = spend
        totals['wujie_payment'] = pay
        totals['wujie_roi'] = (pay / spend
                               if spend not in (None, 0) and pay is not None else None)
        net_sales = totals.get('net_sales')
        totals['wujie_expense_ratio'] = (spend / net_sales
                                         if net_sales not in (None, 0) and spend is not None else None)
        return totals

    def summarize(group_rows, key=None):
        totals, _, basis = category_service._summarize(group_rows)
        # 加购率：只统计有值的行，避免 0 值把均值拉低
        rates = [float(r['cart_rate']) for r in group_rows
                 if r.get('cart_rate') not in (None, 0)]
        totals['cart_rate'] = sum(rates) / len(rates) if rates else None
        ad_spend = totals.get('ad_spend')
        payment = totals.get('payment_amount')
        totals['ad_roi'] = (payment / ad_spend) if ad_spend not in (None, 0) and payment is not None else None

        # 推广平台明细：只在确实存在数值时才求和；全列为 NULL 时保持 None，
        # 这样「平台当期没投放」不会被渲染成 0 费比。
        for column in PROMO_DETAIL_COLUMNS:
            present = [float(r[column]) for r in group_rows
                       if r.get(column) is not None]
            totals[column] = sum(present) if present else None

        apply_wujie(totals, wujie_groups.get(key) if key is not None else wujie_total)
        return totals, basis

    if not group_by_category:
        totals, basis = summarize(rows)
        return totals, basis, rows

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        cat = row.get('category') or '未分类'
        grouped.setdefault(cat, []).append(row)
    return grouped, summarize


def _short_category(name):
    """把「A>B>C」类目路径压成末级名称，便于表格展示。"""
    text = str(name or '').strip()
    if not text:
        return '未分类'
    for sep in ('>', '/', '|', '\\'):
        if sep in text:
            text = text.split(sep)[-1].strip()
    return text or '未分类'


def _matrix_metrics(current, previous):
    """把两组汇总值转成前端矩阵列所需的指标字典。"""
    metrics = {}
    for key, label, fmt, lower_better in MATRIX_METRICS + MATRIX_PROMO_METRICS:
        metrics[key] = _metric_item(key, label, fmt, lower_better, current, previous)
    return metrics


def _build_matrix_row(conn, period_type, period_key, category_mode):
    """聚合单个周期的指标，并自动查找上一周期作为对比基线。"""
    period = resolve_period(period_type, period_key)
    prev_period = resolve_period(period_type, period['prev_key'])
    start = date.fromisoformat(period['start'])
    end = date.fromisoformat(period['end'])
    prev_start = date.fromisoformat(prev_period['start'])
    prev_end = date.fromisoformat(prev_period['end'])

    current, profit_basis, _ = _matrix_aggregate(conn, start, end, category_mode)
    previous, _, _ = _matrix_aggregate(conn, prev_start, prev_end, category_mode)
    metrics = _matrix_metrics(current, previous)

    return {
        'period_key': period['key'],
        'label': period['label'],
        'start': period['start'],
        'end': period['end'],
        'status': _row_status(metrics),
        'profit_basis': profit_basis,
        'metrics': metrics,
    }


def build_metrics_matrix(period_type, period_key, category_mode=None, limit=8):
    """返回最近 N 个周期的指标矩阵，用于周月复盘的「指标矩阵」表格。

    每期自动与上一周期环比，保证口径一致。
    """
    period = resolve_period(period_type, period_key)
    periods = [period]
    for _ in range(max(1, limit) - 1):
        prev = resolve_period(period_type, periods[-1]['prev_key'])
        periods.append(prev)
    periods.reverse()  # 从旧到新，表格按时间正序展示

    rows = []
    with get_db() as conn:
        for p in periods:
            rows.append(_build_matrix_row(conn, period_type, p['key'], category_mode))
    return {
        'period_type': period_type,
        'period_key': period_key,
        'category': {'mode': category_mode or 'all', 'label': mode_to_label(category_mode)},
        'columns': MATRIX_METRICS + MATRIX_PROMO_METRICS,
        'rows': rows,
    }


def build_category_breakdown(period_type, period_key, category_mode=None):
    """返回当前周期按 products.category 拆分的指标表。"""
    period = resolve_period(period_type, period_key)
    prev_period = resolve_period(period_type, period['prev_key'])
    start = date.fromisoformat(period['start'])
    end = date.fromisoformat(period['end'])
    prev_start = date.fromisoformat(prev_period['start'])
    prev_end = date.fromisoformat(prev_period['end'])

    with get_db() as conn:
        current_groups, summarize_current = _matrix_aggregate(conn, start, end, category_mode, group_by_category=True)
        previous_groups, summarize_previous = _matrix_aggregate(
            conn, prev_start, prev_end, category_mode, group_by_category=True)

    categories = sorted(set(current_groups.keys()) | set(previous_groups.keys()))
    rows = []
    for cat in categories:
        # 两期必须各用各自的 summarize：它闭包了本期的无界数据，
        # 混用会让上期的无界花费等于本期，环比恒为 0。
        current, _ = summarize_current(current_groups.get(cat, []), cat)
        previous, _ = summarize_previous(previous_groups.get(cat, []), cat)
        metrics = _matrix_metrics(current, previous)

        # 过滤口径噪声：净销售额、投放、盈亏全部低于 100 元的行不展示。
        # 这类行（例如净销 0.03 元的「赠品」）多为错挂类目，
        # 不足以支撑一次复盘判断，留在表里只会制造噪声。
        MIN_SIGNAL = 100
        has_signal = any(
            abs(metrics[key].get(k) or 0) >= MIN_SIGNAL
            for key in ('net_sales', 'ad_spend', 'wujie_spend', 'operating_profit')
            for k in ('value', 'prev_value')
        )
        if not has_signal:
            continue

        rows.append({
            'category': _short_category(cat),
            'category_path': cat,
            'status': _row_status(metrics),
            'metrics': metrics,
        })

    # 按净销售额降序，未分类放最后
    rows.sort(key=lambda r: (r['category'] == '未分类', -(r['metrics']['net_sales']['value'] or 0)))

    return {
        'period_type': period_type,
        'period_key': period_key,
        'category': {'mode': category_mode or 'all', 'label': mode_to_label(category_mode)},
        'columns': MATRIX_METRICS + MATRIX_PROMO_METRICS,
        'period': {'label': period['label'], 'start': period['start'], 'end': period['end']},
        'rows': rows,
    }


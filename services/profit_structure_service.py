"""利润结构拆解（利润瀑布）——对齐 BI 派米口径，恒等公式已实测验证。

口径（与 `E:/www/BI采集/collectors/collect_overview_daily.py` FIELD_MAP 注释一致）：
    利润(支付预估) = 净销售额(支付) − 销售费用(sales_cost) − 自定义费用(custom_cost)
                      − 净货品成本(product_cost) − 发货费用(logistics_cost) − 其他费用(other_cost)

- 2026-08 全月验证 diff=0；custom_cost（BI「自定义费用」zdyFyAll）≈ 广告+平台费+赠品
  打包（9 月实测 756k ≈ ads 628k + platform 130k + gift 7k），展示时标注构成提示。
- 平台费(platform_fee) 是账单口径的独立列，不在利润公式内——瀑布里作为「参考桶」
  单列，不参与加总。
- 哨兵（2026-10-02 实测）：09-17/18/19 补采窗口（bi_api_full_*）费用列全 NULL 但
  operating_profit 有值/为 0。费用缺失按 NULL 处理（该桶显示「缺失」而非 0，
  否则利润被虚增）；operating_profit=0 且 payment≠0 且费用列全 NULL 的行视为
  「利润未回填哨兵」，整行剔除出恒等校验并计入 sentinel_rows。
全部只读；无数据返回 missing_inputs，不臆造 0。
"""

from datetime import date, timedelta

# 利润公式的费用桶（顺序即瀑布展示顺序；平台费是账单口径参考桶，不参与公式）。
FORMULA_BUCKETS = (
    ('sales_cost', '销售费用'),
    ('custom_cost', '自定义费用'),
    ('product_cost', '净货品成本'),
    ('logistics_cost', '发货费用'),
    ('other_cost', '其他费用'),
)
REFERENCE_BUCKETS = (
    ('platform_fee', '平台花费（账单·参考）'),
    ('gift_cost', '赠品费用（参考）'),
    ('ad_spend', '推广花费（账单·参考）'),
)

SENTINEL_PROFIT_ZERO = 0.0


def _aggregate(conn, start, end, category_label=None):
    """聚合窗口内费用列；SUM 天然跳过 NULL，各桶单独判缺失行数。"""
    scope_sql = ''
    scope_params = []
    if category_label:
        scope_sql = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
        scope_params = [category_label, category_label]
    row = conn.execute(
        f'''SELECT COALESCE(SUM(d.payment_amount), 0) AS gsv,
                   COALESCE(SUM(d.net_sales), 0) AS net_sales,
                   SUM(d.sales_cost) AS sales_cost,
                   SUM(d.custom_cost) AS custom_cost,
                   SUM(d.product_cost) AS product_cost,
                   SUM(d.logistics_cost) AS logistics_cost,
                   SUM(d.other_cost) AS other_cost,
                   SUM(d.platform_fee) AS platform_fee,
                   SUM(d.gift_cost) AS gift_cost,
                   SUM(d.ad_spend) AS ad_spend,
                   SUM(d.operating_profit) AS operating_profit,
                   COUNT(*) AS row_count,
                   SUM(CASE WHEN d.payment_amount != 0 AND d.operating_profit = 0
                             AND d.sales_cost IS NULL AND d.custom_cost IS NULL
                             AND d.product_cost IS NULL AND d.logistics_cost IS NULL
                             AND d.other_cost IS NULL
                        THEN 1 ELSE 0 END) AS sentinel_rows
            FROM daily_data d
            JOIN products p ON p.product_id = d.product_id
            WHERE d.date BETWEEN ? AND ?{scope_sql}''',
        [start, end, *scope_params],
    ).fetchone()
    return dict(row) if row else {}


def _prev_month_range(start, end):
    """对比期 = 等长的上一个自然月窗口（月复盘取上个自然月；周复盘取上周）。"""
    try:
        start_date = date.fromisoformat(str(start))
        end_date = date.fromisoformat(str(end))
        span = (end_date - start_date).days + 1
        prev_end = date.fromordinal(start_date.toordinal() - 1)
        prev_start = date.fromordinal(prev_end.toordinal() - span + 1)
        return prev_start.isoformat(), prev_end.isoformat()
    except (ValueError, TypeError):
        return None, None


def profit_structure(conn, start, end, category_label=None, compare_start=None, compare_end=None):
    """窗口利润结构：6 桶费用 + 利润 + 恒等校验 + 对比期环比。

    identity_ok：净销−Σ费用 与 SUM(operating_profit) 的差 ≤ 净销 0.5%（补采
    窗口的费用 NULL 行会被剔除哨兵后仍有残余噪声，0.5% 容差内视为同口径）。
    """
    if not start or not end:
        return {'available': False, 'missing_inputs': ['daily_data']}
    current = _aggregate(conn, start, end, category_label)
    if not current.get('row_count'):
        return {'available': False, 'missing_inputs': ['daily_data']}

    net_sales = float(current.get('net_sales') or 0)

    def profit_value():
        profit = current.get('operating_profit')
        # 月表 profit=0 是未回填哨兵的同族：整窗利润=0 且费用列全空 → 视为缺失。
        buckets = [current.get(key) for key, _ in FORMULA_BUCKETS]
        if profit == SENTINEL_PROFIT_ZERO and all(v is None for v in buckets):
            return None
        return (round(float(profit), 2) if profit is not None else None)

    profit = profit_value()
    formula_rows = []
    for key, label in FORMULA_BUCKETS:
        value = current.get(key)
        formula_rows.append({
            'key': key,
            'label': label,
            'value': (round(float(value), 2) if value is not None else None),
            'share_of_net': (round(float(value) / net_sales, 6) if value is not None and net_sales else None),
        })
    formula_rows.append({
        'key': 'operating_profit',
        'label': '利润(支付预估)',
        'value': profit,
        'share_of_net': (round(profit / net_sales, 6) if profit is not None and net_sales else None),
    })
    reference_rows = []
    for key, label in REFERENCE_BUCKETS:
        value = current.get(key)
        reference_rows.append({
            'key': key,
            'label': label,
            'value': (round(float(value), 2) if value is not None else None),
            'share_of_net': (round(float(value) / net_sales, 6) if value is not None and net_sales else None),
        })

    # 恒等校验：只对费用列齐全的行有意义；哨兵行剔除后残差应≈0。
    lhs = net_sales - sum(float(current.get(key) or 0) for key, _ in FORMULA_BUCKETS)
    identity_gap = round(lhs - float(profit or 0), 2)
    identity_ok = (abs(identity_gap) <= abs(net_sales) * 0.005) if net_sales else False
    if identity_gap and current.get('sentinel_rows'):
        identity_note = (
            f'恒等残差 {identity_gap:,.0f} 主要来自 {current["sentinel_rows"]} 行利润未回填'
            '（补采窗口费用列缺失），该窗口的费用占比仅供参考。'
        )
    else:
        identity_note = None

    # 对比期（等长前置窗口）环比：费用率口径逐桶对比。
    prev_rows = []
    prev = {}
    if compare_start and compare_end:
        prev = _aggregate(conn, compare_start, compare_end, category_label)
        prev_net = float(prev.get('net_sales') or 0)
        prev_rows = [
            {
                'key': key,
                'label': label,
                'value': (round(float(prev.get(key)), 2) if prev.get(key) is not None else None),
                'share_of_net': (round(float(prev.get(key)) / prev_net, 6)
                                 if prev.get(key) is not None and prev_net else None),
            }
            for key, label in (*FORMULA_BUCKETS, ('operating_profit', '利润(支付预估)'))
        ]

    def with_change(rows, prev_map):
        for row in rows:
            before = prev_map.get(row['key'])
            if row['value'] is None or not before or before['value'] in (None, 0):
                row['prev_value'] = None
                row['change_rate'] = None
                continue
            row['prev_value'] = before['value']
            delta = (float(row['value']) - float(before['value'])) / abs(float(before['value']))
            row['change_rate'] = round(delta, 4)
            if before['share_of_net']:
                row['share_delta_pt'] = round((row['share_of_net'] or 0) - before['share_of_net'], 6)

    if prev_rows:
        with_change(formula_rows, {row['key']: row for row in prev_rows})
        with_change(reference_rows, {row['key']: row for row in prev_rows})

    has_value = any(row['value'] is not None for row in formula_rows)
    return {
        'available': has_value,
        'window': {'start': start, 'end': end},
        'compare': ({'start': compare_start, 'end': compare_end} if prev_rows else None),
        'caliber': {
            'formula': '利润(支付预估) = 净销售额 − 销售费用 − 自定义费用 − 净货品成本 − 发货费用 − 其他费用',
            'custom_cost_note': '自定义费用（BI「自定义费用」）≈ 广告+平台费+赠品打包，构成见参考桶',
        },
        'rows': formula_rows,
        'reference': reference_rows,
        'identity': {'ok': identity_ok, 'gap': identity_gap, 'note': identity_note},
        'sentinel_rows': int(current.get('sentinel_rows') or 0),
        'row_count': int(current.get('row_count') or 0),
        'net_sales': round(net_sales, 2),
        'missing_inputs': [] if has_value else ['daily_data.costs'],
    }


def build_structure(conn, start, end, category_label=None, compare_auto=True):
    """端点入口：自动生成等长前置对比期。"""
    if compare_auto:
        compare_start, compare_end = _prev_month_range(start, end)
    else:
        compare_start = compare_end = None
    return profit_structure(conn, start, end, category_label, compare_start, compare_end)

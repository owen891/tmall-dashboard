"""叶子类目近 3 周对比看板。

按 products.category 的末级（叶子类目）聚合 daily_data，输出：
- 最近一个结束周 W0、上一周 W1、上上一周 W2
- 去年同期同长度周 Y0
- 每周的链接数、净销售、退款率、访客、转化率、客单价、加购率、
  推广花费、花费占比、利润额、利润率
- 本周相对上周（环比 mom）与相对去年同期（同比 yoy）的变化

口径说明：
- 周一定为周一到周日；W0 以「数据里出现过的最近一个周日」所在周为锚，
  避免把今天才第一天的新周当成「本周」。
- 比例指标一律用聚合后的分子/分母计算，不对单日比率取平均。
- 动销链接数 links_active = 该周期内出现过日数据的去重商品数；
  全量链接数 links_total = products 表里该叶子类目下的商品总数。
- 净销售额、推广费、利润绝对值 < 100 元的类目行视为噪声，不展示。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from db import get_db, get_shop_id
from services.category_mode_service import SOCK_LABEL, mode_to_label


def _leaf_name(category: str | None) -> str:
    text = str(category or '').strip()
    if not text:
        return '未分类'
    for sep in ('>', '/', '|', '\\'):
        if sep in text:
            text = text.split(sep)[-1].strip()
    return text or '未分类'


def _rate(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _pct(current: float | None, previous: float | None) -> dict[str, float | None]:
    """增长率：金额/链接数这类可除指标。"""
    if current is None or previous in (None, 0):
        return {'amount': None, 'rate': None}
    amount = current - previous
    return {'amount': amount, 'rate': amount / previous if previous else None}


def _anchor_weeks(conn, shop_id: str) -> dict[str, dict[str, Any]]:
    """以数据里最近一个周日所在周为 W0，向前推两周，并取去年同期。"""
    # 「最新日期」必须限定在当前店铺内，否则另一家店铺的最新数据会把
    # 本店的周锚点整体平移，三周看板全部对错周期。
    row = conn.execute(
        'SELECT MAX(date) AS latest FROM daily_data WHERE shop_id = ?', (shop_id,)
    ).fetchone()
    latest = date.fromisoformat(row['latest']) if row and row['latest'] else date.today()
    # 本周一 = 最近周日的前 6 天。latest 是周一 9.21 时，最近周日 = 9.20。
    this_sunday = latest - timedelta(days=latest.weekday() + 1) if latest.weekday() != 6 else latest
    w0_start = this_sunday - timedelta(days=6)

    def make(start: date, label: str) -> dict[str, Any]:
        end = start + timedelta(days=6)
        return {'start': start.isoformat(), 'end': end.isoformat(), 'label': label}

    weeks = {
        'w0': make(w0_start, f'本周 {w0_start.month}.{w0_start.day}-{this_sunday.day}'),
        'w1': make(w0_start - timedelta(days=7),
                   f"上周 {(w0_start - timedelta(days=7)).month}.{(w0_start - timedelta(days=7)).day}-{(this_sunday - timedelta(days=7)).day}"),
        'w2': make(w0_start - timedelta(days=14),
                   f"上上周 {(w0_start - timedelta(days=14)).month}.{(w0_start - timedelta(days=14)).day}-{(this_sunday - timedelta(days=14)).day}"),
        'y0': make(w0_start - timedelta(days=364),
                   f"去年同期 {w0_start.year - 1}.{w0_start.month}.{w0_start.day}-{this_sunday.year - 1}.{this_sunday.month}.{this_sunday.day}"),
    }
    return weeks


def _aggregate_period(conn, start: str, end: str, shop_id: str, label: str | None = None) -> dict[str, dict[str, Any]]:
    """聚合一个周期内所有商品，按叶子类目分组。"""
    extra = ""
    params = [shop_id, start, end]
    if label:
        extra = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
        params.extend([label, label])
    query = f"""
        SELECT p.category AS category,
               d.product_id AS product_id,
               SUM(COALESCE(d.net_sales, 0))        AS net_sales,
               SUM(COALESCE(d.payment_amount, 0))  AS payment_amount,
               SUM(COALESCE(d.refund_amount, 0))    AS refund_amount,
               SUM(COALESCE(d.ipv, 0))              AS ipv,
               SUM(COALESCE(d.buyers, 0))           AS buyers,
               SUM(COALESCE(d.cart_qty, 0))         AS cart_qty,
               SUM(COALESCE(d.ad_spend, 0))         AS ad_spend,
               SUM(COALESCE(d.operating_profit, 0))  AS operating_profit
        FROM daily_data d
        LEFT JOIN products p ON p.product_id = d.product_id
        WHERE d.shop_id = ? AND d.date >= ? AND d.date <= ?{extra}
        GROUP BY p.category, d.product_id
    """
    groups: dict[str, dict[str, Any]] = {}
    for row in conn.execute(query, params).fetchall():
        leaf = _leaf_name(row['category'])
        g = groups.setdefault(leaf, {
            'links': set(), 'net_sales': 0.0, 'payment_amount': 0.0,
            'refund_amount': 0.0, 'ipv': 0.0, 'buyers': 0.0,
            'cart_qty': 0.0, 'ad_spend': 0.0, 'operating_profit': 0.0,
        })
        g['links'].add(row['product_id'])
        for k in ('net_sales', 'payment_amount', 'refund_amount', 'ipv',
                  'buyers', 'cart_qty', 'ad_spend', 'operating_profit'):
            g[k] += float(row[k] or 0.0)
    return groups


def _on_sale_links_by_leaf(conn) -> dict[str, int]:
    """products 表里各叶子类目的商品总数。"""
    rows = conn.execute(
        """SELECT category FROM products
           WHERE COALESCE(status, 'active') = 'active'
             AND (shop_label = ? OR instr(',' || shop_label || ',', ',' || ? || ',') > 0)""",
        [SOCK_LABEL, SOCK_LABEL],
    ).fetchall()
    totals: dict[str, int] = {}
    for r in rows:
        leaf = _leaf_name(r['category'])
        totals[leaf] = totals.get(leaf, 0) + 1
    return totals


def summarize_week(category_mode: str | None = None, shop_id: str | None = None) -> dict[str, Any]:
    label = mode_to_label(category_mode)
    shop_id = str(shop_id or get_shop_id())
    with get_db() as conn:
        weeks = _anchor_weeks(conn, shop_id)
        # 实际覆盖天数
        for key, w in weeks.items():
            row = conn.execute(
                'SELECT COUNT(DISTINCT date) AS days, MIN(date) AS d0, MAX(date) AS d1 '
                'FROM daily_data WHERE shop_id = ? AND date >= ? AND date <= ?',
                [shop_id, w['start'], w['end']]).fetchone()
            w['covered_days'] = row['days'] or 0
            w['complete'] = w['covered_days'] == 7

        period_data = {key: _aggregate_period(conn, w['start'], w['end'], shop_id, label)
                       for key, w in weeks.items()}
        on_sale_links = _on_sale_links_by_leaf(conn)

        leaves = set(on_sale_links)
        for data in period_data.values():
            leaves.update(data.keys())

        rows = []
        totals_week: dict[str, dict[str, Any]] = {}
        for leaf in leaves:
            week_metrics: dict[str, dict[str, Any]] = {}
            for key, data in period_data.items():
                g = data.get(leaf)
                if not g:
                    week_metrics[key] = None
                    continue
                net_sales = g['net_sales'] or None
                week_metrics[key] = {
                    'links_active': len(g['links']),
                    'net_sales': net_sales,
                    'payment_amount': g['payment_amount'] or None,
                    'refund_amount': g['refund_amount'] or None,
                    'refund_rate': _rate(g['refund_amount'], g['payment_amount']),
                    'ipv': int(g['ipv']) or None,
                    'buyers': int(g['buyers']) or None,
                    'cvr': _rate(g['buyers'], g['ipv']),
                    'aov': _rate(g['payment_amount'], g['buyers']),
                    'cart_rate': _rate(g['cart_qty'], g['ipv']),
                    'cart_qty': int(g['cart_qty']) or None,
                    'ad_spend': g['ad_spend'] or None,
                    'ad_ratio': _rate(g['ad_spend'], net_sales),
                    'profit': g['operating_profit'] or None,
                    'profit_rate': _rate(g['operating_profit'], net_sales),
                }
            # 噪声过滤：任何一周的净额/广告费/利润绝对值都不足 100 元，视为噪声行
            signal = week_metrics.get('w0') or week_metrics.get('w1') or week_metrics.get('w2')
            if signal:
                if not any(abs(signal.get(k) or 0) >= 100
                           for k in ('net_sales', 'ad_spend', 'profit')):
                    continue
            w0 = week_metrics.get('w0') or {}
            w1 = week_metrics.get('w1') or {}
            y0 = week_metrics.get('y0') or {}

            def field_change(field: str) -> dict[str, float | None]:
                return {
                    'mom': _pct(w0.get(field), w1.get(field)),
                    'yoy': _pct(w0.get(field), y0.get(field)),
                }

            row = {
                'leaf': leaf,
                'weeks': week_metrics,
                'links_on_sale': on_sale_links.get(leaf, 0),
                'links_active': field_change('links_active'),
                'net_sales': field_change('net_sales'),
                'ad_spend': field_change('ad_spend'),
                'profit': field_change('profit'),
            }
            # 占比类指标用百分点差
            for field in ('ad_ratio', 'profit_rate'):
                a, b = w0.get(field), w1.get(field)
                row[field + '_mom_pp'] = None if a is None or b is None else a - b
                a, b = w0.get(field), y0.get(field)
                row[field + '_yoy_pp'] = None if a is None or b is None else a - b
            rows.append(row)

        rows.sort(key=lambda r: (
            r['leaf'] == _leaf_name(None),
            -((r['weeks'].get('w0') or {}).get('net_sales') or 0),
        ))

        # 全店合计行
        for key, w in weeks.items():
            agg = period_data[key]
            sums = {'net_sales': 0.0, 'payment_amount': 0.0, 'refund_amount': 0.0,
                    'ipv': 0.0, 'buyers': 0.0, 'cart_qty': 0.0,
                    'ad_spend': 0.0, 'operating_profit': 0.0}
            link_set: set = set()
            for g in agg.values():
                for k in sums:
                    sums[k] += g[k]
                link_set |= g['links']
            net = sums['net_sales'] or None
            totals_week[key] = {
                'links_active': len(link_set),
                'net_sales': net,
                'refund_rate': _rate(sums['refund_amount'], sums['payment_amount']),
                'ipv': int(sums['ipv']) or None,
                'cvr': _rate(sums['buyers'], sums['ipv']),
                'aov': _rate(sums['payment_amount'], sums['buyers']),
                'cart_rate': _rate(sums['cart_qty'], sums['ipv']),
                'ad_spend': sums['ad_spend'] or None,
                'ad_ratio': _rate(sums['ad_spend'], net),
                'profit': sums['operating_profit'] or None,
                'profit_rate': _rate(sums['operating_profit'], net),
            }

        return {
            'weeks': weeks,
            'rows': rows,
            'totals': totals_week,
            'data_quality': {
                'coverage_end': weeks['w0']['end'],
                'w0_covered_days': weeks['w0']['covered_days'],
                'source_tables': ['daily_data', 'products'],
            },
        }

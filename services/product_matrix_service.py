"""货品矩阵地图（对齐 XMind「货品-品类 / 产品分层」，2026-10-02 用户拍板口径）。

三分法全自动推断，判定条件（费比口径 = 推广花费 ÷ GSV，用户拍板；与
problem_items 的 30% 阈值同源，勿与净费比混）：
- 引流款：本期有推广花费 且 费比 ≥ 30%（付费主投，费比控制在 30%+）；
- 利润款：经营利润 > 0 且 费比 < 10%（低价扫流，费比 10% 内）；
- 动销款：本期有动销（GSV>0）且 无推广花费（不推广）；
- 亏损观察：经营利润 < 0（不论花费，优先排查）；
- 未分层：其余（无动销无花费的新品/在架等）。

分层结果写回 products.tier（用户拍板：写回），但只写分层标签，
不覆盖人工已设置的值——人工分层优先，算法只填空与更新算法自填的行。
"""

from datetime import date, timedelta

from db import get_shop_id
from services.tier_source import TIER_SOURCE_MATRIX as TIER_SOURCE_TAG
from services.tier_source import is_tier_locked

# tier 写回来源标记：非算法来源的既有值（人工或其他系统）不覆盖。
# 常量定义统一放在 services/tier_source.py，避免两套算法各自维护一份标记集合。
# 写回仅针对算法可判定的标签；「未分层」不写（留空保持可推断态）。
TIER_WRITABLE_LABELS = ('引流款', '利润款', '动销款')

HIGH_EXPENSE_RATIO = 0.30   # 引流款费比下限（XMind：费比控制在 30%+）
LOW_EXPENSE_RATIO = 0.10    # 利润款费比上限（XMind：低价扫流费比 10% 内）


def resolve_period(conn, period=None, shop_id=None):
    """缺省取 daily_data 最近有数据的完整月（当天在该月内则取上个月）。"""
    if period:
        return str(period)[:7]
    shop_id = str(shop_id or get_shop_id())
    # 「最近有数据的月份」必须限定店铺：多店表里另一家店铺的最新日期
    # 会把本店默认周期整体带偏（甚至指向本店完全没有数据的月份）。
    row = conn.execute(
        'SELECT MAX(date) AS latest FROM daily_data WHERE shop_id = ?', (shop_id,)
    ).fetchone()
    latest = str(row['latest'])[:7] if row and row['latest'] else None
    if not latest:
        return None
    # 进行中的月份只覆盖部分天数，费比/分层噪声大，退上一个月。
    today = date.today().isoformat()
    if latest == today[:7]:
        year, month = int(latest[:4]), int(latest[5:7])
        prev = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
        return prev.isoformat()[:7]
    return latest


def _period_range(month_key):
    year, month = int(month_key[:4]), int(month_key[5:7])
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _classify(row):
    spend, gsv, profit = row['ad_spend'], row['gsv'], row['operating_profit']
    ad_ratio = (float(spend) / float(gsv)) if spend not in (None, 0) and gsv not in (None, 0) else None
    loss = profit is not None and float(profit) < 0
    # 分层先按推广角色判（引流/利润/动销是策略定位，与盈亏正交），
    # 亏损不吞掉分层——主力款亏损仍应显示其角色，亏损以 flags.loss 另行标注。
    if ad_ratio is not None and ad_ratio >= HIGH_EXPENSE_RATIO:
        return '引流款', ad_ratio
    if gsv not in (None, 0) and spend in (None, 0):
        # 「不推广」是策略层判定，优先于利润款：无花费的盈利款也是动销款。
        return '动销款', ad_ratio
    if (profit is not None and float(profit) > 0
            and (ad_ratio is None or ad_ratio < LOW_EXPENSE_RATIO)):
        return '利润款', ad_ratio
    if loss:
        return '亏损观察', ad_ratio
    return '未分层', ad_ratio


def product_matrix(conn, period=None, category_label=None, compare_month=None, shop_id=None):
    """按周期聚合单品并自动分层；返回散点 + 分层统计 + 类目汇总。

    只取「本期有动销或有花费」的商品（其余归未取样子集，不进散点）；
    compare_month 用于利润/费比环比（缺省为上一个自然月，可关）。
    """
    shop_id = str(shop_id or get_shop_id())
    month_key = resolve_period(conn, period, shop_id)
    if not month_key:
        return {'available': False, 'missing_inputs': ['daily_data'], 'month': None}
    start, end = _period_range(month_key)

    scope_sql = ' AND d.shop_id = ?'
    scope_params = [shop_id]
    if category_label:
        scope_sql += " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
        scope_params.extend([category_label, category_label])

    # tier_source 列可能尚未补齐（writeback 才 ALTER），读取侧按有无该列分支。
    has_tier_source = 'tier_source' in {row[1] for row in conn.execute('PRAGMA table_info(products)').fetchall()}
    source_sql = ', MAX(p.tier_source) AS tier_source' if has_tier_source else ", '' AS tier_source"
    rows = conn.execute(
        f'''SELECT d.product_id,
                   COALESCE(SUM(d.payment_amount), 0) AS gsv,
                   COALESCE(SUM(d.net_sales), 0) AS net_sales,
                   COALESCE(SUM(d.refund_amount), 0) AS refund_amount,
                   COALESCE(SUM(d.ipv), 0) AS visitors,
                   COALESCE(SUM(d.ad_spend), 0) AS ad_spend,
                   SUM(d.operating_profit) AS operating_profit,
                   MAX(p.title) AS title, MAX(p.category) AS category,
                   MAX(p.tier) AS tier{source_sql}
            FROM daily_data d
            JOIN products p ON p.product_id = d.product_id
            WHERE d.date BETWEEN ? AND ?{scope_sql}
            GROUP BY d.product_id
            HAVING SUM(d.payment_amount) > 0 OR SUM(d.ad_spend) > 0''',
        [start, end, *scope_params],
    ).fetchall()

    items = []
    for row in rows:
        gsv = float(row['gsv'] or 0)
        spend = float(row['ad_spend'] or 0)
        profit = row['operating_profit']
        label, ad_ratio = _classify({
            'ad_spend': spend, 'gsv': gsv, 'operating_profit': profit,
        })
        items.append({
            'product_id': row['product_id'],
            'title': row['title'] or row['product_id'],
            'category': row['category'] or '',
            'gsv': round(gsv, 2),
            'net_sales': round(float(row['net_sales'] or 0), 2),
            'visitors': int(row['visitors'] or 0),
            'ad_spend': round(spend, 2),
            'ad_ratio': (round(ad_ratio, 6) if ad_ratio is not None else None),
            'loss': bool(profit is not None and float(profit) < 0),
            'operating_profit': (round(float(profit), 2) if profit is not None else None),
            'profit_rate': (round(float(profit) / gsv, 6) if profit is not None and gsv else None),
            'segment': label,
            'stored_tier': row['tier'] or '',
        })

    stats = {}
    for item in items:
        entry = stats.setdefault(item['segment'], {
            'segment': item['segment'], 'count': 0, 'net_sales': 0.0,
            'ad_spend': 0.0, 'gsv': 0.0, 'visitors': 0, 'loss_count': 0,
        })
        entry['count'] += 1
        entry['net_sales'] += item['net_sales']
        entry['ad_spend'] += item['ad_spend']
        entry['gsv'] += item['gsv']
        entry['visitors'] += item['visitors']
        if item['loss']:
            entry['loss_count'] += 1
    total_net = sum(entry['net_sales'] for entry in stats.values())
    total_visitors = sum(entry['visitors'] for entry in stats.values())
    stats_list = []
    for entry in stats.values():
        spend_ratios = [item['ad_ratio'] for item in items
                        if item['segment'] == entry['segment'] and item['ad_ratio'] is not None]
        stats_list.append({
            **entry,
            'net_sales': round(entry['net_sales'], 2),
            'ad_spend': round(entry['ad_spend'], 2),
            'net_sales_share': (round(entry['net_sales'] / total_net, 6) if total_net else None),
            'visitors_share': (round(entry['visitors'] / total_visitors, 6) if total_visitors else None),
            'avg_ad_ratio': (round(sum(spend_ratios) / len(spend_ratios), 4) if spend_ratios else None),
        })
    order = {'引流款': 0, '利润款': 1, '动销款': 2, '亏损观察': 3, '未分层': 4}
    stats_list.sort(key=lambda entry: order.get(entry['segment'], 9))

    category_totals = {}
    for item in items:
        entry = category_totals.setdefault(item['category'] or '未分类', {'count': 0, 'net_sales': 0.0})
        entry['count'] += 1
        entry['net_sales'] += item['net_sales']
    categories = sorted(
        ({'category': key, 'count': value['count'], 'net_sales': round(value['net_sales'], 2)}
         for key, value in category_totals.items()),
        key=lambda entry: entry['net_sales'], reverse=True,
    )[:8]

    return {
        'available': bool(items),
        'month': month_key,
        'period': {'start': start, 'end': end},
        'caliber': {
            'ad_ratio': '推广花费 ÷ GSV',
            'rules': [
                {'segment': '引流款', 'rule': '本期有推广花费 且 费比≥30%（付费主投）'},
                {'segment': '利润款', 'rule': '经营利润>0 且 费比<10%（低价扫流）'},
                {'segment': '动销款', 'rule': '本期有动销（GSV>0）且 无推广花费（不推广）'},
                {'segment': '亏损观察', 'rule': '经营利润<0 且不满足上述角色（优先排查）'},
                {'note': '亏损与角色正交：引流/利润/动销款中亏损的商品带 loss 标志，不改变分层'},
            ],
        },
        'stats': stats_list,
        'categories': categories,
        'items': items,
        'missing_inputs': [] if items else ['daily_data'],
    }


def apply_tier_writeback(conn, matrix, operator='matrix'):
    """把算法分层写回 products.tier（用户拍板：写回）。

    覆盖规则：tier 为空、或 tier_source 在算法标记集合内（算法自填）的行才更新；
    有档位但来源不是算法标记（含来源为空）的行绝不覆盖。

    2026-10-22 修正：原判定是 ``if current_source and current_source != TAG``，
    当 ``tier_source`` 为空时直接放行，与 ``scripts/sync_five_dim_tier.is_locked``
    （空来源 → 锁定）语义相反。同一个空值两个算法一边保护一边覆盖，
    取决于谁先跑。现统一走 ``services.tier_source.is_tier_locked``。
    products.tier_source 列不存在时自动补列（ALTER TABLE ADD COLUMN）。
    """
    if not matrix.get('available'):
        return {'updated': 0, 'skipped_locked': 0, 'reason': 'no-data'}
    cols = {row[1] for row in conn.execute('PRAGMA table_info(products)').fetchall()}
    if 'tier_source' not in cols:
        conn.execute("ALTER TABLE products ADD COLUMN tier_source TEXT NOT NULL DEFAULT ''")
    updated = 0
    skipped_locked = 0
    for item in matrix['items']:
        label = item['segment']
        if label not in TIER_WRITABLE_LABELS:
            continue
        row = conn.execute(
            'SELECT tier, tier_source FROM products WHERE product_id = ?',
            (item['product_id'],),
        ).fetchone()
        if row is None:
            continue
        current_tier, current_source = row['tier'] or '', row['tier_source'] or ''
        if is_tier_locked(current_tier, current_source):
            skipped_locked += 1
            continue
        if current_tier == label and current_source == TIER_SOURCE_TAG:
            continue
        conn.execute(
            "UPDATE products SET tier = ?, tier_source = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?",
            (label, TIER_SOURCE_TAG, item['product_id']),
        )
        updated += 1
    return {'updated': updated, 'skipped_locked': skipped_locked}

# -*- coding: utf-8 -*-
"""构建「推广分析复盘」数据集（近30天，指定品类，叠加单品利润 + 主图）。

用法：python scripts/promo_review/build_data.py [品类标签]
      默认 'sock'（=默认品类）；传 'all' 表示不限品类。

口径（与月复盘「广告复盘」模块一致）：
- 汇总层（花费/投产/费比/净费比/利润）取自 daily_data（BI 账单口径），品类按
  products.shop_label token 匹配。
- 渠道拆解：**品类模式**下 campaign 粒度行不带商品映射、无法过滤，故走
  promotion_creative_daily（商品×渠道，覆盖 关键词/人群/店铺直达）+ 计划→商品
  1:1 精确归因补「全站推广」→ 即 services.period_context._ads_channel_totals，
  天然是「部分口径」（多商品全站计划无商品级明细），报告须标注。
- 单品层：daily_data 按商品聚合利润/花费/净销（同源、口径自洽），再用
  promotion_daily_facts(grain='product',channel='全部') 补归因成交/直接成交/加购/拉新。
- 主图：services.period_context._product_meta（products.image_url + 推广明细兜底）。
- 一律不做均摊；比率由窗口总量重推，不用均值。
"""
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.period_context import (  # noqa: E402
    _totals_for_range, _derive, _ads_channel_totals, _ads_direct_totals, _product_meta,
)
from services.category_mode_service import mode_to_label  # noqa: E402

DB = 'data/dashboard.db'

# 周期档案：每个周期定义「本期 / 环比基期 / 同比两侧 / 成本齐备窗口」。
# 用法：python build_data.py <品类> <周期>   （周期缺省 near30）
PERIODS = {
    'near30': {
        'name': '近 30 天', 'title': '近 30 天',
        'cur': ('2026-09-07', '2026-10-06'),
        'prev': ('2026-08-08', '2026-09-06'),
        'yoy_cur': ('2026-09-07', '2026-09-30'),
        'yoy_prev': ('2025-09-07', '2025-09-30'),
        'cost': ('2026-09-07', '2026-09-30'),
        'prev_desc': '前 30 天',
        'yoy_desc': '去年同期对齐窗口',
        'monthly_yoy': ('2026-09', '2025-09'),
        'cost_note': '10-01~10-06 费用列在补采窗口内为 NULL，无法拆桶，故不纳入本块。',
        'yoy_note': '同比对齐至 09-07~09-30（两侧同期 24 天）：2025-10 无日粒度数据，30 天窗口无法整段同比。',
    },
    'sept': {
        'name': '2026 年 9 月', 'title': '9 月',
        'cur': ('2026-09-01', '2026-09-30'),
        'prev': ('2026-08-01', '2026-08-31'),
        'yoy_cur': ('2026-09-01', '2026-09-30'),
        'yoy_prev': ('2025-09-01', '2025-09-30'),
        'cost': ('2026-09-01', '2026-09-30'),
        'prev_desc': '上月整月（8 月 1~31 日）',
        'yoy_desc': '去年同期（2025 年 9 月）',
        'monthly_yoy': ('2026-09', '2025-09'),
        'cost_note': '',
        'yoy_note': '两侧均为完整自然月，逐日对齐，无需折算。',
    },
    'oct': {
        'name': '2026 年 10 月（1~6 日）', 'title': '10 月',
        'cur': ('2026-10-01', '2026-10-06'),
        'prev': ('2026-09-01', '2026-09-06'),
        'yoy_cur': ('2026-10-01', '2026-10-06'),
        'yoy_prev': ('2025-10-01', '2025-10-06'),
        'cost': ('2026-10-01', '2026-10-06'),
        'prev_desc': '上月同期（9 月 1~6 日）',
        'yoy_desc': '去年同期（2025 年 10 月 1~6 日）',
        'monthly_yoy': ('2026-10', '2025-10'),
        'cost_note': '本期 6 天费用列在 BI 补采窗口内为 NULL（BI 未导出 10 月成本），利润结构不可拆桶。',
        'yoy_note': '两侧同为 6 个自然日（10 月 1~6 日），逐日对齐。',
    },
    # 自然周（周一~周日）。2026-10-19 是周一，故最近一个完整自然周为 10-12~10-18。
    'week': {
        'name': '本周（10-12~10-18）', 'title': '本周',
        'cur': ('2026-10-12', '2026-10-18'),
        'prev': ('2026-10-05', '2026-10-11'),
        'yoy_cur': ('2026-10-12', '2026-10-18'),
        'yoy_prev': ('2025-10-12', '2025-10-18'),
        'cost': ('2026-10-12', '2026-10-15'),
        'prev_desc': '上周（10-05~10-11）',
        'yoy_desc': '去年同期（2025-10-12~10-18）',
        'monthly_yoy': ('2026-10', '2025-10'),
        'cost_note': ('10-16~10-18 三天的费用列在 BI 字段窗口内为 NULL（API 源不返回成本明细，'
                      '需等窗口过后滚动补采或 Excel 导入回填），故利润结构只覆盖成本齐备的 4 天；'
                      '本期汇总层的净利润仍取 BI 利润列，覆盖全部 7 天。'),
        'yoy_note': ('2025 年 10 月在 daily_data 无任何日粒度数据（历史只采到 2025-09），'
                     '同比两侧不可比 → 同比留空，不臆造。'),
        # 双11 活动时间轴（运营提供的平台规则，外部事实，非数据推测）。
        # 用于把「本期为什么跌」拆成「活动节奏」而不是笼统归因。
        'campaign': {
            'name': '2026 天猫双11',
            'timeline': [
                ('预售定金', '2026-10-15 20:00', '2026-10-20 17:59', '付定金锁客，成交计入尾款日'),
                ('现货预热', '2026-10-17 00:00', '2026-10-20 19:59', '加购/收藏蓄水，用户等开卖'),
                ('现货开卖', '2026-10-20 20:00', '2026-11-13 23:59', '收割期，含尾款支付'),
            ],
            # 阶段切分：**互斥**，可相加（否则各段之和不等于本期合计）。
            # 边界按活动开启日归入新阶段（10-15 20:00 开启 → 10-16 起整日计入定金期）。
            'phases': [
                ('大促尾波', '2026-10-12', '2026-10-12',
                 '承接上一波大促（10-07~10-08 峰值）的余温'),
                ('定金前平销', '2026-10-13', '2026-10-15',
                 '定金期尚未开启，正常平销'),
                ('定金期+预热', '2026-10-16', '2026-10-18',
                 '10-15 20:00 定金开启、10-17 00:00 现货预热开启，用户锁客延后成交'),
            ],
            # 与上面互斥分段不同，这是「纯现货预热」切片（10-17 起），用于单独看预热强度
            'overlap_slice': ('现货预热期内', '2026-10-17', '2026-10-18',
                              '仅统计 10-17 00:00 现货预热开启后的两天'),
            'harvest_start': '2026-10-20',
        },
    },
}

raw_label = (sys.argv[1] if len(sys.argv) > 1 else 'sock').strip()
period_key = (sys.argv[2] if len(sys.argv) > 2 else 'near30').strip()
if period_key not in PERIODS:
    raise SystemExit(f'未知周期 {period_key}，可选：{", ".join(PERIODS)}')
PERIOD = PERIODS[period_key]

CUR = PERIOD['cur']
PREV = PERIOD['prev']
YOY_CUR = PERIOD['yoy_cur']
YOY_PREV = PERIOD['yoy_prev']
COST_START, COST_END = PERIOD['cost']

CATEGORY = None if raw_label in ('all', '') else (mode_to_label(raw_label) or raw_label)

c = sqlite3.connect(DB, timeout=30)
c.row_factory = sqlite3.Row

CAT_SQL = ''
CAT_PARAMS = []
if CATEGORY:
    CAT_SQL = " AND (p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
    CAT_PARAMS = [CATEGORY, CATEGORY]


def rows(sql, params=()):
    return [dict(r) for r in c.execute(sql, params).fetchall()]


def one(sql, params=()):
    r = c.execute(sql, params).fetchone()
    return dict(r) if r else {}


out = {
    'window': {'cur': CUR, 'prev': PREV, 'cost_window': [COST_START, COST_END]},
    'period': {
        'key': period_key, 'name': PERIOD['name'], 'title': PERIOD['title'],
        'prev_desc': PERIOD['prev_desc'], 'yoy_desc': PERIOD['yoy_desc'],
        'monthly_yoy': list(PERIOD['monthly_yoy']),
        'cost_note': PERIOD['cost_note'], 'yoy_note': PERIOD['yoy_note'],
        'asof': CUR[1],
    },
    'category': {'label': CATEGORY, 'filtered': bool(CATEGORY)},
}

# ---------- 1) 汇总（daily_data，服务层同源口径） ----------
tc = _totals_for_range(c, CUR[0], CUR[1], CATEGORY)
tp = _totals_for_range(c, PREV[0], PREV[1], CATEGORY)
cur_d, prev_d = _derive(tc), _derive(tp)
# _derive 不含利润率（利润/净销售额），此处补上；净销为 0 时不臆造。
for d in (cur_d, prev_d):
    ns = d.get('net_sales') or 0
    d['profit_rate'] = (d['profit'] / ns) if ns else None
out['summary'] = {'current': cur_d, 'prev': prev_d}
out['summary']['current']['days'] = int(tc.get('day_count') or 0)
out['summary']['current']['prods'] = int(tc.get('product_count') or 0)
out['summary']['prev']['days'] = int(tp.get('day_count') or 0)
out['summary']['prev']['prods'] = int(tp.get('product_count') or 0)

# ---------- 1b) 同比 ----------
# 同比窗口由周期档案给出（YOY_CUR / YOY_PREV），两侧天数一致、逐日对齐，不做折算。


def aligned_totals(rng):
    t = _totals_for_range(c, rng[0], rng[1], CATEGORY)
    d = _derive(t)
    ns = d.get('net_sales') or 0
    d['profit_rate'] = (d['profit'] / ns) if ns else None
    d['days'] = int(t.get('day_count') or 0)
    d['prods'] = int(t.get('product_count') or 0)
    return d


out['summary']['yoy'] = {
    'window_cur': list(YOY_CUR), 'window_prev': list(YOY_PREV),
    'current': aligned_totals(YOY_CUR), 'prev': aligned_totals(YOY_PREV),
    'note': PERIOD['yoy_note'],
}

# 护栏：同比窗口若日粒度缺失，_totals_for_range 会**回退到整月快照**，
# 拿「整月」去比「本期 N 天」是伪同比。这里实测日行数，缺失即置空并说明。
from datetime import date as _date  # noqa: E402


def _daily_rows_in(rng):
    return c.execute(
        f'SELECT COUNT(*) FROM daily_data d JOIN products p ON p.product_id = d.product_id '
        f'WHERE d.date BETWEEN ? AND ?{CAT_SQL}', [rng[0], rng[1], *CAT_PARAMS]).fetchone()[0]


def _span_days(rng):
    a = _date.fromisoformat(rng[0]); b = _date.fromisoformat(rng[1])
    return (b - a).days + 1


_cov = {'cur_rows': _daily_rows_in(YOY_CUR), 'prev_rows': _daily_rows_in(YOY_PREV)}
_cov['cur_days'], _cov['prev_days'] = _span_days(YOY_CUR), _span_days(YOY_PREV)
out['summary']['yoy']['coverage'] = _cov
# 基线覆盖度告警：去年同期日行数显著少于本期 → 同比被系统性低估（例：2025-09 只采到 ~27% 商品）。
if _cov['cur_rows'] and _cov['prev_rows'] and _cov['prev_rows'] < _cov['cur_rows'] * 0.6:
    _ratio = _cov['prev_rows'] / _cov['cur_rows']
    out['summary']['yoy']['baseline_warn'] = (
        f'去年同期窗口日粒度仅覆盖 {_ratio * 100:.0f}%（{_cov["prev_rows"]:,} 行 vs 本期 {_cov["cur_rows"]:,} 行），'
        f'同比基数被系统性低估 → 下方同比数值仅供参考，补采完整后重跑才可信。')
if _cov['cur_rows'] == 0 or _cov['prev_rows'] == 0:
    _empty = {k: None for k in ('gsv', 'net_sales', 'ad_spend', 'profit', 'roi',
                                'ad_ratio', 'net_expense_ratio', 'profit_rate')}
    for _side in ('current', 'prev'):
        out['summary']['yoy'][_side] = {**_empty, 'days': 0, 'prods': 0}
    out['summary']['yoy']['unavailable'] = True
    _missing = [w for w, n in ((YOY_CUR, _cov['cur_rows']), (YOY_PREV, _cov['prev_rows'])) if n == 0]
    out['summary']['yoy']['note'] = (
        f'同比窗口 {_missing[0][0]}~{_missing[0][1]} 在 daily_data 无日粒度数据，'
        f'取数会回退整月快照、与本期 {_span_days(CUR)} 天不可比 → 同比留空（不臆造）。'
        f'补采完成后重跑即可回填。')


def month_totals(month):
    return one(f"""SELECT COUNT(*) n,
                          COALESCE(SUM(m.payment_amount),0) gsv,
                          COALESCE(SUM(m.net_sales),0) net_sales,
                          COALESCE(SUM(m.ad_spend),0) ad_spend,
                          SUM(m.operating_profit) profit
                   FROM monthly_data m JOIN products p ON p.product_id = m.product_id
                   WHERE m.month = ?{CAT_SQL}""", [month, *CAT_PARAMS])


# 整月同比参考：两侧均取自 monthly_data（完整自然月），完全可比。
_my_cur, _my_prev = PERIOD['monthly_yoy']
_mc, _mp = month_totals(_my_cur), month_totals(_my_prev)
_mc['month'], _mp['month'] = _my_cur, _my_prev
out['summary']['monthly_yoy'] = {'current': _mc, 'prev': _mp}

# ---------- 2) 渠道拆解（品类口径：创意级 + 计划归因补全站） ----------
ch_c = _ads_channel_totals(c, CUR[0], CUR[1], CATEGORY) or {}
ch_p = _ads_channel_totals(c, PREV[0], PREV[1], CATEGORY) or {}
prev_map = {g['name']: g for g in ch_p.get('groups', [])}
ch_list = []
for g in ch_c.get('groups', []):
    p = prev_map.get(g['name'], {})
    g = dict(g)
    g['prev_spend'] = p.get('ad_spend')
    g['spend_change'] = ((g['ad_spend'] - p['ad_spend']) / abs(p['ad_spend'])
                         if p.get('ad_spend') else None)
    ch_list.append(g)
out['channels'] = {
    'current': ch_list,
    'prev': ch_p.get('groups', []),
    'total_spend': sum(g.get('ad_spend') or 0 for g in ch_list),
    'partial': bool(ch_c.get('partial')),
    'source': ch_c.get('source'),
    'missing_inputs': ch_c.get('missing_inputs'),
}

# ---------- 3) 单品层 ----------
prod_daily = {r['product_id']: r for r in rows(f"""
    SELECT d.product_id,
           COALESCE(SUM(d.payment_amount),0) gsv,
           COALESCE(SUM(d.net_sales),0) net_sales,
           COALESCE(SUM(d.ad_spend),0) ad_spend,
           COALESCE(SUM(d.operating_profit),0) profit,
           COALESCE(SUM(d.payment_qty),0) qty,
           COALESCE(SUM(d.buyers),0) buyers,
           COALESCE(SUM(d.ipv),0) ipv,
           COALESCE(SUM(d.cart_users),0) cart_users
    FROM daily_data d JOIN products p ON p.product_id = d.product_id
    WHERE d.date BETWEEN ? AND ?{CAT_SQL}
    GROUP BY d.product_id""", [CUR[0], CUR[1], *CAT_PARAMS])}

# 单品级「引导访问潜客占比」：万相台 inshopPotentialUv / inshopUv（单品日粒度）。
# 已逐行验证平台字段 inshopPotentialUvRate 与该式完全一致（714/714，0 例外）。
# 注意：单品口径**不可相加**——同一用户逛多个商品会重复计数，
#       各单品之和必然大于店铺账户口径，所以这里只在单品行展示，不做店铺汇总。
lead_by_product = {}
lead_by_date = {}
try:
    for _r in rows(f"""SELECT l.product_id,
                              COALESCE(SUM(l.inshop_uv),0) uv,
                              COALESCE(SUM(l.potential_uv),0) pot
                       FROM promotion_lead_daily l JOIN products p ON p.product_id = l.product_id
                       WHERE l.date BETWEEN ? AND ?{CAT_SQL}
                       GROUP BY l.product_id""",
                   [CUR[0], CUR[1], *CAT_PARAMS]):
        _uv = float(_r.get('uv') or 0)
        _pot = float(_r.get('pot') or 0)
        if _uv > 0 and _pot > 0:
            lead_by_product[_r['product_id']] = round(_pot / _uv, 6)
except Exception:
    lead_by_product = {}

try:
    for _r in rows(f"""SELECT l.date d,
                              COALESCE(SUM(l.inshop_uv),0) uv,
                              COALESCE(SUM(l.potential_uv),0) pot
                       FROM promotion_lead_daily l JOIN products p ON p.product_id = l.product_id
                       WHERE l.date BETWEEN ? AND ?{CAT_SQL}
                       GROUP BY l.date""",
                   [CUR[0], CUR[1], *CAT_PARAMS]):
        _uv = float(_r.get('uv') or 0)
        _pot = float(_r.get('pot') or 0)
        lead_by_date[_r['d']] = {
            'inshop_uv': int(_uv),
            'potential_uv': int(_pot),
            'lead_ratio': round(_pot / _uv, 6) if _uv else None,
        }
except Exception:
    lead_by_date = {}

promo = {r['product_id']: r for r in rows(f"""
    SELECT f.product_id,
           SUM(f.ad_spend) spend,
           SUM(f.attributed_payment_amount) attr,
           SUM(f.direct_payment_amount) direct,
           SUM(COALESCE(f.cart_adds,0)) carts,
           SUM(COALESCE(f.new_buyers,0)) new_buyers,
           SUM(COALESCE(f.clicks,0)) clicks,
           SUM(COALESCE(f.impressions,0)) impressions,
           SUM(COALESCE(f.payment_buyers,0)) payment_buyers
    FROM promotion_daily_facts f
    LEFT JOIN products p ON p.product_id = f.product_id
    WHERE f.date BETWEEN ? AND ? AND f.grain='product' AND f.channel='全部'
      AND f.product_id NOT LIKE '-%'{CAT_SQL}
    GROUP BY f.product_id""", [CUR[0], CUR[1], *CAT_PARAMS])}

meta = _product_meta(c, set(prod_daily) | set(promo))


def daily_by_product(rng):
    return {r['product_id']: r for r in rows(f"""
        SELECT d.product_id,
               COALESCE(SUM(d.net_sales),0) net_sales,
               COALESCE(SUM(d.operating_profit),0) profit
        FROM daily_data d JOIN products p ON p.product_id = d.product_id
        WHERE d.date BETWEEN ? AND ?{CAT_SQL}
        GROUP BY d.product_id""", [rng[0], rng[1], *CAT_PARAMS])}


def promo_by_product(rng):
    return {r['product_id']: r for r in rows(f"""
        SELECT f.product_id, SUM(f.ad_spend) spend
        FROM promotion_daily_facts f
        LEFT JOIN products p ON p.product_id = f.product_id
        WHERE f.date BETWEEN ? AND ? AND f.grain='product' AND f.channel='全部'
          AND f.product_id NOT LIKE '-%'{CAT_SQL}
        GROUP BY f.product_id""", [rng[0], rng[1], *CAT_PARAMS])}


# 单品对比列：环比（前 30 天）、同比（09-07~09-30 同期 24 天，两侧同窗口）。
prev_daily, prev_promo = daily_by_product(PREV), promo_by_product(PREV)
yoy_daily_cur, yoy_daily_prev = daily_by_product(YOY_CUR), daily_by_product(YOY_PREV)
yoy_promo_cur, yoy_promo_prev = promo_by_product(YOY_CUR), promo_by_product(YOY_PREV)


def _chg(cur, prev, min_base=0.0):
    """变化率；基数过小（< min_base）或缺失时返回 None —— 不臆造极端百分比。"""
    if cur is None or prev in (None, 0):
        return None
    if abs(prev) < min_base:
        return None
    return (cur - prev) / abs(prev)


def merge(pid):
    d = prod_daily.get(pid, {})
    p = promo.get(pid, {})
    m = meta.get(pid, {})
    net = d.get('net_sales') or 0
    gsv = d.get('gsv') or 0
    ad_bill = d.get('ad_spend') or 0
    profit = d.get('profit') or 0
    spend, attr, direct = p.get('spend'), p.get('attr'), p.get('direct')
    pd_ = prev_daily.get(pid, {})
    yc, yp = yoy_daily_cur.get(pid, {}), yoy_daily_prev.get(pid, {})
    return {
        'product_id': pid,
        'title': m.get('title') or pid,
        'image_url': m.get('image_url') or '',
        'shop_label': m.get('shop_label'),
        'gsv': round(gsv, 2), 'net_sales': round(net, 2),
        'ad_spend_bill': round(ad_bill, 2),
        'profit': round(profit, 2),
        'prev_net_sales': round(pd_.get('net_sales') or 0, 2),
        'prev_profit': round(pd_.get('profit') or 0, 2),
        'prev_promo_spend': round(prev_promo.get(pid, {}).get('spend') or 0, 2),
        'net_sales_change': _chg(net, pd_.get('net_sales'), 500),
        'profit_change': _chg(profit, pd_.get('profit'), 200),
        'promo_spend_change': _chg(spend, prev_promo.get(pid, {}).get('spend'), 100),
        # 同比：对齐 09-07~09-30（两侧同期 24 天）
        'yoy_net_sales': round(yc.get('net_sales') or 0, 2),
        'yoy_profit': round(yp.get('profit') or 0, 2),
        'yoy_promo_spend': round(yoy_promo_prev.get(pid, {}).get('spend') or 0, 2),
        'net_sales_yoy': _chg(yc.get('net_sales'), yp.get('net_sales'), 500),
        'profit_yoy': _chg(yc.get('profit'), yp.get('profit'), 200),
        'promo_spend_yoy': _chg(yoy_promo_cur.get(pid, {}).get('spend'),
                                yoy_promo_prev.get(pid, {}).get('spend'), 100),
        'profit_rate': (profit / net) if net else None,
        'ad_ratio_bill': (ad_bill / net) if net else None,
        'roi_bill': (gsv / ad_bill) if ad_bill else None,
        'promo_spend': (round(spend, 2) if spend is not None else None),
        'promo_attr': (round(attr, 2) if attr is not None else None),
        'promo_direct': (round(direct, 2) if direct is not None else None),
        'promo_roi': (attr / spend) if (spend and attr is not None) else None,
        'promo_direct_roi': (direct / spend) if (spend and direct is not None) else None,
        'promo_ad_ratio': (spend / attr) if (attr and spend is not None) else None,
        'cart_cost': (spend / (p.get('carts') or 0)) if spend and p.get('carts') else None,
        'new_cost': (spend / (p.get('new_buyers') or 0)) if spend and p.get('new_buyers') else None,
        'cart_rate': ((p.get('carts') or 0) / p['clicks']) if p.get('clicks') else None,
        # 店铺侧加购率：加购人数 ÷ 访客（与分阶段表的「加购率」同口径，可横向对照）
        'cart_rate_shop': (((d.get('cart_users') or 0) / (d.get('ipv') or 0))
                           if (d.get('ipv') or 0) else None),
        # 引导潜客占比：monthly_data 口径，库里全为 0 → 一律 None，表格显示 --
        'lead_ratio': lead_by_product.get(pid),
        'carts': p.get('carts'), 'new_buyers': p.get('new_buyers'), 'clicks': p.get('clicks'),
    }


all_pids = set(prod_daily) | set(promo)
merged = [merge(pid) for pid in all_pids]

VIRTUAL_KEYS = ('补差价', '运费', '邮费', '赠品', '测试', '差价', '补拍', '专用链接')


def is_virtual(m):
    return any(k in str(m.get('title') or '') for k in VIRTUAL_KEYS)


virtual_items = [m for m in merged if is_virtual(m)]
real = [m for m in merged if not is_virtual(m)]
out['virtual_items'] = sorted(virtual_items, key=lambda x: x['profit'])[:10]
out['promo_product_total'] = round(sum(m['promo_spend'] or 0 for m in merged), 2)
out['product_count'] = len(real)

out['top_spend_items'] = sorted([m for m in real if m['promo_spend']],
                                key=lambda x: x['promo_spend'], reverse=True)[:20]
out['top_profit_items'] = sorted([m for m in real if m['profit'] > 0],
                                 key=lambda x: x['profit'], reverse=True)[:15]

loss = sorted([m for m in real if m['profit'] < 0], key=lambda x: x['profit'])
out['loss_items'] = loss[:20]
out['loss_summary'] = {
    'count': len(loss),
    'total_loss': round(sum(m['profit'] for m in loss), 2),
    'with_promo': len([m for m in loss if (m['promo_spend'] or 0) > 0]),
    'promo_spend_of_loss': round(sum(m['promo_spend'] or 0 for m in loss), 2),
}

out['high_ratio_items'] = sorted(
    [m for m in real if m['net_sales'] > 3000 and (m['ad_ratio_bill'] or 0) > 0.35],
    key=lambda x: x['ad_ratio_bill'], reverse=True)[:15]

out['efficient_items'] = sorted(
    [m for m in real if m['profit'] > 1000 and (m['ad_ratio_bill'] or 1) < 0.15],
    key=lambda x: x['profit'], reverse=True)[:15]

# ---------- 3b) 费比分档 → 利润率（效率标杆的实测依据，不写死结论） ----------
# 报告里「费比 <15% 的款利润率普遍 15%~30%」这类句子必须来自实测；
# 不同周期会反转（本周就没有一款能做到），所以按档位算出来再决定怎么写。
out['ratio_bands'] = rows(f"""
    WITH x AS (
        SELECT d.product_id,
               SUM(d.net_sales) net, SUM(d.operating_profit) op, SUM(d.ad_spend) ad
        FROM daily_data d JOIN products p ON p.product_id = d.product_id
        WHERE d.date BETWEEN ? AND ?{CAT_SQL}
        GROUP BY d.product_id)
    SELECT CASE
             WHEN net <= 1000 THEN 'small'
             WHEN ad / net < 0.15 THEN 'b15'
             WHEN ad / net < 0.25 THEN 'b25'
             WHEN ad / net < 0.35 THEN 'b35'
             ELSE 'over35' END AS band,
           COUNT(*) AS n,
           ROUND(SUM(net), 2) AS net,
           ROUND(SUM(op), 2) AS profit,
           ROUND(SUM(ad), 2) AS ad,
           ROUND(SUM(op) / NULLIF(SUM(net), 0), 4) AS profit_rate,
           ROUND(SUM(ad) / NULLIF(SUM(net), 0), 4) AS ad_ratio,
           SUM(CASE WHEN op < 0 THEN 1 ELSE 0 END) AS loss_n
    FROM x GROUP BY band ORDER BY band""", [CUR[0], CUR[1], *CAT_PARAMS])

# 盈利/亏损两组的规模对比，供「结构性」结论引用
out['pn_split'] = one(f"""
    WITH x AS (
        SELECT d.product_id, SUM(d.net_sales) net, SUM(d.operating_profit) op, SUM(d.ad_spend) ad
        FROM daily_data d JOIN products p ON p.product_id = d.product_id
        WHERE d.date BETWEEN ? AND ?{CAT_SQL}
        GROUP BY d.product_id)
    SELECT SUM(CASE WHEN op > 0 THEN 1 ELSE 0 END) win_n,
           SUM(CASE WHEN op <= 0 THEN 1 ELSE 0 END) loss_n,
           ROUND(SUM(CASE WHEN op > 0 THEN net ELSE 0 END), 2) win_net,
           ROUND(SUM(CASE WHEN op <= 0 THEN net ELSE 0 END), 2) loss_net,
           ROUND(SUM(CASE WHEN op > 0 THEN op ELSE 0 END), 2) win_profit,
           ROUND(SUM(CASE WHEN op <= 0 THEN op ELSE 0 END), 2) loss_profit,
           ROUND(SUM(CASE WHEN op > 0 THEN ad ELSE 0 END), 2) win_ad,
           ROUND(SUM(CASE WHEN op <= 0 THEN ad ELSE 0 END), 2) loss_ad,
           COUNT(*) AS total_n
    FROM x""", [CUR[0], CUR[1], *CAT_PARAMS])

# 退款率（环比看质量），本期/对比期各一
out['refund'] = {
    'cur': one(f"""SELECT ROUND(SUM(d.refund_amount),2) refund, ROUND(SUM(d.payment_amount),2) pay
                   FROM daily_data d JOIN products p ON p.product_id = d.product_id
                   WHERE d.date BETWEEN ? AND ?{CAT_SQL}""", [CUR[0], CUR[1], *CAT_PARAMS]),
    'prev': one(f"""SELECT ROUND(SUM(d.refund_amount),2) refund, ROUND(SUM(d.payment_amount),2) pay
                    FROM daily_data d JOIN products p ON p.product_id = d.product_id
                    WHERE d.date BETWEEN ? AND ?{CAT_SQL}""", [PREV[0], PREV[1], *CAT_PARAMS]),
}

# ---------- 4) 利润结构（成本齐备子窗口，品类过滤） ----------
ps = one(f"""SELECT COALESCE(SUM(d.net_sales),0) net_sales,
                    SUM(d.sales_cost) sales_cost, SUM(d.custom_cost) custom_cost,
                    SUM(d.product_cost) product_cost,
                    SUM(d.logistics_cost) logistics_cost, SUM(d.other_cost) other_cost,
                    SUM(d.platform_fee) platform_fee, SUM(d.gift_cost) gift_cost,
                    SUM(d.ad_spend) ad_spend, SUM(d.operating_profit) profit,
                    COUNT(*) n
             FROM daily_data d JOIN products p ON p.product_id = d.product_id
             WHERE d.date BETWEEN ? AND ?{CAT_SQL}""", [COST_START, COST_END, *CAT_PARAMS])
out['profit_structure'] = ps

# 恒等式诊断：本窗口内「BI 导出 Excel 源」vs「API 采集源」的行/天分布。
# Excel 源的 net_sales/operating_profit 被取整为整数、成本列保留小数 → 逐项相加与利润列不闭合；
# API 源逐行严格闭合。据此在报告里解释恒等残差的真实来源。
out['profit_structure_diag'] = one(f"""SELECT
        SUM(CASE WHEN d.data_source LIKE '%.xlsx%' THEN 1 ELSE 0 END) xlsx_rows,
        SUM(CASE WHEN d.data_source LIKE '%.json%' THEN 1 ELSE 0 END) json_rows,
        COUNT(DISTINCT CASE WHEN d.data_source LIKE '%.xlsx%' THEN d.date END) xlsx_days,
        COUNT(DISTINCT CASE WHEN d.data_source LIKE '%.json%' THEN d.date END) json_days,
        COUNT(*) n
      FROM daily_data d JOIN products p ON p.product_id = d.product_id
      WHERE d.date BETWEEN ? AND ?{CAT_SQL}""", [COST_START, COST_END, *CAT_PARAMS])

# ---------- 5) 日趋势（品类过滤） ----------
out['trend'] = rows(f"""SELECT d.date,
                               COALESCE(SUM(d.ad_spend),0) ad_spend,
                               COALESCE(SUM(d.net_sales),0) net_sales,
                               COALESCE(SUM(d.payment_amount),0) gsv,
                               COALESCE(SUM(d.operating_profit),0) profit,
                               COALESCE(SUM(d.ipv),0) ipv,
                               COALESCE(SUM(d.buyers),0) buyers,
                               COALESCE(SUM(d.cart_users),0) cart_users,
                               COALESCE(SUM(d.payment_qty),0) qty
                        FROM daily_data d JOIN products p ON p.product_id = d.product_id
                        WHERE d.date BETWEEN ? AND ?{CAT_SQL}
                        GROUP BY d.date ORDER BY d.date""", [CUR[0], CUR[1], *CAT_PARAMS])
# 逐日转化/加购派生指标（比率一律由当日总量重推，不用均值）
for _r in out['trend']:
    _ip = float(_r.get('ipv') or 0) or 1
    _ct = float(_r.get('cart_users') or 0)
    _ad = float(_r.get('ad_spend') or 0)
    _bu = float(_r.get('buyers') or 0)
    _r['cvr'] = round(_bu / _ip, 6)
    _r['cart_rate'] = round(_ct / _ip, 6)
    _r['cart_cost'] = round(_ad / _ct, 4) if _ct else None
    _r['cart_to_buy'] = round(_bu / _ct, 6) if _ct else None

out['promo_trend'] = rows(f"""SELECT f.date, SUM(f.ad_spend) spend,
                                     SUM(f.attributed_payment_amount) attr,
                                     SUM(f.direct_payment_amount) direct
                              FROM promotion_daily_facts f
                              LEFT JOIN products p ON p.product_id = f.product_id
                              WHERE f.date BETWEEN ? AND ? AND f.grain='product'
                                AND f.channel='全部' AND f.product_id NOT LIKE '-%'{CAT_SQL}
                              GROUP BY f.date ORDER BY f.date""", [CUR[0], CUR[1], *CAT_PARAMS])

# ---------- 6) 数据缺口自检（供报告「口径与缺口」节如实引用，不写死日期） ----------
from datetime import date as _dt_date, timedelta as _td  # noqa: E402


def _date_span(rng):
    a = _dt_date.fromisoformat(rng[0]); b = _dt_date.fromisoformat(rng[1])
    return [(a + _td(days=i)).isoformat() for i in range((b - a).days + 1)]


_span = _date_span(CUR)
_daily_days = {r['date'] for r in out['trend']}
_promo_days = {r['date'] for r in out['promo_trend']}
# 成本列齐全的天：当天该品类所有行 product_cost 均非 NULL
_cost_days = {r['date'] for r in rows(f"""
    SELECT d.date FROM daily_data d JOIN products p ON p.product_id = d.product_id
    WHERE d.date BETWEEN ? AND ?{CAT_SQL}
    GROUP BY d.date
    HAVING SUM(CASE WHEN d.product_cost IS NULL THEN 1 ELSE 0 END) = 0
""", [CUR[0], CUR[1], *CAT_PARAMS])}
out['coverage'] = {
    'window_days': len(_span),
    'missing_daily': [d for d in _span if d not in _daily_days],
    'missing_promo': [d for d in _span if d not in _promo_days],
    'cost_ready_days': sorted(_cost_days),
    'cost_missing_days': [d for d in _span if d not in _cost_days],
}

# ---------- 7) 活动阶段拆解（双11 预热期归因） ----------
# 目的：把「本期为什么跌」从「投放变差」拆成「活动节奏 + 投放动作」两件事。
# 蓄水期考核不看当期 ROI（用户此刻在攒加购，成交延后到收割日），改看
#   加购成本 = 花费 / 加购人数   —— 买一个「未来的成交机会」多少钱
#   加购→成交 转化             —— 蓄的水有多少真的流到成交
# 这两个指标能在「当期 GSV 崩了」的情况下判断投放本身有没有变差。
_CAMP = PERIOD.get('campaign') or {}
out['campaign'] = {
    'name': _CAMP.get('name'),
    'timeline': _CAMP.get('timeline') or [],
    'harvest_start': _CAMP.get('harvest_start'),
    'phases': [],
}


def _phase_agg(start, end):
    r = one(f"""SELECT COUNT(DISTINCT d.date) days,
                       COALESCE(SUM(d.ad_spend),0) ad,
                       COALESCE(SUM(d.payment_amount),0) gsv,
                       COALESCE(SUM(d.net_sales),0) net,
                       COALESCE(SUM(d.operating_profit),0) profit,
                       COALESCE(SUM(d.ipv),0) ipv,
                       COALESCE(SUM(d.buyers),0) buyers,
                       COALESCE(SUM(d.payment_qty),0) qty,
                       COALESCE(SUM(d.cart_users),0) cart_u,
                       COALESCE(SUM(d.fav_users),0) fav_u
                FROM daily_data d JOIN products p ON p.product_id = d.product_id
                WHERE d.date BETWEEN ? AND ?{CAT_SQL}""", [start, end, *CAT_PARAMS])
    return dict(r) if r else {}


def _lead_agg(start, end):
    """区间内品类口径的引导访问潜客合计（单品级 SUM，仅供看结构，不是店铺口径）。"""
    try:
        return one(f"""SELECT COUNT(DISTINCT l.date) days,
                              COUNT(*) rows_n,
                              COALESCE(SUM(l.inshop_uv),0) inshop_uv,
                              COALESCE(SUM(l.potential_uv),0) potential_uv,
                              COALESCE(SUM(l.ad_spend),0) ad
                       FROM promotion_lead_daily l JOIN products p ON p.product_id = l.product_id
                       WHERE l.date BETWEEN ? AND ?{CAT_SQL}""",
                   [start, end, *CAT_PARAMS]) or {}
    except Exception as _e:
        return {'error': str(_e)}


for _nm, _s, _e, _desc in (_CAMP.get('phases') or []):
    _a = _phase_agg(_s, _e)
    _n = int(_a.get('days') or 0) or 1
    _ipv = float(_a.get('ipv') or 0) or 1
    _cart = float(_a.get('cart_u') or 0)
    _ad = float(_a.get('ad') or 0)
    _lgl = _lead_agg(_s, _e)
    _luv = float(_lgl.get('inshop_uv') or 0)
    _lpot = float(_lgl.get('potential_uv') or 0)
    out['campaign']['phases'].append({
        'name': _nm, 'start': _s, 'end': _e, 'desc': _desc,
        'days': int(_a.get('days') or 0),
        'gsv': round(float(_a.get('gsv') or 0), 2),
        'net': round(float(_a.get('net') or 0), 2),
        'ad': round(_ad, 2),
        'profit': round(float(_a.get('profit') or 0), 2),
        'ipv': int(_ipv),
        'buyers': int(float(_a.get('buyers') or 0)),
        'qty': int(float(_a.get('qty') or 0)),
        'cart_u': int(_cart),
        'fav_u': int(float(_a.get('fav_u') or 0)),
        'gsv_per_day': round(float(_a.get('gsv') or 0) / _n, 2),
        'ipv_per_day': round(_ipv / _n, 2),
        'buyers_per_day': round(float(_a.get('buyers') or 0) / _n, 2),
        'cart_per_day': round(_cart / _n, 2),
        'cvr': round(float(_a.get('buyers') or 0) / _ipv, 6),
        'cart_rate': round(_cart / _ipv, 6),
        'cart_cost': round(_ad / _cart, 4) if _cart else None,
        'fav_cost': round(_ad / float(_a.get('fav_u') or 1), 4) if float(_a.get('fav_u') or 0) else None,
        'cart_to_buy': round(float(_a.get('buyers') or 0) / _cart, 6) if _cart else None,
        'feibi': round(_ad / float(_a.get('gsv') or 1), 6) if float(_a.get('gsv') or 0) else None,
        'lead_inshop_uv': int(_luv),
        'lead_potential_uv': int(_lpot),
        'lead_ratio': round(_lpot / _luv, 6) if _luv else None,
    })

# 对照基线：9 月正常期（无大促）的蓄水效率，用来判断「加购成本 3 元」是否异常
_b = one(f"""SELECT COALESCE(SUM(d.ad_spend),0) ad,
                    COALESCE(SUM(d.cart_users),0) cart_u,
                    COALESCE(SUM(d.buyers),0) buyers,
                    COALESCE(SUM(d.ipv),0) ipv,
                    COALESCE(SUM(d.payment_amount),0) gsv
             FROM daily_data d JOIN products p ON p.product_id = d.product_id
             WHERE d.date BETWEEN '2026-09-01' AND '2026-09-30'{CAT_SQL}""", [*CAT_PARAMS])
if _b and float(_b.get('cart_u') or 0):
    out['campaign']['baseline_sept'] = {
        'label': '2026-09 整月（无大促对照）',
        'cart_cost': round(float(_b['ad']) / float(_b['cart_u']), 4),
        'cart_to_buy': round(float(_b['buyers']) / float(_b['cart_u']), 6),
        'cvr': round(float(_b['buyers']) / (float(_b['ipv']) or 1), 6),
        'cart_rate': round(float(_b['cart_u']) / (float(_b['ipv']) or 1), 6),
    }
else:
    out['campaign']['baseline_sept'] = None

# 重叠切片：现货预热纯窗口（与上面互斥分段并存，用于单独度量预热强度）
_ov = _CAMP.get('overlap_slice')
if _ov:
    _onm, _os, _oe, _odesc = _ov
    _oa = _phase_agg(_os, _oe)
    _on = int(_oa.get('days') or 0) or 1
    _ocart = float(_oa.get('cart_u') or 0)
    _oad = float(_oa.get('ad') or 0)
    out['campaign']['overlap_slice'] = {
        'name': _onm, 'start': _os, 'end': _oe, 'desc': _odesc,
        'days': int(_oa.get('days') or 0),
        'gsv': round(float(_oa.get('gsv') or 0), 2),
        'ad': round(_oad, 2),
        'profit': round(float(_oa.get('profit') or 0), 2),
        'ipv': int(float(_oa.get('ipv') or 0)),
        'buyers': int(float(_oa.get('buyers') or 0)),
        'cart_u': int(_ocart),
        'cvr': round(float(_oa.get('buyers') or 0) / (float(_oa.get('ipv') or 0) or 1), 6),
        'cart_cost': round(_oad / _ocart, 4) if _ocart else None,
        'cart_to_buy': round(float(_oa.get('buyers') or 0) / _ocart, 6) if _ocart else None,
        'gsv_per_day': round(float(_oa.get('gsv') or 0) / _on, 2),
    }
else:
    out['campaign']['overlap_slice'] = None

# ---------- 8) 引导访问潜客占比（万相台单品日粒度，promotion_lead_daily） ----------
# 口径：potential_uv / inshop_uv，即万相台「引导访问潜客数 ÷ 入店访客数」。
# 已验证平台字段 inshopPotentialUvRate 与该式逐行一致（品类 714 行样本，0 例外）。
# 重要：单品口径**不可相加**，同一用户逛多个商品会被重复计数，
#       所以这里的 SUM 只代表「各单品之和」，不是店铺账户口径，报告必须标注。
def _lead_pack(_l):
    _uv = float(_l.get('inshop_uv') or 0)
    _pot = float(_l.get('potential_uv') or 0)
    return {
        'days': int(_l.get('days') or 0),
        'rows': int(_l.get('rows_n') or 0),
        'inshop_uv': int(_uv),
        'potential_uv': int(_pot),
        'ratio': round(_pot / _uv, 6) if _uv else None,
        'ad': round(float(_l.get('ad') or 0), 2),
    }


_lead_cur = _lead_agg(CUR[0], CUR[1])
_lead_prev = _lead_agg(PREV[0], PREV[1])
_lead_range = None
try:
    _lr = one('SELECT MIN(date) a, MAX(date) b, COUNT(*) n FROM promotion_lead_daily')
    if _lr and _lr.get('a'):
        _lead_range = {'start': _lr['a'], 'end': _lr['b'], 'rows': int(_lr.get('n') or 0)}
except Exception:
    _lead_range = None
out['campaign']['lead'] = {
    'source': 'promotion_lead_daily（万相台 item_promotion 报表）',
    'field_note': 'inshopPotentialUv / inshopUv；平台 inshopPotentialUvRate 与该式逐行一致',
    'grain': 'product_day',
    'window': f'{CUR[0]}~{CUR[1]}',
    'available': bool(_lead_cur.get('inshop_uv')),
    'current': _lead_pack(_lead_cur),
    'prev': _lead_pack(_lead_prev),
    'daily': [{'date': _k, **(_v or {})} for _k, _v in sorted(lead_by_date.items())],
    'table_range': _lead_range,
    'caveat': '单品口径不可相加：SUM 是各单品之和，必然大于店铺账户口径，不能当店铺整体看',
    'error': _lead_cur.get('error'),
}

suffix = 'all' if not CATEGORY else 'sock'
out_path = f'_tmp/promo_review_data_{suffix}_{period_key}.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)

# ---------- 摘要 ----------
s, p = out['summary']['current'], out['summary']['prev']
print(f'品类: {CATEGORY or "全部"}  | 单品数: {out["product_count"]}  有图: '
      f'{len([m for m in real if m["image_url"]])}')
print('== 汇总 ==')
for k in ('gsv', 'net_sales', 'ad_spend', 'profit', 'roi', 'ad_ratio', 'net_expense_ratio', 'profit_rate', 'days', 'prods'):
    print(f'  {k:18s} {s.get(k)}   prev={p.get(k)}')
print('== 渠道 (品类口径, partial=%s) ==' % out['channels']['partial'])
for r in ch_list:
    print(f"  {r['name']:6s} spend={r['ad_spend']:>10.0f} attr={r.get('attributed_payment') or 0:>10.0f} "
          f"roi={r.get('roi')} share={r.get('spend_share')}")
print('== 亏损 ==', out['loss_summary'])
print('== 利润结构 ==', {k: ps.get(k) for k in ('net_sales', 'sales_cost', 'custom_cost', 'product_cost', 'logistics_cost', 'other_cost', 'profit')})
print('== TOP消耗 top5 ==')
for m in out['top_spend_items'][:5]:
    print(f"  {m['product_id']} {m['title'][:16]:18s} spend={m['promo_spend']:>8.0f} profit={m['profit']:>8.0f} img={'Y' if m['image_url'] else 'N'}")
print(f'写入 {out_path}')

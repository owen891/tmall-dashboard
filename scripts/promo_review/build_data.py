# -*- coding: utf-8 -*-
"""构建「推广分析复盘」数据集（近30天，指定品类，叠加单品利润 + 主图）。

用法：python scripts/promo_review/build_data.py [品类标签]
      默认 'sock'（=标品袜子）；传 'all' 表示不限品类。

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
           COALESCE(SUM(d.buyers),0) buyers
    FROM daily_data d JOIN products p ON p.product_id = d.product_id
    WHERE d.date BETWEEN ? AND ?{CAT_SQL}
    GROUP BY d.product_id""", [CUR[0], CUR[1], *CAT_PARAMS])}

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
                               COALESCE(SUM(d.operating_profit),0) profit
                        FROM daily_data d JOIN products p ON p.product_id = d.product_id
                        WHERE d.date BETWEEN ? AND ?{CAT_SQL}
                        GROUP BY d.date ORDER BY d.date""", [CUR[0], CUR[1], *CAT_PARAMS])

out['promo_trend'] = rows(f"""SELECT f.date, SUM(f.ad_spend) spend,
                                     SUM(f.attributed_payment_amount) attr,
                                     SUM(f.direct_payment_amount) direct
                              FROM promotion_daily_facts f
                              LEFT JOIN products p ON p.product_id = f.product_id
                              WHERE f.date BETWEEN ? AND ? AND f.grain='product'
                                AND f.channel='全部' AND f.product_id NOT LIKE '-%'{CAT_SQL}
                              GROUP BY f.date ORDER BY f.date""", [CUR[0], CUR[1], *CAT_PARAMS])

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

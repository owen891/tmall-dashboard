# -*- coding: utf-8 -*-
"""生成「推广分析复盘」HTML 报告（指定品类，近30天，叠加单品利润 + 主图 + 商品ID）。

用法：python scripts/promo_review/gen_report.py [sock|all]
"""
import base64
import io
import json
import os
import sys
import urllib.request
from html import escape

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
raw = (sys.argv[1] if len(sys.argv) > 1 else 'sock').strip()
suffix = 'all' if raw in ('all', '') else 'sock'
period_key = (sys.argv[2] if len(sys.argv) > 2 else 'near30').strip()
DATA = json.load(open(os.path.join(BASE, f'_tmp/promo_review_data_{suffix}_{period_key}.json'), encoding='utf-8'))

# 主图内嵌：下载 → 压缩 → base64。带磁盘缓存，重复生成不重复下载。
# 环境有代理，主图 CDN 需直连，故用空 ProxyHandler 绕过。
THUMB_DIR = os.path.join(BASE, '_tmp/thumbs')
os.makedirs(THUMB_DIR, exist_ok=True)
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_THUMB_CACHE = {}


def thumb_data_uri(url, pid, size=96):
    if not url:
        return ''
    key = str(pid)
    if key in _THUMB_CACHE:
        return _THUMB_CACHE[key]
    path = os.path.join(THUMB_DIR, f'{pid}.jpg')
    if not os.path.exists(path):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0', 'Referer': 'https://detail.tmall.com/'})
            with _OPENER.open(req, timeout=15) as resp:
                blob = resp.read()
            from PIL import Image
            im = Image.open(io.BytesIO(blob)).convert('RGB')
            im.thumbnail((size, size))
            im.save(path, 'JPEG', quality=82)
        except Exception:
            _THUMB_CACHE[key] = ''
            return ''
    try:
        with open(path, 'rb') as f:
            uri = 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()
    except Exception:
        uri = ''
    _THUMB_CACHE[key] = uri
    return uri

W = DATA['window']
CUR, PREV = W['cur'], W['prev']
S, P = DATA['summary']['current'], DATA['summary']['prev']
CH = DATA['channels']
PS = DATA['profit_structure']
CAT_LABEL = (DATA.get('category') or {}).get('label') or '全部品类'


def money(x, nd=0):
    return '--' if x is None else f'{x:,.{nd}f}'


def wan(x, nd=1):
    return '--' if x is None else f'{x / 10000:,.{nd}f}'


def pct(x, nd=1):
    return '--' if x is None else f'{x * 100:.{nd}f}%'


def dec(x, nd=2):
    return '--' if x is None else f'{x:,.{nd}f}'


def delta(cur, prev, kind='pct'):
    if cur is None or prev in (None, 0):
        return '--', 0
    if kind == 'pt':
        d = (cur - prev) * 100
        return f'{"+" if d >= 0 else ""}{d:.2f}pt', (1 if d >= 0 else -1)
    d = (cur - prev) / abs(prev) * 100
    return f'{"+" if d >= 0 else ""}{d:.1f}%', (1 if d >= 0 else -1)


def cls(v):
    if v is None:
        return ''
    return 'pos' if v > 0 else ('neg' if v < 0 else '')


spend_chg, _ = delta(S['ad_spend'], P['ad_spend'])
gsv_chg, _ = delta(S['gsv'], P['gsv'])
net_chg, _ = delta(S['net_sales'], P['net_sales'])
ratio_delta = f'{S["ad_ratio"] * 100 - P["ad_ratio"] * 100:+.2f}pt'
ner_delta = f'{S["net_expense_ratio"] * 100 - P["net_expense_ratio"] * 100:+.2f}pt'
roi_delta = f'{S["roi"] - P["roi"]:+.2f}'
loss = DATA['loss_summary']
promo_product_total = DATA.get('promo_product_total') or 0
loss_share = loss['promo_spend_of_loss'] / promo_product_total if promo_product_total else 0
kw = next((r for r in CH['current'] if r['name'] == '关键词'), None)
site = next((r for r in CH['current'] if r['name'] == '全站'), None)

# ---- 渠道结论不再写死「全站挑大梁、关键词拖效率」，改为按实测 ROI 排序生成 ----
CH_RANKED = sorted([r for r in CH['current'] if (r.get('ad_spend') or 0) > 0],
                   key=lambda r: (r.get('roi') or 0), reverse=True)
# 花费占比过低的渠道（<1%）不参与「最高/最低效率」排名——单笔波动就能翻盘，是噪声。
CH_SIGNIFICANT = [r for r in CH_RANKED if (r.get('spend_share') or 0) >= 0.01]
CH_NOISE = [r for r in CH_RANKED if (r.get('spend_share') or 0) < 0.01]
CH_BEST = CH_SIGNIFICANT[0] if CH_SIGNIFICANT else None
CH_WORST = CH_SIGNIFICANT[-1] if len(CH_SIGNIFICANT) > 1 else None
CH_KW_VS_SITE = ''
CH_KW_GAP = None
if kw and site and (kw.get('roi') is not None) and (site.get('roi') is not None):
    # _gap = 全站 - 关键词。>0 表示全站更高，则关键词是「低于」。
    _gap = (site['roi'] or 0) - (kw['roi'] or 0)
    CH_KW_VS_SITE = ('低于' if _gap > 0 else '高于')
    CH_KW_GAP = abs(_gap)

YOY = DATA['summary'].get('yoy') or {}
MYOY = DATA['summary'].get('monthly_yoy') or {}
YC, YP = YOY.get('current') or {}, YOY.get('prev') or {}

# ---- 周期文案（由 build_data 的 period 块驱动，报告不再写死「近30天」） ----
PERIOD = DATA.get('period') or {}
P_NAME = PERIOD.get('name') or '近 30 天'
P_TITLE = PERIOD.get('title') or '近 30 天'
P_PREV_DESC = PERIOD.get('prev_desc') or '上一周期'
P_YOY_DESC = PERIOD.get('yoy_desc') or '去年同期'
P_ASOF = PERIOD.get('asof') or (CUR[1] if CUR else '')
P_COST_NOTE = PERIOD.get('cost_note') or ''
P_YOY_NOTE = PERIOD.get('yoy_note') or ''
MY_CUR_M, MY_PREV_M = (list(PERIOD.get('monthly_yoy') or ['--', '--']) + ['--', '--'])[:2]
CUR_DAYS = int(S.get('days') or 0)
PREV_DAYS = int(P.get('days') or 0)
YOY_DAYS = int(YC.get('days') or 0)
YOY_CW = list(YOY.get('window_cur') or ['--', '--'])
YOY_PW = list(YOY.get('window_prev') or ['--', '--'])
COST_W = W.get('cost_window') or ['--', '--']
TREND = DATA.get('trend') or []
LOSS_DAYS = len([r for r in TREND if (r.get('profit') or 0) < 0])

# ---- 期内节奏：找出峰值日与峰值后的塌陷幅度，供「核心结论」与第 1 节引用 ----
# 只在窗口 ≥5 天时启用（短窗口谈「节奏」没有意义）。
RHYTHM = {}
if len(TREND) >= 5:
    _peak = max(TREND, key=lambda r: (r.get('gsv') or 0))
    _last = TREND[-1]
    _peak_idx = TREND.index(_peak)
    _after = TREND[_peak_idx + 1:]
    RHYTHM = {
        'peak_date': _peak['date'],
        'peak_gsv': _peak.get('gsv') or 0,
        'last_date': _last['date'],
        'last_gsv': _last.get('gsv') or 0,
        'drop': ((_last.get('gsv') or 0) - (_peak.get('gsv') or 0)) / (_peak.get('gsv') or 1),
        'after_days': len(_after),
        'after_loss_days': len([r for r in _after if (r.get('profit') or 0) < 0]),
        'first_half_gsv': sum((r.get('gsv') or 0) for r in TREND[:max(1, len(TREND) // 2)]),
        'second_half_gsv': sum((r.get('gsv') or 0) for r in TREND[max(1, len(TREND) // 2):]),
    }
    _fh = RHYTHM['first_half_gsv'] or 1
    RHYTHM['h2h'] = (RHYTHM['second_half_gsv'] - _fh) / _fh

# 成本桶是否齐备（决定第 6 节和第 7 节根因能不能引用费用结构）
PS_EMPTY_EARLY = all(PS.get(k) is None for k in
                     ('sales_cost', 'custom_cost', 'product_cost', 'logistics_cost', 'other_cost'))
COST_DAYS_COVERED = int((DATA.get('profit_structure') or {}).get('n') or 0)

# ---- 数据缺口自检（build_data 实测得出，报告里不写死日期） ----
COV = DATA.get('coverage') or {}
COV_MISS_DAILY = COV.get('missing_daily') or []
COV_MISS_PROMO = COV.get('missing_promo') or []
COV_COST_MISSING = COV.get('cost_missing_days') or []
COV_COST_READY = COV.get('cost_ready_days') or []

# 同比是否可用（build_data 已实测日粒度；缺失则留空，避免拿整月比 N 天）
YOY_OK = not bool(YOY.get('unavailable'))
_yoy_note = YOY.get('note') or ''
COST_DAYS = 0
if COST_W[0] not in (None, '--'):
    try:
        from datetime import date as _d
        _a = _d.fromisoformat(COST_W[0]); _b = _d.fromisoformat(COST_W[1])
        COST_DAYS = (_b - _a).days + 1
    except Exception:
        COST_DAYS = 0


def _pair_line(cur, prev, label, kind='pct', good_up=True):
    """返回 (文本, 颜色类)。good_up=False 时涨=红（费率类）。"""
    if cur is None or prev in (None, 0):
        return f'{label} --', 'muted'
    if kind == 'pt':
        d = (cur - prev) * 100
        txt, sign = f'{label} {d:+.2f}pt', ('pos' if d > 0 else 'neg')
    elif kind == 'abs':
        d = cur - prev
        txt, sign = f'{label} {d:+,.2f}', ('pos' if d > 0 else 'neg')
    else:
        d = (cur - prev) / abs(prev) * 100
        txt, sign = f'{label} {d:+.1f}%', ('pos' if d > 0 else 'neg')
    cls = sign if good_up else ('neg' if sign == 'pos' else 'pos')
    return txt, cls


def _yoy_line(cur, prev, kind='pct', good_up=True):
    return _pair_line(cur, prev, '同比', kind, good_up)


def _mom_line(cur, prev, kind='pct', good_up=True):
    return _pair_line(cur, prev, '环比', kind, good_up)


# 同比文案（放在 _pair_line 定义之后；日粒度缺失时留空）
if YOY_OK:
    yoy_li_html = (
        f'<li><b>同比（{P_YOY_DESC}，{YOY_PW[0]}~{YOY_PW[1]}，两侧各 {YOY_DAYS} 天）：</b>'
        f'去年同期净利 <b>{wan(YP.get("profit"))}万</b>（利润率 {pct(YP.get("profit_rate"))}），'
        f'今年同期 <b>{wan(YC.get("profit"))}万</b>（利润率 {pct(YC.get("profit_rate"))}）；'
        f'同期推广花费 {wan(YP.get("ad_spend"))}万 → {wan(YC.get("ad_spend"))}万'
        f'（{_pair_line(YC.get("ad_spend"), YP.get("ad_spend"), "", "pct", False)[0]}），'
        f'GSV {_pair_line(YC.get("gsv"), YP.get("gsv"), "", "pct", True)[0]}。'
        + (f'<span class="tag tag--bad">基线覆盖不足，数值偏低</span>' if YOY.get('baseline_warn') else '')
        + '</li>')
    yoy_callout_html = (
        f'<div class="callout callout--bad"><b>同比（{P_YOY_DESC}）：</b>'
        f'去年同期 {escape(CAT_LABEL)} 净利 <b>{wan(YP.get("profit"))}万、利润率 {pct(YP.get("profit_rate"))}</b>，'
        f'今年同期 <b>净利 {wan(YC.get("profit"))}万、利润率 {pct(YC.get("profit_rate"))}</b>；'
        f'同期推广花费 {wan(YP.get("ad_spend"))}万 → {wan(YC.get("ad_spend"))}万'
        f'（{_pair_line(YC.get("ad_spend"), YP.get("ad_spend"), "", "pct", False)[0]}），'
        f'投产 {dec(YP.get("roi"))} → {dec(YC.get("roi"))}。'
        f'<br><span style="opacity:.85">整月参考（{MY_CUR_M} vs {MY_PREV_M}，取自 <code>monthly_data</code>）：'
        f'GSV {wan((MYOY.get("prev") or {}).get("gsv"))}万 → {wan((MYOY.get("current") or {}).get("gsv"))}万，'
        f'净利润 {wan((MYOY.get("prev") or {}).get("profit"))}万 → {wan((MYOY.get("current") or {}).get("profit"))}万。</span>'
        + (f'<br><span style="opacity:.85">⚠️ {YOY.get("baseline_warn")}</span>'
           if YOY.get('baseline_warn') else '') + '</div>')
else:
    yoy_li_html = f'<li><b>同比不可用（已留空）。</b>{_yoy_note}</li>'
    yoy_callout_html = f'<div class="callout callout--warn"><b>同比留空：</b>{_yoy_note}</div>'


# ---------------- 期内节奏（峰值 → 塌陷） ----------------
if RHYTHM:
    _drop = RHYTHM['drop'] * 100
    _h2h = RHYTHM['h2h'] * 100
    _peak_is_first = TREND.index(max(TREND, key=lambda r: (r.get('gsv') or 0))) == 0
    _shape = ('<b>开局即本周最高，此后一路下滑</b>' if _peak_is_first
              else f'<b>峰值出现在 {RHYTHM["peak_date"]}</b>')
    rhythm_li_html = (
        f'<li><b>节奏：周内单边下行。</b>{_shape}'
        f'（GSV {money(RHYTHM["peak_gsv"])}），到 <b>{RHYTHM["last_date"]}</b> 只剩 '
        f'{money(RHYTHM["last_gsv"])}，<b>{_drop:+.1f}%</b>；'
        f'后半周 GSV 较前半周 <b>{_h2h:+.1f}%</b>。'
        f'峰值之后的 {RHYTHM["after_days"]} 天'
        f'{("净利<b>全部为负</b>" if RHYTHM["after_loss_days"] == RHYTHM["after_days"] else "里有 <b>" + str(RHYTHM["after_loss_days"]) + " 天净利为负</b>")}'
        f'——不是单日失手，是连续下滑。'
        f'<span class="tag tag--bad">周内趋势比周环比更重要</span></li>')
else:
    rhythm_li_html = ''


# ---------------- 渠道结论（按实测 ROI 排序，不写死） ----------------
def _ch_bit(r):
    # 花费占比 <1% 时用两位小数，否则 pct(...,0) 会把 0.34% 显示成「0%」，读者会误以为没投
    _sh = r.get('spend_share') or 0
    _sh_txt = pct(_sh, 2) if _sh < 0.01 else pct(_sh, 0)
    return f'{r["name"]}占花费 {_sh_txt}、ROI <b>{dec(r.get("roi"))}</b>'


if CH_RANKED:
    # 主叙述只用有统计意义的渠道（占比 ≥1%）；噪声渠道单独列出，不参与「谁高谁低」
    _parts = [_ch_bit(r) for r in (CH_SIGNIFICANT or CH_RANKED)]
    _verdict = ''
    if CH_BEST and CH_WORST and CH_BEST is not CH_WORST:
        _verdict = (f'有效花费里效率最高的是 <b>{CH_BEST["name"]}</b>（ROI {dec(CH_BEST.get("roi"))}），'
                    f'最低的是 <b>{CH_WORST["name"]}</b>（ROI {dec(CH_WORST.get("roi"))}）。')
    if kw and site and CH_KW_VS_SITE:
        _verdict += (f'关键词 ROI {dec(kw.get("roi"))} <b>{CH_KW_VS_SITE}</b>'
                     f'全站 {dec(site.get("roi"))}（差 {CH_KW_GAP:.2f}）。')
    if CH_NOISE:
        _noise = '、'.join(f'{r["name"]}（占 {pct(r.get("spend_share"), 2)}）' for r in CH_NOISE)
        _verdict += (f'<span class="tag tag--warn">花费占比 &lt;1% 的渠道不参与效率排名：'
                     f'{_noise}，其 ROI 不具备统计意义</span>')
    channel_li_html = (
        f'<li><b>渠道：{"；".join(_parts)}。</b>{_verdict}'
        + (' <span class="tag tag--warn">渠道为部分口径</span>' if CH.get('partial') else '')
        + '</li>')
else:
    channel_li_html = '<li><b>渠道：</b>本周期无渠道级花费明细。</li>'


# ---------------- 效率标杆（实测费比分档，不再写死「<15% 就赚钱」） ----------------
RATIO_BANDS = {b['band']: b for b in (DATA.get('ratio_bands') or [])}
PN = DATA.get('pn_split') or {}
_b15 = RATIO_BANDS.get('b15')
_over35 = RATIO_BANDS.get('over35')
_b35 = RATIO_BANDS.get('b35')

if _b15 and (_b15.get('n') or 0) > 0:
    _b15_pr = _b15.get('profit_rate')
    _b15_line = (f'净销费比 &lt;15% 的 {_b15["n"]} 款，合计利润率 '
                 f'<b>{pct(_b15_pr, 1)}</b>（净销 {money(_b15.get("net"))}）')
    # 只有当这一档真的赚钱时才说「是标杆」；否则如实说这一档也没兜住。
    if (_b15_pr or 0) > 0.05:
        _b15_line += '——<b>这一档才是真标杆</b>，说明毛利结构本身撑得住低费比。'
    else:
        _b15_line += '——<b>连低费比档都没兜住利润</b>，问题在毛利/成本结构，不在推广费。'
else:
    _b15_line = '本期没有净销费比 &lt;15% 且净销 &gt;1000 的款'

if _over35:
    _b15_line += (f' 对照：费比 &gt;35% 的 {_over35["n"]} 款利润率 '
                  f'<b>{pct(_over35.get("profit_rate"), 1)}</b>'
                  f'（{_over35.get("loss_n")}/{_over35["n"]} 款亏损）。')

_pn_line = ''
if PN.get('win_n') is not None:
    _pn_line = (f' 结构上：盈利款 <b>{PN["win_n"]} 款</b>合计利润 {money(PN.get("win_profit"))}，'
                f'亏损款 <b>{PN["loss_n"]} 款</b>合计 {money(PN.get("loss_profit"))}；'
                f'亏损款吃掉了 {pct((PN.get("loss_ad") or 0) / ((PN.get("win_ad") or 0) + (PN.get("loss_ad") or 1)), 0)} 的商品级推广费。')

efficiency_li_html = (
    f'<li><b>效率标杆要按本期实测说，不能套模板。</b>{_b15_line}'
    f'<b>投产为正 ≠ 赚钱</b>——推广费吃掉了毛利。{_pn_line}</li>')


# ---------------- 双11 活动阶段归因（判断本期是「投入期」还是「投放失效」） ----------------
# 逻辑：蓄水期（定金/预热）成交被推迟到收割日，当期 GSV 天然塌陷。
# 所以不能用当期 ROI 判断投放好坏，要看两个「买流量」的指标：
#   加购成本 = 花费/加购人数（买一个未来成交机会多少钱）
#   加购→成交 转化（蓄的水有多少真流到成交）
# 若加购成本没恶化、只是加购→成交崩 → 是时间错配，不是投放失能。
CAMP = DATA.get('campaign') or {}
CAMP_PHASES = CAMP.get('phases') or []
CAMP_TL = CAMP.get('timeline') or []
CAMP_OV = CAMP.get('overlap_slice') or {}
CAMP_BASE = CAMP.get('baseline_sept') or {}
CAMP_HARVEST = CAMP.get('harvest_start')
HAS_CAMP = bool(CAMP_PHASES)

campaign_timeline_html = ''
if CAMP_TL:
    _tl_rows = []
    for _tn, _ts, _te, _td in CAMP_TL:
        _starts_in = CUR[0] <= _ts[:10] <= CUR[1]
        _tag = ('<span class="tag tag--bad">本期窗口内开启</span>' if _starts_in
                else '<span class="tag">在窗口之后</span>')
        _tl_rows.append(f'<tr><td><b>{escape(_tn)}</b></td><td>{_ts} ~ {_te}</td>'
                        f'<td>{escape(_td)}</td><td>{_tag}</td></tr>')
    campaign_timeline_html = (
        '<div class="table-wrap"><table class="rpt"><thead><tr>'
        '<th>活动阶段</th><th>时间</th><th>说明</th><th>与本报告窗口的关系</th>'
        '</tr></thead><tbody>' + ''.join(_tl_rows) + '</tbody></table></div>')

campaign_phase_rows = ''
campaign_base_row = ''
campaign_li_html = ''
campaign_verdict_html = ''
campaign_headline = ''

if HAS_CAMP:
    for _cp in CAMP_PHASES:
        _cv = _cp.get('cvr') or 0
        _ctb = _cp.get('cart_to_buy') or 0
        campaign_phase_rows += (
            f'<tr><td><b>{escape(_cp["name"])}</b><br>'
            f'<span style="opacity:.65;font-size:12px">{_cp["start"][5:]}~{_cp["end"][5:]}</span></td>'
            f'<td>{_cp["days"]}</td>'
            f'<td>{money(_cp["gsv_per_day"])}</td>'
            f'<td>{_cp["ipv_per_day"]:,.0f}</td>'
            f'<td>{_cp["buyers_per_day"]:,.0f}</td>'
            f'<td class="{"neg" if _cv < 0.03 else ""}">{pct(_cv, 2)}</td>'
            f'<td>{pct(_cp.get("cart_rate"), 2)}</td>'
            f'<td>{pct(_cp.get("lead_ratio"), 2)}</td>'
            f'<td>{dec(_cp.get("cart_cost"))}</td>'
            f'<td class="{"neg" if _ctb < 0.2 else ""}">{pct(_ctb, 1)}</td>'
            f'<td>{pct(_cp.get("feibi"), 1)}</td>'
            f'<td class="{cls(_cp.get("profit"))}">'
            f'{money((_cp.get("profit") or 0) / (_cp["days"] or 1))}</td></tr>')
    if CAMP_BASE:
        campaign_base_row = (
            f'<tr style="background:rgba(99,102,241,.06)"><td><b>{escape(CAMP_BASE.get("label") or "基线")}</b><br>'
            f'<span style="opacity:.65;font-size:12px">对照，非本期</span></td>'
            f'<td>30</td><td>--</td><td>--</td><td>--</td>'
            f'<td>{pct(CAMP_BASE.get("cvr"), 2)}</td>'
            f'<td>{pct(CAMP_BASE.get("cart_rate"), 2)}</td>'
            f'<td>--</td>'
            f'<td>{dec(CAMP_BASE.get("cart_cost"))}</td>'
            f'<td>{pct(CAMP_BASE.get("cart_to_buy"), 1)}</td>'
            f'<td>--</td><td>--</td></tr>')

    _p1, _plast = CAMP_PHASES[0], CAMP_PHASES[-1]
    _cc1, _cc3 = _p1.get('cart_cost'), _plast.get('cart_cost')
    _ctb1, _ctb3 = _p1.get('cart_to_buy'), _plast.get('cart_to_buy')
    _cr1, _cr3 = _p1.get('cart_rate'), _plast.get('cart_rate')
    _b_cr = CAMP_BASE.get('cart_rate')
    _b_cc = CAMP_BASE.get('cart_cost')
    _b_ctb = CAMP_BASE.get('cart_to_buy')
    _t0, _t1 = TREND[0], TREND[-1]
    _ipv_chg = ((_t1.get('ipv') or 0) - (_t0.get('ipv') or 0)) / ((_t0.get('ipv') or 0) or 1)
    _buy_chg = ((_t1.get('buyers') or 0) - (_t0.get('buyers') or 0)) / ((_t0.get('buyers') or 0) or 1)
    _gsv_chg_t = ((_t1.get('gsv') or 0) - (_t0.get('gsv') or 0)) / ((_t0.get('gsv') or 0) or 1)
    _cart_chg = ((_t1.get('cart_users') or 0) - (_t0.get('cart_users') or 0)) / ((_t0.get('cart_users') or 0) or 1)

    # 核心结论里的一条（放在环比之前，因为它是「为什么跌」的第一解释）
    _cheap = (_b_cc and _cc3 and _cc3 <= _b_cc)
    _first_camp_day = CAMP_PHASES[-1]['start'][5:] if CAMP_PHASES else ''
    campaign_li_html = (
        f'<li><b>先看归因：本期没有任何一天是收割日。</b>'
        f'{escape(CAMP.get("name") or "大促")} 定金 {CAMP_TL[0][1][5:]} 开启、'
        f'现货预热 {CAMP_TL[1][1][5:]} 开启，<b>现货开卖 {CAMP_HARVEST} 才在窗口之外</b>；'
        f'即 {_first_camp_day} 起已进入投入期（付定金、攒加购），成交被推到开卖日。'
        f'判据不是当期 ROI，而是「买流量的效率有没有变差」：'
        f'加购成本 {dec(_cc1)} → <b>{dec(_cc3)}</b> 元'
        f'{("（比 9 月无大促基线的 " + dec(_b_cc) + " 元还低）") if _cheap and _b_cc else ""}，'
        f'说明<b>拉新/加购没变贵</b>；真正塌掉的是<b>加购→成交 {pct(_ctb1, 1)} → {pct(_ctb3, 1)}</b>'
        f'{("（9 月基线 " + pct(_b_ctb, 1) + "）") if _b_ctb else ""}——'
        f'用户在攒加购、等开卖。'
        f'蓄水动作本身也没变少：<b>加购率 {pct(_cr1, 2)} → {pct(_cr3, 2)}</b>'
        f'{("，与 9 月无大促基线的 " + pct(_b_cr, 2) + " 基本持平") if _b_cr else ""}——'
        f'进店的人照样把商品留了下来，只是不再按下付款。'
        f'同期访客 {_ipv_chg * 100:+.1f}%、加购人数 {_cart_chg * 100:+.1f}%，'
        f'只有支付买家 {_buy_chg * 100:+.1f}%。<b>这是成交被推迟，不是投放失能。</b></li>')

    campaign_headline = (
        f'本报告窗口 {CUR[0]} ~ {CUR[1]} 共 {CUR_DAYS} 天，<b>没有一天是收割日</b>；'
        f'其中 {_first_camp_day} 起已进入{CAMP.get("name") or "大促"}投入期（定金期 + 现货预热），'
        f'现货开卖要等到 <b>{CAMP_HARVEST}</b>。'
        f'所以末段 GSV 塌陷是活动节奏的结果，评估口径必须换成「蓄水效率」而非当期投产。')

    # 第 1 节的判断正文
    _verdict_bits = []
    _verdict_bits.append(
        f'<b>买流量没变贵：</b>加购成本 {dec(_cc1)} → {dec(_cc3)} 元'
        f'{("（9 月基线 " + dec(_b_cc) + " 元，本期反而更低）") if _cheap and _b_cc else ""}；'
        f'10-18 访客 {_t1.get("ipv"):,} 为窗口内最高（较 {_t0.get("date")[5:]} {_ipv_chg * 100:+.1f}%）。')
    _verdict_bits.append(
        f'<b>蓄水动作本身没变少：</b>加购率 {pct(_cr1, 2)} → <b>{pct(_cr3, 2)}</b>'
        f'{("（9 月无大促基线 " + pct(_b_cr, 2) + "，本期末段与基线持平）") if _b_cr else ""}——'
        f'进店的人照样把商品加进购物车，只是不再下单。这条把「用户跑了」排除掉了：'
        f'人还在、动作还在，卡在付款这一步。')
    _verdict_bits.append(
        f'<b>崩的是成交转化：</b>加购→成交 {pct(_ctb1, 1)} → <b>{pct(_ctb3, 1)}</b>'
        f'{("，9 月无大促基线为 " + pct(_b_ctb, 1)) if _b_ctb else ""}；'
        f'支付买家 {_buy_chg * 100:+.1f}%，GSV {_gsv_chg_t * 100:+.1f}%。')
    _lr1, _lr3 = _p1.get('lead_ratio'), _plast.get('lead_ratio')
    if _lr1 and _lr3 and _lr3 > _lr1:
        _verdict_bits.append(
            f'<b>进店人群的意向浓度反而更高：</b>引导访问潜客占比 {pct(_lr1, 2)} → '
            f'<b>{pct(_lr3, 2)}</b>（{( _lr3 - _lr1) * 100:+.2f}pt）——'
            f'进店的人里被识别为潜客的比例在升，说明<b>流量质量没有退</b>，'
            f'是这批人把下单动作留到了 {CAMP_HARVEST}。这条进一步排除了「投放买来一堆垃圾流量」的解释。')

    # 被推迟的成交量级（粗算，标注口径边界）
    if CAMP_OV and _b_ctb and (CAMP_OV.get('cart_u') or 0):
        _ov_buyers = CAMP_OV.get('buyers') or 0
        _cf_buyers = (CAMP_OV.get('cart_u') or 0) * _b_ctb
        _aov = (CAMP_OV.get('gsv') or 0) / (_ov_buyers or 1)
        _gap_buyers = _cf_buyers - _ov_buyers
        if _gap_buyers > 0:
            _verdict_bits.append(
                f'<b>被推迟的量级（粗算）：</b>现货预热两天 {CAMP_OV.get("cart_u"):,} 次加购只成交 '
                f'{_ov_buyers} 个买家（{pct(CAMP_OV.get("cart_to_buy"), 1)}）；'
                f'若按 9 月 {pct(_b_ctb, 1)} 的加购转化，同样加购量约对应 {_cf_buyers:,.0f} 个买家，'
                f'差额约 <b>{_gap_buyers:,.0f} 个买家 ≈ {wan(_gap_buyers * _aov)}万 GSV</b>'
                f'（按本期客单价 {dec(_aov)} 元折算）。这是<b>推迟</b>不是<b>消失</b>——'
                f'开卖后能否回流，取决于承接动作。')

    campaign_verdict_html = '<br>'.join(_verdict_bits)

# ---- 引导访问潜客占比：万相台 inshopPotentialUv / inshopUv（单品日粒度） ----
_LEAD = (CAMP or {}).get('lead') or {}
_LEAD_RANGE = _LEAD.get('table_range') or {}
_LC = _LEAD.get('current') or {}
_LP = _LEAD.get('prev') or {}
_LEAD_CAVEAT = _LEAD.get('caveat') or '单品口径不可相加'
if _LEAD.get('available') and _LC.get('ratio') is not None:
    _cmp_txt = ''
    if _LP.get('ratio') is not None:
        _dpt = (_LC['ratio'] - _LP['ratio']) * 100
        _cmp_txt = (f'；{P_PREV_DESC} {pct(_LP["ratio"], 2)}'
                    f'（{"+" if _dpt >= 0 else ""}{_dpt:.2f}pt）')
    lead_value_html = (
        f'<b>{pct(_LC["ratio"], 2)}</b>'
        f'（潜客 {_LC.get("potential_uv", 0):,} / 入店访客 {_LC.get("inshop_uv", 0):,}，'
        f'{_LC.get("days", 0)} 天{_cmp_txt}）')
    lead_note_html = (
        '口径：万相台 <code>inshopPotentialUv / inshopUv</code>，即「引导访问潜客数 ÷ 入店访客数」，'
        '与平台字段 <code>inshopPotentialUvRate</code> 逐行一致（714 行核对，0 例外）。'
        '<b>注意两点：</b>①这里的「入店访客」是<b>推广引导进店</b>的人数，'
        '不等于左侧「访客」（BI 店铺访客），两者不同源、<b>不能相除或对照</b>；'
        f'②{_LEAD_CAVEAT}——本行是先把阶段内各单品之相加总、再相除，'
        '用来比阶段之间的高低没问题，但不能当店铺整体指标看。')
else:
    lead_value_html = '<b>--</b>'
    lead_note_html = ('万相台潜客数据本期未取到'
                      + (f'（{_LEAD.get("error")}）' if _LEAD.get('error') else '')
                      + '，本报告用「加购率」作蓄水代理指标。')

if _LEAD.get('available'):
    ITEM_RATE_NOTE = (
        '「加购率」＝店铺侧加购人数 ÷ 访客（与分阶段表同口径，<b>不是</b>推广点击转化）；'
        '「潜客占比」＝引导访问潜客数 ÷ 入店访客数（万相台 <code>inshopPotentialUvRate</code>，'
        '单品日粒度），可横向比较；<b>但各行不可相加</b>，加总没有意义。')
else:
    ITEM_RATE_NOTE = (
        '「加购率」＝店铺侧加购人数 ÷ 访客（与分阶段表同口径，<b>不是</b>推广点击转化）；'
        '「潜客占比」本期显示 <b>--</b>：万相台潜客数据未取到——<b>缺数就是缺数，没有拿别的口径冒充</b>。')

# ---- 逐日蓄水表：把「流量涨、加购涨、买家掉」这件事按天摊开 ----
_LEAD_DAY = {(_d.get('date') or ''): _d for _d in (_LEAD.get('daily') or [])}
_camp_daily_rows = ''
for _r in TREND:
    _cv = _r.get('cvr') or 0
    _ctb = _r.get('cart_to_buy') or 0
    _in_pre = CAMP_OV and CAMP_OV.get('start') and CAMP_OV['start'] <= _r['date'] <= CAMP_OV.get('end', '')
    _mark = (' <span class="tag tag--bad">预热</span>' if _in_pre else '')
    _camp_daily_rows += (
        f'<tr><td>{_r["date"][5:]}{_mark}</td>'
        f'<td>{(_r.get("ipv") or 0):,}</td>'
        f'<td>{(_r.get("buyers") or 0):,}</td>'
        f'<td class="{"neg" if _cv < 0.03 else ""}">{pct(_cv, 2)}</td>'
        f'<td>{(_r.get("cart_users") or 0):,}</td>'
        f'<td>{pct(_r.get("cart_rate"), 2)}</td>'
        f'<td>{pct((_LEAD_DAY.get(_r["date"]) or {}).get("lead_ratio"), 2)}</td>'
        f'<td class="{"neg" if _ctb < 0.2 else ""}">{pct(_ctb, 1)}</td>'
        f'<td>{dec(_r.get("cart_cost"))}</td>'
        f'<td>{money(_r.get("ad_spend"))}</td>'
        f'<td class="{cls(_r.get("profit"))}">{money(_r.get("profit"))}</td></tr>')

campaign_block = ''
if HAS_CAMP:
    campaign_block = f'''
<section>
  <h2><span class="n">◎</span>活动节奏：窗口内没有一天是收割日</h2>
  <p class="sub">这一节回答「为什么跌」。{escape(CAMP.get("name") or "大促")} 把成交切成两段：投入期（付定金、攒加购）与收割期（付尾款、成交）。
  本报告窗口的末段（{CAMP_PHASES[-1]["start"][5:]} 起）已进入投入期，<b>且整段不含收割日</b>，
  因此末段 GSV 塌陷有相当部分是活动节奏所致，不能拿当期投产直接判断投放好坏。</p>

  {campaign_timeline_html}

  <div class="callout callout--info" style="margin-top:14px">
    <b>判据换一下：</b>投入期不看 ROI，看两个「买流量」的指标——
    <b>加购成本</b>（花费 ÷ 加购人数，即买一个未来成交机会要多少钱）和
    <b>加购→成交转化</b>（攒下的加购有多少真流到成交）。前者衡量投放效率，后者衡量成交时点。
    {campaign_headline}
  </div>

  <h3>分阶段：蓄水效率 vs 成交转化</h3>
  <p class="sub" style="margin-top:-4px">各段为<b>互斥</b>分段（可相加＝本期合计）。日均值便于跨段比较；加购成本与加购→成交为比率，由段内总量重推。</p>
  <div class="table-wrap"><table class="rpt">
    <thead><tr><th>阶段</th><th>天数</th><th>日均 GSV</th><th>日均访客</th><th>日均买家</th>
    <th>转化率</th><th>加购率</th><th>潜客占比</th><th>加购成本</th><th>加购→成交</th><th>费比</th><th>日均净利</th></tr></thead>
    <tbody>{campaign_phase_rows}{campaign_base_row}</tbody>
  </table></div>
  <p class="legend">「加购率」＝加购人数 ÷ 访客，量的是<b>进店的人里有多少把商品留了下来</b>；「潜客占比」＝引导访问潜客数 ÷ 入店访客数（万相台口径，各段内按单品汇总后相除，只看高低不比加总；其分母是<b>推广引导进店</b>人数，与本表「访客」不同源）；「加购成本」越低＝买流量越便宜；「加购→成交」越低＝用户越不愿意此刻下单。基线行为 2026-09 整月（无大促），用于判断本期数值是否异常。</p>

  <div class="callout callout--info">
    <b>引导潜客占比：</b>{lead_value_html}
    <br><span style="opacity:.85">{lead_note_html}</span>
  </div>

  <h3>逐日：流量在涨、加购在涨、买家在掉</h3>
  <div class="table-wrap"><table class="rpt">
    <thead><tr><th>日期</th><th>访客</th><th>支付买家</th><th>转化率</th><th>加购人数</th>
    <th>加购率</th><th>潜客占比</th><th>加购→成交</th><th>加购成本</th><th>推广花费</th><th>净利润</th></tr></thead>
    <tbody>{_camp_daily_rows}</tbody>
  </table></div>
  <p class="legend">「访客/支付买家/加购人数」为 BI 店铺口径；「潜客占比」为万相台口径（分母是<b>推广引导进店</b>人数，与「访客」列不同源，不可相除）。两列并排是为了看趋势是否同向，不是同一分母下的两个比例。</p>

  <div class="callout callout--warn">
    <b>归因结论：</b>{campaign_verdict_html}
    <br><span style="opacity:.85"><b>边界：</b>定金/预售金额未入库（<code>daily_data.presale_amount</code> 本期全为 NULL），
    因此「被推迟了多少成交」只能用加购量 × 历史加购转化率<b>粗算</b>，不是账实数字；
    开卖后实际回流多少，需在 {CAMP_HARVEST} 之后用同期数据复核。</span>
  </div>
</section>
'''




# ---------------- 第 4 节高费比规律（按实测亏损比例说） ----------------
_hr_items = DATA.get('high_ratio_items') or []
if _over35 and (_over35.get('n') or 0) > 0:
    _hr_n, _hr_loss = int(_over35['n']), int(_over35.get('loss_n') or 0)
    _hr_verdict = (f'净销费比 &gt;35% 的 {_hr_n} 款里 <b>{_hr_loss} 款亏损</b>'
                   f'（合计利润率 {pct(_over35.get("profit_rate"), 1)}，'
                   f'合计净销 {money(_over35.get("net"))}）。')
    if _hr_loss == _hr_n:
        _hr_verdict += '全部亏损——高投放冲量但毛利撑不起费比，是本轮费比恶化的直接来源。'
    else:
        _hr_verdict += f'有 {_hr_n - _hr_loss} 款仍盈利，不能一概而论，需逐款看毛利。'
elif _hr_items:
    _hr_loss = len([m for m in _hr_items if (m.get('profit') or 0) < 0])
    _hr_verdict = (f'上表 {len(_hr_items)} 款高费比单品中 {_hr_loss} 款亏损。')
else:
    _hr_verdict = '本周期没有净销费比 &gt;35% 且净销 &gt;3000 的单品，该风险在本期不成立。'


# ---------------- 第 5 节机会单品：内容在 COLS_EFF 定义之后拼（见文件后部 eff_body） ----------------
_eff = DATA.get('efficient_items') or []


# ---------------- 第 7 节：分析 / 根因 / 下一步（全部由实测值拼） ----------------
_rc = []

# 根因 1：渠道效率（只在关键词确实更低时才这么写）
if kw and site and CH_KW_VS_SITE == '低于':
    _rc.append(f'<li><b>渠道结构失衡：</b>关键词推广占 {pct(kw.get("spend_share"), 0)} 花费但 '
               f'ROI 仅 <b>{dec(kw.get("roi"))}</b>，低于全站推广的 {dec(site.get("roi"))}'
               f'（差 {CH_KW_GAP:.2f}）；预算压在低效渠道上，投产被系统性拉低。</li>')
elif CH_RANKED:
    _best = CH_SIGNIFICANT[0] if CH_SIGNIFICANT else CH_RANKED[0]
    _rc.append(f'<li><b>渠道效率：</b>本期渠道 ROI 最高为 {_best["name"]}'
               f'（{dec(_best.get("roi"))}），最低为 '
               f'{(CH_SIGNIFICANT[-1] if len(CH_SIGNIFICANT) > 1 else _best)["name"]}'
               f'（{dec((CH_SIGNIFICANT[-1] if len(CH_SIGNIFICANT) > 1 else _best).get("roi"))}）。'
               f'渠道不是本期利润转负的主因——{pct(S.get("profit_rate"), 1)} 的利润率下滑'
               f'需要从毛利/成本侧解释。</li>')

# 根因 2：投放与利润脱钩（用实测数字）
if loss.get('count'):
    _rc.append(f'<li><b>投放与利润脱钩：</b>{loss["count"]} 款亏损单品合计亏 '
               f'{money(abs(loss["total_loss"]))}，其中 {loss["with_promo"]} 款仍在投、'
               f'耗掉 {money(loss["promo_spend_of_loss"])} 推广费'
               f'（占商品级推广花费 {pct(loss_share, 0)}）——投放决策只看投产、没看利润。</li>')

# 根因 3：毛利/成本结构（成本齐备时才算占比，否则如实说不可拆）
if not PS_EMPTY_EARLY and (PS.get('net_sales') or 0):
    _ps_net = PS['net_sales']
    _buckets = [('商品成本', PS.get('product_cost')), ('销售费用', PS.get('sales_cost')),
                ('自定义费用', PS.get('custom_cost')), ('物流费', PS.get('logistics_cost')),
                ('平台费', PS.get('platform_fee')), ('其他', PS.get('other_cost'))]
    _buckets = [(n, v) for n, v in _buckets if v is not None]
    _top = sorted(_buckets, key=lambda x: x[1], reverse=True)[:2]
    _detail = '、'.join(f'{n}占净销 {pct(v / _ps_net)}' for n, v in _top)
    _rc.append(f'<li><b>费用本已沉重：</b>成本齐备的 {COST_DAYS} 天窗口里，{_detail}；'
               f'毛利空间被挤压，费比一升利润立刻被吞。</li>')
else:
    _rc.append('<li><b>费用结构不可拆：</b>本期成本列在 BI 字段窗口内为 NULL，'
               '利润结构只能覆盖部分天数，费用桶结论存在边界（见第 6 节）。</li>')

# 根因 4：需求侧（转化率）——区分「投放失能」与「成交被推迟」
_conv = S.get('conversion')
_conv_prev = P.get('conversion')
if _conv is not None and _conv_prev:
    _conv_chg = (_conv - _conv_prev) / abs(_conv_prev)
    if _conv_chg < -0.1:
        if HAS_CAMP:
            _ctb_a = (CAMP_PHASES[0].get('cart_to_buy') or 0)
            _ctb_z = (CAMP_PHASES[-1].get('cart_to_buy') or 0)
            _cc_a = CAMP_PHASES[0].get('cart_cost')
            _cc_z = CAMP_PHASES[-1].get('cart_cost')
            _rc.append(
                f'<li><b>成交被活动节奏推迟，不是投放失能：</b>转化率 {pct(_conv_prev, 2)} → {pct(_conv, 2)}'
                f'（{_conv_chg * 100:+.1f}%）看着像投放失效，但拆开看——加购成本 {dec(_cc_a)} → {dec(_cc_z)} 元'
                f'（拉新没变贵，甚至更便宜），塌的是<b>加购→成交 {pct(_ctb_a, 1)} → {pct(_ctb_z, 1)}</b>。'
                f'本期末段（{CAMP_PHASES[-1]["start"][5:]} 起）已进入{CAMP.get("name") or "大促"}投入期'
                f'（定金 {CAMP_TL[0][1][5:]} 开、现货预热 {CAMP_TL[1][1][5:]} 开），'
                f'现货开卖 {CAMP_HARVEST} 才在窗口之外——'
                f'用户把成交压到了开卖日。<b>真正的风险不是这一周亏，而是开卖时承接不住这批加购。</b></li>')
        else:
            _rc.append(f'<li><b>转化端同步走弱：</b>本期转化率 {pct(_conv, 2)} vs 上期 '
                       f'{pct(_conv_prev, 2)}（{_conv_chg * 100:+.1f}%），'
                       f'流量还在但成交效率下降——这是需求侧信号，不只是投放问题。</li>')

root_cause_items = '\n        '.join(_rc)

# 下一步：按本期是否真的有机会单品分叉，不写死「放大机会单品」
_ns = []
if HAS_CAMP:
    # 有活动节奏时，第一动作不是「砍」，而是「别在收割前砍」+「确保承接」
    _ov_cart = (CAMP_OV or {}).get('cart_u') or 0
    _ns.append(
        f'<li><b>先别按这一周的 ROI 做止损决策（最重要）：</b>窗口末段是投入期，'
        f'当期投产 {dec(S.get("roi"))} 天然偏低。<b>{CAMP_HARVEST} 现货开卖前不要砍量</b>——'
        f'现货预热两天买来的 {_ov_cart:,} 次加购正是开卖日的成交来源，'
        f'此刻降预算等于把蓄好的水放掉。止损动作放到开卖后 3~5 天，用真实回流数据再判。</li>')
    _ns.append(
        f'<li><b>收割期承接（{CAMP_HARVEST} 前必须就位）：</b>'
        f'①对已加购未成交人群做定向召回（加购人群包 + 短信/专属券），'
        f'把 {pct((CAMP_OV or {}).get("cart_to_buy"), 1)} 的加购→成交拉回 9 月 {pct((CAMP_BASE or {}).get("cart_to_buy"), 1)} 的水平；'
        f'②库存与价格对齐尾款节奏（定金用户付尾款优先级、避免到手价高于预热期）；'
        f'③开卖当天预算提前预留，不要等到当天才加——预热期加购成本 '
        f'{dec((CAMP_OV or {}).get("cart_cost"))} 元是本周最便宜的一档。</li>')
else:
    _ns.append(f'<li><b>止损（下周）：</b>对 {loss["count"]} 款亏损单品逐款过审，'
               f'先降预算/关停 TOP 亏损款，预计释放 '
               f'{money(loss["promo_spend_of_loss"] * 0.5)} 预算。</li>')
if kw and site and CH_KW_VS_SITE == '低于':
    _ns.append(f'<li><b>调结构（开卖后执行）：</b>关键词推广预算下调 20%~30%，'
               f'向全站推广（ROI {dec(site.get("roi"))}）与 ROI 更高的渠道迁移；'
               f'建立「利润 + 费比」双门槛的投放准入。</li>' if HAS_CAMP else
               f'<li><b>调结构：</b>关键词推广预算下调 20%~30%，'
               f'向全站推广（ROI {dec(site.get("roi"))}）与 ROI 更高的渠道迁移；'
               f'建立「利润 + 费比」双门槛的投放准入。</li>')
else:
    _ns.append('<li><b>调结构：</b>建立「利润 + 费比」双门槛的投放准入，'
               '不以投产作为唯一放量依据。</li>')
if _eff:
    _ns.append(f'<li><b>放大：</b>对第 5 节 {len(_eff)} 款机会单品加曝光、提货品权重，'
               f'用自然转化力换规模。</li>')
else:
    _ns.append('<li><b>先修结构、再谈放大：</b>本期没有「利润&gt;1000 且费比&lt;15%」的款，'
               '不具备加预算放大的标的。优先做毛利与成本侧排查'
               '（商品成本、销售费用、自定义费用占比），把「不投推广也能赚」的款找出来，'
               '再作为放量池。</li>')
_ns.append(f'<li><b>数据补口：</b>{P_COST_NOTE or "费用列缺失需补采"}'
           f' 另外 2025-10 无日粒度数据，同比补齐后才能做年度对比；'
           f'<code>presale_amount</code> 需在采集侧补上，否则定金蓄水量永远只能粗算。</li>')
next_step_items = '\n        '.join(_ns)


def _fmt(v, kind):
    if v is None:
        return '--'
    if kind == 'money':
        return money(v)
    if kind == 'wanu':
        return f'{wan(v)}万'
    if kind == 'pct':
        return pct(v)
    if kind == 'pct2':
        return pct(v, 2)
    if kind == 'roi':
        return dec(v)
    if kind == 'wan':
        return wan(v)
    return str(v)


def cmp_table():
    """环比 / 同比 对比表。环比=前 30 天；同比=09-07~09-30 同期 24 天（两侧同窗口）。"""
    yc, yp = YC, YP

    def change(cur, prev, kind):
        if cur is None or prev in (None, 0):
            return '--', ''
        if kind == 'pt':
            d = (cur - prev) * 100
            return f'{d:+.2f}pt', ('pos' if d > 0 else 'neg')
        if kind == 'abs':
            d = cur - prev
            return f'{d:+,.2f}', ('pos' if d > 0 else 'neg')
        if kind == 'abs_wan':
            d = (cur - prev) / 10000
            return f'{d:+,.2f}万', ('pos' if d > 0 else 'neg')
        d = (cur - prev) / abs(prev) * 100
        return f'{d:+.1f}%', ('pos' if d > 0 else 'neg')

    # (标签, 本期, 环比基期, 同比本期, 同比基期, 展示格式, 变化格式, 涨是好事?)
    rows = [
        ('推广花费（万元）', S['ad_spend'], P['ad_spend'], yc.get('ad_spend'), yp.get('ad_spend'), 'wanu', 'pct', None),
        ('销售额 GSV（万元）', S['gsv'], P['gsv'], yc.get('gsv'), yp.get('gsv'), 'wanu', 'pct', True),
        ('净销售额（万元）', S['net_sales'], P['net_sales'], yc.get('net_sales'), yp.get('net_sales'), 'wanu', 'pct', True),
        ('净利润（万元）', S['profit'], P['profit'], yc.get('profit'), yp.get('profit'), 'wanu', 'abs_wan', True),
        ('利润率', S['profit_rate'], P['profit_rate'], yc.get('profit_rate'), yp.get('profit_rate'), 'pct2', 'pt', True),
        ('投产比', S['roi'], P['roi'], yc.get('roi'), yp.get('roi'), 'roi', 'abs', True),
        ('费比', S['ad_ratio'], P['ad_ratio'], yc.get('ad_ratio'), yp.get('ad_ratio'), 'pct2', 'pt', False),
        ('净费比', S['net_expense_ratio'], P['net_expense_ratio'], yc.get('net_expense_ratio'), yp.get('net_expense_ratio'), 'pct2', 'pt', False),
    ]
    body = []
    for label, cur, prev, ycur, yprev, fmt, ckind, good_up in rows:
        mom_txt, mom_sign = change(cur, prev, ckind)
        yoy_txt, yoy_sign = change(ycur, yprev, ckind)
        if good_up is None:
            mom_cls = yoy_cls = ''
        else:
            mom_cls = (mom_sign if good_up else ('neg' if mom_sign == 'pos' else ('pos' if mom_sign == 'neg' else '')))
            yoy_cls = (yoy_sign if good_up else ('neg' if yoy_sign == 'pos' else ('pos' if yoy_sign == 'neg' else '')))
        body.append(
            f'<tr><td class="ttl">{label}</td><td>{_fmt(cur, fmt)}</td>'
            f'<td class="{mom_cls}">{mom_txt}</td>'
            f'<td class="{yoy_cls}">{yoy_txt}</td>'
            f'<td class="muted">{_fmt(yprev, fmt)}</td></tr>')
    _yoy_hdr = f'{YOY_DAYS} 天' if YOY_OK else '无数据'
    return ('<div class="table-wrap"><table class="rpt">'
            f'<thead><tr><th>指标</th><th>本期（{CUR_DAYS} 天）</th><th>环比（{P_PREV_DESC}，{PREV_DAYS} 天）</th>'
            f'<th>同比（{_yoy_hdr}）</th><th>去年同期值（{_yoy_hdr}）</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


# ============ 图表 ============
def chart_trend():
    tr = DATA['trend']
    w, h = 1000, 240
    pad_l, pad_r, pad_t, pad_b = 56, 56, 16, 34
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b
    max_spend = max((r['ad_spend'] or 0) for r in tr) or 1
    profits = [r['profit'] or 0 for r in tr]
    pmax, pmin = max(profits + [0]), min(profits + [0])
    prange = (pmax - pmin) or 1
    n = len(tr)
    bw = iw / n * 0.6
    bars, pts = [], []
    for i, r in enumerate(tr):
        x = pad_l + iw / n * (i + 0.5)
        bh = (r['ad_spend'] or 0) / max_spend * ih
        bars.append(f'<rect x="{x - bw / 2:.1f}" y="{pad_t + ih - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="#c7d2fe" rx="2"><title>{r["date"]} 花费 {money(r["ad_spend"])} 元</title></rect>')
        py = pad_t + ih - ((r['profit'] or 0) - pmin) / prange * ih
        pts.append((x, py, r))
    zero_y = pad_t + ih - (0 - pmin) / prange * ih
    poly = ' '.join(f'{x:.1f},{y:.1f}' for x, y, _ in pts)
    dots = ''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{"#dc2626" if r["profit"] < 0 else "#16a34a"}"><title>{r["date"]} 净利润 {money(r["profit"])} 元</title></circle>' for x, y, r in pts)
    labels = ''.join(f'<text x="{pad_l + iw / n * (i + 0.5):.1f}" y="{h - 12}" font-size="10" fill="#64748b" text-anchor="middle">{r["date"][5:]}</text>' for i, r in enumerate(tr) if i % 5 == 0)
    return f'''<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="推广花费与净利润日趋势">
<line x1="{pad_l}" y1="{pad_t + ih}" x2="{w - pad_r}" y2="{pad_t + ih}" stroke="#e2e8f0"/>
<line x1="{pad_l}" y1="{zero_y:.1f}" x2="{w - pad_r}" y2="{zero_y:.1f}" stroke="#94a3b8" stroke-dasharray="4 3"/>
{''.join(bars)}<polyline points="{poly}" fill="none" stroke="#6366f1" stroke-width="2"/>{dots}{labels}
<text x="{pad_l}" y="{pad_t - 4}" font-size="10" fill="#a5b4fc">▮ 推广花费</text>
<text x="{pad_l + 76}" y="{pad_t - 4}" font-size="10" fill="#6366f1">━ 净利润</text>
<text x="6" y="{pad_t + 10}" font-size="10" fill="#64748b">花费峰值 {wan(max_spend)}万</text>
<text x="{w - 6}" y="{pad_t + 10}" font-size="10" fill="#64748b" text-anchor="end">利润 {money(pmin)} ~ {money(pmax)}</text>
</svg>'''


def chart_channels():
    rows = [r for r in CH['current'] if (r['ad_spend'] or 0) > 0]
    if not rows:
        return '<p class="legend">当前品类下无可用渠道数据。</p>'
    w = 1000
    row_h = 46
    h = row_h * len(rows) + 16
    maxs = max(r['ad_spend'] for r in rows) or 1
    bar_x, bar_w, roi_x = 150, 440, 900
    parts = []
    for i, r in enumerate(rows):
        y = 10 + i * row_h
        bl = (r['ad_spend'] or 0) / maxs * bar_w
        roi = r.get('roi')
        color = '#16a34a' if (roi or 0) >= 3 else ('#f59e0b' if (roi or 0) >= 1.5 else '#dc2626')
        parts.append(
            f'<text x="0" y="{y + 18}" font-size="13" fill="#0f172a">{escape(r["name"])}</text>'
            f'<rect x="{bar_x}" y="{y + 4}" width="{bl:.1f}" height="22" fill="{color}" rx="3" opacity="0.85"/>'
            f'<text x="{bar_x + bl + 8:.1f}" y="{y + 20}" font-size="12" fill="#334155">{wan(r["ad_spend"])}万 · {pct(r.get("spend_share"), 1)}</text>'
            f'<text x="{roi_x}" y="{y + 20}" font-size="12.5" font-weight="600" fill="{color}">ROI {dec(roi, 2)}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="渠道花费与投产">{ "".join(parts) }</svg>'


def chart_scatter():
    items = sorted([m for m in DATA['top_spend_items'] if (m['promo_spend'] or 0) > 0],
                   key=lambda x: x['promo_spend'], reverse=True)[:40]
    if not items:
        return ''
    w, h = 1000, 340
    pad_l, pad_r, pad_t, pad_b = 60, 24, 20, 40
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b
    xmax = max(m['promo_spend'] or 0 for m in items) or 1
    ys = [m['profit_rate'] or 0 for m in items]
    # 纵轴按分位裁剪，避免小样本极值（如净销千元级、利润率 -100%）把轴压扁；
    # 越界点贴边显示，真实值仍在悬浮提示里。
    srt = sorted(ys)
    n = len(srt)

    def q(p):
        return srt[min(max(int(n * p), 0), n - 1)]

    if n > 6:
        lo, hi = q(0.10), q(0.90)
    else:
        lo, hi = min(srt), max(srt)
    lo, hi = min(lo, 0), max(hi, 0)
    lo = max(lo, -0.8)   # 硬下限，防止单点拖垮整轴
    hi = min(hi, 0.5)
    if (hi - lo) < 0.2:
        lo, hi = lo - 0.1, hi + 0.1
    yr = (hi - lo) or 1
    ymin, ymax = lo - yr * 0.08, hi + yr * 0.08
    yr = ymax - ymin
    net_max = max((m['net_sales'] or 0) for m in items) or 1

    def px(v):
        return pad_l + v / xmax * iw

    def py(v):
        return min(max(pad_t + ih - (v - ymin) / yr * ih, pad_t), pad_t + ih)

    zero_y = py(0)
    clipped = sum(1 for v in ys if v < ymin or v > ymax)
    dots = []
    for m in items:
        cx, cy = px(m['promo_spend'] or 0), py(m['profit_rate'] or 0)
        r = 4 + (m['net_sales'] or 0) / net_max * 10
        color = '#dc2626' if (m['profit'] or 0) < 0 else '#16a34a'
        dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{color}" fill-opacity="0.5" stroke="{color}" stroke-width="1.2"><title>{escape(m["title"][:24])}&#10;推广花费 {money(m["promo_spend"])} 元&#10;净利润 {money(m["profit"])} 元 · 利润率 {pct(m["profit_rate"])}&#10;净销售额 {money(m["net_sales"])} 元</title></circle>')
    ticks = ''.join(
        f'<line x1="{pad_l}" y1="{py(ymin + yr * f):.1f}" x2="{w - pad_r}" y2="{py(ymin + yr * f):.1f}" stroke="#eef2f7"/>'
        f'<text x="{pad_l - 6}" y="{py(ymin + yr * f) + 3:.1f}" font-size="10" fill="#64748b" text-anchor="end">{(ymin + yr * f) * 100:.0f}%</text>'
        for f in (0, 0.25, 0.5, 0.75, 1))
    return f'''<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="单品推广花费与利润率散点">
{ticks}<line x1="{pad_l}" y1="{zero_y:.1f}" x2="{w - pad_r}" y2="{zero_y:.1f}" stroke="#94a3b8" stroke-dasharray="5 3"/>
<text x="{pad_l + 4}" y="{zero_y - 5:.1f}" font-size="10" fill="#64748b">盈亏平衡线</text>{''.join(dots)}
<text x="{pad_l}" y="{h - 12}" font-size="11" fill="#64748b">推广花费 →</text>
<text x="{w - pad_r}" y="{h - 12}" font-size="11" fill="#64748b" text-anchor="end">纵轴：利润率（净利润/净销售额）· 气泡：净销售额{' · ' + str(clipped) + ' 个极值贴边显示' if clipped else ''}</text></svg>'''


# ============ 表格（含主图 + 商品ID） ============
# 单品表列头缩写（全表 16~18 列，长表头会把右侧列挤出可视区，故只在此缩写，全称见 title/表注）
_TH_TITLE = {
    '潜客占比': '引导访问潜客占比 = 引导访问潜客数 ÷ 入店访客数（万相台 inshopPotentialUvRate，单品日粒度；各行不可相加）',
    '加购率': '店铺侧加购率 = 加购人数 ÷ 访客（不是推广点击转化率）',
}


def item_table(items, cols):
    head = ''.join(
        (f'<th title="{_TH_TITLE[c[1]]}">{c[1]}</th>' if c[1] in _TH_TITLE else f'<th>{c[1]}</th>')
        for c in cols)
    body = []
    for m in items:
        img = m.get('image_url') or ''
        uri = thumb_data_uri(img, m['product_id']) if img else ''
        thumb = (f'<img class="thumb" src="{uri}" alt="">'
                 if uri else '<span class="thumb thumb--ph"></span>')
        tds = []
        for key, _l, fmt, polarity in cols:
            v = m.get(key)
            if fmt == 'money':
                txt = money(v)
            elif fmt == 'wan':
                txt = wan(v)
            elif fmt == 'pct':
                txt = pct(v)
            elif fmt == 'roi':
                txt = dec(v, 2)
            else:
                txt = '--' if v is None else str(v)
            klass = ''
            if polarity and v is not None:
                if polarity == 'up_good':
                    klass = cls(v)
                elif polarity == 'low' and key in ('ad_ratio_bill', 'promo_ad_ratio'):
                    klass = 'neg' if v > 0.35 else ''
            tds.append(f'<td class="{klass}">{txt}</td>')
        body.append(
            f'<tr><td class="prod"><div class="prod__cell">{thumb}'
            f'<span class="prod__ttl" title="{escape(m["title"])}">{escape(m["title"])}</span></div></td>'
            f'<td class="pid">{escape(m["product_id"])}</td>' + ''.join(tds) + '</tr>')
    return (f'<div class="table-wrap"><table class="rpt{" rpt--wide" if len(cols) >= 9 else ""}">'
            f'<thead><tr><th>商品</th><th>商品ID</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


COLS_TOP = [
    ('promo_spend', '推广花费', 'money', None),
    ('promo_attr', '推广成交', 'money', None),
    ('promo_roi', '投产', 'roi', 'up_good'),
    ('promo_direct_roi', '直接投产', 'roi', 'up_good'),
    ('promo_ad_ratio', '费比', 'pct', 'low'),
    ('cart_cost', '加购成本', 'money', None),
    ('cart_rate_shop', '加购率', 'pct', None),
    ('lead_ratio', '潜客占比', 'pct', None),
    ('new_cost', '拉新成本', 'money', None),
    ('net_sales', '净销售额', 'money', None),
    ('net_sales_change', '净销环比', 'pct', 'up_good'),
    ('profit', '净利润', 'money', 'up_good'),
    ('profit_change', '净利环比', 'pct', 'up_good'),
    ('profit_yoy', '净利同比', 'pct', 'up_good'),
    ('profit_rate', '利润率', 'pct', 'up_good'),
    ('ad_ratio_bill', '净销费比', 'pct', 'low'),
]
COLS_LOSS = [
    ('net_sales', '净销售额', 'money', None),
    ('profit', '净利润', 'money', 'up_good'),
    ('profit_rate', '利润率', 'pct', 'up_good'),
    ('profit_change', '净利环比', 'pct', 'up_good'),
    ('profit_yoy', '净利同比', 'pct', 'up_good'),
    ('promo_spend', '推广花费', 'money', None),
    ('promo_roi', '投产', 'roi', 'up_good'),
    ('cart_rate_shop', '加购率', 'pct', None),
    ('lead_ratio', '潜客占比', 'pct', None),
    ('ad_ratio_bill', '净销费比', 'pct', 'low'),
]
COLS_EFF = [
    ('net_sales', '净销售额', 'money', None),
    ('net_sales_yoy', '净销同比', 'pct', 'up_good'),
    ('ad_ratio_bill', '净销费比', 'pct', 'low'),
    ('cart_rate_shop', '加购率', 'pct', None),
    ('lead_ratio', '潜客占比', 'pct', None),
    ('profit', '净利润', 'money', 'up_good'),
    ('profit_yoy', '净利同比', 'pct', 'up_good'),
    ('profit_rate', '利润率', 'pct', 'up_good'),
    ('promo_spend', '推广花费', 'money', None),
]

# ---- 第 5 节正文（依赖 item_table / COLS_EFF，必须定义在其后） ----
if _eff:
    eff_body = (item_table(_eff[:15], COLS_EFF) +
                f'<p class="legend">{ITEM_RATE_NOTE}</p>' +
                '<div class="callout callout--good"><b>共同特征：</b>'
                '净销费比低（近乎自然流量驱动）、利润率明显高于品类均值。'
                '这类款<b>不是靠砸钱起来的</b>，说明产品本身有自然转化力，'
                '值得在货品结构里加大权重。</div>')
else:
    _b15_n = int((_b15 or {}).get('n') or 0)
    _b15_pr = (_b15 or {}).get('profit_rate')
    eff_body = (
        '<div class="callout callout--bad">'
        '<b>本周期没有符合「利润&gt;1000 且费比&lt;15%」的款——这一栏是空的，不是没渲染。</b><br>'
        f'最接近的一档是净销费比 &lt;15% 的 {_b15_n} 款，合计利润率 <b>{pct(_b15_pr, 1)}</b>，'
        f'也没能覆盖成本。说明本期<b>不是「少投几个款就能救回来」的问题</b>：'
        f'连几乎不投推广的款都在亏，压力来自毛利/成本结构，'
        f'加预算放大在当前结构下只会放大亏损。'
        '</div>')

ch_rows = []
for r in CH['current']:
    if not (r.get('ad_spend')):
        continue
    roi = r.get('roi')
    roi_c = 'pos' if (roi or 0) >= 3 else ('neg' if (roi or 0) < 1.5 else 'warn')
    sc = r.get('spend_change')
    ch_rows.append(
        f'<tr><td class="ttl">{escape(r["name"])}</td>'
        f'<td>{money(r.get("ad_spend"))}</td><td>{pct(r.get("spend_share"))}</td>'
        f'<td>{money(r.get("attributed_payment"))}</td><td class="{roi_c}">{dec(roi)}</td>'
        f'<td>{dec(r.get("direct_roi"))}</td><td>{pct(r.get("cart_rate"), 2)}</td>'
        f'<td>{money(r.get("cart_cost"))}</td><td>{money(r.get("new_cost"))}</td>'
        f'<td>{pct(r.get("new_buyer_share"), 2)}</td>'
        f'<td class="{cls(sc)}">{("+" if (sc or 0) >= 0 else "") + pct(sc) if sc is not None else "--"}</td></tr>')

bucket_defs = [('product_cost', '净货品成本'), ('sales_cost', '销售费用'), ('custom_cost', '自定义费用'),
               ('logistics_cost', '发货费用'), ('other_cost', '其他费用')]
ps_net_raw = PS.get('net_sales') or 0
ps_net = ps_net_raw or 1
ps_five = sum(PS.get(k) or 0 for k in
              ('sales_cost', 'custom_cost', 'product_cost', 'logistics_cost', 'other_cost'))
ps_profit = PS.get('profit') or 0
ps_resid = (ps_net_raw - ps_five) - ps_profit
# 成本桶是否齐备：任一桶有值即可拆；全为 None 说明本期成本列未采集（≠ 为 0）。
PS_EMPTY = all(PS.get(k) is None for k in
               ('sales_cost', 'custom_cost', 'product_cost', 'logistics_cost', 'other_cost'))
if PS_EMPTY:
    ps_body = (
        '<div class="callout callout--warn"><b>本期成本列全为 NULL，利润结构不可拆桶。</b>'
        '下方各项显示 <code>--</code> 只代表「未采集」，<b>不代表为 0</b>；净利润总额仍有效（取自 BI 利润字段）。'
        '根因：BI 对近期日期不返回成本字段（字段窗口），需等窗口过后由滚动补采回填，或由 BI 导出 Excel 后导入。</div>')
    ps_note = ''
else:
    # 五项占比统一以「成本合计」为分母 → 合计恒为 100%（构成图语义成立）；
    # 净销售额与成本合计按同一尺度绘制，便于看出「成本是否超过净销」。
    scale = max(ps_net, ps_five) or 1
    ps_parts = ''.join(
        f'<div class="pf-row"><span class="pf-lbl">{lb}</span>'
        f'<div class="pf-bar"><i style="width:{(PS.get(k) or 0) / (ps_five or 1) * 100:.1f}%"></i></div>'
        f'<span class="pf-val">{wan(PS.get(k))}万 · {pct((PS.get(k) or 0) / (ps_five or 1))}</span></div>'
        for k, lb in bucket_defs)
    gap = ps_five - ps_net
    gap_txt = f'　净销的 {pct(ps_five / ps_net)}' if gap > 0 else ''
    ps_body = (
        f'<div class="pf-row"><span class="pf-lbl">净销售额</span>'
        f'<div class="pf-bar"><i style="width:{ps_net / scale * 100:.1f}%"></i></div>'
        f'<span class="pf-val">{wan(ps_net)}万</span></div>'
        f'<div class="pf-sep">净销售额与成本合计按同一尺度对比 · 以下五项占比以「成本合计」为分母（合计恒为 100%）</div>'
        + ps_parts +
        f'<div class="pf-row pf-row--total"><span class="pf-lbl">成本合计</span>'
        f'<div class="pf-bar"><i style="width:{ps_five / scale * 100:.1f}%;background:var(--bad)"></i></div>'
        f'<span class="pf-val" style="color:var(--bad)">100.0%{gap_txt}</span></div>'
        f'<div class="pf-row pf-row--profit"><span class="pf-lbl">利润</span>'
        f'<div class="pf-bar"><i style="width:{min(abs(ps_profit) / (ps_five or 1) * 100, 100):.1f}%;'
        f'background:{"var(--bad)" if ps_profit < 0 else "var(--good)"}"></i></div>'
        f'<span class="pf-val" style="color:{"var(--bad)" if ps_profit < 0 else "var(--good)"};font-weight:600">'
        f'{wan(ps_profit)}万 · 利润率 {pct(ps_profit / ps_net, 2)}</span></div>')
    DIAG = DATA.get('profit_structure_diag') or {}
    xlsx_rows = DIAG.get('xlsx_rows') or 0
    xlsx_days = DIAG.get('xlsx_days') or 0
    resid_html = ''
    if abs(ps_resid) > 1:
        resid_html = (
            f'<br><b>恒等校验：</b>净销售额 − 成本合计 = {wan(ps_net_raw - ps_five)}万，'
            f'BI 利润列 {wan(ps_profit)}万，两者相差 <b>{ps_resid:,.0f} 元</b>'
            f'（占净销 {abs(ps_resid) / ps_net * 100:.2f}%）。')
        if xlsx_rows:
            resid_html += (
                f'差额来自 <b>Excel 导入源</b>的日期（本窗口 {xlsx_days} 天 / {xlsx_rows:,} 行）：'
                f'该源的净销售额与利润被取整为整数、成本列保留小数，逐项相加与利润列不闭合；'
                f'API 采集源的日期该差额 ≈ 0，逐行严格闭合。')
    ps_note = (
        f'<div class="callout callout--info"><b>结构解读：</b>成本合计 {wan(ps_five)}万中，'
        f'<b>自定义费用（含广告+平台费+赠品）占 {pct((PS["custom_cost"] or 0) / (ps_five or 1))}</b>、'
        f'销售费用占 {pct((PS["sales_cost"] or 0) / (ps_five or 1))}、'
        f'净货品成本占 {pct((PS["product_cost"] or 0) / (ps_five or 1))}。'
        f'该窗口利润 {wan(ps_profit)}万（利润率 {pct(ps_profit / ps_net, 2)}）。'
        f'<br><span style="opacity:.8">口径提示：平台花费 {wan(PS["platform_fee"])}万为账单参考桶，不参与利润公式；'
        f'利润取 BI 利润列（= 净销售额 − 五项成本）。</span>'
        f'{resid_html}</div>')

ch_note = ('渠道为部分口径：品类模式下 campaign 粒度行不带商品映射，渠道花费由「商品×渠道创意明细 + 计划→商品 1:1 精确归因补全站」合成，'
           '多商品全站计划无商品级明细，故渠道花费合计小于品类账单花费。' if CH.get('partial') else '')

# ---- 渠道结构结论：按实测 ROI 分叉，不写死「关键词是效率洼地」 ----
if kw and site and CH_KW_VS_SITE == '低于':
    ch_verdict_html = (
        f'关键词推广花了 {wan(kw["ad_spend"])}万（占 {pct(kw["spend_share"], 0)}），'
        f'投产仅 <b>{dec(kw["roi"])}</b>，低于全站推广（ROI {dec(site["roi"])}，差 {CH_KW_GAP:.2f}）。'
        f'<b>预算应向全站倾斜、压缩低效关键词计划</b>。')
elif kw and site:
    ch_verdict_html = (
        f'关键词推广花了 {wan(kw["ad_spend"])}万（占 {pct(kw["spend_share"], 0)}），'
        f'投产 <b>{dec(kw["roi"])}</b>，<b>{CH_KW_VS_SITE}</b>全站推广（ROI {dec(site["roi"])}，差 {CH_KW_GAP:.2f}）。'
        f'本期渠道之间没有明显效率塌陷，<b>不宜把预算迁移当作主要抓手</b>。')
elif CH_RANKED:
    _b = CH_SIGNIFICANT[0] if CH_SIGNIFICANT else CH_RANKED[0]
    ch_verdict_html = f'本期有效渠道中 {_b["name"]} 的 ROI 最高（{dec(_b.get("roi"))}）。'
else:
    ch_verdict_html = '本期无渠道级花费明细。'

GEN_DATE = __import__('datetime').date.today().isoformat()

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>推广分析复盘 · {CAT_LABEL} · {P_NAME}（{CUR[0]}~{CUR[1]}）</title>
<style>
:root{{--brand:#6366f1;--brand-soft:#eef2ff;--ink:#0f172a;--ink2:#334155;--muted:#64748b;
--line:#e2e8f0;--bg:#f8fafc;--card:#fff;--good:#16a34a;--bad:#dc2626;--warn:#f59e0b;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.65;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 24px 80px}}
.hero{{background:linear-gradient(135deg,#4f46e5,#6366f1 55%,#818cf8);color:#fff;padding:44px 40px 38px;border-radius:0 0 22px 22px;margin:0 -24px 30px;box-shadow:0 10px 30px rgba(79,70,229,.18)}}
.hero__eyebrow{{font-size:13px;letter-spacing:.14em;text-transform:uppercase;opacity:.85;font-weight:600}}
.hero h1{{margin:8px 0 12px;font-size:30px;letter-spacing:-.4px}}
.hero__meta{{font-size:13.5px;opacity:.92;display:flex;gap:18px;flex-wrap:wrap}}
.hero__meta b{{font-weight:600}}
.hero__cat{{display:inline-block;margin-top:12px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);padding:3px 12px;border-radius:20px;font-size:13px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:26px 28px;margin-bottom:22px;box-shadow:0 1px 2px rgba(15,23,42,.04)}}
h2{{font-size:19px;margin:0 0 4px;display:flex;align-items:center;gap:10px}}
h2 .n{{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:8px;background:var(--brand-soft);color:var(--brand);font-size:14px;font-weight:700;flex:none}}
.sub{{color:var(--muted);font-size:13px;margin:0 0 18px}}
h3{{font-size:15px;margin:26px 0 10px;color:var(--ink2)}}
h3:first-of-type{{margin-top:14px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:6px}}
.kpi{{border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:#fff}}
.kpi__lbl{{font-size:12.5px;color:var(--muted);margin-bottom:6px}}
.kpi__val{{font-size:23px;font-weight:700;letter-spacing:-.5px}}
.kpi__val small{{font-size:13px;font-weight:500;color:var(--muted);margin-left:3px}}
.kpi__d{{font-size:12.5px;margin-top:5px}}
.pos{{color:var(--good)}} .neg{{color:var(--bad)}} .warn{{color:var(--warn)}} .muted{{color:var(--muted)}}
.chart{{width:100%;height:auto;display:block;margin:8px 0 4px}}
.table-wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:10px}}
table.rpt{{width:100%;border-collapse:collapse;font-size:12.8px;font-variant-numeric:tabular-nums}}
table.rpt th{{background:#f1f5f9;color:var(--ink2);font-weight:600;text-align:right;padding:9px 11px;white-space:nowrap;border-bottom:1px solid var(--line);position:sticky;top:0}}
table.rpt th:first-child,table.rpt th:nth-child(2),table.rpt td:first-child,table.rpt td.pid{{text-align:left}}
table.rpt td{{padding:7px 11px;text-align:right;border-bottom:1px solid #f1f5f9;white-space:nowrap;vertical-align:middle}}
table.rpt tbody tr:hover{{background:#f8fafc}}
td.prod{{min-width:250px;max-width:300px}}
.prod__cell{{display:flex;align-items:center;gap:9px}}
.thumb{{width:40px;height:40px;border-radius:7px;object-fit:cover;border:1px solid var(--line);background:#f1f5f9;flex:none}}
.thumb--ph{{display:inline-block}}
.prod__ttl{{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ink);font-size:12.5px;line-height:1.35;max-width:240px}}
td.pid{{color:var(--muted);font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}}
/* 宽表（列数 >11）压缩字号与内边距，避免右侧列被挤出可视区 */
table.rpt--wide{{font-size:10.5px}}
table.rpt--wide th,table.rpt--wide td{{padding:4px 5px}}
table.rpt--wide td.prod{{min-width:148px;max-width:160px}}
table.rpt--wide .prod__ttl{{max-width:88px;font-size:10.5px}}
table.rpt--wide .thumb{{width:28px;height:28px;border-radius:5px}}
table.rpt--wide td.pid{{font-size:10px}}
.callout{{border-radius:12px;padding:16px 18px;margin:14px 0;font-size:14px;border:1px solid}}
.callout--warn{{background:#fffbeb;border-color:#fde68a;color:#92400e}}
.callout--info{{background:var(--brand-soft);border-color:#c7d2fe;color:#3730a3}}
.callout--bad{{background:#fef2f2;border-color:#fecaca;color:#991b1b}}
.callout--good{{background:#f0fdf4;border-color:#bbf7d0;color:#166534}}
.concl{{list-style:none;padding:0;margin:0;counter-reset:c}}
.concl li{{position:relative;padding:13px 16px 13px 52px;border-bottom:1px solid var(--line);font-size:14.2px}}
.concl li:last-child{{border-bottom:none}}
.concl li::before{{counter-increment:c;content:counter(c);position:absolute;left:14px;top:12px;width:24px;height:24px;background:var(--brand);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:700}}
.triple{{display:grid;grid-template-columns:1fr;gap:12px}}
.tcard{{border:1px solid var(--line);border-left:4px solid var(--brand);border-radius:10px;padding:14px 18px;background:#fcfcff}}
.tcard h4{{margin:0 0 6px;font-size:14.5px;color:var(--brand)}}
.tcard p{{margin:0;font-size:13.8px;color:var(--ink2)}}
.tcard ul{{margin:6px 0 0;padding-left:18px;font-size:13.8px;color:var(--ink2)}}
.pf-row{{display:flex;align-items:center;gap:12px;margin:7px 0;font-size:13.5px}}
.pf-lbl{{width:96px;color:var(--ink2);flex:none}}
.pf-bar{{flex:1;height:16px;background:#f1f5f9;border-radius:8px;overflow:hidden}}
.pf-bar i{{display:block;height:100%;background:linear-gradient(90deg,#818cf8,#6366f1);border-radius:8px}}
.pf-val{{width:190px;text-align:right;color:var(--muted);font-variant-numeric:tabular-nums;flex:none}}
.pf-sep{{font-size:12px;color:var(--muted);margin:12px 0 2px;padding-top:10px;border-top:1px dashed var(--line)}}
.pf-row--total{{margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)}}
.pf-row--total .pf-lbl{{font-weight:700}}
.pf-row--profit{{margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)}}
.legend{{font-size:12px;color:var(--muted);margin-top:10px}}
.tag{{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:20px;background:#f1f5f9;color:var(--ink2);margin-left:6px}}
.tag--bad{{background:#fef2f2;color:#b91c1c}} .tag--good{{background:#f0fdf4;color:#15803d}}
footer{{text-align:center;color:var(--muted);font-size:12.5px;padding:10px}}
@media(max-width:760px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.hero{{padding:32px 22px}}.wrap{{padding:0 14px 60px}}}}
</style>
</head>
<body>
<div class="wrap">
<header class="hero">
  <div class="hero__eyebrow">推广分析复盘 · 结合单品利润</div>
  <h1>{P_TITLE}推广投放复盘</h1>
  <div class="hero__meta">
    <span>数据窗口 <b>{CUR[0]} ~ {CUR[1]}</b>（{CUR_DAYS} 天）</span>
    <span>对比期 <b>{PREV[0]} ~ {PREV[1]}</b>（{PREV_DAYS} 天）</span>
    <span>数据截至 <b>{P_ASOF}</b></span>
  </div>
  <div class="hero__cat">品类口径：{escape(CAT_LABEL)}</div>
</header>

<section>
  <h2><span class="n">✦</span>核心结论</h2>
  <p class="sub">先看结论，再往下看数据。红＝需关注（亏损 / 效率恶化），绿＝正向。</p>
  <ol class="concl">
    {campaign_li_html}
    {yoy_li_html}
    <li><b>环比（{P_PREV_DESC}）：</b>推广花费 {wan(P['ad_spend'])}万 → <b>{wan(S['ad_spend'])}万</b>（{spend_chg}），GSV {wan(P['gsv'])}万 → <b>{wan(S['gsv'])}万</b>（{gsv_chg}），投产 {dec(P['roi'])} → <b>{dec(S['roi'])}</b>（{roi_delta}）、净费比 {pct(P['net_expense_ratio'])} → <b>{pct(S['net_expense_ratio'])}</b>（{ner_delta}）。净利润 {wan(P['profit'])}万 → <b>{wan(S['profit'])}万</b>（利润率 {pct(S['profit_rate'], 2)}）。</li>
    {rhythm_li_html}
    <li><b>预算高度压在亏损款上。</b>{escape(CAT_LABEL)} {DATA['product_count']} 款中 <b>{loss['count']} 款净利为负</b>，合计亏损 <b>{wan(abs(loss['total_loss']))}万</b>；其中 {loss['with_promo']} 款仍在投推广，耗掉 <b>{wan(loss['promo_spend_of_loss'])}万</b> 推广费（≈商品级推广花费的 {pct(loss_share, 0)}）。</li>
    {channel_li_html}
    {efficiency_li_html}
  </ol>
</section>

{campaign_block}

<section>
  <h2><span class="n">1</span>推广总览</h2>
  <p class="sub">花费/投产/费比/净费比/利润取自 BI 账单口径（daily_data），品类按 products.shop_label 过滤；与月复盘「广告复盘」汇总同源。</p>
  <div class="kpis">
    <div class="kpi"><div class="kpi__lbl">推广花费</div><div class="kpi__val">{wan(S['ad_spend'])}<small>万</small></div><div class="kpi__d muted">{_mom_line(S['ad_spend'], P['ad_spend'], 'pct', None)[0]} · {_yoy_line(YC.get('ad_spend'), YP.get('ad_spend'), 'pct', None)[0]}</div></div>
    <div class="kpi"><div class="kpi__lbl">投产比（GSV/花费）</div><div class="kpi__val">{dec(S['roi'])}</div><div class="kpi__d {_mom_line(S['roi'], P['roi'], 'abs', True)[1]}">{_mom_line(S['roi'], P['roi'], 'abs', True)[0]}</div><div class="kpi__d {_yoy_line(YC.get('roi'), YP.get('roi'), 'abs', True)[1]}">{_yoy_line(YC.get('roi'), YP.get('roi'), 'abs', True)[0]}</div></div>
    <div class="kpi"><div class="kpi__lbl">费比（花费/GSV）</div><div class="kpi__val">{pct(S['ad_ratio'])}</div><div class="kpi__d {_mom_line(S['ad_ratio'], P['ad_ratio'], 'pt', False)[1]}">{_mom_line(S['ad_ratio'], P['ad_ratio'], 'pt', False)[0]}</div><div class="kpi__d {_yoy_line(YC.get('ad_ratio'), YP.get('ad_ratio'), 'pt', False)[1]}">{_yoy_line(YC.get('ad_ratio'), YP.get('ad_ratio'), 'pt', False)[0]}</div></div>
    <div class="kpi"><div class="kpi__lbl">净费比（花费/净销售额）</div><div class="kpi__val">{pct(S['net_expense_ratio'])}</div><div class="kpi__d {_mom_line(S['net_expense_ratio'], P['net_expense_ratio'], 'pt', False)[1]}">{_mom_line(S['net_expense_ratio'], P['net_expense_ratio'], 'pt', False)[0]}</div><div class="kpi__d {_yoy_line(YC.get('net_expense_ratio'), YP.get('net_expense_ratio'), 'pt', False)[1]}">{_yoy_line(YC.get('net_expense_ratio'), YP.get('net_expense_ratio'), 'pt', False)[0]}</div></div>
    <div class="kpi"><div class="kpi__lbl">净销售额</div><div class="kpi__val">{wan(S['net_sales'])}<small>万</small></div><div class="kpi__d {_mom_line(S['net_sales'], P['net_sales'], 'pct', True)[1]}">{_mom_line(S['net_sales'], P['net_sales'], 'pct', True)[0]}</div><div class="kpi__d {_yoy_line(YC.get('net_sales'), YP.get('net_sales'), 'pct', True)[1]}">{_yoy_line(YC.get('net_sales'), YP.get('net_sales'), 'pct', True)[0]}</div></div>
    <div class="kpi"><div class="kpi__lbl">净利润</div><div class="kpi__val {cls(S['profit'])}">{wan(S['profit'])}<small>万</small></div><div class="kpi__d muted">环比前值 {wan(P['profit'])}万 · 去年同期 {wan(YP.get('profit'))}万</div></div>
    <div class="kpi"><div class="kpi__lbl">利润率（净利/净销）</div><div class="kpi__val {cls(S['profit_rate'])}">{pct(S['profit_rate'], 2)}</div><div class="kpi__d {_mom_line(S['profit_rate'], P['profit_rate'], 'pt', True)[1]}">{_mom_line(S['profit_rate'], P['profit_rate'], 'pt', True)[0]}</div><div class="kpi__d {_yoy_line(YC.get('profit_rate'), YP.get('profit_rate'), 'pt', True)[1]}">{_yoy_line(YC.get('profit_rate'), YP.get('profit_rate'), 'pt', True)[0]}</div></div>
    <div class="kpi"><div class="kpi__lbl">品类商品数 / 覆盖天</div><div class="kpi__val">{S['prods']:,}<small>款</small></div><div class="kpi__d" style="color:var(--muted)">{S['days']} 天</div></div>
  </div>
  <h3>环比 / 同比对比</h3>
  <p class="sub" style="margin-top:-4px">环比＝{P_PREV_DESC}（{PREV[0]}~{PREV[1]}，{PREV_DAYS} 天）；同比＝{P_YOY_DESC}（{YOY_PW[0]}~{YOY_PW[1]}{"，两侧各 " + str(YOY_DAYS) + " 天，等长可比" if YOY_OK else "，去年同期无日粒度数据，同比留空"}）。红＝不利，绿＝有利。</p>
  {cmp_table()}
  {yoy_callout_html}
  <h3>日趋势：推广花费（柱）与净利润（线）</h3>
  {chart_trend()}
  <div class="callout callout--info">
    <b>怎么读：</b>柱状（浅紫）＝每日推广花费；折线（靛蓝）＝每日净利润，绿点＝当日盈利、红点＝当日亏损。
    柱状（浅紫）＝每日推广花费；折线（靛蓝）＝每日净利润，绿点＝当日盈利、红点＝当日亏损。
    本周期共 {len(TREND)} 天，其中 <b>{LOSS_DAYS} 天当日净利为负</b>——花费抬升的日子与利润承压的日子是否同向，一眼可辨。
  </div>
</section>

<section>
  <h2><span class="n">2</span>渠道拆解</h2>
  <p class="sub">品类口径：商品×渠道创意明细（关键词/人群/店铺直达）+ 计划→商品 1:1 精确归因补全站推广。ROI＝归因成交÷花费，绿≥3 / 黄 1.5~3 / 红&lt;1.5。</p>
  {chart_channels()}
  <div class="table-wrap"><table class="rpt">
    <thead><tr><th>渠道</th><th>推广花费</th><th>花费占比</th><th>推广成交</th><th>投产</th><th>直接投产</th><th>加购率</th><th>加购成本</th><th>拉新成本</th><th>新客占比</th><th>花费环比</th></tr></thead>
    <tbody>{''.join(ch_rows)}</tbody>
  </table></div>
  <div class="callout callout--warn">
    <b>结构问题：</b>{ch_verdict_html}
    <br><span style="opacity:.85">{ch_note}另：<b>渠道同比不可算</b>——{YOY_PW[0][:4]} 年的推广事实只有商品级合计行（渠道名挂在计划粒度行上，去年无该粒度），故渠道表只给环比。</span>
  </div>
</section>

<section>
  <h2><span class="n">3</span>单品推广 × 利润</h2>
  <p class="sub">横轴＝推广花费，纵轴＝利润率（净利润/净销售额），气泡＝净销售额；红＝亏损、绿＝盈利。这是「投放是否真的赚钱」的一眼判断。</p>
  {chart_scatter()}
  <div class="callout callout--bad">
    <b>一眼看出：</b>花费越大的商品，越容易落在盈亏平衡线下方。TOP 消耗里
    「{escape(DATA['top_spend_items'][0]['title'][:20])}」花费 {money(DATA['top_spend_items'][0]['promo_spend'])} 元、投产 {dec(DATA['top_spend_items'][0]['promo_roi'])}，
    净利润 <b>{money(DATA['top_spend_items'][0]['profit'])} 元</b>（利润率 {pct(DATA['top_spend_items'][0]['profit_rate'])}）——<b>投产为正 ≠ 赚钱</b>。
  </div>
  <h3>TOP20 消耗单品（按推广花费）</h3>
  {item_table(DATA['top_spend_items'], COLS_TOP)}
  <p class="legend">推广花费/成交/投产/费比/加购成本/拉新成本＝万相台归因口径（商品级合计）；净销售额/净利润/利润率/净销费比＝BI 账单口径。两套花费口径不同源，勿相减。<b>净利环比＝{P_PREV_DESC}（{PREV[0]}~{PREV[1]}）；净利同比＝{P_YOY_DESC}（{YOY_PW[0]}~{YOY_PW[1]}，两侧等长）</b>；基数过小（利润 &lt;200 元）时不出变化率，显示 --。<br>{ITEM_RATE_NOTE}</p>
</section>

<section>
  <h2><span class="n">4</span>问题单品：亏损榜 & 高费比榜</h2>
  <p class="sub">亏损单品＝窗口内净利润&lt;0；高费比榜＝净销售额&gt;3000 且净销费比&gt;35%（有规模、效率差）。</p>
  <h3>亏损单品 TOP（按亏损额）<span class="tag tag--bad">共 {loss['count']} 款 · 合计 -{wan(abs(loss['total_loss']))}万</span></h3>
  {item_table(DATA['loss_items'][:15], COLS_LOSS)}
  <p class="legend">{ITEM_RATE_NOTE}</p>
  <div class="callout callout--warn">
    <b>注：</b>「补差价专用」等虚拟链接（净销极低、利润率 -1000%+）已单独隔离，不计入亏损榜与合计；上表为真实货品。
  </div>
  <h3>高费比单品 TOP（净销费比 &gt; 35%）<span class="tag tag--bad">几乎全部亏损</span></h3>
  {item_table(DATA['high_ratio_items'][:12], COLS_LOSS)}
  <div class="callout callout--bad">
    <b>规律（本期实测）：</b>{_hr_verdict}
  </div>
</section>

<section>
  <h2><span class="n">5</span>机会单品：可放大</h2>
  <p class="sub">净利润&gt;1000 且净销费比&lt;15%——赚钱且不依赖高投放，是加预算/加曝光的优先对象。</p>
  {eff_body}
</section>

<section>
  <h2><span class="n">6</span>利润结构（费用桶）</h2>
  <p class="sub">成本明细窗口 {COST_W[0]} ~ {COST_W[1]}（{COST_DAYS} 天）。{P_COST_NOTE}</p>
  {ps_body}
  {ps_note}
</section>

<section>
  <h2><span class="n">7</span>复盘结论：分析 / 根因 / 下一步</h2>
  <div class="triple">
    <div class="tcard">
      <h4>分析</h4>
      <p>{P_NAME}「{escape(CAT_LABEL)}」推广花费 {wan(S['ad_spend'])}万（环比 {spend_chg}），投产 {dec(S['roi'])}（{roi_delta}）、
      净费比 {pct(S['net_expense_ratio'])}（{ner_delta}）；净销售额 {net_chg}，
      净利润 <b>{wan(S['profit'])}万</b>（利润率 {pct(S['profit_rate'], 2)}）。
      亏损单品 {loss['count']} 款、合计 -{wan(abs(loss['total_loss']))}万，其中 {loss['with_promo']} 款仍在投、耗掉 {wan(loss['promo_spend_of_loss'])}万 预算。
      {("但这一周的亏不能单独判：窗口末段（" + CAMP_PHASES[-1]["start"][5:] + " 起）已进入 " + (CAMP.get("name") or "大促") + " 投入期，现货开卖 " + str(CAMP_HARVEST) + " 才在窗口之外；同期加购成本 " + dec((CAMP_PHASES[0].get("cart_cost"))) + " → " + dec((CAMP_PHASES[-1].get("cart_cost"))) + " 元（拉新没变贵），而加购→成交 " + pct((CAMP_PHASES[0].get("cart_to_buy")), 1) + " → " + pct((CAMP_PHASES[-1].get("cart_to_buy")), 1) + "（成交被推迟）。") if HAS_CAMP else ""}</p>
    </div>
    <div class="tcard">
      <h4>根因</h4>
      <ul>
        {root_cause_items}
      </ul>
    </div>
    <div class="tcard">
      <h4>下一步规划</h4>
      <ul>
        {next_step_items}
      </ul>
    </div>
  </div>
</section>

<section>
  <h2><span class="n">i</span>口径与数据缺口</h2>
  <ul style="font-size:13.5px;color:var(--ink2);padding-left:20px">
    <li><b>品类口径：</b>按 <code>products.shop_label</code> token 匹配「{escape(CAT_LABEL)}」（支持多标签值），全表口径一致。</li>
    <li><b>汇总口径：</b>推广花费/投产/费比/净费比/净销售额/净利润/利润率来自 <code>daily_data</code>（BI 账单口径），与月复盘「广告复盘」汇总同源。</li>
    <li><b>渠道口径：</b>品类模式下由 <code>promotion_creative_daily</code>（商品×渠道）+ 计划→商品 1:1 精确归因补全站推广合成，为<b>部分口径</b>，不支持多商品全站计划的商品级拆分。</li>
    <li><b>单品推广口径：</b><code>promotion_daily_facts</code> grain=product &amp; channel=全部（唯一带商品 ID 的完整商品级汇总），排除负 ID 与无批次行；与账单口径花费不同源，二者不可相减。</li>
    <li><b>引导访问潜客口径：</b><code>promotion_lead_daily</code>（万相台 <code>item_promotion</code> 报表，商品×日粒度），
      = <code>inshopPotentialUv / inshopUv</code>，即「引导访问潜客数 ÷ 入店访客数」，与平台 <code>inshopPotentialUvRate</code> 逐行一致。
      <b>两点限制：</b>①分母是<b>推广引导进店</b>人数，不是店铺访客（<code>daily_data.ipv</code>），两者不可相除；
      ②单品口径<b>不可相加</b>，同一用户逛多个商品会重复计数，故只用于单品横向比较与阶段趋势，不做店铺汇总。
      {('<b>本期实测：</b>该表覆盖 ' + _LEAD_RANGE['start'] + ' ~ ' + _LEAD_RANGE['end'] + '（' + f"{_LEAD_RANGE['rows']:,}" + ' 行）；本期 ' + str(_LC.get('days') or 0) + ' / ' + str(CUR_DAYS) + ' 天有数据' + ('（齐备）' if (_LC.get('days') or 0) >= CUR_DAYS else '（缺口日潜客列显示 --）') + '。') if _LEAD_RANGE else '<span class="neg"><b>本期实测：</b>该表无数据，潜客列显示 --。</span>'}</li>
    <li><b>主图：</b>取自 <code>products.image_url</code>（缺失时按推广明细兜底），已下载压缩后<b>内嵌为 base64</b>，报告可离线查看、可单文件转发。</li>
    <li><b>环比口径：</b>对比期＝{P_PREV_DESC}（{PREV[0]} ~ {PREV[1]}，{PREV_DAYS} 天），与本期等长同口径，可直接比。</li>
    <li><b>同比口径：</b>{P_YOY_DESC}（{YOY_PW[0]} ~ {YOY_PW[1]}）。{_yoy_note if not YOY_OK else P_YOY_NOTE}</li>
    <li><b>整月同比参考：</b>{MY_CUR_M} vs {MY_PREV_M}（<code>monthly_data</code>）：GSV {wan((MYOY.get('prev') or {}).get('gsv'))}万 → {wan((MYOY.get('current') or {}).get('gsv'))}万，净利润 {wan((MYOY.get('prev') or {}).get('profit'))}万 → {wan((MYOY.get('current') or {}).get('profit'))}万。
      <span class="neg"><b>注意：</b>本期所在月 {MY_CUR_M} 在月表里是<b>未走完的月份快照</b>（{MY_CUR_M} 的月度聚合在月中跑过一次，未含全月），与完整的 {MY_PREV_M} 直接比会系统性低估；此行的方向性参考价值大于数值价值。</span></li>
    <li class="neg"><b>渠道同比缺：</b>{YOY_PW[0][:4]} 年的 <code>promotion_daily_facts</code> 只有 <code>grain='product'</code> 行，无计划/渠道粒度 → 渠道表无同比。</li>
    <li><b>小基数保护：</b>单品对比列在基期过小时不出变化率（利润 &lt;200 元、净销 &lt;500 元、推广花费 &lt;100 元），避免出现几十上百倍的伪变化。</li>
    <li><b>比率重推：</b>所有比率均由窗口总量重推，不使用均值。</li>
    <li class="neg"><b>费用列缺口：</b>BI 对近期日期不返回成本字段（字段窗口）→ 本期成本拆桶情况见第 6 节。成本明细的另一来源是 BI 导出的 Excel（<code>商品总览_*.xlsx</code>），需导出后导入。
      {("<b>本期实测：</b>成本齐备 " + str(len(COV_COST_READY)) + " 天（" + (COV_COST_READY[0] + " ~ " + COV_COST_READY[-1] if COV_COST_READY else "--") + "）；缺失 " + str(len(COV_COST_MISSING)) + " 天（" + "、".join(d[5:] for d in COV_COST_MISSING) + "）。") if COV_COST_MISSING else "<b>本期实测：成本列全部齐备。</b>"}</li>
    <li class="neg"><b>推广事实缺口：</b>{("<b>本期实测：</b>" + "、".join(COV_MISS_PROMO) + " 无商品级推广事实行，渠道/单品花费在该日被低估。") if COV_MISS_PROMO else "<b>本期实测：推广事实覆盖完整。</b>"}</li>
    <li class="neg"><b>账单日粒度缺口：</b>{("<b>本期实测：</b>" + "、".join(COV_MISS_DAILY) + " 无 daily_data 行，汇总已被低估。") if COV_MISS_DAILY else "<b>本期实测：daily_data 覆盖本期全部 " + str(COV.get('window_days') or 0) + " 天。</b>"}</li>
    <li><b>不做均摊：</b>多商品推广计划的花费不向单品摊派（无依据），故「商品级推广花费合计」（{wan(promo_product_total)}万）小于品类账单口径总花费（{wan(S['ad_spend'])}万）。</li>
  </ul>
</section>

<footer>推广分析复盘 · {escape(CAT_LABEL)} · {P_NAME} · 数据窗口 {CUR[0]} ~ {CUR[1]} · 生成于 {GEN_DATE}</footer>
</div>
</body>
</html>'''

fn = (f'reports/推广分析复盘_{CAT_LABEL}_{P_TITLE.replace(" ", "")}_'
      f'{CUR[0].replace("-", "")}-{CUR[1].replace("-", "")}.html')
with open(os.path.join(BASE, fn), 'w', encoding='utf-8') as f:
    f.write(html)
print('OK ->', fn, len(html), 'chars')

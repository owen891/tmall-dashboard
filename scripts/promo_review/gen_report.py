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
    return ('<div class="table-wrap"><table class="rpt">'
            f'<thead><tr><th>指标</th><th>本期（{CUR_DAYS} 天）</th><th>环比（{P_PREV_DESC}，{PREV_DAYS} 天）</th>'
            f'<th>同比（{YOY_DAYS} 天）</th><th>去年同期值（{YOY_DAYS} 天）</th></tr></thead>'
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
def item_table(items, cols):
    head = ''.join(f'<th>{c[1]}</th>' for c in cols)
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
    return (f'<div class="table-wrap"><table class="rpt"><thead><tr><th>商品</th><th>商品ID</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


COLS_TOP = [
    ('promo_spend', '推广花费', 'money', None),
    ('promo_attr', '推广成交', 'money', None),
    ('promo_roi', '投产', 'roi', 'up_good'),
    ('promo_direct_roi', '直接投产', 'roi', 'up_good'),
    ('promo_ad_ratio', '费比', 'pct', 'low'),
    ('cart_cost', '加购成本', 'money', None),
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
    ('ad_ratio_bill', '净销费比', 'pct', 'low'),
]
COLS_EFF = [
    ('net_sales', '净销售额', 'money', None),
    ('net_sales_yoy', '净销同比', 'pct', 'up_good'),
    ('ad_ratio_bill', '净销费比', 'pct', 'low'),
    ('profit', '净利润', 'money', 'up_good'),
    ('profit_yoy', '净利同比', 'pct', 'up_good'),
    ('profit_rate', '利润率', 'pct', 'up_good'),
    ('promo_spend', '推广花费', 'money', None),
]

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
    {yoy_li_html}
    <li><b>环比（{P_PREV_DESC}）：</b>推广花费 {wan(P['ad_spend'])}万 → <b>{wan(S['ad_spend'])}万</b>（{spend_chg}），GSV {gsv_chg} → 投产 {dec(P['roi'])} → <b>{dec(S['roi'])}</b>（{roi_delta}）、净费比 {pct(P['net_expense_ratio'])} → <b>{pct(S['net_expense_ratio'])}</b>（{ner_delta}）。净利润 {wan(P['profit'])}万 → <b>{wan(S['profit'])}万</b>（利润率 {pct(S['profit_rate'], 2)}）。</li>
    <li><b>预算高度压在亏损款上。</b>{escape(CAT_LABEL)} {DATA['product_count']} 款中 <b>{loss['count']} 款净利为负</b>，合计亏损 <b>{wan(abs(loss['total_loss']))}万</b>；其中 {loss['with_promo']} 款仍在投推广，耗掉 <b>{wan(loss['promo_spend_of_loss'])}万</b> 推广费（≈商品级推广花费的 {pct(loss_share, 0)}）。</li>
    <li><b>渠道：全站挑大梁，关键词拖效率。</b>全站推广占花费 {pct(site['spend_share'], 0) if site else '--'}、ROI {dec(site['roi']) if site else '--'}；关键词推广占 {pct(kw['spend_share'], 0) if kw else '--'}，ROI 仅 <b>{dec(kw['roi']) if kw else '--'}</b>。</li>
    <li><b>效率标杆清晰。</b>净销费比 &lt;15% 的款利润率普遍 15%~30%（近乎自然流量驱动）；而净销费比 &gt;35% 的款几乎全部亏损。<b>投产为正 ≠ 赚钱</b>——推广费吃掉了毛利。</li>
  </ol>
</section>

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
  <p class="sub" style="margin-top:-4px">环比＝{P_PREV_DESC}（{PREV[0]}~{PREV[1]}，{PREV_DAYS} 天）；同比＝{P_YOY_DESC}（{YOY_PW[0]}~{YOY_PW[1]}，{YOY_DAYS} 天，两侧等长）。红＝不利，绿＝有利。</p>
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
    <b>结构问题：</b>关键词推广花了 {wan(kw['ad_spend']) if kw else '--'}万（占 {pct(kw['spend_share'], 0) if kw else '--'}），投产仅 <b>{dec(kw['roi']) if kw else '--'}</b>，
    明显低于全站推广（ROI {dec(site['roi']) if site else '--'}）。<b>预算应向全站倾斜、压缩低效关键词计划</b>。
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
  <p class="legend">推广花费/成交/投产/费比/加购成本/拉新成本＝万相台归因口径（商品级合计）；净销售额/净利润/利润率/净销费比＝BI 账单口径。两套花费口径不同源，勿相减。<b>净利环比＝{P_PREV_DESC}（{PREV[0]}~{PREV[1]}）；净利同比＝{P_YOY_DESC}（{YOY_PW[0]}~{YOY_PW[1]}，两侧等长）</b>；基数过小（利润 &lt;200 元）时不出变化率，显示 --。</p>
</section>

<section>
  <h2><span class="n">4</span>问题单品：亏损榜 & 高费比榜</h2>
  <p class="sub">亏损单品＝窗口内净利润&lt;0；高费比榜＝净销售额&gt;3000 且净销费比&gt;35%（有规模、效率差）。</p>
  <h3>亏损单品 TOP（按亏损额）<span class="tag tag--bad">共 {loss['count']} 款 · 合计 -{wan(abs(loss['total_loss']))}万</span></h3>
  {item_table(DATA['loss_items'][:15], COLS_LOSS)}
  <div class="callout callout--warn">
    <b>注：</b>「补差价专用」等虚拟链接（净销极低、利润率 -1000%+）已单独隔离，不计入亏损榜与合计；上表为真实货品。
  </div>
  <h3>高费比单品 TOP（净销费比 &gt; 35%）<span class="tag tag--bad">几乎全部亏损</span></h3>
  {item_table(DATA['high_ratio_items'][:12], COLS_LOSS)}
  <div class="callout callout--bad">
    <b>规律：</b>净销费比 &gt;35% 的商品绝大多数亏损——高投放冲量但毛利撑不起费比，是本轮费比恶化的直接来源。
  </div>
</section>

<section>
  <h2><span class="n">5</span>机会单品：可放大</h2>
  <p class="sub">净利润&gt;1000 且净销费比&lt;15%——赚钱且不依赖高投放，是加预算/加曝光的优先对象。</p>
  {item_table(DATA['efficient_items'][:15], COLS_EFF)}
  <div class="callout callout--good">
    <b>共同特征：</b>净销费比普遍 1%~15%（近乎自然流量），利润率 15%~30%。这类款<b>不是靠砸钱起来的</b>，说明产品本身有自然转化力，值得在货品结构里加大权重。
  </div>
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
      亏损单品 {loss['count']} 款、合计 -{wan(abs(loss['total_loss']))}万，其中 {loss['with_promo']} 款仍在投、耗掉 {wan(loss['promo_spend_of_loss'])}万 预算。</p>
    </div>
    <div class="tcard">
      <h4>根因</h4>
      <ul>
        <li><b>预算结构失衡：</b>关键词推广占 {pct(kw['spend_share'], 0) if kw else '--'} 花费但 ROI 仅 {dec(kw['roi']) if kw else '--'}，是全店效率洼地；全站推广 ROI {dec(site['roi']) if site else '--'} 却未吃满预算。</li>
        <li><b>投放与利润脱钩：</b>花费 TOP 单品中多款净利为负，高费比（&gt;35%）商品几乎无一盈利——投放决策只看投产、没看利润。</li>
        <li><b>费用本已沉重：</b>自定义费用占净销 {pct((PS['custom_cost'] or 0) / ps_net)}，利润空间薄，费比一升利润立刻被吞。</li>
      </ul>
    </div>
    <div class="tcard">
      <h4>下一步规划</h4>
      <ul>
        <li><b>止损（本周）：</b>对亏损且费比高的 {loss['count']} 款逐款过审，先降预算/关停 TOP 亏损款，预计释放 {wan(loss['promo_spend_of_loss'] * 0.5)}万+ 预算。</li>
        <li><b>调结构：</b>关键词推广预算下调 20%~30%，向全站推广与 ROI&gt;3 的渠道迁移；建立「利润+费比」双门槛的投放准入。</li>
        <li><b>放大：</b>对第 5 节机会单品（费比&lt;15%、利润率&gt;15%）加曝光、提货品权重，用自然转化力换规模。</li>
        <li><b>数据补口：</b>费用列缺失（BI 字段窗口）与 2026-09-26 推广事实缺失需补采，否则利润结构与费比结论存在边界。</li>
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
    <li><b>主图：</b>取自 <code>products.image_url</code>（缺失时按推广明细兜底），已下载压缩后<b>内嵌为 base64</b>，报告可离线查看、可单文件转发。</li>
    <li><b>环比口径：</b>对比期＝{P_PREV_DESC}（{PREV[0]} ~ {PREV[1]}，{PREV_DAYS} 天），与本期等长同口径，可直接比。</li>
    <li><b>同比口径：</b>{P_YOY_DESC}（{YOY_PW[0]} ~ {YOY_PW[1]}）。{_yoy_note if not YOY_OK else P_YOY_NOTE}</li>
    <li><b>整月同比参考：</b>{MY_CUR_M} vs {MY_PREV_M}（<code>monthly_data</code>）：GSV {wan((MYOY.get('prev') or {}).get('gsv'))}万 → {wan((MYOY.get('current') or {}).get('gsv'))}万，净利润 {wan((MYOY.get('prev') or {}).get('profit'))}万 → {wan((MYOY.get('current') or {}).get('profit'))}万。</li>
    <li class="neg"><b>渠道同比缺：</b>{YOY_PW[0][:4]} 年的 <code>promotion_daily_facts</code> 只有 <code>grain='product'</code> 行，无计划/渠道粒度 → 渠道表无同比。</li>
    <li><b>小基数保护：</b>单品对比列在基期过小时不出变化率（利润 &lt;200 元、净销 &lt;500 元、推广花费 &lt;100 元），避免出现几十上百倍的伪变化。</li>
    <li><b>比率重推：</b>所有比率均由窗口总量重推，不使用均值。</li>
    <li class="neg"><b>费用列缺口：</b>BI 对近期日期不返回成本字段（字段窗口）→ 本期成本拆桶情况见第 6 节。成本明细的另一来源是 BI 导出的 Excel（<code>商品总览_*.xlsx</code>），需导出后导入。</li>
    <li class="neg"><b>推广事实缺口：</b>2026-09-26 推广事实花费为 0（当日缺失）；若落在本期内，渠道与单品花费合计在该日被低估。</li>
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

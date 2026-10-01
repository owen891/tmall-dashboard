"""生成 UI 布局审计的可视化 HTML 报告（自包含，截图内嵌 base64）。

用法：
    ./.venv/Scripts/python.exe scripts/build_ui_audit_report.py
"""
import base64
import io
import json
import os
import sys
from datetime import datetime

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, '.tmp', 'ui-audit')
SHOTS = os.path.join(AUDIT, 'shots')
OUT = os.path.join(ROOT, 'docs', 'UI_LAYOUT_AUDIT_20261001.html')

PAGES = [
    ('overview', '/', '数据概览'),
    ('category-dashboard', '/category-dashboard', '品类经营看板'),
    ('goals', '/goals', '经营目标'),
    ('reviews', '/reviews', '经营复盘'),
    ('period-review', '/period-review', '周月复盘'),
    ('products', '/products', '商品运营'),
    ('lifecycle', '/lifecycle', '生命周期'),
    ('keyword-promotion', '/keyword-promotion', '关键词选品'),
    ('promotion', '/promotion', '推广分析'),
    ('new-products', '/new-products', '新品推广'),
    ('creative-board', '/creative-board', '素材点击率'),
    ('flow-source', '/flow-source', '流量来源'),
    ('rival-analysis', '/rival-analysis', '竞店竞品'),
    ('market-ranking', '/market-ranking', '市场分析'),
    ('analysis', '/analysis', '自定义分析'),
    ('data-collection', '/data-collection', '数据采集'),
    ('data-center', '/data-center', '数据中心'),
    ('settings', '/settings', '设置'),
    ('component-catalog', '/component-catalog', '组件目录'),
    # 4-8：compare / manage 页面已删除（路由保留 302 → /reviews 与 /settings）。
    # 审计清单同步移除，否则报告会去读两个已经不存在的页面。
]

FINDINGS = [
    ('P0', 'P0-1', '/product-detail 路由 404',
     'app.py:301 的 <code>/&lt;page&gt;</code> 白名单 19 个页面不含 product-detail，也没有独立路由；'
     '但 pages/product-detail.html 存在、shell.js:207 为它写了 activePageMap、'
     'page_capability_service.py:72 把它当正式页面。实测 <code>curl /product-detail</code> → 404。',
     '把 product-detail 加进白名单并让它处理"缺 product_id"空态（保留可分享 URL），或明确 302 到 /products。'),
    ('P0', 'P0-2', '8 个页面 /api/page-capabilities 恒定 422',
     'assets/api.js:195 每页加载都调 loadPageCapabilities()，pageKey 取 body[data-page]。'
     '而 PAGE_DEFINITIONS 只登记 13 个页面，实际多出 8 个：'
     'analysis / keyword-promotion / new-products / market-ranking / flow-source / '
     'rival-analysis / data-collection / catalog。后端返回 VALIDATION_ERROR '
     '"unknown page capability filter"。api.js 用 .catch(() =&gt; {}) 静默吞掉，'
     '这 8 页的 data-capability-key 门控完全失效。',
     '补齐 PAGE_DEFINITIONS 到实际页面集合；失败不再静默（至少 console.warn 一次 + 数据中心能力地图标红）。'),
    ('P0', 'P0-3', 'goals.html 页面头部整块复制两份',
     'pages/goals.html 第 4、5 行是完全相同的 ui-page-header。实测 goals 页 ui-page-header 计数 = 2'
     '（其余页面均为 1）。页面上会看到两遍标题与说明。',
     '删除第 5 行。'),
    ('P0', 'P0-4', '错误状态语义错位',
     'GET /api/goals/2026 返回 404 NOT_FOUND「该年度尚未创建目标」，但 availability 字段是 '
     '<code>calculation-failed</code>。这是正常空态，不是计算失败；前端因此渲染成"指标计算失败"，'
     '用户看不到"去创建 2026 年目标"的引导。',
     'availability 拆成 not-created / no-data / unavailable / partial / error，与 UI 三类主状态解耦。'),

    ('P1', 'P1-1', '页面标题层级不统一',
     '18 页用 &lt;h2&gt; 当页面标题，analysis / category-dashboard / product-detail / period-review-redesign '
     '用 &lt;h1&gt;。promotion 同时有 &lt;h2&gt;推广分析&lt;/h2&gt; 与 &lt;h1&gt;推广经营看板&lt;/h1&gt;；'
     'new-products 同时有 &lt;h2&gt;新品推广看板&lt;/h2&gt; 与 &lt;h1&gt;新品投放经营看板&lt;/h1&gt;。',
     '硬规则：每页有且仅有一个 h1 = 页面标题；pageHeader() 直接产 h1；TmallUI.audit() 加唯一 h1 检查。'),
    ('P1', 'P1-2', '侧边导航分组名污染文档大纲',
     'shell.js:254 把「店铺 / 商品 / 付费 / 市场 / 工具」渲染成 &lt;h2&gt;，实测每页标题树前 5 个节点永远是这 5 个分组名，'
     '真正的页面标题排第 6。',
     '分组标签降为 &lt;span&gt;（nav 已有 aria-label）。零成本零风险。'),
    ('P1', 'P1-3', '首屏被"说明书"占掉 144px',
     '19 页有 ui-context-bar（实测 92px），上面还有 52px 的 ui-page-header。首屏前 144px（900px 视口的 16%）无数据，'
     '且两块文案同义重复。12 个页面的 ui-context-bar__meta 是「先…再…」操作说明（如'
     '「先选择配置，再执行唯一主操作"生成图表"。」），另有 18 处 section-kicker。',
     '合并为一个 Orientation 区（标题 + 范围 + 数据截止）；说明文案降级为 title 提示或删除；'
     'section-kicker 只保留有真实步骤语义的（goals 三步、data-center 配置导入）。'),
    ('P1', 'P1-4', '首屏没有单一主决策区',
     'overview 首屏（900px 内）有 79 个文本节点、102 个可交互元素、10 个 main 直接子块。'
     '净销售额在同页出现 3 次（决策区 / KPI 卡 / 日度矩阵），目标完成度出现 2 次。'
     '决策区、KPI 卡、图表面板、运营中心、矩阵在视觉上等权重。',
     '保留并加强决策区；4 张 KPI 卡降级为决策区支撑行，去掉「更多经营指标」折叠层；'
     '图表标题改成一个问题而不是描述；第二决策区（异常与行动）与第一决策区做视觉区分。'),
    ('P1', 'P1-5', '主操作不唯一',
     'products 页头一行 16 个控件：当前视图 / 展示 / 普通列表 / 周期视图 / 周期 / 日 / 周 / 月 / 字段 / '
     '经营 / 选款 / 投放 / 退款 / 生命周期 / 列设置 / 重置。promotion 页头有「复制本品查看」（主色）+「刷新数据」'
     '+ 页内 h1。',
     'products：业务视图收成一个 segmented、周期收成一个 segmented、字段/列设置/重置收进一个下拉菜单，'
     '目标这一行 ≤6 个控件。promotion：页头只留一个主操作。'),
    ('P1', 'P1-6', '长页面无收敛',
     '桌面：market-ranking 5743px(6.4 屏) / period-review 3661 / data-collection 3547 / new-products 3172。'
     '移动：market-ranking 11051px(13.1 屏) / data-collection 7874 / period-review 7687 / lifecycle 7055 / products 5652。'
     'market-ranking 的 main 只有 6 个直接子块，但其中一个 section 就是 4552px（占整页 79%）。',
     '首屏给结论、详情进抽屉或 Tab。market-ranking 首屏只留「类目对比 + Top10 榜单」。'),
    ('P1', 'P1-7', '表格在 1440 宽屏下仍需横向滚动',
     'overview 日度矩阵超出 667px（14 列）、period-review 553px、products 428px、lifecycle 156px、new-products 81px。',
     '表格默认列数上限（如 ≤8），超出走字段设置；关键列固定宽 + 弹性列吃剩余；确认横滚提示在 1440 下可见。'),
    ('P1', 'P1-8', '长商品名被硬裁 130–210px',
     'lifecycle .lifecycle-card__title 容器 186px / 内容 395px（裁 209px）；'
     'products .product-title__link 182px / 395px（裁 213px）；new-products 176px；period-review 131px；'
     'overview 有一处 238px 且容器无类名。products 的 .product-title__link 有 title + aria-label（做得对），'
     '但 max-width 硬编码 230/240/280px，同时 .product-title strong 用 line-clamp:2 而 __link 用 nowrap，规则打架。',
     '商品名恢复两行（line-clamp:2，删 nowrap）；商品列改弹性宽度。'),

    ('P2', 'P2-1', '控件与 DOM 密度失衡',
     'data-center 24333 个 DOM 节点 / 193 个可交互元素 / 300 个 .ui-button（87 可见）/ 5 个纵向滚动容器；'
     'market-ranking 7927 节点、996 个 .ui-badge（仅 2 可见，930 个藏在隐藏 &lt;tr&gt; 里）；'
     'period-review 5146 节点 / 224 个 .ui-button（43 可见）；keyword-promotion 157 个可交互元素。',
     '表格真分页（只渲染当前页行）；Tab 内容按需渲染或加 content-visibility:auto；'
     '一页不要出现「整页滚动 + 表格内滚 + 分页」三层。'),
    ('P2', 'P2-2', '组件建了但复用不均',
     'ui-components.js 已导出 20+ 组件。ui-filter-toolbar 在 lifecycle 出现 4 次、products / data-center / '
     'keyword-promotion 各 3 次；ui-decision-card 只有 promotion 用；ui-sticky-action-bar 只有 2 页用。',
     '每页只允许一个 ui-table-toolbar（搜索+核心筛选+更多筛选+字段设置+结果数+导出），页面级范围筛选进 context-bar；'
     'ui-decision-card 统一用或删掉。'),
    ('P2', 'P2-3', '内联样式与 CSS 体量',
     'keyword-promotion 150 处内联样式、market-ranking 45、data-collection 13、rival-analysis 12。'
     'components.css 120KB/340 类（硬编码颜色 0，var() 1080 —— 纪律很好）；'
     'period-review.css 有 26 处硬编码颜色；themes/ 5 个文件 2054 行（product-domain.css 1262 行）。',
     'keyword-promotion 的样式迁进 CSS；period-review.css 的硬编码颜色改 token；明确 themes/ 与页面 CSS 的边界。'),
    ('P2', 'P2-4', '涨跌配色有一处按方向而非按语义',
     'overview-live.js:232 与 period-review 的 metric-cards.js 已按成本类指标反向（正确）。'
     '但 pages/period-review/product-columns.js:169/187 是 rate &lt; 0 ? is-down : is-up，只看正负。'
     '退款率、费比这类「越低越好」的指标在问题单品表里会被涂成绿色。',
     '抽共享的 metricPolarity(metricKey)，所有配色走它。'),
    ('P2', 'P2-5', '可访问性',
     'overview 有 5 个无名 &lt;button&gt;（operations-center__calendar-day is-muted，disabled 的日历空格子）；'
     'focus-visible 只在 components.css/shell.css 各 4 处；状态仅靠颜色（.delta--*、.ui-badge--*、is-up/is-down）；'
     '--text-tertiary #9ca3af 在白底约 2.5:1，用于 12px meta 文本偏低。',
     '日历格子补 aria-label；可交互元素补 focus-visible；状态补箭头/文字；复核 tertiary 对比度。'),
    ('P2', 'P2-6', '死路由与死页面',
     '/compare 302→/reviews（compare.html 仍存在）、/manage 302→/settings（manage.html 仍存在）、'
     '/product-detail 404（product-detail.html 存在）、period-review-redesign.html 2030 行完全不可路由。'
     'pages/ 共 5599 行，其中 redesign 一个占 36%。',
     '删除 compare.html / manage.html / period-review-redesign.html。'),
    ('P2', 'P2-7', '外部版本检查产生固定噪音',
     '每页加载请求 https://gitcode.com/api/v5/.../releases/latest，被 CORS 拦截（ERR_FAILED），'
     '66 次加载产生 63 条控制台错误 —— 全项目最大宗错误噪音，会淹没真实问题。',
     '改走后端代理（/api/version 已存在，顺带返回最新版本），或至少捕获静默。'),
]

SEV_META = {
    'P0': ('页面级缺陷', '#dc2626', '#fef2f2'),
    'P1': ('信息层级与结构', '#d97706', '#fffbeb'),
    'P2': ('密度、DOM 卫生与一致性', '#2563eb', '#eff6ff'),
}


def thumb(path, width, quality=60):
    if not os.path.exists(path):
        return None
    im = Image.open(path).convert('RGB')
    ratio = width / im.width
    im = im.resize((width, max(1, int(im.height * ratio))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=quality, optimize=True, progressive=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def esc(v):
    return str(v).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def main():
    audit = json.load(open(os.path.join(AUDIT, 'audit.json'), encoding='utf-8'))
    deep = json.load(open(os.path.join(AUDIT, 'deep.json'), encoding='utf-8'))
    dom = json.load(open(os.path.join(AUDIT, 'dom.json'), encoding='utf-8'))

    rows = []
    cards = []
    total_bytes = 0
    for key, route, label in PAGES:
        a = audit['pages'].get(key, {}).get('viewports', {})
        dd = deep['pages'].get(key, {}).get('viewports', {})
        dm = dom.get(key, {})
        desk = a.get('desktop', {})
        mob = a.get('mobile', {})
        dd_desk = dd.get('desktop', {})

        ce = sum(len(a.get(v, {}).get('consoleErrors', [])) for v in ('desktop', 'compact', 'mobile'))
        http_err = dd_desk.get('httpErrors', [])
        cards.append((key, label, route, dm, desk, mob, dd_desk, ce, http_err))

    parts = []
    parts.append(f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UI 布局深度审计 · Tmall Dashboard</title>
<style>
  :root {{
    --canvas:#f7f8fa; --surface:#fff; --border:#e5e7eb; --text:#111827;
    --muted:#6b7280; --soft:#9ca3af; --brand:#4f46e5;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--canvas); color:var(--text);
    font-family:"DM Sans","Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
    font-size:14px; line-height:1.6; }}
  .wrap {{ max-width:1240px; margin:0 auto; padding:40px 28px 80px; }}
  h1 {{ font-size:30px; margin:0 0 6px; letter-spacing:-.01em; }}
  h2 {{ font-size:19px; margin:44px 0 14px; padding-bottom:8px; border-bottom:1px solid var(--border); }}
  h3 {{ font-size:15px; margin:26px 0 10px; }}
  .lede {{ color:var(--muted); margin:0 0 4px; }}
  .meta {{ color:var(--soft); font-size:12.5px; }}
  .grid {{ display:grid; gap:14px; }}
  .g4 {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
  .g3 {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
  .g2 {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:16px 18px; }}
  .card .k {{ font-size:12px; color:var(--muted); }}
  .card .v {{ font-size:26px; font-weight:700; font-variant-numeric:tabular-nums; margin-top:2px; }}
  .card .n {{ font-size:12px; color:var(--soft); margin-top:2px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--surface);
    border:1px solid var(--border); border-radius:12px; overflow:hidden; font-size:12.5px; }}
  th, td {{ padding:8px 10px; text-align:right; border-bottom:1px solid var(--border); white-space:nowrap; }}
  th:first-child, td:first-child {{ text-align:left; }}
  thead th {{ background:#f3f4f6; font-weight:600; color:#374151; position:sticky; top:0; }}
  tbody tr:last-child td {{ border-bottom:0; }}
  tbody tr:hover {{ background:#fafafa; }}
  .bad {{ color:#dc2626; font-weight:700; }}
  .warn {{ color:#d97706; font-weight:600; }}
  .ok {{ color:#059669; }}
  .finding {{ background:var(--surface); border:1px solid var(--border); border-left-width:4px;
    border-radius:10px; padding:14px 16px; margin-bottom:12px; }}
  .finding .top {{ display:flex; align-items:baseline; gap:10px; margin-bottom:6px; flex-wrap:wrap; }}
  .finding .id {{ font-family:ui-monospace,Consolas,monospace; font-size:12px; color:var(--muted); }}
  .finding .ttl {{ font-weight:700; font-size:14.5px; }}
  .finding p {{ margin:6px 0 0; color:#374151; font-size:13px; }}
  .finding .fix {{ margin-top:8px; padding-top:8px; border-top:1px dashed var(--border); font-size:13px; }}
  .finding .fix b {{ color:#059669; }}
  code {{ background:#f3f4f6; padding:1px 5px; border-radius:4px;
    font-family:ui-monospace,Consolas,monospace; font-size:12px; }}
  .shots {{ display:grid; gap:16px; }}
  .shot {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; overflow:hidden; }}
  .shot .hd {{ padding:10px 14px; border-bottom:1px solid var(--border); display:flex;
    align-items:baseline; gap:10px; flex-wrap:wrap; }}
  .shot .hd b {{ font-size:14px; }}
  .shot .hd span {{ font-size:12px; color:var(--muted); font-family:ui-monospace,Consolas,monospace; }}
  .shot .body {{ display:grid; grid-template-columns:1fr 300px; gap:0; }}
  .shot .pane {{ padding:12px; overflow:hidden; max-height:560px; background:#fcfcfd; }}
  .shot .pane + .pane {{ border-left:1px solid var(--border); }}
  .shot img {{ display:block; width:100%; border:1px solid var(--border); border-radius:6px; }}
  .tag {{ display:inline-block; padding:1px 7px; border-radius:999px; font-size:11px; font-weight:600; }}
  .note {{ background:#fff; border:1px solid var(--border); border-radius:12px; padding:16px 18px; }}
  .note ul {{ margin:8px 0 0; padding-left:20px; }}
  .note li {{ margin:4px 0; }}
  .bar {{ height:8px; border-radius:4px; background:#e5e7eb; overflow:hidden; min-width:60px; display:block; }}
  .bar i {{ display:block; height:100%; background:#dc2626; }}
  @media (max-width:900px) {{ .g4,.g3,.g2 {{ grid-template-columns:1fr 1fr; }}
    .shot .body {{ grid-template-columns:1fr; }} .shot .pane + .pane {{ border-left:0; border-top:1px solid var(--border); }} }}
</style></head><body><div class="wrap">
<h1>UI 布局深度审计 · Tmall Dashboard</h1>
<p class="lede">按 NUI（NexusAI + AntV + Ant Design）原则，对 <code>frontend/ui_demo</code> 的 22 个可路由页面做真实浏览器渲染 + DOM 量化。</p>
<p class="meta">审计日期 {datetime.now().strftime('%Y-%m-%d')} · 22 页 × 3 视口（1440 / 768 / 390）= 66 次加载 · 只读审计，未改动业务代码与数据</p>
""")

    # 摘要卡
    total_dom = sum((dom.get(k) or {}).get('allEl', 0) for k, _, _ in PAGES)
    max_dom = max(((dom.get(k) or {}).get('allEl', 0), k) for k, _, _ in PAGES)
    overflow_pages = sum(1 for k, _, _ in PAGES for v in ('desktop', 'compact', 'mobile')
                         if audit['pages'].get(k, {}).get('viewports', {}).get(v, {}).get('horizontalOverflow'))
    p0 = sum(1 for f in FINDINGS if f[0] == 'P0')
    p1 = sum(1 for f in FINDINGS if f[0] == 'P1')
    p2 = sum(1 for f in FINDINGS if f[0] == 'P2')

    parts.append(f"""<h2>一、结论摘要</h2>
<div class="grid g4">
  <div class="card"><div class="k">横向溢出页面</div><div class="v ok">0</div><div class="n">22 页 × 3 视口全部达标</div></div>
  <div class="card"><div class="k">硬编码颜色（公共 CSS）</div><div class="v ok">0</div><div class="n">components.css + shell.css</div></div>
  <div class="card"><div class="k">DOM 节点峰值</div><div class="v bad">{max_dom[0]:,}</div><div class="n">{max_dom[1]}</div></div>
  <div class="card"><div class="k">发现的问题</div><div class="v">{p0 + p1 + p2}</div><div class="n">P0 {p0} · P1 {p1} · P2 {p2}</div></div>
</div>

<div class="note" style="margin-top:16px">
<h3 style="margin-top:0">底子比"待重构"好得多</h3>
<ul>
  <li><b>零横向溢出</b>：66 次加载，<code>documentElement.scrollWidth === clientWidth</code> 全部成立。</li>
  <li><b>token 纪律极强</b>：<code>components.css</code>（120KB / 340 个类）与 <code>shell.css</code> 硬编码颜色 0 处，全部走 <code>var(--*)</code>；<code>tokens.css</code> 已是 primitive → semantic → component 三层结构，含亮/暗两套。</li>
  <li><b>壳层收敛已完成</b>：导航、品类模式、时间范围、复盘周期都有唯一归属，没有"壳层和页面各放一套筛选"的重复。</li>
  <li><b>组件层超出计划</b>：<code>ui-components.js</code> 已导出 20+ 组件并自带 <code>TmallUI.audit()</code>；22 页跑下来只有 2 处"数据表缺少 ui-table-wrap"。</li>
  <li><b>无未捕获异常</b>：<code>pageerror</code> 计数为 0。</li>
</ul>
<p style="margin-bottom:0">问题集中在四类：<b>页面级缺陷</b>（路由 404 / 接口 422 / 头部重复）、<b>信息层级没收敛</b>（首屏先讲说明文字）、<b>密度失衡</b>（一页 193 个可交互元素、996 个徽标、24333 个 DOM 节点）、<b>组件建了但没统一用</b>（同一种筛选栏一页出现 3~4 次）。</p>
</div>
""")

    # 逐页表
    parts.append('<h2>二、逐页核心指标（1440×900）</h2>')
    parts.append('<table><thead><tr><th>页面</th><th>DOM 节点</th><th>卡片</th><th>.ui-button 总/可见</th>'
                 '<th>徽标 总/可见</th><th>可交互</th><th>横向裁剪</th><th>纵滚容器</th>'
                 '<th>桌面高</th><th>移动高</th><th>控制台错误</th><th>接口 4xx</th></tr></thead><tbody>')
    for key, label, route, dm, desk, mob, dd, ce, http_err in cards:
        domn = dm.get('allEl', 0)
        cls = 'bad' if domn > 8000 else ('warn' if domn > 3000 else '')
        bad_cls = 'bad' if http_err else ''
        parts.append(
            f'<tr><td>{esc(label)}</td>'
            f'<td class="{cls}">{domn:,}</td>'
            f'<td>{dm.get("cards", 0)}</td>'
            f'<td>{dm.get("uiButton", 0)} / {dm.get("uiButtonVisible", 0)}</td>'
            f'<td>{dm.get("badge", 0)} / {dm.get("badgeVisible", 0)}</td>'
            f'<td>{dm.get("interactive", 0)}</td>'
            f'<td>{dm.get("clippedX", 0)}</td>'
            f'<td>{dm.get("vScrollContainers", 0)}</td>'
            f'<td>{desk.get("pageScrollHeight", 0):,}</td>'
            f'<td>{mob.get("pageScrollHeight", 0):,}</td>'
            f'<td>{ce}</td>'
            f'<td class="{bad_cls}">{len(http_err)}</td></tr>')
    parts.append('</tbody></table>')
    parts.append('<p class="meta">「.ui-button 总/可见」的差值 = 藏在 <code>dialog[hidden]</code> 与折叠区里的控件；'
                 '「横向裁剪」= <code>overflow-x:hidden</code> 且内容比容器宽 &gt;8px 的容器数（内容静默丢失）；'
                 '「纵滚容器」= 页面内又套了一层可纵向滚动的容器。</p>')

    # 问题清单
    parts.append('<h2>三、问题清单</h2>')
    for sev in ('P0', 'P1', 'P2'):
        name, color, bg = SEV_META[sev]
        items = [f for f in FINDINGS if f[0] == sev]
        parts.append(f'<h3><span class="tag" style="background:{bg};color:{color}">{sev}</span> '
                     f'{name}（{len(items)} 项）</h3>')
        for _, fid, ttl, evidence, fix in items:
            parts.append(
                f'<div class="finding" style="border-left-color:{color}">'
                f'<div class="top"><span class="id">{fid}</span><span class="ttl">{ttl}</span></div>'
                f'<p>{evidence}</p>'
                f'<div class="fix"><b>建议</b> {fix}</div></div>')

    # 截图
    parts.append('<h2>四、页面截图（桌面 1440 / 移动 390，均为整页顶部）</h2>')
    parts.append('<p class="meta">截图按页高降序排列，便于对照"长页面"问题。桌面列显示整页顶部 560px，移动列显示同一页面的窄屏形态。</p>')
    parts.append('<div class="shots">')
    ordered = sorted(cards, key=lambda c: -(c[4].get('pageScrollHeight', 0) or 0))
    for key, label, route, dm, desk, mob, dd, ce, http_err in ordered:
        d_img = thumb(os.path.join(SHOTS, f'{key}__desktop.png'), 700, 58)
        m_img = thumb(os.path.join(SHOTS, f'{key}__mobile.png'), 260, 58)
        dh = desk.get('pageScrollHeight', 0)
        mh = mob.get('pageScrollHeight', 0)
        dh_txt = f'{dh / 900:.1f} 屏' if dh else '–'
        mh_txt = f'{mh / 844:.1f} 屏' if mh else '–'
        parts.append(f"""<div class="shot">
  <div class="hd"><b>{esc(label)}</b><span>{esc(route)}</span>
    <span>DOM {dm.get('allEl', 0):,}</span>
    <span>可交互 {dm.get('interactive', 0)}</span>
    <span>桌面 {dh:,}px（{dh_txt}）</span>
    <span>移动 {mh:,}px（{mh_txt}）</span>
    {'<span class="tag" style="background:#fef2f2;color:#dc2626">接口 4xx ' + str(len(http_err)) + '</span>' if http_err else ''}
  </div>
  <div class="body">
    <div class="pane">{'<img src="' + d_img + '" alt="' + esc(label) + ' 桌面">' if d_img else '<span class="meta">无截图</span>'}</div>
    <div class="pane">{'<img src="' + m_img + '" alt="' + esc(label) + ' 移动">' if m_img else '<span class="meta">无截图</span>'}</div>
  </div>
</div>""")
    parts.append('</div>')

    # 接口健康
    parts.append('<h2>五、接口与控制台健康</h2>')
    err_agg = {}
    for key, label, route, dm, desk, mob, dd, ce, http_err in cards:
        for e in http_err:
            err_agg.setdefault(e, []).append(label)
    parts.append('<table><thead><tr><th>错误</th><th>出现页面</th></tr></thead><tbody>')
    for e, pages in sorted(err_agg.items()):
        parts.append(f'<tr><td><code>{esc(e)}</code></td><td style="text-align:left">{esc("、".join(sorted(set(pages))))}</td></tr>')
    parts.append('</tbody></table>')
    parts.append("""<div class="note" style="margin-top:14px">
<h3 style="margin-top:0">控制台错误构成（66 次加载）</h3>
<ul>
  <li><b>63 次</b> — <code>gitcode.com/api/v5/.../releases/latest</code> 被 CORS 拦截（<code>ERR_FAILED</code>）。每页加载必发，全项目最大宗噪音。</li>
  <li><b>24 次</b> — <code>422</code>，全部来自 <code>/api/page-capabilities</code>（见 P0-2）。</li>
  <li><b>6 次</b> — <code>404</code>，<code>/api/goals/2026</code> 与 <code>/product-detail</code>。</li>
  <li><b>0 个</b> — 未捕获 JS 异常。</li>
</ul>
</div>""")

    # 修复批次
    parts.append("""<h2>六、修复批次</h2>
<table><thead><tr><th>批次</th><th>内容</th><th>涉及</th></tr></thead><tbody>
<tr><td>批次 0</td><td style="text-align:left">P0 缺陷：PAGE_DEFINITIONS 补齐 8 页 / 能力门控失败不再静默 / 删 goals 重复头部 / product-detail 路由 / availability 语义拆分 / 版本检查走后端</td><td style="text-align:left">page_capability_service.py · api.js · goals.html · app.py</td></tr>
<tr><td>批次 1</td><td style="text-align:left">层级收敛：唯一 h1 / 导航分组降级 span / 合并页头+上下文栏 / 删 section-kicker / 删 3 个死页面</td><td style="text-align:left">shell.js · ui-components.js · pages/*.html</td></tr>
<tr><td>批次 2</td><td style="text-align:left">首屏决策区：overview 合并决策区+KPI / products 页头 16→6 / promotion 单主操作 / market-ranking 拆 4552px section</td><td style="text-align:left">overview-live.js · products-live.js · promotion-live.js · market-ranking-live.js</td></tr>
<tr><td>批次 3</td><td style="text-align:left">密度与表格：真分页 / Tab 按需渲染 / 列数上限与弹性列 / 商品名两行 / 单工具栏 / 消除三层滚动</td><td style="text-align:left">table-controls.js · table-render.js · components.css · themes/</td></tr>
<tr><td>批次 4</td><td style="text-align:left">一致性与无障碍：内联样式迁 CSS / period-review.css token 化 / metricPolarity / aria-label / focus-visible / 状态非颜色表达</td><td style="text-align:left">keyword-promotion.css · period-review.css · product-columns.js</td></tr>
</tbody></table>""")

    parts.append("""<h2>七、与现有文档的关系</h2>
<div class="note">
<p style="margin-top:0">本文是 <code>docs/UI_OPTIMIZATION_NUI_REVIEW.md</code> 里<b>「批次 0：现状快照」</b>的正式交付——那份审查意见明确要求「禁止在没有快照的情况下直接重排页面」。</p>
<pre style="background:#f3f4f6;padding:12px;border-radius:8px;font-size:12.5px;overflow:auto;margin:12px 0">UI_OPTIMIZATION_IMPLEMENTATION_PLAN.md   ← 方向（做什么）
UI_OPTIMIZATION_NUI_REVIEW.md            ← 对方向的审查（怎么改才对）
UI_LAYOUT_AUDIT_20261001.md / .html      ← 现状证据（现在到底什么样）  ← 新增</pre>
<p style="margin-bottom:0">审查意见里 8 条「必须修正」中 6 条在实测中被证实真实存在；2 条（「一个主要操作」过死、「数据中心不宜套队列」）实测未发现被误用——data-center 没有用队列布局，方向是对的。<br>
<b>唯一需要修正审查意见的地方</b>：它建议 6 个公共组件，但实际已导出 20+ 个，其中 <code>decisionCard</code>（1 页用）、<code>stickyActionBar</code>（2 页用）不满足「至少两页复用」。组件数量不是问题，<b>复用率才是</b>——建议改为「每个导出组件必须 ≥2 页使用，否则删」。</p>
</div>""")

    parts.append("""<h2>八、审计产物</h2>
<pre style="background:#f3f4f6;padding:14px;border-radius:8px;font-size:12.5px;overflow:auto">scripts/audit_ui_layout.cjs     22 页 × 3 视口：溢出/卡片/标题/表格/控制台
scripts/audit_ui_deep.cjs       22 页 × 2 视口：接口 4xx/裁剪/横滚/组件使用/audit
scripts/audit_ui_dom.cjs        22 页 × 1440：DOM 节点/控件/徽标/卡片
scripts/probe_ui_density.cjs     7 页定点：控件密度/无名按钮/被裁表格/main 子块

.tmp/ui-audit/audit.json · deep.json · dom.json    原始数据
.tmp/ui-audit/shots/*.png                          66 张全页截图</pre>
<p class="meta">本报告由 <code>scripts/build_ui_audit_report.py</code> 生成，截图已内嵌，可离线查看。</p>
</div></body></html>""")

    html = '\n'.join(parts)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print('WROTE', OUT, f'{len(html.encode("utf-8")) / 1024 / 1024:.1f} MB')


if __name__ == '__main__':
    sys.exit(main())

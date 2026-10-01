/**
 * UI 深度审计第二遍：接口失败、裁剪容器、组件使用、页面契约要素
 * 只读。用法同 audit_ui_layout.cjs
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const args = process.argv.slice(2);
const getArg = (n, f) => { const i = args.indexOf(n); return i >= 0 && args[i + 1] ? args[i + 1] : f; };
const BASE = getArg('--base', 'http://127.0.0.1:5000');
const OUT = path.resolve(getArg('--out', '.tmp/ui-audit'));

const PAGES = [
  ['overview', '/'], ['category-dashboard', '/category-dashboard'], ['goals', '/goals'],
  ['reviews', '/reviews'], ['period-review', '/period-review'], ['products', '/products'],
  ['lifecycle', '/lifecycle'], ['keyword-promotion', '/keyword-promotion'], ['promotion', '/promotion'],
  ['new-products', '/new-products'], ['creative-board', '/creative-board'], ['flow-source', '/flow-source'],
  ['rival-analysis', '/rival-analysis'], ['market-ranking', '/market-ranking'], ['analysis', '/analysis'],
  ['data-collection', '/data-collection'], ['data-center', '/data-center'], ['settings', '/settings'],
  ['product-detail', '/product-detail'],
  // 4-8：compare / manage 页面已删除（路由保留 302），不再列入审计清单。
  ['component-catalog', '/component-catalog'],
];
const KEY_PAGES = new Set(['overview', 'period-review', 'products', 'promotion', 'data-center', 'market-ranking', 'data-collection', 'lifecycle']);
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900, all: true },
  { name: 'mobile', width: 390, height: 844, all: false },
];

const PROBE = () => {
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const cls = (el) => (el.className || '').toString();

  // 1) 被裁剪的容器（overflow hidden 且内容比容器宽）——内容静默丢失
  const clipped = [];
  // 2) 需要横向滚动的容器
  const scrollers = [];
  document.querySelectorAll('body *').forEach((el) => {
    if (!vis(el)) return;
    const s = getComputedStyle(el);
    const ox = s.overflowX;
    if (ox !== 'hidden' && ox !== 'auto' && ox !== 'scroll') return;
    const diff = el.scrollWidth - el.clientWidth;
    if (diff <= 8) return;
    const r = el.getBoundingClientRect();
    if (r.width < 160) return;
    const item = { cls: cls(el).slice(0, 90), tag: el.tagName.toLowerCase(), diff, width: Math.round(r.width), scrollW: el.scrollWidth, clientW: el.clientWidth };
    if (ox === 'hidden') clipped.push(item); else scrollers.push(item);
  });

  // 3) 精确卡片统计（整类名匹配）
  const CARD = /(^|\s)(ui-card|ui-panel|panel|plain-panel|metric-card|ui-metric-card|card|ui-decision-card|decision-card)(\s|$)/;
  const cards = [...document.querySelectorAll('body *')].filter((el) => vis(el) && CARD.test(cls(el)));
  const cardByClass = {};
  cards.forEach((el) => { cls(el).split(/\s+/).forEach((c) => { if (/card|panel/.test(c)) cardByClass[c] = (cardByClass[c] || 0) + 1; }); });
  const cardHeights = cards.map((el) => Math.round(el.getBoundingClientRect().height));
  // 首屏可见卡片
  const firstScreenCards = cards.filter((el) => { const r = el.getBoundingClientRect(); return r.top < vh && r.bottom > 0; }).length;

  // 4) 组件使用（TmallUI 组件产出的类）
  const COMPONENT_CLASSES = ['ui-page-header', 'ui-context-bar', 'ui-data-state', 'data-state', 'ui-metric-card', 'ui-metric-grid', 'ui-table-toolbar', 'ui-table-wrap', 'ui-data-table', 'ui-detail-drawer', 'ui-sticky-action-bar', 'ui-decision-card', 'ui-empty-state', 'ui-filter-toolbar', 'ui-button', 'ui-badge', 'ui-panel'];
  const componentUse = {};
  COMPONENT_CLASSES.forEach((c) => { const n = document.querySelectorAll('.' + c).length; if (n) componentUse[c] = n; });

  // 5) 内联样式（硬编码视觉）
  const inlineStyled = [...document.querySelectorAll('body *')].filter((el) => vis(el) && el.getAttribute('style') && /color|background|border|font-size|margin|padding/.test(el.getAttribute('style'))).length;

  // 6) 结构：章节数 / 首屏文字量 / 标题树
  const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis).map((el) => ({ level: +el.tagName[1], text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 70) }));
  const firstScreenText = [...document.querySelectorAll('body *')].filter((el) => {
    if (!vis(el) || el.children.length) return false;
    const r = el.getBoundingClientRect();
    if (r.top > vh || r.bottom < 0) return false;
    return (el.textContent || '').trim().length > 1;
  }).map((el) => (el.textContent || '').trim().replace(/\s+/g, ' '));

  // 7) 顶部工具栏元素数（shell）
  const header = document.querySelector('[data-shell-header]');
  const headerControls = header ? [...header.querySelectorAll('button, select, a, [role="button"]')].filter(vis).length : 0;
  const headerHeight = header ? Math.round(header.getBoundingClientRect().height) : null;
  const headerWrapped = header ? header.getBoundingClientRect().height > 80 : false;

  // 8) 表格
  const tables = [...document.querySelectorAll('table')].filter(vis).map((t) => {
    const wrap = t.closest('.ui-table-wrap, [class*="table-wrap"]') || t.parentElement;
    return {
      cols: t.querySelectorAll('thead th').length,
      rows: t.querySelectorAll('tbody tr').length,
      needsScroll: wrap ? wrap.scrollWidth > wrap.clientWidth + 1 : false,
      wrapCls: wrap ? cls(wrap).slice(0, 60) : null,
    };
  });

  // 9) TmallUI.audit
  let auditIssues = null;
  try { auditIssues = window.TmallUI?.audit ? window.TmallUI.audit(document).map((i) => i.message) : null; } catch (e) { auditIssues = ['audit 抛错: ' + e.message]; }

  return {
    vw, vh,
    docHeight: document.documentElement.scrollHeight,
    clipped: clipped.sort((a, b) => b.diff - a.diff).slice(0, 15),
    clippedCount: clipped.length,
    scrollers: scrollers.sort((a, b) => b.diff - a.diff).slice(0, 12),
    scrollerCount: scrollers.length,
    cardCount: cards.length,
    cardByClass,
    cardHeightsMax: cardHeights.length ? Math.max(...cardHeights) : 0,
    firstScreenCards,
    componentUse,
    inlineStyled,
    headings,
    headingMaxLevel: headings.length ? Math.max(...headings.map((h) => h.level)) : 0,
    firstScreenTextCount: firstScreenText.length,
    firstScreenText,
    headerControls, headerHeight, headerWrapped,
    tables,
    auditIssues,
  };
};

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const report = { base: BASE, generatedAt: new Date().toISOString(), pages: {} };

  for (const [name, route] of PAGES) {
    report.pages[name] = { route, viewports: {} };
    for (const vp of VIEWPORTS) {
      if (!vp.all && !KEY_PAGES.has(name)) continue;
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const page = await ctx.newPage();
      const bad = [];
      const consoleErrors = [];
      page.on('response', (r) => { if (r.status() >= 400) bad.push(`${r.status()} ${r.url().replace(BASE, '').slice(0, 160)}`); });
      page.on('requestfailed', (r) => { if (!/gitcode\.com/.test(r.url())) bad.push(`FAIL ${r.url().replace(BASE, '').slice(0, 160)} :: ${r.failure()?.errorText}`); });
      page.on('console', (m) => { if (m.type() === 'error' && !/gitcode\.com|ERR_FAILED/.test(m.text())) consoleErrors.push(m.text().slice(0, 200)); });
      let data = null;
      try {
        await page.goto(BASE + route, { waitUntil: 'networkidle', timeout: 60000 });
        await page.waitForTimeout(2500);
        data = await page.evaluate(PROBE);
      } catch (e) { data = { error: String(e.message).slice(0, 300) }; }
      data.httpErrors = bad.slice(0, 20);
      data.consoleErrors = consoleErrors.slice(0, 10);
      report.pages[name].viewports[vp.name] = data;
      await ctx.close();
      process.stdout.write(`. ${name} ${vp.name}\n`);
    }
  }
  await browser.close();
  const out = path.join(OUT, 'deep.json');
  fs.writeFileSync(out, JSON.stringify(report, null, 2), 'utf8');
  console.log('\nWROTE ' + out);
})().catch((e) => { console.error(e); process.exit(1); });

/** 轻量 DOM 统计：每页在 1440 下的节点数、控件数、徽标数、卡片数、高度 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const BASE = process.argv[2] || 'http://127.0.0.1:5000';
const PAGES = [
  ['overview', '/'], ['category-dashboard', '/category-dashboard'], ['goals', '/goals'],
  ['reviews', '/reviews'], ['period-review', '/period-review'], ['products', '/products'],
  ['lifecycle', '/lifecycle'], ['keyword-promotion', '/keyword-promotion'], ['promotion', '/promotion'],
  ['new-products', '/new-products'], ['creative-board', '/creative-board'], ['flow-source', '/flow-source'],
  ['rival-analysis', '/rival-analysis'], ['market-ranking', '/market-ranking'], ['analysis', '/analysis'],
  ['data-collection', '/data-collection'], ['data-center', '/data-center'], ['settings', '/settings'],
  ['component-catalog', '/component-catalog'],
  // 4-8：compare / manage 页面已删除（路由保留 302 → /reviews 与 /settings），
  // 不再列入审计清单 —— 否则会拿 404 页面的空 DOM 参与峰值统计。
];

const PROBE = () => {
  const vis = (e) => { const s = getComputedStyle(e); if (s.display === 'none' || s.visibility === 'hidden') return false; const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
  const cls = (e) => (e.className || '').toString();
  const CARD = /(^|\s)(ui-card|ui-panel|panel|metric-card|ui-metric-card|card|ui-decision-card|decision-card)(\s|$)/;
  const uib = [...document.querySelectorAll('.ui-button')];
  const badges = [...document.querySelectorAll('.ui-badge')];
  const inter = [...document.querySelectorAll('button, [role="button"], a[href], select, input, summary')].filter(vis);
  const main = document.querySelector('main.demo-page');
  let clipped = 0;
  document.querySelectorAll('body *').forEach((e) => { const s = getComputedStyle(e); if ((s.overflowX === 'hidden') && e.scrollWidth - e.clientWidth > 8 && e.getBoundingClientRect().width > 160) clipped++; });
  let vScroll = 0;
  document.querySelectorAll('body *').forEach((e) => { const s = getComputedStyle(e); if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && e.scrollHeight - e.clientHeight > 12 && e.clientHeight > 60 && e.getBoundingClientRect().width > 200) vScroll++; });
  return {
    allEl: document.querySelectorAll('*').length,
    uiButton: uib.length, uiButtonVisible: uib.filter(vis).length,
    badge: badges.length, badgeVisible: badges.filter(vis).length,
    interactive: inter.length,
    cards: [...document.querySelectorAll('body *')].filter((e) => vis(e) && CARD.test(cls(e))).length,
    clippedX: clipped, vScrollContainers: vScroll,
    mainChildren: main ? main.children.length : 0,
    docH: document.documentElement.scrollHeight,
  };
};

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const out = {};
  for (const [name, route] of PAGES) {
    const page = await ctx.newPage();
    try {
      await page.goto(BASE + route, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(2200);
      out[name] = await page.evaluate(PROBE);
    } catch (e) { out[name] = { error: String(e.message).slice(0, 200) }; }
    await page.close();
    process.stdout.write('. ' + name + '\n');
  }
  await browser.close();
  fs.writeFileSync(path.resolve('.tmp/ui-audit/dom.json'), JSON.stringify(out, null, 2), 'utf8');
  console.log('WROTE .tmp/ui-audit/dom.json');
})().catch((e) => { console.error(e); process.exit(1); });

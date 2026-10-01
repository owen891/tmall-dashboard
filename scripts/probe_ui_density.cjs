/** 针对性探针：控件密度、无名按钮、被裁表格、徽标密度 */
const { chromium } = require('playwright-core');
const BASE = 'http://127.0.0.1:5000';

const TARGETS = [
  ['promotion', '/promotion'],
  ['overview', '/'],
  ['market-ranking', '/market-ranking'],
  ['data-center', '/data-center'],
  ['products', '/products'],
  ['data-collection', '/data-collection'],
  ['lifecycle', '/lifecycle'],
];

const PROBE = () => {
  const vis = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const out = {};

  // .ui-button 到底挂在哪
  const uib = [...document.querySelectorAll('.ui-button')];
  out.uiButtonTotal = uib.length;
  out.uiButtonVisible = uib.filter(vis).length;
  out.uiButtonByTag = {};
  uib.forEach((el) => { const k = el.tagName.toLowerCase() + (el.hasAttribute('role') ? '[role=' + el.getAttribute('role') + ']' : ''); out.uiButtonByTag[k] = (out.uiButtonByTag[k] || 0) + 1; });

  // 所有可交互元素
  const all = [...document.querySelectorAll('button, [role="button"], a[href], select, input, summary')].filter(vis);
  out.interactiveVisible = all.length;
  out.interactiveByTag = {};
  all.forEach((el) => { const k = el.tagName.toLowerCase(); out.interactiveByTag[k] = (out.interactiveByTag[k] || 0) + 1; });

  // 无名可交互（无文本、无 aria-label、无 title、无 aria-labelledby）
  out.unnamed = all.filter((el) => {
    const t = (el.textContent || '').trim();
    return !t && !el.getAttribute('aria-label') && !el.getAttribute('title') && !el.getAttribute('aria-labelledby');
  }).slice(0, 20).map((el) => ({ tag: el.tagName.toLowerCase(), cls: (el.className || '').toString().slice(0, 70), html: el.outerHTML.slice(0, 160) }));

  // 徽标密度
  out.badgeTotal = document.querySelectorAll('.ui-badge').length;
  out.badgeVisible = [...document.querySelectorAll('.ui-badge')].filter(vis).length;
  const badgeText = {};
  [...document.querySelectorAll('.ui-badge')].filter(vis).forEach((el) => { const t = (el.textContent || '').trim(); badgeText[t] = (badgeText[t] || 0) + 1; });
  out.badgeTop = Object.entries(badgeText).sort((a, b) => b[1] - a[1]).slice(0, 12);

  // 表格被裁：表格容器 max-height + overflow hidden，最后一行被切
  out.clippedTables = [];
  document.querySelectorAll('table').forEach((t) => {
    if (!vis(t)) return;
    let p = t.parentElement;
    while (p && p !== document.body) {
      const s = getComputedStyle(p);
      if (s.overflowY === 'hidden' || s.overflowY === 'auto' || s.overflowY === 'scroll') {
        const clipped = p.scrollHeight - p.clientHeight;
        if (clipped > 12 && s.overflowY === 'hidden') {
          out.clippedTables.push({ cls: (p.className || '').toString().slice(0, 70), clipped, clientH: p.clientHeight, scrollH: p.scrollHeight, rows: t.querySelectorAll('tbody tr').length });
        }
        break;
      }
      p = p.parentElement;
    }
  });

  // 表格列数 / 每行按钮数
  out.tables = [...document.querySelectorAll('table')].filter(vis).map((t) => ({
    cols: t.querySelectorAll('thead th').length,
    rows: t.querySelectorAll('tbody tr').length,
    btnsPerRow: t.querySelector('tbody tr') ? t.querySelector('tbody tr').querySelectorAll('button,[role="button"]').length : 0,
    th: [...t.querySelectorAll('thead th')].slice(0, 20).map((th) => (th.textContent || '').trim().slice(0, 14)),
  }));

  // 文本节点里出现「--」的次数（缺失值）
  out.dashCount = (document.body.innerText.match(/--/g) || []).length;

  // 页面主要区块数（直接子区块）
  const main = document.querySelector('main.demo-page');
  out.mainChildren = main ? main.children.length : 0;
  out.sections = main ? [...main.children].map((c) => ({ tag: c.tagName.toLowerCase(), cls: (c.className || '').toString().slice(0, 60), h: Math.round(c.getBoundingClientRect().height) })) : [];

  return out;
};

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  for (const [name, route] of TARGETS) {
    const page = await ctx.newPage();
    await page.goto(BASE + route, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(2500);
    const d = await page.evaluate(PROBE);
    console.log('\n########## ' + name + ' ##########');
    console.log('ui-button 总数/可见:', d.uiButtonTotal, '/', d.uiButtonVisible, JSON.stringify(d.uiButtonByTag));
    console.log('可交互可见:', d.interactiveVisible, JSON.stringify(d.interactiveByTag));
    console.log('ui-badge 总数/可见:', d.badgeTotal, '/', d.badgeVisible, ' top:', JSON.stringify(d.badgeTop.slice(0, 6)));
    console.log('无名可交互:', d.unnamed.length, JSON.stringify(d.unnamed.slice(0, 5)));
    console.log('被裁表格:', JSON.stringify(d.clippedTables));
    console.log('表格:', JSON.stringify(d.tables.map((t) => ({ c: t.cols, r: t.rows, b: t.btnsPerRow }))));
    console.log('main 直接子块:', d.mainChildren);
    d.sections.forEach((s) => console.log('   ', s.h + 'px', s.tag, s.cls));
    await page.close();
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });

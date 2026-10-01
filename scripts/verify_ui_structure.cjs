/**
 * UI 结构契约验证（批次 1 起）——只读，输出 PASS/FAIL。
 *
 * 校验的是「结构不变量」，不是观感：
 *   1. 每页有且仅有一个 h1（页面标题）
 *   2. 侧栏导航分组标签不能是标题元素（否则污染文档大纲）
 *   3. 已合并页头的页面不得再出现 .ui-context-bar
 *   4. TmallUI.audit() 无问题
 *   5. 无 pageerror
 * 另外报告首屏高度与「kicker 紧跟同名标题」的冗余对（提示级，不计失败）。
 *
 * 用法：
 *   NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/verify_ui_structure.cjs
 * 可选参数：--base http://127.0.0.1:5000   --out .tmp/ui-audit
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const args = process.argv.slice(2);
const getArg = (n, f) => { const i = args.indexOf(n); return i >= 0 && args[i + 1] ? args[i + 1] : f; };
const BASE = getArg('--base', 'http://127.0.0.1:5000');
const OUT = path.resolve(getArg('--out', '.tmp/ui-audit'));

const PAGES = [
  ['overview', '/'], ['analysis', '/analysis'], ['category-dashboard', '/category-dashboard'],
  ['products', '/products'], ['promotion', '/promotion'], ['keyword-promotion', '/keyword-promotion'],
  ['new-products', '/new-products'], ['market-ranking', '/market-ranking'], ['lifecycle', '/lifecycle'],
  ['reviews', '/reviews'], ['period-review', '/period-review'], ['data-center', '/data-center'],
  ['data-collection', '/data-collection'], ['settings', '/settings'], ['goals', '/goals'],
  ['flow-source', '/flow-source'], ['rival-analysis', '/rival-analysis'], ['component-catalog', '/component-catalog'],
  ['creative-board', '/creative-board'], ['product-detail', '/product-detail'],
];

// 批次 1-3：这些页面已把 scope 并进页头，不应再有独立的 .ui-context-bar。
const MERGED_HEADER_PAGES = new Set([
  'analysis', 'category-dashboard', 'data-center', 'flow-source', 'lifecycle', 'manage',
  'goals', 'keyword-promotion', 'overview', 'reviews', 'rival-analysis', 'settings',
]);

const PROBE = () => {
  const headings = [...document.querySelectorAll('h1')].map((h) => h.textContent.trim().slice(0, 30));
  const navLabels = [...document.querySelectorAll('.demo-nav__label')].map((el) => el.tagName.toLowerCase());
  const kickers = [...document.querySelectorAll('.section-kicker')].map((el) => {
    const parent = el.parentElement;
    const heading = parent ? parent.querySelector('h2, h3, h4') : null;
    return { text: el.textContent.trim(), heading: heading ? heading.textContent.trim().slice(0, 24) : null };
  });
  const main = document.querySelector('main');
  const firstBlock = main?.firstElementChild;
  return {
    h1: headings,
    navLabelTags: [...new Set(navLabels)],
    contextBars: document.querySelectorAll('.ui-context-bar').length,
    kickers,
    redundantKickers: kickers.filter((k) => k.heading).length,
    auditIssues: (window.TmallUI?.audit ? window.TmallUI.audit() : []).map((i) => i.message),
    firstScreenTop: firstBlock ? Math.round(firstBlock.getBoundingClientRect().top + window.scrollY) : null,
    pageHeight: Math.round(document.documentElement.scrollHeight),
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PW_CHROMIUM || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const rows = [];
  const failures = [];

  for (const [name, route] of PAGES) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(String(e.message).slice(0, 160)));
    let probe = null;
    try {
      // 不用 networkidle：看板页有常驻轮询/慢接口，networkidle 可能永不触发（曾导致整轮 15 分钟超时）。
      await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(2500);
      probe = await page.evaluate(PROBE);
    } catch (error) {
      failures.push({ page: name, check: 'load', detail: error.message.slice(0, 120) });
    }
    await context.close();

    if (!probe) { rows.push({ page: name, route, status: 'LOAD_FAILED' }); continue; }

    const checks = [];
    if (probe.h1.length !== 1) checks.push(`h1 数量 ${probe.h1.length}`);
    if (probe.navLabelTags.some((t) => /^h[1-6]$/.test(t))) checks.push(`导航分组标签是 ${probe.navLabelTags.join('/')}`);
    if (MERGED_HEADER_PAGES.has(name) && probe.contextBars > 0) checks.push(`仍有 ${probe.contextBars} 个 ui-context-bar`);
    if (probe.auditIssues.length) checks.push(`audit: ${probe.auditIssues.join(' | ').slice(0, 90)}`);
    if (pageErrors.length) checks.push(`pageerror: ${pageErrors[0]}`);
    if (probe.scrollWidth > probe.clientWidth + 1) checks.push(`横向溢出 ${probe.scrollWidth - probe.clientWidth}px`);

    if (checks.length) failures.push({ page: name, check: 'structure', detail: checks.join('; ') });
    rows.push({
      page: name, route,
      status: checks.length ? 'FAIL' : 'PASS',
      h1: probe.h1.join(' | '),
      navTags: probe.navLabelTags.join(','),
      contextBars: probe.contextBars,
      redundantKickers: probe.redundantKickers,
      pageHeight: probe.pageHeight,
      issues: checks.join('; '),
    });
  }

  await browser.close();

  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(path.join(OUT, 'structure.json'), JSON.stringify({ rows, failures }, null, 2));

  console.log('页面'.padEnd(22) + '结果'.padEnd(8) + 'h1'.padEnd(22) + 'contextBar'.padEnd(12) + '页高');
  console.log('-'.repeat(90));
  for (const r of rows) {
    console.log(
      String(r.page).padEnd(22) + String(r.status).padEnd(8) +
      String(r.h1 || '-').slice(0, 20).padEnd(22) +
      String(r.contextBars ?? '-').padEnd(12) + (r.pageHeight ?? '-'),
    );
  }
  console.log('-'.repeat(90));
  const passed = rows.filter((r) => r.status === 'PASS').length;
  console.log(`PASS ${passed} / ${rows.length}`);
  if (failures.length) {
    console.log('\n失败项：');
    failures.forEach((f) => console.log(`  [${f.page}] ${f.check}: ${f.detail}`));
  }
  console.log(`\n原始数据: ${path.join(OUT, 'structure.json')}`);
  process.exit(failures.length ? 1 : 0);
})();

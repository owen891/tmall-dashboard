/**
 * 周期复盘页整页冒烟：检查平铺的四个工作区及拆因导航。
 *
 * 用于改完前端后一次性确认「没有哪个页签是空的 / 报错的」。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/smoke_period_review_tabs.js [port] [category_mode] [start] [end]
 */
const path = require('path');

const PORT = process.argv[2] || '5000';
const CATEGORY_MODE = process.argv[3] || 'sock';
const RANGE_START = process.argv[4] || '';
const RANGE_END = process.argv[5] || '';
const BASE = `http://127.0.0.1:${PORT}`;
const OUT_DIR = path.join(__dirname, '..', 'logs');
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const WORKSPACES = [
  ['conclusion', '结论写作', '[data-pr-workbench-panel="conclusion"]'],
  ['execution', '计划与动作', '[data-pr-workbench-panel="execution"]'],
  ['reference', '数据参考', '[data-pr-workbench-panel="reference"]'],
];

const FAILURE_HINTS = ['加载失败', '接口不存在', '未就绪', '失败，请重试'];

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1200 } });

  const consoleErrors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push('PAGEERROR ' + err.message));

  await page.addInitScript((mode) => {
    try { window.localStorage.setItem('dashboard.categoryMode', mode); } catch (_) {}
  }, CATEGORY_MODE);

  await page.goto(`${BASE}/pages/period-review.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  if (RANGE_START && RANGE_END) {
    await page.evaluate(({ start, end }) => {
      window.TmallDateRange?.setRange?.(start, end, 'custom');
    }, { start: RANGE_START, end: RANGE_END });
  }
  await page.waitForTimeout(8000);

  await page.waitForTimeout(5000);
  const results = await page.evaluate(({ workspaces, hints }) => workspaces.map(([key, label, selector]) => {
    const node = document.querySelector(selector);
    if (!node) return { key, label, missing: true, failure: [], sample: '' };
    const text = (node.innerText || '').replace(/\s+/g, ' ').trim();
    return {
      key, label, missing: false,
      tables: node.querySelectorAll('table').length,
      rows: node.querySelectorAll('tbody tr').length,
      empty: !text,
      failure: hints.filter((hint) => text.includes(hint)),
      sample: text.slice(0, 90),
      // 拆因已并入结论段：归因/货品/推广明细应出现在 conclusion 的板块数据里。
      gapBody: key === 'conclusion' && Boolean(node.querySelector('.pr-gap')),
      productBoards: key === 'conclusion' && node.querySelectorAll('.pr-materials').length,
      promotionTables: key === 'conclusion' ? node.querySelectorAll('table').length : null,
    };
  }), { workspaces: WORKSPACES, hints: FAILURE_HINTS });
  const period = await page.evaluate(() => {
    const n = document.querySelector('[data-pr-period-label]');
    return n ? (n.innerText || '').replace(/\s+/g, ' ').trim() : '(missing)';
  });

  console.log('周期: ' + period);
  console.log('');
  let bad = 0;
  results.forEach((r) => {
    const problems = [];
    if (r.missing) problems.push('工作区缺失');
    else if (r.failure.length) problems.push(`出现失败文案: ${r.failure.join('/')}`);
    else if (r.empty) problems.push('工作区空白');
    if (r.key === 'conclusion' && !r.missing) {
      if (!r.gapBody) problems.push('目标差距归因摘要缺失');
      if (!r.productBoards) problems.push('货品明细缺失');
      if (!r.promotionTables) problems.push('推广/货品明细表缺失');
    }
    if (problems.length) bad += 1;
    const shape = r.missing ? '缺失' : `${r.tables}表/${r.rows}行`;
    console.log(`${problems.length ? 'FAIL' : 'OK  '}  ${r.label.padEnd(6, '　')} ${shape}${problems.length ? '  <<< ' + problems.join('; ') : ''}`);
    if (!r.missing && !r.failure.length) console.log(`        ${r.sample}`);
  });

  console.log('');
  const realErrors = consoleErrors.filter((t) => !t.includes('gitcode.com') && !t.includes('ERR_FAILED'));
  console.log('控制台错误（已过滤 gitcode 版本检查）: ' + (realErrors.length ? '\n  ' + realErrors.join('\n  ') : '无'));
  console.log(bad ? `\n结论：${bad} 个工作区有问题` : '\n结论：3 个工作区全部正常');

  await page.screenshot({ path: path.join(OUT_DIR, 'pr_smoke_last_tab.png'), fullPage: true });
  await browser.close();
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

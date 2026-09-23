/**
 * 周月复盘页整页冒烟：依次点开全部 8 个页签，dump 每个面板的渲染结果。
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

const TABS = [
  ['conclusion', '结论与诊断', ['[data-pr-overview]', '[data-pr-sections]']],
  ['products', '货品与异常', ['[data-pr-product-analysis]']],
  ['execution', '动作与计划', ['[data-pr-execution-analysis]']],
  ['market', '市场', ['[data-pr-market-analysis]']],
  ['promotion', '推广', ['[data-pr-channel-analysis]', '[data-pr-promotion-analysis]']],
  ['matrix', '指标矩阵', ['[data-pr-matrix]']],
  ['category', '类目拆解', ['[data-pr-category-breakdown]']],
  ['history', '历史与口径', ['[data-pr-history]']],
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

  const results = [];
  for (const [key, label, selectors] of TABS) {
    await page.evaluate((k) => document.querySelector(`[data-pr-workbench-tab="${k}"]`)?.click(), key);
    await page.waitForTimeout(key === 'matrix' || key === 'category' ? 3000 : 1200);
    const snapshot = await page.evaluate(({ sels, hints }) => {
      const parts = sels.map((sel) => {
        const node = document.querySelector(sel);
        if (!node) return { sel, missing: true };
        const text = (node.innerText || '').replace(/\s+/g, ' ').trim();
        return {
          sel,
          tables: node.querySelectorAll('table').length,
          rows: node.querySelectorAll('tbody tr').length,
          empty: !text,
          failure: hints.filter((h) => text.includes(h)),
          sample: text.slice(0, 90),
        };
      });
      return parts;
    }, { sels: selectors, hints: FAILURE_HINTS });
    results.push({ key, label, parts: snapshot });
  }

  const period = await page.evaluate(() => {
    const n = document.querySelector('[data-pr-period-label]');
    return n ? (n.innerText || '').replace(/\s+/g, ' ').trim() : '(missing)';
  });

  console.log('周期: ' + period);
  console.log('');
  let bad = 0;
  results.forEach((r) => {
    const problems = [];
    r.parts.forEach((p) => {
      if (p.missing) problems.push(`${p.sel} 缺失`);
      else if (p.failure.length) problems.push(`${p.sel} 出现失败文案: ${p.failure.join('/')}`);
      else if (p.empty) problems.push(`${p.sel} 空白`);
    });
    if (problems.length) bad += 1;
    const shape = r.parts.map((p) => (p.missing ? '缺失' : `${p.tables}表/${p.rows}行`)).join(' ');
    console.log(`${problems.length ? 'FAIL' : 'OK  '}  ${r.label.padEnd(6, '　')} ${shape}${problems.length ? '  <<< ' + problems.join('; ') : ''}`);
    r.parts.forEach((p) => { if (!p.missing && !p.failure.length) console.log(`        ${p.sample}`); });
  });

  console.log('');
  const realErrors = consoleErrors.filter((t) => !t.includes('gitcode.com') && !t.includes('ERR_FAILED'));
  console.log('控制台错误（已过滤 gitcode 版本检查）: ' + (realErrors.length ? '\n  ' + realErrors.join('\n  ') : '无'));
  console.log(bad ? `\n结论：${bad} 个页签有问题` : '\n结论：8 个页签全部正常');

  await page.screenshot({ path: path.join(OUT_DIR, 'pr_smoke_last_tab.png'), fullPage: true });
  await browser.close();
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

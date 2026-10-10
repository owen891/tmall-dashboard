/**
 * 抓「周期复盘 → 指标矩阵 / 类目拆解」两个页签的截图，并 dump 表头与首行文本。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/shot_period_review_matrix.js [port] [category_mode]
 */
const path = require('path');

const PORT = process.argv[2] || '5055';
const CATEGORY_MODE = process.argv[3] || 'sock';
const RANGE_START = process.argv[4] || '2026-09-07';
const RANGE_END = process.argv[5] || '2026-09-13';
const BASE = `http://127.0.0.1:${PORT}`;
const OUT_DIR = path.join(__dirname, '..', 'logs');
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

function dumpTable(page, panel) {
  return page.evaluate((sel) => {
    const root = document.querySelector(sel);
    if (!root) return { missing: sel };
    const table = root.querySelector('table');
    if (!table) {
      return { empty: (root.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 200) };
    }
    const headers = [...table.querySelectorAll('thead th')].map((th) => (th.innerText || '').trim());
    const rows = [...table.querySelectorAll('tbody tr')].map((tr) => ({
      status: (tr.querySelector('.pr-status-tag') || {}).innerText || '',
      cells: [...tr.querySelectorAll('td')].map((td) => (td.innerText || '').replace(/\s+/g, ' ').trim()),
    }));
    const nullCells = [...table.querySelectorAll('td')]
      .filter((td) => (td.innerText || '').includes('null')).length;
    return { headers, rowCount: rows.length, rows, nullCells };
  }, panel);
}

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1200 } });
  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log('PAGE-ERROR ' + msg.text());
  });

  // 品类模式来自 localStorage（api.js 会给所有 GET 自动带上），
  // 复盘周期来自顶栏共享时间范围，两者都不是 URL 参数，需要在加载前注入。
  await page.addInitScript((mode) => {
    try { window.localStorage.setItem('dashboard.categoryMode', mode); } catch (_) {}
  }, CATEGORY_MODE);

  await page.goto(`${BASE}/pages/period-review.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  await page.evaluate(({ start, end }) => {
    window.TmallDateRange?.setRange?.(start, end, 'custom');
  }, { start: RANGE_START, end: RANGE_END });
  await page.waitForTimeout(7000);

  // 指标矩阵
  await page.evaluate(() => {
    const tab = document.querySelector('[data-pr-workbench-tab="matrix"]');
    tab?.click();
  });
  await page.waitForTimeout(1500);
  const matrix = await dumpTable(page, '[data-pr-matrix]');
  console.log('MATRIX ' + JSON.stringify(matrix, null, 2));
  await page.screenshot({ path: path.join(OUT_DIR, 'pr_matrix.png'), fullPage: true });

  // 类目拆解
  await page.evaluate(() => {
    const tab = document.querySelector('[data-pr-workbench-tab="category"]');
    tab?.click();
  });
  await page.waitForTimeout(1500);
  const category = await dumpTable(page, '[data-pr-category-breakdown]');
  console.log('CATEGORY ' + JSON.stringify(category, null, 2));
  await page.screenshot({ path: path.join(OUT_DIR, 'pr_category.png'), fullPage: true });

  // 月复盘模式：确认周期口径切到自然月后表格仍正常
  await page.evaluate(() => {
    document.querySelector('[data-pr-mode="month"]')?.click();
  });
  await page.waitForTimeout(6000);
  await page.evaluate(() => {
    document.querySelector('[data-pr-workbench-tab="matrix"]')?.click();
  });
  await page.waitForTimeout(1200);
  const monthMatrix = await dumpTable(page, '[data-pr-matrix]');
  console.log('MONTH-MATRIX ' + JSON.stringify(monthMatrix, null, 2));
  await page.screenshot({ path: path.join(OUT_DIR, 'pr_matrix_month.png'), fullPage: true });

  console.log('SHOT ' + path.join(OUT_DIR, 'pr_matrix.png'));
  console.log('SHOT ' + path.join(OUT_DIR, 'pr_category.png'));
  console.log('SHOT ' + path.join(OUT_DIR, 'pr_matrix_month.png'));
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

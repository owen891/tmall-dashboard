/**
 * 抓「周月复盘 → 复盘设置（4 项目标）＋ 目标 vs 实际表」的截图，并 dump 表内容。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/shot_period_review_targets.js [port] [category_mode] [start] [end]
 */
const path = require('path');

const PORT = process.argv[2] || '5000';
const CATEGORY_MODE = process.argv[3] || 'sock';
const RANGE_START = process.argv[4] || '2026-09-14';
const RANGE_END = process.argv[5] || '2026-09-20';
const BASE = `http://127.0.0.1:${PORT}`;
const OUT_DIR = path.join(__dirname, '..', 'logs');
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1400 } });
  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log('PAGE-ERROR ' + msg.text());
  });
  page.on('pageerror', (err) => console.log('PAGE-EXCEPTION ' + err.message));

  // 品类模式来自 localStorage，复盘周期来自顶栏共享时间范围，都不是 URL 参数。
  await page.addInitScript((mode) => {
    try { window.localStorage.setItem('dashboard.categoryMode', mode); } catch (_) {}
  }, CATEGORY_MODE);

  await page.goto(`${BASE}/pages/period-review.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  await page.evaluate(({ start, end }) => {
    window.TmallDateRange?.setRange?.(start, end, 'custom');
  }, { start: RANGE_START, end: RANGE_END });
  await page.waitForTimeout(7000);

  const inputs = await page.evaluate(() => {
    const pick = (sel) => {
      const el = document.querySelector(sel);
      return el ? el.value : null;
    };
    return {
      sales: pick('[data-pr-target]'),
      profit: pick('[data-pr-target-profit]'),
      adSpend: pick('[data-pr-target-ad-spend]'),
      netRatio: pick('[data-pr-target-net-expense-ratio]'),
      period: window.TmallDateRange?.getState?.() || null,
    };
  });
  console.log('INPUTS ' + JSON.stringify(inputs, null, 2));

  const table = await page.evaluate(() => {
    const root = document.querySelector('[data-pr-overview]');
    if (!root) return { missing: '[data-pr-overview]' };
    const box = root.querySelector('.pr-target-table');
    if (!box) return { missing: '.pr-target-table', text: (root.innerText || '').slice(0, 400) };
    const tbl = box.querySelector('table');
    if (!tbl) return { noTable: true, text: (box.innerText || '').slice(0, 300) };
    return {
      title: (box.querySelector('.pr-target-table__title') || {}).innerText || '',
      headers: [...tbl.querySelectorAll('thead th')].map((th) => (th.innerText || '').trim()),
      rows: [...tbl.querySelectorAll('tbody tr')].map((tr) => ({
        key: tr.getAttribute('data-pr-target-row'),
        cells: [...tr.querySelectorAll('td')].map((td) => ({
          text: (td.innerText || '').trim(),
          cls: td.className,
        })),
      })),
    };
  });
  console.log('TARGET-TABLE ' + JSON.stringify(table, null, 2));

  const out = path.join(OUT_DIR, `pr_targets_${RANGE_START}_${RANGE_END}.png`);
  await page.screenshot({ path: out, fullPage: true });
  console.log('SHOT ' + out);

  // 再单独抓「复盘设置 + 业绩全景（含目标 vs 实际）」区域，便于看清数值
  const box = await page.evaluate(() => {
    const toolbar = document.querySelector('.pr-toolbar');
    const overview = document.querySelector('[data-pr-overview]');
    if (!toolbar || !overview) return null;
    const a = toolbar.getBoundingClientRect();
    const b = overview.getBoundingClientRect();
    // 目标表在 overview 里，但面板高度可能小于内容高度，取两者下沿的最大值再留点余量。
    const table = overview.querySelector('.pr-target-table');
    const t = table ? table.getBoundingClientRect() : b;
    const top = a.top + window.scrollY;
    const bottom = Math.max(b.bottom, t.bottom) + window.scrollY + 16;
    return { x: Math.max(a.left, b.left), y: top, width: Math.max(a.width, b.width), height: bottom - top };
  });
  if (box) {
    const focus = path.join(OUT_DIR, `pr_targets_focus_${RANGE_START}.png`);
    await page.screenshot({ path: focus, clip: box });
    console.log('SHOT ' + focus);
  }
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

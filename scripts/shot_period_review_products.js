/**
 * 抓「周月复盘 → 货品与异常」两张货品表的截图，并验证字段设置（列开关）。
 *
 * 校验点：
 *   1. 表格含「商品ID」列，且标题列不再换行（单行截断）
 *   2. 字段设置浮层可打开，勾选后列实时出现
 *   3. 开关写入 localStorage，刷新后仍生效
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/shot_period_review_products.js [port] [category_mode] [start] [end]
 */
const path = require('path');

const PORT = process.argv[2] || '5000';
const CATEGORY_MODE = process.argv[3] || 'sock';
const RANGE_START = process.argv[4] || '2026-09-07';
const RANGE_END = process.argv[5] || '2026-09-13';
const BASE = `http://127.0.0.1:${PORT}`;
const OUT_DIR = path.join(__dirname, '..', 'logs');
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const PANEL = '[data-section-key="goods"]';

// 表头 + 每行文本 + 标题列是否被压成单行（比较 scrollWidth 与 clientWidth 之外的粗判：行高）
function dumpTables(page) {
  return page.evaluate((sel) => {
    const root = document.querySelector(sel);
    if (!root) return { missing: sel };
    const tables = [...root.querySelectorAll('table')];
    return tables.map((table) => {
      const headers = [...table.querySelectorAll('thead th')].map((th) => (th.innerText || '').trim());
      const widths = [...table.querySelectorAll('thead th')].map((th) => Math.round(th.getBoundingClientRect().width));
      const rows = [...table.querySelectorAll('tbody tr')].map((tr) => ({
        height: Math.round(tr.getBoundingClientRect().height),
        cells: [...tr.querySelectorAll('td')].map((td) => (td.innerText || '').replace(/\s+/g, ' ').trim()),
      }));
      const nullCells = [...table.querySelectorAll('td')]
        .filter((td) => (td.innerText || '').includes('null')).length;
      const titleCells = [...table.querySelectorAll('.pr-table__title-text')];
      const truncated = titleCells.filter((node) => node.scrollWidth > node.clientWidth + 1).length;
      const hover = titleCells[0] ? (titleCells[0].getAttribute('title') || '') : '';
      const toolbar = !!document.querySelector('.pr-table-toolbar');
      return { headers, widths, toolbar, rowCount: rows.length, truncatedTitles: truncated, hoverTitleLen: hover.length, nullCells, rows };
    });
  }, PANEL);
}

async function openProducts(page) {
  // 拆因已并入结论段：滚动到货品复盘段（板块数据含货品榜）。
  await page.evaluate(() => {
    document.querySelector('[data-section-key="goods"]')
      ?.scrollIntoView({ behavior: 'instant', block: 'start' });
  });
  await page.waitForTimeout(1200);
}

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1200 } });
  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log('PAGE-ERROR ' + msg.text());
  });

  await page.addInitScript((mode) => {
    try { window.localStorage.setItem('dashboard.categoryMode', mode); } catch (_) {}
  }, CATEGORY_MODE);

  await page.goto(`${BASE}/pages/period-review.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  await page.evaluate(({ start, end }) => {
    window.TmallDateRange?.setRange?.(start, end, 'custom');
  }, { start: RANGE_START, end: RANGE_END });
  await page.waitForTimeout(7000);

  await openProducts(page);
  const before = await dumpTables(page);
  console.log('BEFORE ' + JSON.stringify(before, null, 2));
  await page.screenshot({ path: path.join(OUT_DIR, 'pr_products.png'), fullPage: true });

  // 打开字段设置浮层
  const openPopover = async () => {
    await page.evaluate(() => {
      if (document.querySelector('.pr-field-popover')) return;
      const button = [...document.querySelectorAll('.pr-table-toolbar button')]
        .find((node) => (node.innerText || '').includes('字段设置'));
      button?.click();
    });
    await page.waitForTimeout(500);
  };

  await openPopover();
  const popover = await page.evaluate(() => {
    const node = document.querySelector('.pr-field-popover');
    if (!node) return { missing: true };
    const rect = node.getBoundingClientRect();
    return {
      rect: { top: Math.round(rect.top), left: Math.round(rect.left), width: Math.round(rect.width) },
      items: [...node.querySelectorAll('.pr-field-popover__item')].map((label) => ({
        text: (label.innerText || '').replace(/\s+/g, ' ').trim(),
        checked: !!label.querySelector('input')?.checked,
        disabled: !!label.querySelector('input')?.disabled,
      })),
    };
  });
  console.log('POPOVER ' + JSON.stringify(popover, null, 2));
  // 浮层是 position: fixed，fullPage 截图会把它拼到错误位置，这里只截浮层本身。
  const popoverEl = await page.$('.pr-field-popover');
  if (popoverEl) await popoverEl.screenshot({ path: path.join(OUT_DIR, 'pr_products_fields.png') });

  // 勾选「支付转化率」+「推广花费」，确认列实时出现
  await openPopover();
  await page.evaluate(() => {
    [...document.querySelectorAll('.pr-field-popover__item')]
      .filter((label) => ['支付转化率', '推广花费'].some((name) => (label.innerText || '').includes(name)))
      .forEach((label) => {
        const input = label.querySelector('input');
        if (input && !input.checked) input.click();
      });
  });
  await page.waitForTimeout(900);
  const stored = await page.evaluate(() => window.localStorage.getItem('dashboard.periodReviewProductColumns'));
  const after = await dumpTables(page);
  console.log('STORED ' + stored);
  console.log('AFTER-TOGGLE ' + JSON.stringify(after.map((t) => t.headers), null, 2));
  await page.screenshot({ path: path.join(OUT_DIR, 'pr_products_toggled.png'), fullPage: true });

  // 刷新验证持久化
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(9000);
  await openProducts(page);
  const persisted = await dumpTables(page);
  console.log('AFTER-RELOAD ' + JSON.stringify(persisted.map((t) => t.headers), null, 2));
  await page.screenshot({ path: path.join(OUT_DIR, 'pr_products_reload.png'), fullPage: true });

  console.log('SHOT ' + path.join(OUT_DIR, 'pr_products.png'));
  console.log('SHOT ' + path.join(OUT_DIR, 'pr_products_fields.png'));
  console.log('SHOT ' + path.join(OUT_DIR, 'pr_products_toggled.png'));
  console.log('SHOT ' + path.join(OUT_DIR, 'pr_products_reload.png'));
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

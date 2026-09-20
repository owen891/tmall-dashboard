/**
 * 验证「付费推广」两张表的表头排序：必须作用在**全量**行上，而不是只在当前页里排。
 * 判据：按「推广花费」降序后，第一行的值应等于接口返回的 46 条计划里的最大值。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/verify_promotion_sort.js <item_id>
 */
const path = require('path');

const ITEM_ID = process.argv[2] || '711021416206';
const OUT = path.join(__dirname, '..', 'logs', `promotion_sort_${ITEM_ID}.png`);
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const readCampaignTable = () => {
  const dlg = document.querySelector('dialog[open]');
  const tables = [...dlg.querySelectorAll('.product-detail-promotion-block table')];
  const table = tables[tables.length - 1];
  if (!table) return null;
  const headers = [...table.querySelectorAll('thead th')].map((th) => th.innerText.trim());
  const rows = [...table.querySelectorAll('tbody tr')].map((tr) => [...tr.querySelectorAll('td')].map((td) => td.innerText.trim()));
  const pagers = [...dlg.querySelectorAll('.product-detail-promotion-pagination .panel__hint')].map((el) => el.innerText.trim());
  const globalPagers = [...dlg.querySelectorAll('.table-controls__summary')].map((el) => el.innerText.trim());
  return { headers, rowCount: rows.length, firstRow: rows[0], secondRow: rows[1], lastRow: rows[rows.length - 1], pagers, globalPagers };
};

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

  await page.goto(`http://127.0.0.1:5000/products?start=2026-08-22&end=2026-09-20&preset=custom`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);

  // 先拿接口真值，用于校验"全量排序"（必须在有 origin 的页面上 fetch）
  const raw = await page.evaluate(async (id) => {
    const r = await fetch(`/api/promotion/product-detail?start=2026-08-22&end=2026-09-20&product_id=${id}`);
    const j = await r.json();
    const campaigns = (j.data && j.data.campaigns) || [];
    return { count: campaigns.length, maxSpend: Math.max(...campaigns.map((c) => Number(c.ad_spend) || 0)), minSpend: Math.min(...campaigns.map((c) => Number(c.ad_spend) || 0)) };
  }, ITEM_ID).catch(() => null);

  await page.evaluate((id) => window.ProductDetailDialog?.open({ productId: id, title: id }), ITEM_ID);
  await page.waitForTimeout(9000);
  await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const tab = [...dlg.querySelectorAll('button, [role=tab]')].find((el) => (el.textContent || '').trim() === '付费推广');
    tab?.click();
  });
  await page.waitForTimeout(4000);

  const before = await page.evaluate(readCampaignTable);

  // 点「推广花费」表头 → 第一次升序，第二次降序
  const clickHeader = (label, times) => page.evaluate(([text, n]) => {
    const dlg = document.querySelector('dialog[open]');
    const tables = [...dlg.querySelectorAll('.product-detail-promotion-block table')];
    const table = tables[tables.length - 1];
    const th = [...table.querySelectorAll('thead th')]
      .find((cell) => (cell.innerText || '').trim().replace(/[↑↓\s]/g, '') === text);
    if (!th) return 'header not found: ' + text;
    const button = th.querySelector('button') || th;
    for (let i = 0; i < n; i += 1) button.click();
    return 'clicked ' + text;
  }, [label, times]);

  const ascMsg = await clickHeader('推广花费', 1);
  await page.waitForTimeout(2500);
  const asc = await page.evaluate(readCampaignTable);

  const descMsg = await clickHeader('推广花费', 1);
  await page.waitForTimeout(2500);
  const desc = await page.evaluate(readCampaignTable);
  await page.screenshot({ path: OUT });

  // 「推广花费」在第几列由表头决定（计划/渠道/投放方式/推广花费/…）
  const spendIndex = before?.headers ? before.headers.indexOf('推广花费') : -1;
  const spendOf = (row) => Number(String((row || [])[spendIndex] || '').replace(/[¥,]/g, ''));
  console.log(JSON.stringify({
    apiTruth: raw,
    spendIndex,
    before: before && { headers: before.headers, rowCount: before.rowCount, firstRow: before.firstRow, pagers: before.pagers, globalPagers: before.globalPagers },
    ascMsg, ascFirst: asc && asc.firstRow, ascSpend: spendOf(asc && asc.firstRow),
    descMsg, descFirst: desc && desc.firstRow, descSpend: spendOf(desc && desc.firstRow),
    checks: {
      singlePagerPerTable: Boolean(before && before.globalPagers.length === 0),
      ascEqualsMin: Boolean(raw && Math.abs(spendOf(asc && asc.firstRow) - raw.minSpend) < 0.05),
      descEqualsMax: Boolean(raw && Math.abs(spendOf(desc && desc.firstRow) - raw.maxSpend) < 0.05),
      descIsGlobalMax: Boolean(raw && spendOf(desc && desc.firstRow) > spendOf(before && before.firstRow)),
    },
    errors: errors.slice(0, 5),
    out: OUT,
  }, null, 2));
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

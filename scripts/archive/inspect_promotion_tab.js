/**
 * 检查单品弹窗「付费推广」标签页的实际渲染结果与请求。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/inspect_promotion_tab.js <item_id>
 */
const path = require('path');

const ITEM_ID = process.argv[2] || '711021416206';
const OUT = path.join(__dirname, '..', 'logs', `promotion_tab_${ITEM_ID}.png`);
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });

  const calls = [];
  const errors = [];
  page.on('request', (r) => { if (r.url().includes('/api/promotion/')) calls.push({ url: r.url(), status: null }); });
  page.on('response', (r) => {
    if (!r.url().includes('/api/promotion/')) return;
    const hit = calls.find((c) => c.url === r.url());
    if (hit) hit.status = r.status();
  });
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));

  await page.goto('http://127.0.0.1:5000/products', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);

  const range = await page.evaluate(() => window.TmallDateRange?.getState?.() || null);
  await page.evaluate((id) => window.ProductDetailDialog?.open({ productId: id, title: id }), ITEM_ID);
  await page.waitForTimeout(9000);

  // 弹窗默认就是「概览」标签，先看这页的推广指标
  const overviewMetrics = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    return [...dlg.querySelectorAll('.detail-metric')].map((el) => (el.innerText || '').replace(/\s+/g, ' ').trim());
  });
  console.log('OVERVIEW_METRICS ' + JSON.stringify(overviewMetrics, null, 2));
  await page.screenshot({ path: OUT.replace('.png', '_overview.png') });

  const clickTab = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const tab = [...dlg.querySelectorAll('button, [role=tab]')].find((el) => (el.textContent || '').trim() === '付费推广');
    if (!tab) return 'tab not found';
    tab.click();
    return 'clicked';
  });
  await page.waitForTimeout(5000);

  const report = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const panel = dlg.querySelector('.product-detail-dialog__panels') || dlg;
    const sections = [...panel.querySelectorAll('.product-detail-section')].map((s) => ({
      title: (s.querySelector('.panel__title') || {}).textContent || '',
      hints: [...s.querySelectorAll('.panel__hint')].map((el) => (el.innerText || '').replace(/\s+/g, ' ').trim()).slice(0, 4),
      metrics: [...s.querySelectorAll('.detail-metric')].map((el) => (el.innerText || '').replace(/\s+/g, ' ').trim()),
      tables: [...s.querySelectorAll('table')].map((t) => ({
        headers: [...t.querySelectorAll('thead th')].map((th) => th.innerText.trim()),
        rowCount: t.querySelectorAll('tbody tr').length,
        firstRow: [...(t.querySelector('tbody tr')?.querySelectorAll('td') || [])].map((td) => td.innerText.trim()).join(' | '),
      })),
      text: (s.innerText || '').replace(/\s+/g, ' ').slice(0, 300),
    }));
    return { sectionCount: sections.length, sections };
  });

  await page.screenshot({ path: OUT });
  console.log(JSON.stringify({ range, clickTab, calls, report, errors: errors.slice(0, 6), out: OUT }, null, 2));
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

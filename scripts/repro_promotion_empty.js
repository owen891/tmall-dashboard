/**
 * 复现亮哥的截图状态：把共享日期范围固定成 2026-08-22 ~ 2026-09-20（锚点未校准到数据截止时出现），
 * 再打开单品弹窗的「付费推广」，抓实际请求 URL / 响应体 / 渲染结果。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/repro_promotion_empty.js <item_id> [start] [end]
 */
const path = require('path');

const ITEM_ID = process.argv[2] || '711021416206';
const START = process.argv[3] || '2026-08-22';
const END = process.argv[4] || '2026-09-20';
const OUT = path.join(__dirname, '..', 'logs', `repro_promotion_${START}_${END}.png`);
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });

  const log = [];
  page.on('response', async (r) => {
    const u = r.url();
    if (!u.includes('/api/')) return;
    const interesting = u.includes('/promotion/') || u.includes('/periods') || u.includes('/detail') || u.includes('/products/');
    if (!interesting) return;
    let body = '';
    try { body = (await r.text()).slice(0, 400); } catch (_) {}
    log.push({ status: r.status(), url: u.replace('http://127.0.0.1:5000', ''), body });
  });

  const url = `http://127.0.0.1:5000/products?start=${START}&end=${END}&preset=custom`;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);

  const rangeState = await page.evaluate(() => window.TmallDateRange?.getState?.() || null);
  await page.evaluate((id) => window.ProductDetailDialog?.open({ productId: id, title: id }), ITEM_ID);
  await page.waitForTimeout(9000);

  const header = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    return {
      idLine: (dlg.querySelector('[data-shared-product-id]') || {}).textContent || '',
      overview: [...dlg.querySelectorAll('.detail-metric')].map((el) => (el.innerText || '').replace(/\s+/g, ' ').trim()),
    };
  });

  await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const tab = [...dlg.querySelectorAll('button, [role=tab]')].find((el) => (el.textContent || '').trim() === '付费推广');
    tab?.click();
  });
  await page.waitForTimeout(4000);

  const promo = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const s = dlg.querySelector('.product-detail-section');
    return {
      metrics: [...(s?.querySelectorAll('.detail-metric') || [])].map((el) => (el.innerText || '').replace(/\s+/g, ' ').trim()),
      hints: [...(s?.querySelectorAll('.panel__hint') || [])].map((el) => (el.innerText || '').replace(/\s+/g, ' ').trim()),
      tables: [...(s?.querySelectorAll('table') || [])].map((t) => t.querySelectorAll('tbody tr').length),
    };
  });

  await page.screenshot({ path: OUT });
  console.log(JSON.stringify({ url, rangeState, header, promo, calls: log, out: OUT }, null, 2));
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

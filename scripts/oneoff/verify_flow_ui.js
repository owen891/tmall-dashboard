/**
 * 视觉验收：打开商品详情页，截取「流量结构」区域，确认层级下钻已生效。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/verify_flow_ui.js <item_id> [out.png]
 */
const path = require('path');
const fs = require('fs');

const ITEM_ID = process.argv[2] || '711021416206';
const OUT = process.argv[3] || path.join(__dirname, '..', 'logs', 'flow_verify_%s.png'.replace('%s', ITEM_ID));
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));

  await page.goto(`http://127.0.0.1:5000/products/${ITEM_ID}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);

  // 切到「流量来源」标签（流量结构在这一屏）。只认商品工作台内的 tab 按钮，
  // 避免误点侧边栏同名导航（demo-nav__item）。
  const tabHandle = await page.evaluateHandle(() => {
    const tabs = [...document.querySelectorAll('button.product-workbench__tab')]
      .filter(el => (el.textContent || '').trim() === '流量来源');
    return tabs[0] || null;
  });
  const tabEl = tabHandle.asElement();
  if (tabEl) {
    await tabEl.click().catch(() => {});
    await page.waitForTimeout(7000);
  } else {
    console.error('未找到商品工作台的「流量来源」标签');
  }

  const section = await page.$('text=流量结构');
  if (section) {
    await section.scrollIntoViewIfNeeded().catch(() => {});
    await page.waitForTimeout(1500);
  }

  // 读取页面里的渠道行结构，便于文本断言
  const summary = await page.evaluate(() => {
    const boxes = [...document.querySelectorAll('section, .panel, article, div')]
      .filter(el => /流量结构/.test(el.textContent || '') && el.querySelector('table'));
    const box = boxes[boxes.length - 1];
    if (!box) return { found: false };
    const rows = [...box.querySelectorAll('table tbody tr')].map(tr =>
      [...tr.querySelectorAll('td')].map(td => (td.innerText || '').trim()));
    return {
      found: true,
      hint: (box.querySelector('.panel__hint') || {}).innerText || '',
      rows: rows.slice(0, 14),
      drillables: rows.filter(r => /→/.test(r[0] || '')).map(r => r[0]),
    };
  });

  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  await page.screenshot({ path: OUT, fullPage: false });
  console.log(JSON.stringify({ out: OUT, summary, errors: errors.slice(0, 8) }, null, 2));
  await browser.close();
})().catch(err => { console.error('FAIL', err); process.exit(1); });

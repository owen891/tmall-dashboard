/**
 * 抓「流量结构」标签页的整页截图（用于确认板块数量与排布）。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/shot_flow_tab.js <item_id>
 */
const path = require('path');

const ITEM_ID = process.argv[2] || '711021416206';
const OUT = path.join(__dirname, '..', 'logs', `flow_tab_full_${ITEM_ID}.png`);
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 3600 } });

  await page.goto('http://127.0.0.1:5000/products', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  await page.evaluate((id) => window.ProductDetailDialog?.open({ productId: id, title: id }), ITEM_ID);
  await page.waitForTimeout(8000);
  await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const tab = [...dlg.querySelectorAll('button, [role=tab]')].find((el) => (el.textContent || '').trim() === '流量结构');
    tab?.click();
  });
  await page.waitForTimeout(7000);

  const report = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const panels = [...dlg.querySelectorAll('.product-detail-section')];
    return {
      sectionCount: panels.length,
      sections: panels.map((panel) => ({
        title: (panel.querySelector('.panel__title') || {}).textContent || '',
        hints: [...panel.querySelectorAll('.panel__hint')].map((el) => (el.innerText || '').replace(/\s+/g, ' ').trim()).slice(0, 3),
        tables: panel.querySelectorAll('table').length,
        headers: [...panel.querySelectorAll('table thead th')].map((th) => (th.innerText || '').trim()),
        rowCount: panel.querySelectorAll('table tbody tr').length,
        firstRow: [...(panel.querySelector('table tbody tr')?.querySelectorAll('td') || [])]
          .map((td) => (td.innerText || '').replace(/\s+/g, ' ').trim()).join(' | '),
      })),
    };
  });
  console.log('SECTIONS ' + JSON.stringify(report, null, 2));

  // 口径切换：点第二个按钮应换成「全程来源」的数据
  const switchInfo = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const buttons = [...dlg.querySelectorAll('.segmented button')];
    if (buttons.length < 2) return { buttons: buttons.map((b) => b.textContent.trim()) };
    const labels = buttons.map((b) => b.textContent.trim());
    buttons[1].click();
    return { labels, clicked: labels[1] };
  });
  await page.waitForTimeout(2500);
  const after = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const panel = dlg.querySelector('.product-detail-section');
    return {
      pressed: [...panel.querySelectorAll('.segmented button')]
        .map((b) => `${b.textContent.trim()}=${b.getAttribute('aria-pressed')}`),
      rowCount: panel.querySelectorAll('table tbody tr').length,
      firstRow: [...(panel.querySelector('table tbody tr')?.querySelectorAll('td') || [])]
        .map((td) => (td.innerText || '').replace(/\s+/g, ' ').trim()).join(' | '),
      metrics: [...panel.querySelectorAll('.detail-metric')]
        .map((el) => (el.innerText || '').replace(/\s+/g, ' ').trim()),
    };
  });
  console.log('SWITCH ' + JSON.stringify({ switchInfo, after }, null, 2));
  await page.screenshot({ path: OUT.replace('.png', '_switch.png') });

  // 弹窗是固定高度、内部滚动的，先解除高度限制再截整块
  await page.addStyleTag({
    content: 'dialog[open]{max-height:none!important;height:auto!important;}'
      + 'dialog[open] .product-detail-dialog__body{max-height:none!important;height:auto!important;overflow:visible!important;}'
      + 'dialog[open] .product-detail-dialog__shell{max-height:none!important;height:auto!important;}',
  });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: OUT });
  console.log('SHOT ' + OUT);
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

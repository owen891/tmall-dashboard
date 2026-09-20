/**
 * 视觉验收（弹窗版）：验证「流量结构」的字段设置（列可配置 + 模板 + 持久化）。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/verify_flow_fields.js <item_id>
 */
const path = require('path');

const ITEM_ID = process.argv[2] || '711021416206';
const OUT_MAIN = path.join(__dirname, '..', 'logs', `flow_fields_${ITEM_ID}.png`);
const OUT_DIALOG = path.join(__dirname, '..', 'logs', `flow_fields_dialog_${ITEM_ID}.png`);
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const FIELD_DIALOG = `document.querySelector('#productDetailFlowFieldTitle')?.closest('dialog')`;

const readHeaders = () => [...document.querySelectorAll('dialog[open]')]
  .filter((dlg) => !dlg.querySelector('#productDetailFlowFieldTitle'))
  .flatMap((dlg) => [...dlg.querySelectorAll('table thead th')])
  .map((th) => (th.innerText || '').trim());

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

  const openDialog = async () => {
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
  };

  await openDialog();

  const headersBefore = await page.evaluate(readHeaders);
  const tableCount = await page.evaluate(() => document.querySelectorAll('dialog[open] table').length);

  // 打开「字段设置」
  const openMsg = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const btn = [...dlg.querySelectorAll('button')].find((b) => (b.textContent || '').trim() === '字段设置');
    if (!btn) return 'button not found';
    btn.click();
    return 'clicked';
  });
  await page.waitForTimeout(1500);

  const dialogInfo = await page.evaluate((sel) => {
    const dlg = eval(sel);
    if (!dlg) return null;
    const options = [...dlg.querySelectorAll('[data-flow-field-key]')].map((input) => ({
      key: input.getAttribute('data-flow-field-key'),
      label: (input.parentElement?.textContent || '').trim(),
      checked: input.checked,
      disabled: input.disabled,
    }));
    return {
      count: (dlg.querySelector('[data-flow-field-count]')?.textContent || '').trim(),
      groups: [...dlg.querySelectorAll('.ui-field-selector__group > strong')].map((el) => el.textContent.trim()),
      options,
      preview: [...dlg.querySelectorAll('[data-flow-field-preview]')].map((el) => (el.textContent || '').trim()),
      templates: [...dlg.querySelectorAll('[data-flow-template-select] option')].map((o) => o.textContent),
    };
  }, FIELD_DIALOG);
  await page.screenshot({ path: OUT_DIALOG, fullPage: false });

  // 选「成交明细」模板并套用，再手动取消勾选「客单价」
  const applyTemplate = await page.evaluate((sel) => {
    const dlg = eval(sel);
    if (!dlg) return 'no dialog';
    const select = dlg.querySelector('[data-flow-template-select]');
    const target = [...select.options].find((o) => o.textContent.trim() === '成交明细');
    if (!target) return 'template not found';
    select.value = target.value;
    dlg.querySelector('[data-flow-template-apply]').click();
    return 'applied ' + target.value;
  }, FIELD_DIALOG);
  await page.waitForTimeout(1000);

  const afterTemplate = await page.evaluate((sel) => {
    const dlg = eval(sel);
    return {
      count: (dlg.querySelector('[data-flow-field-count]')?.textContent || '').trim(),
      preview: [...dlg.querySelectorAll('[data-flow-field-preview]')].map((el) => (el.textContent || '').trim()),
    };
  }, FIELD_DIALOG);

  const uncheck = await page.evaluate((sel) => {
    const dlg = eval(sel);
    const input = [...dlg.querySelectorAll('[data-flow-field-key]')]
      .find((el) => el.getAttribute('data-flow-field-key') === 'customer_price');
    if (!input) return 'field not found';
    if (!input.checked) return 'already unchecked';
    input.click();
    return 'unchecked customer_price';
  }, FIELD_DIALOG);
  await page.waitForTimeout(800);

  const applyMsg = await page.evaluate((sel) => {
    const dlg = eval(sel);
    const btn = dlg.querySelector('[data-flow-field-apply]');
    if (!btn || btn.disabled) return 'apply unavailable';
    btn.click();
    return 'applied';
  }, FIELD_DIALOG);
  await page.waitForTimeout(4000);

  const headersAfter = await page.evaluate(readHeaders);
  const stored = await page.evaluate(() => localStorage.getItem('tmall_product_detail_flow_fields_v1'));
  await page.screenshot({ path: OUT_MAIN, fullPage: false });

  // 重新加载页面，验证字段配置被记住
  await openDialog();
  const headersAfterReload = await page.evaluate(readHeaders);

  console.log(JSON.stringify({
    openMsg, applyTemplate, uncheck, applyMsg,
    headersBefore,
    headersAfter,
    headersAfterReload,
    persisted: headersAfter.join('|') === headersAfterReload.join('|'),
    tableCount,
    dialogInfo,
    afterTemplate,
    stored,
    out: { main: OUT_MAIN, dialog: OUT_DIALOG },
    errors: errors.slice(0, 6),
  }, null, 2));
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

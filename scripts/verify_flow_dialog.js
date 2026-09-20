/**
 * 视觉验收（弹窗版）：在商品列表页打开商品详情弹窗，抓「流量结构」区域。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/verify_flow_dialog.js <item_id>
 */
const path = require('path');
const fs = require('fs');

const ITEM_ID = process.argv[2] || '711021416206';
const OUT = path.join(__dirname, '..', 'logs', `flow_dialog_${ITEM_ID}.png`);
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

  await page.goto('http://127.0.0.1:5000/products', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);

  const opened = await page.evaluate((id) => {
    if (!window.ProductDetailDialog) return 'no ProductDetailDialog';
    window.ProductDetailDialog.open({ productId: id, title: id });
    return 'opened';
  }, ITEM_ID).catch(e => 'eval error: ' + e.message);
  await page.waitForTimeout(9000);

  // 弹窗内的「流量结构」标签页
  const tabHandle = await page.evaluateHandle(() => {
    const dlg = document.querySelector('dialog[open]');
    if (!dlg) return null;
    return [...dlg.querySelectorAll('button, [role=tab], a')]
      .find(el => (el.textContent || '').trim() === '流量结构') || null;
  });
  const tabEl = tabHandle.asElement();
  let tabClicked = false;
  if (tabEl) {
    await tabEl.click().catch(() => {});
    tabClicked = true;
    await page.waitForTimeout(7000);
  }

  const info = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    if (!dlg) return { found: false, dialogText: '(无弹窗)' };
    const head = [...dlg.querySelectorAll('*')].find(el =>
      el.children.length <= 3 && (el.textContent || '').trim().startsWith('流量结构'));
    const tables = [...dlg.querySelectorAll('table')];
    const table = tables[tables.length - 1];
    const rows = table ? [...table.querySelectorAll('tbody tr')]
      .map(tr => [...tr.querySelectorAll('td')].map(td => (td.innerText || '').trim())) : [];
    const metrics = [...dlg.querySelectorAll('.detail-metric')]
      .map(el => (el.innerText || '').replace(/\s+/g, ' ').trim());
    const hints = [...dlg.querySelectorAll('.panel__hint')]
      .map(el => (el.innerText || '').replace(/\s+/g, ' ').trim())
      .filter(t => /渠道|统计区间|父级|口径/.test(t));
    return {
      found: !!table,
      title: head ? (head.textContent || '').trim().slice(0, 90) : '(未渲染)',
      metrics,
      hints,
      totalRows: rows.length,
      rows: rows.slice(0, 18),
      drillables: rows.filter(r => /→/.test(r[0] || '')).map(r => r[0]),
    };
  });

  await page.screenshot({ path: OUT, fullPage: false });

  const readTable = (index) => page.evaluate((i) => {
    const dlg = document.querySelector('dialog[open]');
    const tables = [...dlg.querySelectorAll('table')];
    const table = tables[i];
    if (!table) return null;
    const rows = [...table.querySelectorAll('tbody tr')].map(tr => {
      const cell = tr.querySelector('.channel-cell');
      const toggle = tr.querySelector('.toggle-btn');
      return {
        name: (tr.querySelector('.channel-name') || {}).textContent || '',
        uv: (tr.querySelectorAll('td')[1] || {}).textContent || '',
        indent: cell ? (cell.style.paddingLeft || '0px') : '',
        toggle: toggle ? toggle.textContent : '',
      };
    });
    return rows;
  }, index);

  const clickToggle = (tableIndex, name) => page.evaluate(([i, n]) => {
    const dlg = document.querySelector('dialog[open]');
    const tables = [...dlg.querySelectorAll('table')];
    const table = tables[i];
    if (!table) return 'no table';
    const rows = [...table.querySelectorAll('tbody tr')];
    const row = rows.find(tr => (tr.querySelector('.channel-name') || {}).textContent === n);
    if (!row) return 'row not found: ' + n;
    const btn = row.querySelector('.toggle-btn');
    if (!btn) return 'no toggle: ' + n;
    btn.click();
    return 'clicked ' + n;
  }, [tableIndex, name]);

  const before = await readTable(0);
  const rootName = (before || [])[0] ? before[0].name : '';
  const expandDeep = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const tables = [...dlg.querySelectorAll('table')];
    const table = tables[1];
    if (!table) return null;
    const rows = [...table.querySelectorAll('tbody tr')];
    const row = rows.find(tr => (tr.querySelector('.toggle-btn') || {}).textContent === '+');
    if (!row) return null;
    row.querySelector('.toggle-btn').click();
    return (row.querySelector('.channel-name') || {}).textContent || '';
  });
  await page.waitForTimeout(1200);
  const deepRows = expandDeep ? await readTable(1) : null;

  const collapseMsg = rootName ? await clickToggle(0, rootName) : 'no root';
  await page.waitForTimeout(1200);
  const collapsed = await readTable(0);
  const expandMsg = rootName ? await clickToggle(0, rootName) : 'no root';
  await page.waitForTimeout(1200);
  const restored = await readTable(0);
  await page.screenshot({ path: OUT.replace('.png', '_tree.png'), fullPage: false });

  const drillInfo = {
    collapseMsg, expandMsg, expandDeep,
    root: rootName,
    rowsBefore: (before || []).length,
    rowsAfterCollapse: (collapsed || []).length,
    rowsRestored: (restored || []).length,
    defaultRows: (before || []).slice(0, 6),
    collapsedRows: collapsed,
    deepRows: (deepRows || []).slice(0, 8),
  };

  console.log(JSON.stringify({ opened, tabClicked, out: OUT, info, drillInfo, errors: errors.slice(0, 5) }, null, 2));
  await browser.close();
})().catch(e => { console.error('FAIL', e); process.exit(1); });

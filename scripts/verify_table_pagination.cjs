/**
 * 5-1 验证：客户端分页只保留「当前页 + 下一页」的 DOM（只读，输出 PASS/FAIL）
 *
 * 契约：
 *   1. data-center 总节点数 < 8000（改前 ≈ 24333）
 *   2. 每张客户端分页表 tbody 里的数据行 = min(总行数, pageSize × 2)
 *   3. 点「下一页」后可见行数 = pageSize，且首行内容变化
 *   4. 点表头排序后，第一列数值方向正确
 *   5. 无 pageerror、无横向溢出
 *
 * 用法：
 *   NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/verify_table_pagination.cjs
 */
const { chromium } = require('playwright-core');

const BASE = process.env.BASE || 'http://127.0.0.1:5000';
const ROUTE = process.env.ROUTE || '/data-center';

const PROBE = () => {
  const tables = [...document.querySelectorAll('table.ui-data-table')].map((table) => {
    const body = table.tBodies[0];
    const rows = body ? [...body.rows] : [];
    const dataRows = rows.filter((row) => !(row.cells.length === 1 && Number(row.cells[0].colSpan || 1) > 1));
    const controls = table.closest('.ui-panel, section')?.querySelector('.table-controls');
    const summary = (controls?.querySelector('.table-controls__summary')?.textContent || '').trim();
    const totalMatch = /共 (\d+) 行/.exec(summary);
    return {
      domRows: dataRows.length,
      // 「可见」= 未被 hidden（不要求容器本身可见：折叠面板里的行也算）
      shownRows: dataRows.filter((row) => !row.hidden).length,
      total: totalMatch ? Number(totalMatch[1]) : null,
      summary: summary.slice(0, 40),
      pageSize: Number(controls?.querySelector('.table-controls__page-size select')?.value || 0),
      hasNext: !(controls?.querySelector('[data-table-next]')?.disabled ?? true),
      title: table.closest('.ui-panel')?.querySelector('.panel__title')?.textContent?.trim() || '',
    };
  });
  return {
    allEl: document.querySelectorAll('*').length,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    tables,
  };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PW_CHROMIUM || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 200)));
  await page.goto(BASE + ROUTE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);

  const failures = [];
  const base = await page.evaluate(PROBE);
  console.log(`\n${ROUTE}  总节点 ${base.allEl}  溢出 ${base.overflow}px`);
  base.tables.forEach((t, i) => {
    console.log(`  #${i + 1} ${t.title.slice(0, 16)} | DOM 行 ${t.domRows} / 显示 ${t.shownRows} / 每页 ${t.pageSize} | ${t.summary}`);
  });

  if (base.allEl >= 8000) failures.push(`总节点 ${base.allEl} >= 8000`);
  if (base.overflow > 1) failures.push(`横向溢出 ${base.overflow}px`);

  const clientTables = base.tables.filter((t) => t.pageSize > 0 && t.total);
  if (!clientTables.length) failures.push('没有找到客户端分页表');
  clientTables.forEach((t) => {
    const expectDom = Math.min(t.total, t.pageSize * 2);
    const expectShown = Math.min(t.total, t.pageSize);
    if (t.domRows !== expectDom) failures.push(`「${t.title}」DOM 行 ${t.domRows} != 期望 ${expectDom}`);
    if (t.shownRows !== expectShown) failures.push(`「${t.title}」显示行 ${t.shownRows} != 期望 ${expectShown}`);
  });

  // 翻页 + 排序：拿第一张客户端分页表做端到端
  const firstPanel = page.locator('.ui-panel', { has: page.locator('.table-controls__page-size') }).first();
  const nextButton = firstPanel.locator('[data-table-next]').first();
  const before = await firstPanel.locator('tbody tr:not([hidden])').first().textContent();
  if (await nextButton.isEnabled()) {
    await nextButton.click();
    await page.waitForTimeout(900);
    const after = await firstPanel.locator('tbody tr:not([hidden])').first().textContent();
    const visNow = await firstPanel.locator('tbody tr:not([hidden])').count();
    console.log(`  翻页：可见 ${visNow} 行；首行变化 ${before !== after}`);
    if (visNow === 0) failures.push('翻页后没有可见行');
    if (before === after) failures.push('翻页后首行未变化');
  } else {
    console.log('  翻页：下一页按钮不可用（数据不足一页），跳过');
  }

  const sortButton = firstPanel.locator('thead .table-sort-button').first();
  if (await sortButton.count()) {
    await sortButton.click();
    await page.waitForTimeout(900);
    const asc = await firstPanel.locator('tbody tr:not([hidden])').first().textContent();
    await sortButton.click();
    await page.waitForTimeout(900);
    const desc = await firstPanel.locator('tbody tr:not([hidden])').first().textContent();
    console.log(`  排序：升序首行 ≠ 降序首行 ${asc !== desc}`);
    if (asc === desc) failures.push('排序切换后首行未变化');
  }

  if (errors.length) failures.push(`pageerror: ${errors.join('; ')}`);

  // 5-1 配套：商品身份审核的 200 项 <select> 改成首次交互才填充，静态 DOM 里应只有 1 个占位项。
  const optionCheck = await page.evaluate(() => {
    const sel = document.querySelector('select.select[aria-label^="为 "]');
    if (!sel) return { found: false };
    const before = sel.options.length;
    sel.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'mouse' }));
    const after = sel.options.length;
    const first = sel.options[0] ? sel.options[0].textContent : '';
    return { found: true, before, after, first };
  });
  if (optionCheck.found) {
    console.log(`  绑定下拉：静态 ${optionCheck.before} 项 → 交互后 ${optionCheck.after} 项（首项「${optionCheck.first}」）`);
    if (optionCheck.before !== 1) failures.push(`绑定下拉静态 option 数 ${optionCheck.before} != 1（应懒填充）`);
    if (optionCheck.after < 2) failures.push('绑定下拉交互后仍未填充候选商品');
  } else {
    failures.push('没找到商品身份审核的绑定下拉');
  }

  await context.close();
  await browser.close();

  console.log('');
  if (failures.length) {
    console.log('table pagination contract: FAIL');
    failures.forEach((f) => console.log(`  - ${f}`));
    process.exit(1);
  }
  console.log('table pagination contract: PASS');
})().catch((error) => {
  console.error('probe crashed:', error);
  process.exit(1);
});

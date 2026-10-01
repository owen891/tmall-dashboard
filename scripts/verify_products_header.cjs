/**
 * 2-3 验证：products 页头控件收敛（只读，输出 PASS/FAIL）
 *
 * 契约：
 *   1. 页头可见控件 ≤ 6（字段 ×5 + 列设置）
 *   2. 展示 / 周期 / 粒度 都在表格工具栏（.product-view-switch）里
 *   3. 重置按钮在筛选工具栏（.product-filters__actions）
 *   4. 周期视图下：粒度出现、字段组隐藏
 *   5. 1440 / 390 两个宽度都没有横向溢出，且无 pageerror
 *
 * 用法：
 *   NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/verify_products_header.cjs
 * 可选：--base http://127.0.0.1:5000
 */
const path = require('path');
const { chromium } = require('playwright-core');

const args = process.argv.slice(2);
const getArg = (n, f) => { const i = args.indexOf(n); return i >= 0 && args[i + 1] ? args[i + 1] : f; };
const BASE = getArg('--base', 'http://127.0.0.1:5000');

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
];

const PROBE = () => {
  const visible = (el) => !!(el && el.getClientRects().length);
  const header = document.querySelector('.ui-page-header');
  const headerControls = [...(header ? header.querySelectorAll('button, select, input') : [])].filter(visible);
  const viewSwitch = document.querySelector('.product-view-switch');
  const viewControls = [...(viewSwitch ? viewSwitch.querySelectorAll('button, select, input') : [])].filter(visible);
  const reset = document.querySelector('[data-products-reset]');
  return {
    headerControlCount: headerControls.length,
    headerControlLabels: headerControls.map((el) => (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 12)),
    viewSwitchPresent: !!viewSwitch,
    viewControlCount: viewControls.length,
    viewControls: viewControls.map((el) => (el.textContent || '').trim().slice(0, 12)),
    modeSwitchInView: !!(viewSwitch && viewSwitch.querySelector('[data-products-mode="timeline"]')),
    periodSwitchInView: !!(viewSwitch && viewSwitch.querySelector('[data-products-period="weekly"]')),
    timelineLimitInView: !!(viewSwitch && viewSwitch.querySelector('[data-products-timeline-limit="6"]')),
    resetInFilterActions: !!(reset && reset.closest('.product-filters__actions')),
    timelineToolsVisible: visible(document.querySelector('[data-products-timeline-tools]')),
    fieldsGroupVisible: visible(document.querySelector('.product-control-group--fields')),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PW_CHROMIUM || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const failures = [];
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 160)));
    await page.goto(`${BASE}/products`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const list = await page.evaluate(PROBE);
    const tag = `[${vp.name} ${vp.width}px]`;
    console.log(`\n${tag} 列表视图`);
    console.log(`  页头可见控件: ${list.headerControlCount} -> ${list.headerControlLabels.join(' | ')}`);
    console.log(`  工具栏呈现方式控件: ${list.viewControlCount} -> ${list.viewControls.join(' | ')}`);
    console.log(`  重置在筛选工具栏: ${list.resetInFilterActions}`);
    console.log(`  横向溢出: ${list.overflow}px`);

    if (list.headerControlCount > 6) failures.push(`${tag} 页头控件 ${list.headerControlCount} > 6`);
    if (!list.viewSwitchPresent) failures.push(`${tag} 缺少 .product-view-switch`);
    if (!list.modeSwitchInView) failures.push(`${tag} 展示切换未进工具栏`);
    if (!list.periodSwitchInView) failures.push(`${tag} 周期切换未进工具栏`);
    if (!list.timelineLimitInView) failures.push(`${tag} 粒度切换未进工具栏`);
    if (!list.resetInFilterActions) failures.push(`${tag} 重置未在筛选工具栏`);
    if (list.timelineToolsVisible) failures.push(`${tag} 列表视图不应显示粒度`);
    if (!list.fieldsGroupVisible) failures.push(`${tag} 列表视图字段组应可见`);
    if (list.overflow > 1) failures.push(`${tag} 横向溢出 ${list.overflow}px`);
    if (errors.length) failures.push(`${tag} pageerror: ${errors.join('; ')}`);

    // 切到周期视图
    await page.click('[data-products-mode="timeline"]');
    await page.waitForTimeout(2000);
    const tl = await page.evaluate(PROBE);
    console.log(`${tag} 周期视图`);
    console.log(`  页头可见控件: ${tl.headerControlCount} -> ${tl.headerControlLabels.join(' | ')}`);
    console.log(`  工具栏呈现方式控件: ${tl.viewControlCount} -> ${tl.viewControls.join(' | ')}`);
    console.log(`  粒度可见: ${tl.timelineToolsVisible} / 字段组可见: ${tl.fieldsGroupVisible}`);
    console.log(`  横向溢出: ${tl.overflow}px`);

    if (tl.headerControlCount > 6) failures.push(`${tag} 周期视图页头控件 ${tl.headerControlCount} > 6`);
    if (!tl.timelineToolsVisible) failures.push(`${tag} 周期视图应显示粒度`);
    if (tl.fieldsGroupVisible) failures.push(`${tag} 周期视图字段组应隐藏`);
    if (tl.overflow > 1) failures.push(`${tag} 周期视图横向溢出 ${tl.overflow}px`);
    if (errors.length) failures.push(`${tag} pageerror: ${errors.join('; ')}`);

    await context.close();
  }
  await browser.close();

  console.log('');
  if (failures.length) {
    console.log('products header contract: FAIL');
    failures.forEach((f) => console.log(`  - ${f}`));
    process.exit(1);
  }
  console.log('products header contract: PASS');
})().catch((error) => {
  console.error('probe crashed:', error);
  process.exit(1);
});

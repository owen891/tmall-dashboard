/**
 * 2-5 验证：market-ranking 首屏瘦身（只读，输出 PASS/FAIL）
 *
 * 契约：
 *   1. 页高：1440px < 3000，390px < 6000
 *   2. 「店铺/单品趋势」Tab 存在，默认不显示（市场总览是默认）
 *   3. 切到该 Tab：趋势面板可见、店铺/单品列表有内容、两个面板隐藏
 *   4. 无横向溢出、无 pageerror
 *
 * 用法：
 *   NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/verify_market_ranking_tabs.cjs
 */
const path = require('path');
const { chromium } = require('playwright-core');

const BASE = process.env.BASE || 'http://127.0.0.1:5000';
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900, maxHeight: 3000 },
  { name: 'mobile', width: 390, height: 844, maxHeight: 6000 },
];

const PROBE = () => {
  const visible = (el) => !!(el && el.getClientRects().length);
  const panels = {};
  document.querySelectorAll('[data-market-panel]').forEach((p) => {
    const key = p.dataset.marketPanel;
    panels[key] = (panels[key] || 0) + (visible(p) ? 1 : 0);
  });
  return {
    pageHeight: Math.round(document.documentElement.scrollHeight),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    tabs: [...document.querySelectorAll('[data-market-tab]')].map((t) => t.dataset.marketTab),
    activeTab: (document.querySelector('[data-market-tab].is-active') || {}).dataset?.marketTab || null,
    panels,
    shopRows: document.querySelectorAll('[data-market-shop-list] .market-entity-row, [data-market-shop-list] > *').length,
    itemRows: document.querySelectorAll('[data-market-item-list] .market-entity-row, [data-market-item-list] > *').length,
    shopPager: (document.querySelector('[data-market-shop-pager]') || {}).textContent?.trim().slice(0, 40) || '',
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
    await page.goto(`${BASE}/market-ranking`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);

    const tag = `[${vp.name} ${vp.width}px]`;
    const base = await page.evaluate(PROBE);
    console.log(`\n${tag} 默认`);
    console.log(`  页高 ${base.pageHeight} (上限 ${vp.maxHeight}) / 溢出 ${base.overflow}px`);
    console.log(`  tabs: ${base.tabs.join(' | ')}  当前: ${base.activeTab}`);
    console.log(`  可见面板: ${JSON.stringify(base.panels)}`);

    if (base.pageHeight >= vp.maxHeight) failures.push(`${tag} 页高 ${base.pageHeight} >= ${vp.maxHeight}`);
    if (!base.tabs.includes('trends')) failures.push(`${tag} 缺少 trends tab`);
    if (base.activeTab !== 'overview') failures.push(`${tag} 默认 tab 应为 overview，实为 ${base.activeTab}`);
    if (base.panels.trends) failures.push(`${tag} 默认不应显示 trends 面板`);
    if (base.overflow > 1) failures.push(`${tag} 横向溢出 ${base.overflow}px`);

    await page.click('[data-market-tab="trends"]');
    await page.waitForTimeout(1500);
    const trends = await page.evaluate(PROBE);
    console.log(`${tag} 切到 店铺/单品趋势`);
    console.log(`  可见面板: ${JSON.stringify(trends.panels)}`);
    console.log(`  店铺行 ${trends.shopRows} / 单品行 ${trends.itemRows} / 分页 ${trends.shopPager}`);
    console.log(`  页高 ${trends.pageHeight} / 溢出 ${trends.overflow}px`);

    if (!trends.panels.trends) failures.push(`${tag} trends 面板未显示`);
    if (trends.panels.overview) failures.push(`${tag} 切到 trends 后 overview 面板仍可见`);
    if (trends.shopRows < 1) failures.push(`${tag} 店铺趋势列表为空`);
    if (trends.itemRows < 1) failures.push(`${tag} 单品趋势列表为空`);
    if (trends.overflow > 1) failures.push(`${tag} trends 视图横向溢出 ${trends.overflow}px`);
    if (errors.length) failures.push(`${tag} pageerror: ${errors.join('; ')}`);

    await context.close();
  }
  await browser.close();

  console.log('');
  if (failures.length) {
    console.log('market-ranking tabs contract: FAIL');
    failures.forEach((f) => console.log(`  - ${f}`));
    process.exit(1);
  }
  console.log('market-ranking tabs contract: PASS');
})().catch((error) => {
  console.error('probe crashed:', error);
  process.exit(1);
});

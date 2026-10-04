#!/usr/bin/env node
/**
 * 全站页面健康检查（回归防线）
 *
 * 逐页打开所有页面，报告四类「不白屏但静默吃掉功能」的问题：
 *   1. pageerror —— 未捕获异常（往往中断该页后续初始化）
 *   2. console.error
 *   3. HTTP >= 400 的请求（排除 favicon）
 *   4. 无 ?v= 的 /assets/*.js 请求 —— 会被 7 天静态缓存卡住
 * 并顺带确认 TmallUI / TmallDateRange / DemoApi 三个公共对象就绪。
 *
 * 用法：
 *   node scripts/audit_pages_health.cjs
 *   node scripts/audit_pages_health.cjs http://127.0.0.1:5000
 *
 * 退出码：0 = 全部干净；1 = 有页面存在问题。
 *
 * 为什么要有这个脚本：这类问题不会让页面白屏，肉眼很难发现。2026-10-03 靠它
 * 抓到 promotion 页 bindDialog 抛错导致后续初始化全丢、product-detail 静态路径
 * 把 `.html` 当商品 id 去请求 404 两个真实问题。改公共脚本后跑一遍成本极低。
 */
const path = require('node:path');
const { chromium } = require(path.join(__dirname, '..', 'desktop', 'node_modules', 'playwright'));

const BASE = process.argv[2] || 'http://127.0.0.1:5000';
const PAGES = ['overview', 'category-dashboard', 'goals', 'reviews', 'period-review', 'products', 'lifecycle',
  'keyword-promotion', 'promotion', 'new-products', 'creative-board', 'flow-source', 'rival-analysis',
  'market-ranking', 'analysis', 'data-collection', 'data-center', 'settings', 'component-catalog', 'product-detail'];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const bad = [];

  for (const name of PAGES) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errs = [];
    const consoleErrs = [];
    const failed = [];
    const versionless = [];

    page.on('pageerror', (e) => errs.push(String(e).split('\n')[0]));
    page.on('console', (m) => { if (m.type() === 'error') consoleErrs.push(m.text().slice(0, 200)); });
    page.on('response', (r) => {
      if (r.status() >= 400 && !r.url().includes('favicon')) failed.push(`${r.status()} ${r.url().replace(BASE, '')}`);
    });
    page.on('request', (r) => {
      const u = r.url();
      if (/\.js$/.test(u) && u.startsWith(`${BASE}/assets/`)) versionless.push(u.replace(BASE, ''));
    });

    const problems = [];
    try {
      await page.goto(`${BASE}/pages/${name}.html`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3500);

      const ready = await page.evaluate(() => ({
        tmallUI: typeof window.TmallUI === 'object' && window.TmallUI !== null,
        dateRange: typeof window.TmallDateRange === 'object' && window.TmallDateRange !== null,
        api: typeof window.DemoApi === 'object' && window.DemoApi !== null,
      }));

      if (errs.length) problems.push(`pageerror: ${errs.slice(0, 2).join(' | ')}`);
      if (consoleErrs.length) problems.push(`console: ${[...new Set(consoleErrs)].slice(0, 2).join(' | ')}`);
      if (failed.length) problems.push(`请求失败: ${[...new Set(failed)].slice(0, 3).join(' | ')}`);
      if (versionless.length) problems.push(`无版本号脚本: ${[...new Set(versionless)].join(', ')}`);
      if (!ready.tmallUI) problems.push('TmallUI 未就绪');
      if (!ready.dateRange) problems.push('TmallDateRange 未就绪');
      if (!ready.api) problems.push('DemoApi 未就绪');
    } catch (error) {
      problems.push(`加载失败: ${String(error).split('\n')[0]}`);
    }

    if (problems.length) { bad.push(name); console.log(`FAIL  ${name}`); problems.forEach((p) => console.log(`        ${p}`)); }
    else console.log(`OK    ${name}`);
    await page.close();
  }

  await browser.close();
  console.log(`\n==== ${PAGES.length - bad.length}/${PAGES.length} 页面干净 ====`);
  process.exit(bad.length ? 1 : 0);
})().catch((error) => { console.error('FAILED:', error); process.exit(1); });

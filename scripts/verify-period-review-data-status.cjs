/**
 * 浏览器级验证：复盘页「顶部数据状态」+「利润部分口径」标注（P0 #3 / #4）。
 *
 * 用法（dev server 在 5000、Chrome 开 CDP 9223）：
 *   node scripts/verify-period-review-data-status.cjs
 *   node scripts/verify-period-review-data-status.cjs --json out.json
 *
 * 验证点：
 *   ① 驾驶舱顶部出现 .pr-data-status（灯 + 原因清单），不是裸文案
 *   ② 展开后按 warning / info 分组列出条目，warning 在前
 *   ③ 净利润指标卡带「部分口径」徽标
 *   ④ 利润瀑布块标题带「部分口径」徽标
 *   ⑤ 无控制台错误
 *
 * ⚠️ 踩坑见 scripts/verify-period-review-promotion.cjs 头部注释（click 挂起 / 别接管道 /
 *    折叠 details + 抽屉副本重复命中 / 截图用视口 / 路由是 /period-review）。
 */
const fs = require('fs');
const puppeteer = require('E:/www/tmallshangjia/node_modules/puppeteer-core');
const CDP = process.env.CDP_URL || 'http://127.0.0.1:9223';
const BASE = process.env.DASHBOARD_URL || 'http://127.0.0.1:5000';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.error('[step]', ...a);

const errors = [];

function grabScript() {
  const out = {};
  // ① 顶部数据状态：只取可见的那个（抽屉里可能有隐藏副本）
  const all = [...document.querySelectorAll('.pr-data-status')];
  const visible = all.filter((el) => el.offsetParent !== null || el.getClientRects().length);
  const el = visible[0] || all[0];
  if (el) {
    const label = el.querySelector('.pr-data-status__label');
    out.dataStatus = {
      present: true,
      classes: el.className,
      label: label ? label.textContent.trim() : null,
      hasDetails: el.tagName === 'DETAILS',
      totalCopies: all.length,
    };
    // 强制展开（DOM 级，避免 click 挂起）
    if (el.tagName === 'DETAILS') el.open = true;
    out.dataStatus.fresh = (el.querySelector('.pr-data-status__fresh') || {}).textContent || null;
    out.dataStatus.summary = (el.querySelector('.pr-data-status__summary') || {}).textContent || null;
    out.dataStatus.groups = [...el.querySelectorAll('.pr-data-status__group')]
      .map((g) => g.textContent.trim());
    out.dataStatus.items = [...el.querySelectorAll('.pr-data-status__list li')]
      .map((li) => ({ severity: li.className.replace('is-', ''), text: li.textContent.trim().slice(0, 70) }));
  } else {
    out.dataStatus = { present: false };
  }

  // ③ 净利润卡
  const cards = [...document.querySelectorAll('.pr-metric-card')];
  out.metricCards = cards.map((card) => {
    const label = card.querySelector('.pr-metric-card__label');
    const badge = card.querySelector('.pr-caliber-badge');
    const hint = card.querySelector('.pr-metric-card__hint');
    return {
      label: label ? label.textContent.trim() : null,
      badge: badge ? badge.textContent.trim() : null,
      hint: hint ? hint.textContent.trim().slice(0, 60) : null,
    };
  });

  // ④ 利润瀑布块标题徽标
  const titles = [...document.querySelectorAll('.pr-material__title')];
  const profitTitle = titles.find((t) => t.textContent.includes('利润结构'));
  out.profitBlock = profitTitle ? {
    found: true,
    badge: (profitTitle.querySelector('.pr-caliber-badge') || {}).textContent || null,
  } : { found: false };

  return out;
}

(async () => {
  log('connect');
  const browser = await puppeteer.connect({ browserURL: CDP, defaultViewport: null });
  const pages = await browser.pages();
  const page = pages.find((p) => p.url().includes('/period-review')) || pages[0];
  page.setDefaultTimeout(15000);
  page.on('pageerror', (e) => errors.push('PAGEERROR ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE ' + m.text()); });

  await page.evaluate(() => { try { localStorage.setItem('dashboard.categoryMode', 'all'); } catch (e) {} });
  log('goto');
  await page.goto(`${BASE}/period-review`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await sleep(4000);

  const report = {};
  log('click 月复盘 (DOM click)');
  await page.evaluate(() => {
    const b = document.querySelector('button[data-pr-mode="month"]');
    if (b) b.click();
  });
  await sleep(4500);
  report.monthAll = await page.evaluate(grabScript);

  // 展开利润瀑布所在段的折叠容器，让 ④ 可断言
  await page.evaluate(() => {
    const t = [...document.querySelectorAll('.pr-material__title')].find((x) => x.textContent.includes('利润结构'));
    const det = t && t.closest('details.pr-evidence');
    if (det) det.open = true;
  });
  await sleep(1200);
  report.profitAfterExpand = await page.evaluate(grabScript);

  log('switch category -> sock');
  await page.evaluate(() => {
    const sel = document.querySelector('[data-category-mode]');
    if (!sel) return;
    sel.value = 'sock';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(5000);
  report.sock = await page.evaluate(grabScript);

  report.consoleErrors = errors.slice(0, 12);
  report.url = page.url();

  const jsonArg = process.argv.indexOf('--json');
  if (jsonArg > -1 && process.argv[jsonArg + 1]) {
    fs.writeFileSync(process.argv[jsonArg + 1], JSON.stringify(report, null, 2));
    log('report written to', process.argv[jsonArg + 1]);
  } else {
    console.log(JSON.stringify(report, null, 2));
  }
  await browser.disconnect();
  log('done');
})().catch((e) => { console.error('FATAL', e.message); process.exit(1); });

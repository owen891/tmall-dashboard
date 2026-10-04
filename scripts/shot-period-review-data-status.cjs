/**
 * 截图存证：复盘页「顶部数据状态」+「利润部分口径」标注（P0 #3 / #4）。
 *
 * 用法（dev server 在 5000、Chrome 开 CDP 9223）：
 *   node scripts/shot-period-review-data-status.cjs --out docs/archive/xxx.png
 *
 * ⚠️ 截图四坑（上一轮反复 5 次才修好，见 verify-period-review-promotion.cjs 头部）：
 *   ① clip 用文档坐标、getBoundingClientRect 是视口坐标 → 不混用
 *   ② 页面有 sticky header → 目标滚到视口中上部再截
 *   ③ 证据块在折叠的 <details class="pr-evidence"> 内 → 先 details.open = true
 *   ④ 抽屉 .pr-drawer__body 默认 visibility:hidden 但有同份副本 → querySelectorAll 会重复命中
 *   → 结论：details 展开 + window.scrollTo + **截视口（不带 clip）**
 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('E:/www/tmallshangjia/node_modules/puppeteer-core');
const CDP = process.env.CDP_URL || 'http://127.0.0.1:9223';
const BASE = process.env.DASHBOARD_URL || 'http://127.0.0.1:5000';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.error('[step]', ...a);

function outArg() {
  const i = process.argv.indexOf('--out');
  return i > -1 ? process.argv[i + 1] : null;
}
// --target status（默认，截顶部数据状态条）| profit（截利润瀑布块徽标）
function targetArg() {
  const i = process.argv.indexOf('--target');
  return i > -1 ? process.argv[i + 1] : 'status';
}

(async () => {
  const out = outArg();
  if (!out) throw new Error('缺少 --out <png path>');

  log('connect');
  const browser = await puppeteer.connect({ browserURL: CDP, defaultViewport: null });
  const pages = await browser.pages();
  const page = pages.find((p) => p.url().includes('/period-review')) || pages[0];
  page.setDefaultTimeout(15000);

  await page.evaluate(() => { try { localStorage.setItem('dashboard.categoryMode', 'all'); } catch (e) {} });
  log('goto');
  await page.goto(`${BASE}/period-review`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await sleep(4000);

  log('click 月复盘');
  await page.evaluate(() => {
    const b = document.querySelector('button[data-pr-mode="month"]');
    if (b) b.click();
  });
  await sleep(4500);

  const target = targetArg();

  // 展开顶部数据状态 + 滚到目标 → 截视口
  const box = await page.evaluate((tgt) => {
    const all = [...document.querySelectorAll('.pr-data-status')];
    const el = all.find((x) => x.offsetParent !== null) || all[0];
    if (!el) return null;
    // 只在 status 目标下展开浮层，避免遮住利润块
    if (tgt === 'status' && el.tagName === 'DETAILS') el.open = true;
    else if (el.tagName === 'DETAILS') el.open = false;

    const t = [...document.querySelectorAll('.pr-material__title')].find((x) => x.textContent.includes('利润结构'));
    const det = t && t.closest('details.pr-evidence');
    if (det) det.open = true;
    if (tgt === 'profit' && t) {
      const top = t.getBoundingClientRect().top + window.scrollY;
      window.scrollTo(0, Math.max(0, top - 120));
      return true;
    }
    const top = el.getBoundingClientRect().top + window.scrollY;
    window.scrollTo(0, Math.max(0, top - 90));
    return true;
  }, target);
  await sleep(1500);
  if (!box) throw new Error('未找到 .pr-data-status');

  const outPath = path.resolve(out);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  log('screenshot →', outPath);
  await page.screenshot({ path: outPath }); // 视口截图，不带 clip

  await browser.disconnect();
  log('done');
})().catch((e) => { console.error('FATAL', e.message); process.exit(1); });

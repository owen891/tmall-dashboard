/**
 * 截图存证：月复盘「市场监控-行业」分级块。
 *
 * 用法：
 *   node scripts/shot-period-review-market-grading.cjs --out docs/archive/xxx.png [--period 2026-09]
 *
 * ⚠️ 截图四坑见 scripts/shot-period-review-data-status.cjs 头部注释。
 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('E:/www/tmallshangjia/node_modules/puppeteer-core');
const CDP = process.env.CDP_URL || 'http://127.0.0.1:9223';
const BASE = process.env.DASHBOARD_URL || 'http://127.0.0.1:5000';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.error('[step]', ...a);

const arg = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
};

(async () => {
  const out = arg('--out');
  const period = arg('--period', '2026-09');
  const anchor = arg('--anchor', '蓝海市场');
  if (!out) throw new Error('缺少 --out <png path>');

  log('connect');
  const browser = await puppeteer.connect({ browserURL: CDP, defaultViewport: null });
  const pages = await browser.pages();
  const page = pages.find((p) => p.url().includes('/period-review')) || pages[0];
  page.setDefaultTimeout(20000);

  await page.evaluate(() => { try { localStorage.setItem('dashboard.categoryMode', 'all'); } catch (e) {} });
  log('goto');
  await page.goto(`${BASE}/period-review`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(4000);
  log('click 月复盘');
  await page.evaluate(() => { const b = document.querySelector('button[data-pr-mode="month"]'); if (b) b.click(); });
  await sleep(4500);

  log('switch period ->', period);
  await page.evaluate((target) => {
    const select = [...document.querySelectorAll('select')]
      .find((el) => [...el.options].some((o) => o.value === target));
    if (!select) return;
    select.value = target;
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }, period);
  await sleep(6000);

  const ok = await page.evaluate((needle) => {
    const section = document.querySelector('[data-section-key="market"]');
    if (!section) return false;
    section.querySelectorAll('details.pr-evidence').forEach((el) => { el.open = true; });
    const block = [...section.querySelectorAll('.pr-material')]
      .find((el) => ((el.querySelector('.pr-material__title') || {}).textContent || '').includes(needle));
    if (!block) return false;
    const top = block.getBoundingClientRect().top + window.scrollY;
    window.scrollTo(0, Math.max(0, top - 110));
    return true;
  }, anchor);
  await sleep(1500);
  if (!ok) throw new Error(`未找到市场段内含「${anchor}」的块`);

  const outPath = path.resolve(out);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  log('screenshot →', outPath);
  await page.screenshot({ path: outPath });
  await browser.disconnect();
  log('done');
})().catch((e) => { console.error('FATAL', e.message); process.exit(1); });

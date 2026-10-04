/**
 * 浏览器级验证：月复盘「市场监控-行业」分级（8大归类 / 趋势节点 / 蓝海词根 /
 * 商品趋势 / 竞店爆品）+ 竞品商品对标修复。
 *
 * 用法（dev server 在 5000、Chrome 开 CDP 9223）：
 *   node scripts/verify-period-review-market-grading.cjs
 *   node scripts/verify-period-review-market-grading.cjs --json out.json
 *
 * 验证点：
 *   ① 六个新块都在市场段内渲染：关键词洞察·8大归类 / 趋势节点分析 /
 *      蓝海市场·低供给词根 / 商品排行·趋势市场 / 竞店爆品排名变化 / 市场分级口径边界
 *   ② 8大归类表有行，且含「类目/人群/属性/品牌/风格/功能/场景/价格」中至少 5 类
 *   ③ 蓝海词根表有行，且分级标签出现「待核」（覆盖 0 不得再判高潜蓝海）
 *   ④ 趋势节点在 2026-09 有行（窗口 15 天够「近7天+基线」）
 *   ⑤ 竞店爆品排名变化表有行
 *   ⑥ 竞品商品对标有行（修掉 detail_url 不存在导致的静默为空）
 *   ⑦ 无控制台错误
 *
 * ⚠️ 踩坑见 scripts/verify-period-review-promotion.cjs 头部（click 挂起 / 别接管道 /
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
  const section = document.querySelector('[data-section-key="market"]');
  const out = { present: Boolean(section) };
  if (!section) return out;
  const blocks = [...section.querySelectorAll('.pr-material')];
  const byTitle = {};
  blocks.forEach((block) => {
    const title = (block.querySelector('.pr-material__title') || {}).textContent;
    if (!title) return;
    const key = title.trim().split('\n')[0].slice(0, 40);
    const table = block.querySelector('table.pr-table');
    byTitle[key] = {
      rows: table ? table.querySelectorAll('tbody tr').length : 0,
      hint: (block.querySelector('.pr-material__hint') || {}).textContent || null,
      empty: (block.querySelector('.pr-material__empty') || {}).textContent || null,
      tags: [...block.querySelectorAll('.pr-status-tag')].map((el) => el.textContent.trim()),
      labels: table ? [...table.querySelectorAll('tbody tr td:first-child')].map((el) => el.textContent.trim()).slice(0, 12) : [],
    };
  });
  out.byTitle = byTitle;
  return out;
}

(async () => {
  log('connect');
  const browser = await puppeteer.connect({ browserURL: CDP, defaultViewport: null });
  const pages = await browser.pages();
  const page = pages.find((p) => p.url().includes('/period-review')) || pages[0];
  page.setDefaultTimeout(20000);
  page.on('pageerror', (e) => errors.push('PAGEERROR ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE ' + m.text()); });

  await page.evaluate(() => { try { localStorage.setItem('dashboard.categoryMode', 'all'); } catch (e) {} });
  log('goto');
  await page.goto(`${BASE}/period-review`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(4000);

  log('click 月复盘 (DOM click)');
  await page.evaluate(() => {
    const b = document.querySelector('button[data-pr-mode="month"]');
    if (b) b.click();
  });
  await sleep(4500);

  log('switch period -> 2026-09');
  const switched = await page.evaluate(() => {
    const select = [...document.querySelectorAll('select')]
      .find((el) => [...el.options].some((o) => o.value === '2026-09'));
    if (!select) return false;
    select.value = '2026-09';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  });
  log('period select found:', switched);
  await sleep(6000);

  // 市场段可能有折叠容器，展开以保证断言能取到（DOM 级，避免 click 挂起）
  await page.evaluate(() => {
    const section = document.querySelector('[data-section-key="market"]');
    if (!section) return;
    section.querySelectorAll('details.pr-evidence').forEach((el) => { el.open = true; });
  });
  await sleep(1200);

  const report = { switched, market: await page.evaluate(grabScript) };
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

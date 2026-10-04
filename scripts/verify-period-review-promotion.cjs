/**
 * 浏览器级验证：复盘页「推广计划拆解（计划 → 商品归因）」+ 商品×渠道来源列。
 *
 * 用法（先确保 dev server 在 5000、Chrome 开了 CDP 9223）：
 *   node scripts/verify-period-review-promotion.cjs            # 输出 JSON 到 stdout
 *   node scripts/verify-period-review-promotion.cjs --json out.json
 *
 * 验证点：① 归因块 20 行 × 8 列，chips 为 精确/多商品；② 商品渠道子表出现「全站」组
 *         且「来源」列标 `计划精确归因`；③ 品类切 sock 后归因块仍非空；④ 无控制台错误。
 *
 * ⚠️ 本页四个坑（都踩过，别重蹈）：
 *   1. elementHandle.click() 会等元素「稳定」，本页有动画/重渲染 → **永久挂起**。
 *      一律用 page.evaluate 内 el.click()；<select> 同理（改 value + 派发 change）。
 *   2. 给可能挂起的 node 进程**接管道会吞输出**（被 SIGTERM 时 tail 拿不到已打印内容）
 *      → 调试时别用 `| tail`。
 *   3. 复盘页路由是 `/period-review`（app.py 的 `/<page>`），
 *      **不是** `/ui_demo/pages/period-review.html`（404）。
 *   4. 证据块在**折叠的 `<details class="pr-evidence">`** 内，且抽屉 `.pr-drawer__body`
 *      （默认 visibility:hidden）里有同一份副本 → `querySelectorAll('.pr-material__title')`
 *      会**重复命中**。要截图必须先 `details.open = true`，再 scrollTo + 截**视口**（不带 clip）。
 *   5. 品类模式前端**不读 URL**（存 localStorage + `[data-category-mode]` 下拉）；
 *      周期也不读 URL（深链会被覆盖为当前周期）→ 必须用 DOM 交互切换。
 */
const fs = require('fs');
const puppeteer = require('E:/www/tmallshangjia/node_modules/puppeteer-core');
const CDP = process.env.CDP_URL || 'http://127.0.0.1:9223';
const BASE = process.env.DASHBOARD_URL || 'http://127.0.0.1:5000';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.error('[step]', ...a);

const errors = [];

function grabScript() {
  const out = { sections: [], titles: [] };
  out.sections = [...document.querySelectorAll('.pr-section')].map((s) => {
    const t = s.querySelector('.pr-section__title');
    return t ? t.textContent.trim().slice(0, 24) : '(no-title)';
  });
  out.titles = [...document.querySelectorAll('.pr-material__title')].map((t) => t.textContent.trim());

  const attrTitle = [...document.querySelectorAll('.pr-material__title')]
    .find((t) => t.textContent.includes('计划 → 商品归因'));
  if (attrTitle) {
    const root = attrTitle.closest('.pr-material');
    const rows = [...root.querySelectorAll('tbody > tr')];
    const hint = root.querySelector('.pr-material__hint');
    out.attribution = {
      head: [...root.querySelectorAll('thead th')].map((th) => th.textContent.trim()),
      rowCount: rows.length,
      chips: [...root.querySelectorAll('td .pr-chip')].map((c) => c.textContent.trim()),
      rows: rows.slice(0, 4).map((tr) => [...tr.querySelectorAll('td')].map((td) => td.textContent.trim())),
      hint: hint ? hint.textContent.trim() : null,
    };
  } else {
    out.attribution = { found: false };
  }

  const piTitle = [...document.querySelectorAll('.pr-material__title')]
    .find((t) => t.textContent.includes('广告单品 TOP20'));
  if (piTitle) {
    const root = piTitle.closest('.pr-material');
    const subs = [...root.querySelectorAll('.pr-promo-item__channels table')];
    const hint = root.querySelector('.pr-material__hint');
    out.promoItems = {
      subTableCount: subs.length,
      samples: subs.slice(0, 3).map((t) => ({
        head: [...t.querySelectorAll('thead th')].map((th) => th.textContent.trim()),
        rows: [...t.querySelectorAll('tbody > tr')].map((tr) =>
          [...tr.querySelectorAll('td')].map((td) => td.textContent.trim())),
      })),
      hint: hint ? hint.textContent.trim() : null,
    };
  } else {
    out.promoItems = { found: false };
  }
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

  log('reset categoryMode=all');
  await page.evaluate(() => { try { localStorage.setItem('dashboard.categoryMode', 'all'); } catch (e) {} });

  log('goto');
  await page.goto(`${BASE}/period-review`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await sleep(4000);

  log('click 月复盘 (DOM click)');
  await page.evaluate(() => {
    const b = document.querySelector('button[data-pr-mode="month"]');
    if (b) b.click();
  });
  await sleep(4000);

  const report = {};
  report.mode = await page.evaluate(() => {
    const b = document.querySelector('button[data-pr-mode].is-active');
    return b ? b.textContent.trim() : null;
  });
  report.all = await page.evaluate(grabScript);

  log('switch category -> sock');
  const switched = await page.evaluate(() => {
    const sel = document.querySelector('[data-category-mode]');
    if (!sel) return null;
    const opts = [...sel.options].map((o) => o.value);
    sel.value = 'sock';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    return opts;
  });
  report.categoryOptions = switched;
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

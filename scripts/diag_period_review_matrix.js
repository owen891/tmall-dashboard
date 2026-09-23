/**
 * 诊断「指标矩阵 / 类目拆解」显示「加载失败或后端接口未就绪」的原因。
 *
 * 会记录：所有 /api/period-reviews/* 请求的状态码与响应、页面控制台报错、
 * 两个面板的最终文案，以及前端实际使用的周期键。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/diag_period_review_matrix.js [port] [category_mode] [start] [end]
 *   start/end 省略时不设置时间范围，用页面默认值。
 */
const path = require('path');

const PORT = process.argv[2] || '5000';
const CATEGORY_MODE = process.argv[3] || 'sock';
const RANGE_START = process.argv[4] || '';
const RANGE_END = process.argv[5] || '';
const BASE = `http://127.0.0.1:${PORT}`;
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1200 } });

  const apiCalls = [];
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push('PAGEERROR ' + err.message));
  page.on('requestfailed', (req) => {
    apiCalls.push({ url: req.url(), status: 'FAILED', error: req.failure()?.errorText });
  });
  page.on('response', async (res) => {
    const url = res.url();
    if (!url.includes('/api/period-reviews')) return;
    let body = '';
    try { body = (await res.text()).slice(0, 300); } catch (_) { body = '<unreadable>'; }
    apiCalls.push({ url: url.replace(BASE, ''), status: res.status(), body });
  });

  await page.addInitScript((mode) => {
    try { window.localStorage.setItem('dashboard.categoryMode', mode); } catch (_) {}
  }, CATEGORY_MODE);

  await page.goto(`${BASE}/pages/period-review.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  if (RANGE_START && RANGE_END) {
    await page.evaluate(({ start, end }) => {
      window.TmallDateRange?.setRange?.(start, end, 'custom');
    }, { start: RANGE_START, end: RANGE_END });
    await page.waitForTimeout(7000);
  } else {
    await page.waitForTimeout(4000);
  }

  console.log('=== /api/period-reviews 请求 ===');
  apiCalls.forEach((call) => {
    console.log(`${String(call.status).padEnd(7)} ${call.url}`);
    if (call.status !== 200) console.log(`         body: ${call.body || call.error}`);
  });

  console.log('\n=== 控制台错误 ===');
  console.log(consoleErrors.length ? consoleErrors.join('\n') : '(无)');

  const panels = await page.evaluate(() => {
    const read = (sel) => {
      const node = document.querySelector(sel);
      return node ? (node.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 200) : '(missing)';
    };
    return {
      periodLabel: read('[data-pr-period-label]'),
      banner: read('[data-pr-state]'),
      matrix: read('[data-pr-matrix]'),
      category: read('[data-pr-category-breakdown]'),
      scriptVersion: [...document.querySelectorAll('script[src]')].map((s) => s.getAttribute('src')).find((s) => s.includes('period-review-live')),
    };
  });
  console.log('\n=== 页面状态 ===');
  console.log(JSON.stringify(panels, null, 2));

  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

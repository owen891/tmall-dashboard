/**
 * 验证首页（经营总览 /）在真实浏览器里能正常出数（只读，不落库）。
 *
 * 背景：首页所有 KPI 卡片曾长期停在 `--` + 「等待加载…」，根因不是前端，
 * 而是 `/api/overview` 单次耗时 44~116 秒——`MetricsRepo.overview_context()`
 * 里那段 `import_batches` 的 EXISTS 查询缺索引，260 个批次 × 十几万行全表扫描。
 * 前端 `overview-live.js::load()` 用 `Promise.all` 聚合 8 个接口，
 * 最慢的那个不返回，后面 renderKpis / renderContext / renderHomeMatrix 全都不会执行。
 *
 * 断言：
 *   1. 首屏 KPI 卡片不再是 `--`，副标题不再是「等待加载…」
 *   2. 数据上下文 / 日度矩阵状态不再是「加载中…」
 *   3. 日度矩阵 tbody 有真实数据行
 *   4. 没有 JS 异常、没有 4xx/5xx
 *   5. 从导航到 KPI 就绪的墙钟时间
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules \
 *     node scripts/verify_overview_home.js [port] [start] [end]
 */
const path = require('path');

const PORT = process.argv[2] || '5000';
const START = process.argv[3] || '2026-08-24';
const END = process.argv[4] || '2026-09-22';
const BASE = `http://127.0.0.1:${PORT}`;
const OUT_DIR = path.join(__dirname, '..', 'logs');
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const KPI_KEYS = [
  'net_sales', 'payment_amount', 'payment_conversion_rate', 'visitors',
  'ad_spend', 'ad_roi', 'refund_rate', 'expense_ratio',
];

const failures = [];

function check(label, ok, detail) {
  console.log(`${ok ? 'PASS' : 'FAIL'} ${label}${detail ? `: ${detail}` : ''}`);
  if (!ok) failures.push(label);
}

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1200 } });

  const pageErrors = [];
  const httpErrors = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));
  page.on('response', (response) => {
    if (response.status() >= 400 && response.url().startsWith(BASE)) {
      httpErrors.push(`HTTP ${response.status()} ${response.url()}`);
    }
  });

  await page.addInitScript(() => {
    try { window.localStorage.setItem('dashboard.categoryMode', 'sock'); } catch (_) {}
  });

  const url = `${BASE}/?startDate=${START}&endDate=${END}&preset=30d&compare=none`;
  const started = Date.now();
  await page.goto(url, { waitUntil: 'domcontentloaded' });

  // KPI 就绪 = 主卡片不再是 `--`。给足 120s，旧代码下这里必然超时。
  // 注意用 textContent 而不是 innerText：ad_spend / ad_roi / refund_rate 三张卡
  // 在折叠的 <details> 里，innerText 对未渲染元素返回空串，会误判成「没出数」。
  let ready = true;
  try {
    await page.waitForFunction(
      (keys) => keys.every((key) => {
        const el = document.querySelector(`[data-overview-kpi="${key}"]`);
        const text = (el?.textContent || '').trim();
        return text && text !== '--';
      }),
      KPI_KEYS,
      { timeout: 120000 },
    );
  } catch (_) {
    ready = false;
  }
  const elapsed = ((Date.now() - started) / 1000).toFixed(2);
  check('KPI 卡片全部出数（不再是 --）', ready, ready ? `${elapsed}s 内就绪` : `120s 超时仍未就绪`);
  console.log(`INFO 导航→KPI 就绪墙钟: ${elapsed}s`);

  // KPI 就绪 ≠ 整页就绪：日度矩阵是 `/api/overview` 之后**串行**发的第二个请求，
  // 状态文案会先停在「正在读取日度明细」。这里等它落定，否则断言会读到占位行。
  let matrixSettled = true;
  try {
    await page.waitForFunction(() => {
      const text = (document.querySelector('[data-overview-matrix-status]')?.textContent || '').trim();
      return text && !text.includes('加载中') && !text.includes('正在读取');
    }, null, { timeout: 60000 });
  } catch (_) {
    matrixSettled = false;
  }
  const settledAt = ((Date.now() - started) / 1000).toFixed(2);
  check('日度矩阵读取完成', matrixSettled, matrixSettled ? `整页就绪 ${settledAt}s` : '60s 内未落定');
  console.log(`INFO 导航→整页就绪墙钟: ${settledAt}s`);

  const snapshot = await page.evaluate((keys) => {
    // textContent 而非 innerText：折叠 <details> 里的卡片 innerText 为空串。
    const text = (sel) => (document.querySelector(sel)?.textContent || '').trim();
    const kpis = {};
    keys.forEach((key) => { kpis[key] = text(`[data-overview-kpi="${key}"]`); });
    const metas = {};
    keys.forEach((key) => { metas[key] = text(`[data-overview-kpi-meta="${key}"]`); });
    return {
      kpis,
      metas,
      context: text('[data-overview-context]'),
      quality: text('[data-overview-quality]'),
      cutoff: text('[data-overview-cutoff]'),
      coverage: text('[data-overview-coverage]'),
      matrixStatus: text('[data-overview-matrix-status]'),
      matrixRows: document.querySelectorAll('[data-overview-home-matrix] tr').length,
      matrixFirstRow: text('[data-overview-home-matrix] tr'),
      targetPanel: text('[data-overview-home-targets]').slice(0, 120),
      summaryNetSales: text('[data-overview-summary="net_sales"]'),
      summaryTarget: text('[data-overview-summary="target"]'),
      summaryActions: text('[data-overview-summary="actions"]'),
    };
  }, KPI_KEYS);

  console.log('KPIS ' + JSON.stringify(snapshot.kpis));
  console.log('KPIS-META ' + JSON.stringify(snapshot.metas));
  console.log('CONTEXT ' + JSON.stringify(snapshot.context));
  console.log('CUTOFF ' + JSON.stringify(snapshot.cutoff) + '  COVERAGE ' + JSON.stringify(snapshot.coverage));
  console.log('MATRIX-STATUS ' + JSON.stringify(snapshot.matrixStatus) + '  ROWS=' + snapshot.matrixRows);
  console.log('SUMMARY ' + JSON.stringify({
    net_sales: snapshot.summaryNetSales, target: snapshot.summaryTarget, actions: snapshot.summaryActions,
  }));
  console.log('TARGET-PANEL ' + JSON.stringify(snapshot.targetPanel));

  check('数据上下文不再是「加载中」', !snapshot.context.includes('加载中'), snapshot.context);
  check('日度矩阵状态不再是「加载中」', !snapshot.matrixStatus.includes('加载中'), snapshot.matrixStatus);
  // 分页大小 7（overview.html 的 data-page-size），30 天区间首屏应满页 7 行。
  check('日度矩阵有数据行', snapshot.matrixRows >= 5, `${snapshot.matrixRows} 行`);
  check('KPI 副标题不再是「等待加载…」',
    Object.values(snapshot.metas).every((v) => !v.includes('等待加载')),
    JSON.stringify(snapshot.metas));
  check('无 JS 异常', pageErrors.length === 0, pageErrors.join(' | '));
  check('无 4xx/5xx', httpErrors.length === 0, httpErrors.join(' | '));

  await page.screenshot({ path: path.join(OUT_DIR, 'overview_home_fixed.png'), fullPage: true });
  console.log('SHOT ' + path.join(OUT_DIR, 'overview_home_fixed.png'));

  await browser.close();
  if (failures.length) {
    console.log('FAILED ' + failures.length + ' 项: ' + failures.join(' / '));
    process.exit(1);
  }
  console.log('ALL CHECKS PASSED');
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

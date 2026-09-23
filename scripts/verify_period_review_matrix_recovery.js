/**
 * 验证「指标矩阵 / 类目拆解」的加载失败自愈能力。
 *
 * 三个阶段：
 *   1. 正常加载 —— 两个面板都应渲染出表格
 *   2. 拦截接口返回 500 —— 面板应显示具体失败原因 + 「重新加载」按钮
 *   3. 放开拦截后点「重新加载」 —— 面板应恢复成表格（无需整页刷新）
 *
 * 另外验证「切到页签自动补拉」：接口恢复后直接点页签也能恢复。
 *
 * 运行（工作目录 E:\www\tmall-dashboard）：
 *   NODE_PATH=E:\www\tmall-dashboard\desktop\node_modules node scripts/verify_period_review_matrix_recovery.js [port] [category_mode]
 */
const path = require('path');

const PORT = process.argv[2] || '5000';
const CATEGORY_MODE = process.argv[3] || 'sock';
const BASE = `http://127.0.0.1:${PORT}`;
const OUT_DIR = path.join(__dirname, '..', 'logs');
const CHROME = process.env.TMALL_CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const MATRIX_PANEL = '[data-pr-matrix]';
const CATEGORY_PANEL = '[data-pr-category-breakdown]';

function readPanels(page) {
  return page.evaluate(({ matrixSel, categorySel }) => {
    const read = (sel) => {
      const node = document.querySelector(sel);
      if (!node) return { missing: sel };
      return {
        hasTable: !!node.querySelector('table'),
        headerCount: node.querySelectorAll('thead th').length,
        rowCount: node.querySelectorAll('tbody tr').length,
        text: (node.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160),
        hasRetry: !!node.querySelector('.pr-load-failure button'),
      };
    };
    return { matrix: read(matrixSel), category: read(categorySel) };
  }, { matrixSel: MATRIX_PANEL, categorySel: CATEGORY_PANEL });
}

async function openTab(page, key) {
  await page.evaluate((k) => document.querySelector(`[data-pr-workbench-tab="${k}"]`)?.click(), key);
  await page.waitForTimeout(700);
}

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1200 } });
  page.on('pageerror', (err) => console.log('PAGE-ERROR ' + err.message));

  await page.addInitScript((mode) => {
    try { window.localStorage.setItem('dashboard.categoryMode', mode); } catch (_) {}
  }, CATEGORY_MODE);

  // ---- 阶段 1：正常加载 ----
  await page.goto(`${BASE}/pages/period-review.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(9000);
  await openTab(page, 'matrix');
  console.log('STAGE-1-NORMAL ' + JSON.stringify(await readPanels(page), null, 2));
  await page.screenshot({ path: path.join(OUT_DIR, 'pr_recover_1_normal.png'), fullPage: true });

  // ---- 阶段 2：把两个接口打成 500 ----
  const breakRoutes = async (route) => {
    const url = route.request().url();
    if (url.includes('/matrix') || url.includes('/category-breakdown')) {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ ok: false, code: 'INTERNAL_ERROR', message: '模拟后端故障' }),
      });
    }
    return route.continue();
  };
  await page.route('**/api/period-reviews/**', breakRoutes);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(9000);
  await openTab(page, 'matrix');
  console.log('STAGE-2-BROKEN ' + JSON.stringify(await readPanels(page), null, 2));
  await page.screenshot({ path: path.join(OUT_DIR, 'pr_recover_2_failed.png'), fullPage: true });

  // ---- 阶段 3a：放开拦截，点「重新加载」 ----
  await page.unroute('**/api/period-reviews/**', breakRoutes);
  await page.evaluate(() => {
    document.querySelector('[data-pr-matrix] .pr-load-failure button')?.click();
  });
  await page.waitForTimeout(4000);
  console.log('STAGE-3A-RETRY ' + JSON.stringify(await readPanels(page), null, 2));

  // ---- 阶段 3b：再打断一次，改验证「切页签自动补拉」 ----
  await page.route('**/api/period-reviews/**', breakRoutes);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(9000);
  await page.unroute('**/api/period-reviews/**', breakRoutes);
  await openTab(page, 'category');   // 接口已恢复，点页签应自动补拉
  await page.waitForTimeout(4000);
  console.log('STAGE-3B-TAB-RELOAD ' + JSON.stringify(await readPanels(page), null, 2));
  await page.screenshot({ path: path.join(OUT_DIR, 'pr_recover_3_recovered.png'), fullPage: true });

  console.log('SHOT ' + path.join(OUT_DIR, 'pr_recover_1_normal.png'));
  console.log('SHOT ' + path.join(OUT_DIR, 'pr_recover_2_failed.png'));
  console.log('SHOT ' + path.join(OUT_DIR, 'pr_recover_3_recovered.png'));
  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });

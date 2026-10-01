/**
 * 2-3 截图留档：products 页头 + 表格工具栏（列表视图 / 周期视图）
 * 用法：NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/shot_products_header.cjs
 * 输出：.tmp/ui-audit/products-*.png
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const OUT = path.resolve('.tmp/ui-audit');
const BASE = process.env.BASE || 'http://127.0.0.1:5000';

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.PW_CHROMIUM || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  for (const [tag, width, height] of [['desktop', 1440, 900], ['mobile', 390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height } });
    const page = await context.newPage();
    await page.goto(`${BASE}/products`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(OUT, `products-${tag}-list.png`) });
    await page.click('[data-products-mode="timeline"]');
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(OUT, `products-${tag}-timeline.png`) });
    await context.close();
  }
  await browser.close();
  console.log('screenshots ->', OUT);
})();

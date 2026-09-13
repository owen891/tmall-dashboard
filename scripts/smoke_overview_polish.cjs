const { chromium } = require(require.resolve('playwright', { paths: [require('path').join(__dirname, '..', 'desktop')] }));

const base = process.env.TMALL_SMOKE_BASE || 'http://127.0.0.1:8771';
const shotDir = process.env.TMALL_SMOKE_SHOTS || 'E:/tm数据表格/tmall-dashboard';
const writeAction = process.env.TMALL_SMOKE_WRITE_ACTION === '1';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const [label, viewport] of [['desktop', { width: 1440, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      let smokeActionId = null;
      page.on('pageerror', (error) => errors.push(error.message));
      page.on('response', (response) => {
        if (response.status() >= 400 && response.url().startsWith(base)) errors.push(`HTTP ${response.status()} ${response.url()}`);
      });
      try {
        await page.goto(`${base}/?startDate=2026-03-21&endDate=2026-04-19&preset=30d&compare=none`, { waitUntil: 'networkidle' });
        await page.waitForFunction(() => {
          const context = document.querySelector('[data-overview-context]')?.textContent || '';
          const matrix = document.querySelector('[data-overview-matrix-status]')?.textContent || '';
          return !context.includes('加载中') && !matrix.includes('加载中');
        });
        const open = page.locator('[data-overview-action-open]');
        const actionEnabled = await open.isEnabled();
        const report = { actionEnabled, actionId: null, writeAction };
        if (actionEnabled) {
          await open.click();
          const dialog = page.locator('[data-overview-action-dialog]');
          await dialog.waitFor({ state: 'visible' });
          const focused = await page.evaluate(() => document.activeElement?.id === 'overview-action-product');
          const box = await dialog.boundingBox();
          await page.screenshot({ path: `${shotDir}/overview-polish-${label}.png`, fullPage: true });
          if (label === 'desktop' && writeAction) {
            const productId = await page.evaluate(async () => {
              const response = await fetch('/api/products?dim=monthly&limit=1&status=active');
              const payload = await response.json();
              return payload?.data?.rows?.[0]?.product_id || '';
            });
            const smokeAction = `smoke-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            if (!productId) errors.push('no active product available for action smoke');
            await page.locator('#overview-action-product').fill(productId || 'smoke-product');
            await page.locator('#overview-action-type').fill(smokeAction);
            await page.locator('#overview-action-detail').fill(`浏览器 smoke ${smokeAction}`);
            await page.locator('#overview-action-purpose').fill('验证正式运营动作创建链路');
            await page.locator('#overview-action-date').fill('2026-04-15');
            await page.locator('#overview-action-window').fill('7');
            await page.locator('[data-overview-action-submit]').click();
            await dialog.waitFor({ state: 'hidden' });
            await page.waitForTimeout(250);
            const actionResponse = await page.request.get(`${base}/api/actions?limit=200`);
            const actionPayload = await actionResponse.json();
            const created = (actionPayload?.data || []).find((item) => item.action_type === smokeAction);
            if (!created) errors.push('saved action not returned by API');
            else { smokeActionId = created.id; report.actionId = created.id; }
          } else {
            await page.keyboard.press('Escape');
          }
          await page.waitForTimeout(50);
          report.focused = focused;
          report.focusRestored = await page.evaluate(() => document.activeElement?.matches('[data-overview-action-open]'));
          report.dialogBox = box;
        }
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2);
        results.push({ label, report, overflow, errors });
      } finally {
        if (smokeActionId) {
          const current = await page.request.get(`${base}/api/actions?limit=200`);
          const payload = await current.json();
          const action = (payload?.data || []).find((item) => item.id === smokeActionId);
          if (action) {
            await page.request.post(`${base}/api/actions/${encodeURIComponent(smokeActionId)}/transition`, {
              data: { status: 'cancelled', version: action.version, capability_key: 'product-detail.review_action', reason: '浏览器 smoke 清理' },
            });
          }
        }
        await page.close();
      }
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(results, null, 2));
  if (results.some((row) => row.errors.length || row.overflow || (row.report.actionEnabled && (!row.report.focused || !row.report.focusRestored)))) process.exitCode = 1;
})();

const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

const base = process.env.TMALL_SMOKE_BASE || 'http://127.0.0.1:8771';
const shotDir = process.env.TMALL_SMOKE_SHOTS || 'E:/tm数据表格/tmall-dashboard';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  for (const [label, viewport] of [['desktop', { width: 1440, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => { if (response.status() >= 400 && response.url().startsWith(base)) errors.push(`HTTP ${response.status()} ${response.url()}`); });
    await page.goto(`${base}/?startDate=2026-03-21&endDate=2026-04-19&preset=30d&compare=none`, { waitUntil: 'networkidle' });
    await page.locator('[data-overview-report-kpis] .overview-report-kpi').first().waitFor();
    const report = {
      kpis: await page.locator('[data-overview-report-kpis] .overview-report-kpi').count(),
      products: await page.locator('[data-overview-report-products] .overview-report-product').count(),
      risks: await page.locator('[data-overview-report-risks] .overview-report-risk').count(),
      period: await page.locator('[data-overview-report-period]').innerText(),
    };
    const open = page.locator('[data-overview-event-open]');
    await open.click();
    const dialog = page.locator('[data-overview-event-dialog]');
    await dialog.waitFor({ state: 'visible' });
    const focused = await page.evaluate(() => document.activeElement?.id === 'overview-event-title-input');
    const swatches = await page.locator('.overview-event-colors__list input').count();
    const box = await dialog.boundingBox();
    await page.screenshot({ path: `${shotDir}/overview-polish-${label}.png`, fullPage: true });
    if (label === 'desktop') {
      await page.locator('#overview-event-title-input').fill('overview polish smoke');
      await page.locator('#overview-event-desc').fill('temporary browser verification event');
      await page.locator('.overview-event-colors__list label').filter({ hasText: '活动' }).click();
      await page.locator('[data-overview-event-submit]').click();
      await dialog.waitFor({ state: 'hidden' });
      await page.locator('[data-overview-events] .timeline__item').filter({ hasText: 'overview polish smoke' }).waitFor();
      const eventResponse = await page.request.get(`${base}/api/chart_events?chart_type=sales`);
      const eventPayload = await eventResponse.json();
      const created = (Array.isArray(eventPayload) ? eventPayload : eventPayload.events || []).find((item) => item.title === 'overview polish smoke');
      if (!created) errors.push('saved event not returned by API');
      else await page.request.delete(`${base}/api/chart_events/${created.id}`);
    } else {
      await page.keyboard.press('Escape');
    }
    await page.waitForTimeout(50);
    const focusRestored = await page.evaluate(() => document.activeElement?.matches('[data-overview-event-open]'));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2);
    results.push({ label, report, focused, focusRestored, swatches, dialogBox: box, overflow, errors });
    await page.close();
  }
  console.log(JSON.stringify(results, null, 2));
  await browser.close();
  if (results.some((row) => row.errors.length || row.overflow || row.report.kpis !== 8 || row.report.products !== 5 || row.report.risks < 1 || !row.focused || !row.focusRestored || row.swatches !== 5)) process.exitCode = 1;
})();

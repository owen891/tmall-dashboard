const { chromium } = require(require.resolve('playwright', { paths: [require('path').join(__dirname, '..', 'desktop')] }));
const path = require('path');

const base = process.env.TMALL_SMOKE_BASE || 'http://127.0.0.1:8770';
const scanRoot = process.env.TMALL_AUDIT_SCAN_ROOT || path.resolve(__dirname, '..', 'data', 'import-inbox');
const pages = [
  ['overview', '/'],
  ['products', '/products'],
  ['promotion', '/promotion'],
  ['lifecycle', '/lifecycle'],
  ['goals', '/goals'],
  ['reviews', '/reviews'],
  ['data-center', '/data-center'],
  ['settings', '/settings'],
];
const selectedPages = process.env.AUDIT_PAGE ? pages.filter(([id]) => id === process.env.AUDIT_PAGE) : pages;

const wait = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitReady(page, id, viewport) {
  await page.waitForLoadState('domcontentloaded');
  await wait(700);
  const selectors = {
    overview: '[data-overview-kpi]',
    promotion: '[data-promotion-body] tr',
    lifecycle: '[data-lifecycle-grid] > *',
    goals: '[data-goals-version]',
    reviews: '[data-reviews-list]',
    'data-center': '[data-import-file]:not(.sr-only)',
    settings: '[data-settings-form]',
  };
  if (id !== 'products') {
    await page.locator(selectors[id]).first().waitFor({ state: 'visible' });
    return;
  }
  const ready = viewport.width <= 520
    ? '[data-products-mobile-summary] .products-mobile-summary__item'
    : '[data-products-body] tr';
  await page.locator(ready).first().waitFor({ state: 'visible' });
}

async function clickIfVisible(page, selector, name, failures) {
  const target = page.locator(selector).first();
  if (!(await target.count()) || !(await target.isVisible())) return false;
  if (await target.isDisabled()) return false;
  try {
    await target.click();
    await wait();
    return true;
  } catch (error) {
    failures.push(`${name}: ${error.message}`);
    return false;
  }
}

async function selectIfReady(page, selector, value, name, failures) {
  const target = page.locator(selector).first();
  if (!(await target.count()) || !(await target.isVisible()) || await target.isDisabled()) return false;
  try {
    const options = await target.locator('option').evaluateAll((items) => items.map((option) => ({
      value: option.value,
      disabled: option.disabled,
    })));
    const option = options.find((item) => item.value === value);
    // A disabled option is an intentional capability signal (for example, a
    // promotion grain with no imported facts), so skip it without failing the
    // interaction audit.  Enabled options must still be exercised normally.
    if (!option || option.disabled) return false;
    await target.selectOption(value);
    await wait();
    return true;
  } catch (error) {
    failures.push(`${name}: ${error.message}`);
    return false;
  }
}

async function runPage(browser, id, path, viewport) {
  const page = await browser.newPage({ viewport });
  page.setDefaultTimeout(5000);
  const failures = [];
  const browserErrors = [];
  page.on('pageerror', (error) => browserErrors.push(`pageerror: ${error.stack || error.message}`));
  page.on('requestfailed', (request) => browserErrors.push(`requestfailed: ${request.url()} ${request.failure()?.errorText || ''}`));
  page.on('response', (response) => {
    if (response.status() >= 400 && response.url().startsWith(base)) browserErrors.push(`HTTP ${response.status()}: ${response.url()}`);
  });

  let response;
  try {
    response = await page.goto(`${base}${path}`, { waitUntil: 'domcontentloaded', timeout: 10000 });
    await waitReady(page, id, viewport);

    await selectIfReady(page, '[data-date-preset]', '7d', 'date preset 7d', failures);
    await clickIfVisible(page, '[data-demo-refresh]', 'global refresh', failures);

    if (id === 'overview') {
      await clickIfVisible(page, '[data-overview-trend-trigger]', 'trend menu open', failures);
      await clickIfVisible(page, '[data-overview-trend-menu] input', 'trend metric toggle', failures);
      await page.keyboard.press('Escape');
      await clickIfVisible(page, '[data-overview-action-open]', 'action dialog open', failures);
      await page.keyboard.press('Escape');
      await clickIfVisible(page, '[data-overview-kpi-select]', 'KPI card interaction', failures);
    }

    if (id === 'products') {
      await clickIfVisible(page, '[data-products-reset]', 'product reset', failures);
      for (const button of await page.locator('[data-products-view]').all()) {
        if (await button.isVisible() && !(await button.isDisabled())) await button.click();
        await wait();
      }
      await selectIfReady(page, '[data-products-sort]', 'net_sales', 'product sort', failures);
      await selectIfReady(page, '[data-products-page-size]', '10', 'product page size', failures);
      await clickIfVisible(page, '[data-products-columns-open]', 'product columns open', failures);
      await clickIfVisible(page, '[data-products-columns-clear-all]', 'product columns clear', failures);
      await clickIfVisible(page, '[data-products-columns-reset]', 'product columns reset', failures);
      await clickIfVisible(page, '[data-products-columns-close]', 'product columns close', failures);
      if (viewport.width > 520) await clickIfVisible(page, '[data-products-body] tr button[aria-label^="查看"]', 'product detail open', failures);
      else await clickIfVisible(page, '[data-products-mobile-summary] .products-mobile-summary__item button', 'mobile product detail open', failures);
      await clickIfVisible(page, '[data-shared-product-close]', 'product detail close', failures);
    }

    if (id === 'promotion') {
      await clickIfVisible(page, '[data-promotion-info]', 'promotion definition open', failures);
      await clickIfVisible(page, '[data-promotion-dialog-close]', 'promotion definition close', failures);
      await selectIfReady(page, '[data-promotion-drill-level]', 'product', 'promotion drill level', failures);
      await clickIfVisible(page, '[data-promotion-drill-load]', 'promotion drill load', failures);
      await clickIfVisible(page, '[data-promotion-manage-fields]', 'promotion fields open', failures);
      await clickIfVisible(page, '[data-promotion-template-apply]', 'promotion template apply', failures);
      await clickIfVisible(page, '[data-promotion-fields-close]', 'promotion fields close', failures);
      await clickIfVisible(page, '[data-alert-rules-open]', 'promotion alert rules open', failures);
      await clickIfVisible(page, '[data-alert-rule-close]', 'promotion alert rules close', failures);
    }

    if (id === 'lifecycle') {
      await clickIfVisible(page, '[data-lifecycle-card]', 'lifecycle detail open', failures);
      for (const tab of await page.locator('[data-lifecycle-detail-tab]').all()) {
        if (await tab.isVisible()) await tab.click();
        await wait();
      }
      await clickIfVisible(page, '[data-efficiency-mode="roi"]', 'lifecycle efficiency mode', failures);
      await clickIfVisible(page, '[data-lifecycle-columns-open]', 'lifecycle columns open', failures);
      await clickIfVisible(page, '[data-lifecycle-columns-clear-all]', 'lifecycle columns clear', failures);
      await clickIfVisible(page, '[data-lifecycle-columns-reset]', 'lifecycle columns reset', failures);
      await clickIfVisible(page, '[data-lifecycle-columns-close]', 'lifecycle columns close', failures);
      await clickIfVisible(page, '[data-lifecycle-back]', 'lifecycle detail close', failures);
    }

    if (id === 'goals') {
      await clickIfVisible(page, '[data-goals-suggest]', 'goal suggestion', failures);
      for (const option of ['year', 'quarter', 'month', 'week', 'date']) await selectIfReady(page, '[data-goals-level-filter]', option, `goal level ${option}`, failures);
    }

    if (id === 'reviews') await clickIfVisible(page, '[data-reviews-refresh]', 'reviews refresh', failures);

    if (id === 'data-center') {
      await clickIfVisible(page, '[data-open-toolbox]', 'toolbox open', failures);
      await clickIfVisible(page, '[data-tool="scan"]', 'scan tab', failures);
      await clickIfVisible(page, '[data-tool="import"]', 'import tab', failures);
      await page.keyboard.press('Escape');
      await clickIfVisible(page, '[data-import-history-refresh]', 'import history refresh', failures);
      await clickIfVisible(page, '[data-governance-disclosure] summary', 'governance disclosure', failures);
    }

    if (id === 'settings') {
      for (const tab of await page.locator('[data-settings-tab]').all()) {
        if (await tab.isVisible()) await tab.click();
        await wait();
      }
      await clickIfVisible(page, '[data-alert-rules-open]', 'settings alert rules open', failures);
      await clickIfVisible(page, '[data-alert-rule-close]', 'settings alert rules close', failures);
      await clickIfVisible(page, '[data-desktop-check-update]', 'desktop update check', failures);
      if (viewport.width > 520) {
        const scanCreate = page.locator('[data-scan-create]');
        if (await scanCreate.count() && await scanCreate.isVisible() && !(await scanCreate.isDisabled())) {
          const taskName = `browser-audit-${Date.now()}`;
          try {
            await scanCreate.click();
            const scanDialog = page.locator('[data-scan-dialog]');
            await scanDialog.waitFor({ state: 'visible' });
            await scanDialog.locator('input[name="task_name"]').fill(taskName);
            await scanDialog.locator('input[name="folder_path"]').fill(scanRoot);
            await scanDialog.locator('input[name="file_pattern"]').fill('*.xlsx;*.xls;*.csv;*.zip');
            await scanDialog.locator('select[name="source_type"]').selectOption('auto');
            await scanDialog.locator('input[name="cron_expr"]').fill('* * * * *');
            await scanDialog.locator('button[type="submit"]').click();
            const createdRow = page.locator('[data-scan-jobs] tr').filter({ hasText: taskName });
            await createdRow.waitFor({ state: 'visible' });
            await createdRow.locator('button[aria-label="立即扫描"]').click();
            await page.locator('[data-scan-status]').waitFor({ state: 'visible' });
            await createdRow.locator('button[aria-label="立即扫描"]').click();
            await page.locator('[data-scan-status]').waitFor({ state: 'visible' });
            await createdRow.locator('button[aria-label="查看记录"]').click();
            const detailDialog = page.locator('[data-scan-detail-dialog]');
            await detailDialog.waitFor({ state: 'visible' });
            if (process.env.TMALL_AUDIT_RETRY === '1') {
              const retryButton = detailDialog.locator('button[aria-label="重新排队"]');
              if (await retryButton.count() && await retryButton.isVisible() && !(await retryButton.isDisabled())) {
                await retryButton.click();
                await detailDialog.locator('[data-scan-files]').waitFor({ state: 'visible' });
              }
            }
            await detailDialog.locator('[data-scan-detail-close][aria-label="关闭"]').click();
            await detailDialog.waitFor({ state: 'hidden' });
            await createdRow.locator('button[aria-label="停用任务"]').click();
            await page.locator('[data-scan-jobs] tr').filter({ hasText: taskName }).waitFor({ state: 'visible' });
          } catch (error) {
            failures.push(`settings scan flow: ${error.message}`);
          }
        }
      }
    }
  } catch (error) {
    failures.push(`page flow: ${error.message}`);
  }

  const state = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    openDialogs: [...document.querySelectorAll('dialog[open]')].map((dialog) => dialog.dataset.modalKind || dialog.className),
    bodyText: document.body.innerText.length,
  }));
  await page.close();
  return { id, viewport: `${viewport.width}x${viewport.height}`, status: response?.status(), failures, browserErrors, state };
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  for (const viewport of [{ width: 1366, height: 768 }, { width: 390, height: 844 }]) {
    for (const [id, path] of selectedPages) results.push(await runPage(browser, id, path, viewport));
  }
  await browser.close();
  console.log(JSON.stringify(results, null, 2));
  if (results.some((result) => result.failures.length || result.browserErrors.length || result.status !== 200 || result.state.scrollWidth > result.state.clientWidth + 2)) process.exitCode = 1;
})();

const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

const base = process.env.TMALL_SMOKE_BASE || 'http://127.0.0.1:8770';
// Product workbench route contract: /products/<product_id>; shared dialog compatibility selector: .product-detail-dialog.
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

async function waitReady(page, id, viewport) {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(500);
  if (id === 'overview') await page.locator('[data-overview-kpi]').first().waitFor({ state: 'visible' });
  if (id === 'products') {
    if (viewport.width <= 520) await page.locator('[data-products-mobile-summary] .products-mobile-summary__item').first().waitFor({ state: 'visible' });
    else await page.locator('[data-products-body] tr').first().waitFor({ state: 'visible' });
  }
  if (id === 'promotion') await page.locator('[data-promotion-body] tr').first().waitFor({ state: 'visible' });
  if (id === 'lifecycle') await page.locator('[data-lifecycle-grid] > *').first().waitFor({ state: 'visible' });
  if (id === 'goals') await page.locator('[data-goals-version]').waitFor({ state: 'visible' });
  if (id === 'reviews') await page.locator('[data-reviews-list]').waitFor({ state: 'visible' });
  if (id === 'data-center') await page.locator('[data-import-file]:not(.sr-only)').first().waitFor({ state: 'visible' });
  if (id === 'settings') await page.locator('[data-settings-form]').waitFor({ state: 'visible' });
}

async function visibleCanvasesArePainted(page) {
  return page.evaluate(() => {
    const canvases = [...document.querySelectorAll('canvas')].filter((node) => (
      getComputedStyle(node).display !== 'none' && node.getClientRects().length
    ));
    return canvases.every((node) => {
      const context = node.getContext('2d');
      if (!context || !node.width || !node.height) return false;
      const data = context.getImageData(0, 0, node.width, node.height).data;
      for (let index = 3; index < data.length; index += 4) if (data[index] !== 0) return true;
      return false;
    });
  });
}

async function waitForCanvases(page) {
  await page.waitForFunction(() => {
    const canvases = [...document.querySelectorAll('canvas')].filter((node) => (
      getComputedStyle(node).display !== 'none' && node.getClientRects().length
    ));
    return canvases.every((node) => {
      const context = node.getContext('2d');
      if (!context || !node.width || !node.height) return false;
      const data = context.getImageData(0, 0, node.width, node.height).data;
      for (let index = 3; index < data.length; index += 4) if (data[index] !== 0) return true;
      return false;
    });
  }, { timeout: 5000 });
}

async function inspectDialogs(page, id, browser, viewport) {
  const checks = [];
  const inspectOpenDialog = async (selector, name) => {
    const dialog = page.locator(selector);
    await dialog.waitFor({ state: 'visible' });
    const metrics = await dialog.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        open: element.open,
        insideViewport: rect.left >= -1 && rect.right <= window.innerWidth + 1 && rect.top >= -1 && rect.bottom <= window.innerHeight + 1,
        noHorizontalOverflow: element.scrollWidth <= element.clientWidth + 2,
      };
    });
    checks.push({ name, ...metrics });
  };
  if (id === 'products') {
    if (viewport.width <= 520) {
      await page.locator('[data-products-mobile-summary] .products-mobile-summary__item').first().locator('button').click();
    } else {
      await page.locator('[data-products-body] tr').first().locator('button[aria-label^="查看商品详情"]').click();
    }
    await page.waitForTimeout(250);
    await inspectOpenDialog('.product-detail-dialog', 'products-detail');
    const workbenchLink = page.locator('[data-shared-product-workbench]');
    await workbenchLink.waitFor({ state: 'visible' });
    if (!(await workbenchLink.getAttribute('href'))?.startsWith('/products/')) throw new Error('product detail workbench link is missing product id');
    await page.locator('[data-shared-product-close]').click();
    await page.locator('[data-products-columns-open]').click();
    await page.locator('[data-products-template-manager] [data-field-template-edit]').first().waitFor({ state: 'visible' });
    if (!(await page.locator('[data-products-template-manager] [data-field-template-delete]').count())) throw new Error('products field template delete control is missing');
    await page.locator('[data-products-columns-close]').first().click();
    return checks;
  }
  if (id === 'promotion') {
    const info = page.locator('[data-promotion-info]');
    if (await info.isDisabled()) await info.evaluate((element) => { element.disabled = false; element.removeAttribute('disabled'); });
    await info.click();
    await inspectOpenDialog('[data-promotion-dialog]', 'promotion-definition');
    await page.locator('[data-promotion-dialog-close]').click();
    await page.locator('[data-promotion-manage-fields]').click();
    await page.locator('[data-promotion-template-manager] [data-field-template-edit]').first().waitFor({ state: 'visible' });
    await page.locator('[data-promotion-fields-close]').first().click();
  }
  if (id === 'lifecycle') {
    const lifecycleCard = page.locator('[data-lifecycle-card]').first();
    await lifecycleCard.waitFor({ state: 'visible' });
    await lifecycleCard.click();
    await page.locator('[data-lifecycle-detail][open]').waitFor({ state: 'visible' });
    await inspectOpenDialog('[data-lifecycle-detail]', 'lifecycle-detail');
    await page.locator('[data-lifecycle-detail-tab="table"]').click();
    await inspectOpenDialog('[data-lifecycle-detail]', 'lifecycle-detail-table');
    await page.locator('[data-lifecycle-columns-open]').waitFor({ state: 'visible' });
    await page.locator('[data-lifecycle-columns-open]').click();
    await page.locator('[data-lifecycle-template-manager] [data-field-template-edit]').first().waitFor({ state: 'visible' });
    await page.locator('[data-lifecycle-columns-close]').first().click();
  }
  if (id === 'settings') {
    await page.locator('[data-alert-rules-open]').click();
    await inspectOpenDialog('.alert-rules-dialog', 'alert-rule-editor');
    await page.locator('[data-alert-rule-close]').first().click();
  }
  if (id === 'data-center') {
    await page.locator('[data-open-toolbox]').first().evaluate((element) => element.click());
    await inspectOpenDialog('[data-toolbox-dialog]', 'toolbox');
    await page.keyboard.press('Escape');
    if (await page.locator('[data-toolbox-dialog]').evaluate((element) => element.open)) throw new Error('toolbox did not close with Escape');
  }
  return checks;
}

async function inspect(browser, viewport, label) {
  const results = [];
  for (const [id, path] of pages) {
    console.error(`[smoke] ${label} ${id}`);
    const page = await browser.newPage({ viewport });
    page.setDefaultTimeout(8000);
    const errors = [];
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
    page.on('response', (response) => {
      if (response.status() >= 400 && response.url().startsWith(base) && !(id === 'goals' && response.status() === 404 && response.url().includes('/api/goals/'))) errors.push(`HTTP ${response.status()}: ${response.url()}`);
    });
    const response = await page.goto(`${base}${path}`, { waitUntil: 'domcontentloaded', timeout: 10000 });
    await waitReady(page, id, viewport);
    const metrics = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      title: document.querySelector('.demo-topbar__title')?.textContent?.trim() || '',
      navCount: document.querySelectorAll('[data-page-link]').length,
      bodyText: document.body.innerText.length,
    }));
    const overflow = metrics.scrollWidth > metrics.clientWidth + 2;
    await waitForCanvases(page);
    let canvas = await page.locator('canvas:visible').count();
    let nonblankCanvas = await visibleCanvasesArePainted(page);
    const dialogs = await inspectDialogs(page, id, browser, viewport);

    results.push({ id, label, status: response?.status(), errors, overflow, canvas, nonblankCanvas, dialogs, ...metrics });
    await page.close();
  }
  return results;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const desktop = await inspect(browser, { width: 1366, height: 768 }, 'desktop-1366');
  const wide = await inspect(browser, { width: 1920, height: 1080 }, 'desktop-1920');
  const tablet = await inspect(browser, { width: 1024, height: 768 }, 'tablet-1024');
  const mobile = await inspect(browser, { width: 390, height: 844 }, 'mobile-390');
  const results = [...desktop, ...wide, ...tablet, ...mobile];
  console.log(JSON.stringify(results, null, 2));
  await browser.close();
  const failed = results.filter((row) => row.status !== 200 || row.errors.length || row.overflow || !row.nonblankCanvas || row.navCount !== 7 || row.bodyText < 100 || row.dialogs.some((dialog) => !dialog.open || !dialog.insideViewport || !dialog.noHorizontalOverflow));
  if (failed.length) process.exitCode = 1;
})();

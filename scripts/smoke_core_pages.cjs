const { gateChromium, assertBase } = require('./gate_browser.cjs');
const chromium = gateChromium();

const base = process.env.TMALL_SMOKE_BASE || 'http://127.0.0.1:8770';
assertBase(base);
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
  ['creative-board', '/creative-board'],
];

async function waitReady(page, id, viewport) {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(500);
  if (id === 'overview') await page.locator('[data-overview-kpi]').first().waitFor({ state: 'visible' });
  if (id === 'products') {
    if (viewport.width <= 520) await page.locator('[data-products-mobile-summary] .products-mobile-summary__item').first().waitFor({ state: 'visible' });
    else await page.locator('[data-products-body] tr').first().waitFor({ state: 'visible' });
  }
  if (id === 'promotion') {
    await page.waitForFunction(() => {
      const body = document.querySelector('[data-promotion-body]');
      if (!body || body.textContent.includes('加载中')) return false;
      return Boolean(body.querySelector('tr, .ui-empty-state'));
    });
  }
  if (id === 'lifecycle') await page.locator('[data-lifecycle-grid] > *').first().waitFor({ state: 'visible' });
  if (id === 'goals') await page.locator('[data-goals-version]').waitFor({ state: 'visible' });
  if (id === 'reviews') await page.locator('[data-reviews-list]').waitFor({ state: 'visible' });
  if (id === 'data-center') await page.locator('[data-import-file]:not(.sr-only)').first().waitFor({ state: 'visible' });
  if (id === 'settings') await page.locator('[data-settings-form]').waitFor({ state: 'visible' });
  if (id === 'creative-board') await page.locator('[data-cb-products]').waitFor({ state: 'visible' });
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
        open: element.open !== false,
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
      // 汇总行按 BI 惯例是 tbody 首行，商品行带 data-product-id，据此跳过汇总行。
      await page.locator('[data-products-body] tr[data-product-id]').first().locator('button[aria-label^="查看商品详情"]').click();
    }
    await page.waitForTimeout(250);
    await inspectOpenDialog('.product-detail-dialog', 'products-detail');
    const workbenchLink = page.locator('[data-shared-product-workbench]');
    await workbenchLink.waitFor({ state: 'visible' });
    await page.waitForFunction(() => {
      const href = document.querySelector('[data-shared-product-workbench]')?.getAttribute('href');
      return Boolean(href && href.startsWith('/products/'));
    }, { timeout: 5000 });
    await page.locator('.product-detail-dialog [data-product-detail-tab="promotion"]').click();
    await page.locator('.product-detail-dialog [data-product-detail-panel="promotion"]').waitFor({ state: 'visible' });
    await inspectOpenDialog('.product-detail-dialog', 'products-detail-promotion');
    await page.locator('.ui-drawer.is-open .ui-drawer__close').click();
    await page.locator('[data-products-columns-open]').click();
    await page.locator('[data-products-template-manager] [data-field-template-edit]').first().waitFor({ state: 'visible' });
    const productTemplateDeletes = page.locator('[data-products-template-manager] [data-field-template-delete]');
    const productTemplateItems = page.locator('[data-products-template-manager] [data-field-template-key]');
    const customTemplateItems = productTemplateItems.filter({ has: page.locator('[data-field-template-delete]') });
    if (await customTemplateItems.count() && !(await productTemplateDeletes.count())) throw new Error('custom products field template is missing delete control');
    await page.locator('[data-products-columns-close]').first().click();
    return checks;
  }
  if (id === 'promotion') {
    const info = page.locator('[data-promotion-info]');
    if (await info.isDisabled()) await info.evaluate((element) => { element.disabled = false; element.removeAttribute('disabled'); });
    await info.click();
    await inspectOpenDialog('.ui-drawer.is-open', 'promotion-definition');
    await page.locator('.ui-drawer.is-open .ui-drawer__close').click();
    const manageFields = page.locator('[data-promotion-manage-fields]');
    if (await manageFields.isVisible()) {
      await manageFields.click();
      await page.locator('[data-promotion-template-manager] [data-field-template-edit]').first().waitFor({ state: 'visible' });
      await page.locator('[data-promotion-fields-close]').first().click();
    }
  }
  if (id === 'lifecycle') {
    const lifecycleCard = page.locator('[data-lifecycle-card]').first();
    await lifecycleCard.waitFor({ state: 'visible' });
    await lifecycleCard.click();
    await page.locator('.ui-drawer.is-open').waitFor({ state: 'visible' });
    await inspectOpenDialog('.ui-drawer.is-open', 'lifecycle-detail');
    await page.locator('[data-lifecycle-detail-tab="table"]').click();
    await inspectOpenDialog('.ui-drawer.is-open', 'lifecycle-detail-table');
    await page.locator('[data-lifecycle-columns-open]').waitFor({ state: 'visible' });
    await page.locator('[data-lifecycle-columns-open]').click();
    await page.locator('[data-lifecycle-template-manager] [data-field-template-edit]').first().waitFor({ state: 'visible' });
    await page.locator('[data-lifecycle-columns-close]').first().click();
  }
  if (id === 'settings') {
    const alertRules = page.locator('[data-alert-rules-open]');
    if (await alertRules.isVisible()) {
      await alertRules.click();
      await inspectOpenDialog('.alert-rules-dialog', 'alert-rule-editor');
      await page.locator('[data-alert-rule-close]').first().click();
    }
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
      navKeys: [...document.querySelectorAll('[data-page-link]')].map((link) => link.dataset.pageLink),
      activeNavCount: document.querySelectorAll('[data-page-link][aria-current="page"]').length,
      bodyText: document.body.innerText.length,
    }));
    const overflow = metrics.scrollWidth > metrics.clientWidth + 2;
    await waitForCanvases(page);
    let canvas = await page.locator('canvas:visible').count();
    let nonblankCanvas = await visibleCanvasesArePainted(page);
    const dialogs = await inspectDialogs(page, id, browser, viewport);

    if (id === 'creative-board') {
      const productCount = await page.locator('[data-cb-products] tr[data-cb-open], [data-cb-products] .ui-empty-state').count();
      if (!productCount) throw new Error('creative board did not render products or empty state');
    }
    results.push({ id, label, status: response?.status(), errors, overflow, canvas, nonblankCanvas, dialogs, ...metrics });
    await page.close();
  }
  return results;
}

(async () => {
  const browser = await chromium.launch(process.env.TMALL_CHROME_PATH
    ? { executablePath: process.env.TMALL_CHROME_PATH, headless: true }
    : { headless: true });
  const desktop = await inspect(browser, { width: 1366, height: 768 }, 'desktop-1366');
  const wide = await inspect(browser, { width: 1920, height: 1080 }, 'desktop-1920');
  const tablet = await inspect(browser, { width: 1024, height: 768 }, 'tablet-1024');
  const mobile = await inspect(browser, { width: 390, height: 844 }, 'mobile-390');
  const results = [...desktop, ...wide, ...tablet, ...mobile];
  console.log(JSON.stringify(results, null, 2));
  await browser.close();
  const failed = results.filter((row) => row.status !== 200 || row.errors.length || row.overflow || !row.nonblankCanvas || row.navCount < 1 || new Set(row.navKeys).size !== row.navCount || row.activeNavCount !== 1 || row.bodyText < 100 || row.dialogs.some((dialog) => !dialog.open || !dialog.insideViewport || !dialog.noHorizontalOverflow));
  if (failed.length) process.exitCode = 1;
})();

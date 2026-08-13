const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

const base = process.env.TMALL_SMOKE_BASE || 'http://127.0.0.1:8770';
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

async function waitReady(page, id) {
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);
  if (id === 'overview') await page.locator('[data-overview-kpi]').first().waitFor({ state: 'visible' });
  if (id === 'products') await page.locator('[data-products-body] tr').first().waitFor({ state: 'visible' });
  if (id === 'promotion') await page.locator('[data-promotion-body] tr').first().waitFor({ state: 'visible' });
  if (id === 'lifecycle') await page.locator('[data-lifecycle-grid] > *').first().waitFor({ state: 'visible' });
  if (id === 'goals') await page.locator('[data-goals-version]').waitFor({ state: 'visible' });
  if (id === 'reviews') await page.locator('[data-reviews-list]').waitFor({ state: 'visible' });
  if (id === 'data-center') await page.locator('[data-import-file]:not(.sr-only)').first().waitFor({ state: 'visible' });
  if (id === 'settings') await page.locator('[data-settings-form]').waitFor({ state: 'visible' });
}

async function inspect(browser, viewport, label) {
  const results = [];
  for (const [id, path] of pages) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
    page.on('response', (response) => {
      if (response.status() >= 400 && response.url().startsWith(base) && !(id === 'goals' && response.status() === 404 && response.url().includes('/api/goals/'))) errors.push(`HTTP ${response.status()}: ${response.url()}`);
    });
    const response = await page.goto(`${base}${path}`, { waitUntil: 'domcontentloaded' });
    await waitReady(page, id);
    const metrics = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      title: document.querySelector('.demo-topbar__title')?.textContent?.trim() || '',
      navCount: document.querySelectorAll('[data-page-link]').length,
      bodyText: document.body.innerText.length,
    }));
    const overflow = metrics.scrollWidth > metrics.clientWidth + 2;
    let canvas = await page.locator('canvas:visible').count();
    let nonblankCanvas = true;
    if (canvas) {
      nonblankCanvas = await page.locator('canvas:visible').evaluateAll((nodes) => nodes.every((node) => {
        const context = node.getContext('2d');
        if (!context || !node.width || !node.height) return false;
        const data = context.getImageData(0, 0, node.width, node.height).data;
        for (let i = 3; i < data.length; i += 4) if (data[i] !== 0) return true;
        return false;
      }));
    }

    if (id === 'promotion') {
      const firstDrill = page.locator('[data-promotion-body] button').first();
      if (await firstDrill.count()) {
        await firstDrill.click();
        await page.locator('[data-promotion-drawer].is-open').waitFor();
        await page.keyboard.press('Escape');
      }
    }
    if (id === 'lifecycle') {
      const card = page.locator('[data-lifecycle-card]').first();
      if (await card.count()) {
        await card.click();
        await page.locator('[data-lifecycle-detail]:not([hidden])').waitFor();
        await page.waitForTimeout(300);
        canvas = await page.locator('canvas:visible').count();
        nonblankCanvas = await page.locator('canvas:visible').evaluateAll((nodes) => nodes.every((node) => {
          const context = node.getContext('2d');
          if (!context || !node.width || !node.height) return false;
          const data = context.getImageData(0, 0, node.width, node.height).data;
          for (let i = 3; i < data.length; i += 4) if (data[i] !== 0) return true;
          return false;
        }));
        await page.locator('[data-lifecycle-back]').click();
      }
    }
    results.push({ id, label, status: response?.status(), errors, overflow, canvas, nonblankCanvas, ...metrics });
    await page.close();
  }
  return results;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const desktop = await inspect(browser, { width: 1440, height: 900 }, 'desktop');
  const mobile = await inspect(browser, { width: 390, height: 844 }, 'mobile');
  const results = [...desktop, ...mobile];
  console.log(JSON.stringify(results, null, 2));
  await browser.close();
    const failed = results.filter((row) => row.status !== 200 || row.errors.length || row.overflow || !row.nonblankCanvas || row.navCount !== 7 || row.bodyText < 100);
  if (failed.length) process.exitCode = 1;
})();

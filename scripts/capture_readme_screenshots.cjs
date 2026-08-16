const fs = require('node:fs');
const path = require('node:path');

function loadPlaywright() {
  try {
    return require('playwright');
  } catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND') throw error;
  }

  const modulePath = process.env.TMALL_PLAYWRIGHT_MODULE || path.join(
    process.env.USERPROFILE || '',
    '.cache',
    'codex-runtimes',
    'codex-primary-runtime',
    'dependencies',
    'node',
    'node_modules',
    'playwright',
  );
  return require(modulePath);
}

const { chromium } = loadPlaywright();

const baseUrl = process.env.TMALL_SCREENSHOT_BASE || 'http://127.0.0.1:8774';
const outputDir = path.resolve(__dirname, '..', 'docs', 'assets', 'readme');
const captures = [
  {
    name: 'overview',
    route: '/',
    ready: '[data-page="overview"]',
    loaded: '[data-overview-summary="net_sales"]',
  },
  {
    name: 'products',
    route: '/products?start=2026-07-14&end=2026-08-12',
    ready: '[data-products-body] tr',
  },
  {
    name: 'data-center',
    route: '/data-center',
    ready: '[data-capability-domain]',
  },
];

async function assertDemoDataset(page) {
  const response = await page.request.get(
    `${baseUrl}/api/products?dim=daily&limit=5000&start=2025-01-01&end=2026-08-12`,
  );
  if (!response.ok()) {
    throw new Error(`Demo safety check failed with HTTP ${response.status()}`);
  }

  const payload = await response.json();
  const rows = payload?.data?.rows;
  const total = Number(payload?.data?.total);
  const isDemoRow = (row) => (
    String(row.product_id || '').startsWith('DEMO-')
    && row.remark === '演示数据'
  );
  if (!Array.isArray(rows) || rows.length === 0 || rows.length !== total || !rows.every(isDemoRow)) {
    throw new Error('Screenshot capture refused: the server is not an isolated DEMO dataset');
  }
}

async function captureScreenshots() {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error));
    await assertDemoDataset(page);

    for (const capture of captures) {
      pageErrors.length = 0;
      await page.goto(`${baseUrl}${capture.route}`, {
        waitUntil: 'networkidle',
        timeout: 30_000,
      });
      await page.waitForSelector(capture.ready, {
        state: 'attached',
        timeout: 15_000,
      });

      if (capture.loaded) {
        await page.waitForFunction(
          (selector) => document.querySelector(selector)?.textContent?.trim() !== '--',
          capture.loaded,
          { timeout: 15_000 },
        );
      }

      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(1500);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      if (overflow > 1) {
        throw new Error(`${capture.name} has ${overflow}px horizontal overflow`);
      }
      if (pageErrors.length) {
        throw pageErrors[0];
      }

      await page.screenshot({
        path: path.join(outputDir, `${capture.name}.png`),
        fullPage: false,
      });
    }
  } finally {
    await browser.close();
  }
}

captureScreenshots().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

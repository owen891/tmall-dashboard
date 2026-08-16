const fs = require('node:fs');
const path = require('node:path');
const {
  chromium,
} = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

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

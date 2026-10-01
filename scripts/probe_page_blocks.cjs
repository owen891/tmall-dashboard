/**
 * 页面分块高度探针（批次 2 用）：按可见直接子块报告高度。
 * 用法：NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/probe_page_blocks.cjs /market-ranking
 */
const { chromium } = require('playwright-core');

const route = process.argv[2] || '/market-ranking';
const BASE = process.env.BASE || 'http://127.0.0.1:5000';
const VIEWPORTS = [[1440, 900], [390, 844]];

const PROBE = () => {
  const main = document.querySelector('main');
  const blocks = [...main.children].map((el) => {
    const r = el.getBoundingClientRect();
    return {
      tag: el.tagName.toLowerCase(),
      cls: (el.className || '').toString().slice(0, 46),
      panel: el.dataset ? el.dataset.marketPanel || '' : '',
      hidden: el.hidden,
      h: Math.round(r.height),
    };
  });
  const panels = [...document.querySelectorAll('[data-market-panel]')].map((el) => ({
    panel: el.dataset.marketPanel,
    hidden: el.hidden,
    h: Math.round(el.getBoundingClientRect().height),
    kids: [...el.children].map((k) => ({ cls: (k.className || '').toString().slice(0, 40), h: Math.round(k.getBoundingClientRect().height) })),
  }));
  return { pageHeight: Math.round(document.documentElement.scrollHeight), blocks, panels };
};

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || undefined, args: ['--no-sandbox'] });
  for (const [width, height] of VIEWPORTS) {
    const context = await browser.newContext({ viewport: { width, height } });
    const page = await context.newPage();
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);
    const r = await page.evaluate(PROBE);
    console.log(`\n===== ${width}px  页高 ${r.pageHeight} =====`);
    console.log('-- main 直接子块 --');
    r.blocks.forEach((b) => console.log(`  ${String(b.h).padStart(6)}  ${b.tag}.${b.cls}${b.panel ? ' [panel=' + b.panel + ']' : ''}${b.hidden ? ' (hidden)' : ''}`));
    console.log('-- market panels --');
    r.panels.forEach((p) => {
      console.log(`  ${String(p.h).padStart(6)}  panel=${p.panel}${p.hidden ? ' (hidden)' : ''}`);
      p.kids.forEach((k) => console.log(`           ${String(k.h).padStart(6)}  .${k.cls}`));
    });
    await context.close();
  }
  await browser.close();
})();

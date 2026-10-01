/**
 * 5-3 列预算探针（批量）：逐个页面报「表宽 / 容器宽 / 溢出」，只列有溢出的表。
 * 用法：NODE_PATH=... node scripts/probe_table_overflow.cjs [route1,route2,...] [W]
 * 默认：W=1440，跑重点页面清单。
 */
const { chromium } = require('playwright-core');

const BASE = process.env.BASE || 'http://127.0.0.1:5000';
const WIDTH = Number(process.argv[3] || process.env.W || 1440);
const ROUTES = (process.argv[2] || [
  '/overview',
  '/period-review',
  '/products',
  '/lifecycle',
  '/keyword-promotion',
  '/new-products',
  '/data-center',
  '/market-ranking',
  '/rival-analysis',
].join(',')).split(',');

const PROBE = () => [...document.querySelectorAll('table.ui-data-table')].map((t, i) => {
  const wrap = t.closest('.ui-table-wrap');
  if (!wrap) return null;
  const head = t.tHead?.rows?.[t.tHead.rows.length - 1];
  const rect = t.getBoundingClientRect();
  const wrect = wrap.getBoundingClientRect();
  if (rect.width === 0) return null;
  return {
    index: i + 1,
    title: t.closest('.ui-panel')?.querySelector('.panel__title')?.textContent?.trim().slice(0, 22)
      || t.closest('section')?.querySelector('h2,h3')?.textContent?.trim().slice(0, 22) || '',
    tableWidth: Math.round(rect.width),
    wrapWidth: Math.round(wrect.width),
    scrollWidth: Math.round(wrap.scrollWidth),
    cols: [...(head?.cells || [])].map((c) => ({
      label: c.textContent.trim().replace(/\s+/g, '').slice(0, 12),
      w: Math.round(c.getBoundingClientRect().width),
      key: c.dataset.fieldKey || '',
    })),
  };
}).filter(Boolean);

(async () => {
  const b = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || undefined, args: ['--no-sandbox'] });
  const c = await b.newContext({ viewport: { width: WIDTH, height: 900 } });
  const p = await c.newPage();
  let totalOver = 0;
  for (const route of ROUTES) {
    await p.goto(BASE + route, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(5000);
    const tables = await p.evaluate(PROBE);
    const bad = tables.filter((t) => t.scrollWidth - t.wrapWidth > 8);
    if (!bad.length) {
      console.log(`OK   ${route.padEnd(22)} ${tables.length} 张表，无溢出`);
      continue;
    }
    console.log(`FAIL ${route}  （${bad.length}/${tables.length} 张表溢出）`);
    for (const t of bad) {
      const over = t.scrollWidth - t.wrapWidth;
      totalOver += over;
      console.log(`   #${t.index} ${t.title} | 表 ${t.tableWidth} / 容器 ${t.wrapWidth} / 溢出 ${over}`);
      console.log(`        ${t.cols.map((col) => `${col.label}:${col.w}${col.key ? '(' + col.key + ')' : ''}`).join('  ')}`);
    }
  }
  console.log(`\n合计溢出 ${totalOver}px @ ${WIDTH}px 宽`);
  await b.close();
})();

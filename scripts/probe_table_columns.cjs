/**
 * 表格列宽探针：报每列宽度 + 表宽 vs 容器宽，用来做 5-3 列预算。
 * 用法：NODE_PATH=... node scripts/probe_table_columns.cjs /lifecycle [表序号从1开始]
 */
const { chromium } = require('playwright-core');

const route = process.argv[2] || '/lifecycle';
const only = Number(process.argv[3] || 0);
const BASE = process.env.BASE || 'http://127.0.0.1:5000';
const WIDTH = Number(process.env.W || 1440);

const PROBE = (only) => [...document.querySelectorAll('table.ui-data-table')].map((t, i) => {
  const wrap = t.closest('.ui-table-wrap');
  const head = t.tHead?.rows?.[0];
  if (!head) return null;
  return {
    index: i + 1,
    title: t.closest('.ui-panel')?.querySelector('.panel__title')?.textContent?.trim().slice(0, 20) || '',
    tableWidth: Math.round(t.getBoundingClientRect().width),
    wrapWidth: wrap ? Math.round(wrap.getBoundingClientRect().width) : null,
    cols: [...head.cells].map((c) => ({
      label: c.textContent.trim().replace(/\s+/g, '').slice(0, 12),
      w: Math.round(c.getBoundingClientRect().width),
      thStyle: c.getAttribute('style') || '',
      key: c.dataset.fieldKey || '',
    })),
  };
}).filter((x) => x && (!only || x.index === only));

(async () => {
  const b = await chromium.launch({ executablePath: process.env.PW_CHROMIUM || undefined, args: ['--no-sandbox'] });
  const c = await b.newContext({ viewport: { width: WIDTH, height: 900 } });
  const p = await c.newPage();
  await p.goto(BASE + route, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(5000);
  const tables = await p.evaluate(PROBE, only);
  for (const t of tables) {
    const over = t.wrapWidth ? t.tableWidth - t.wrapWidth : 0;
    console.log(`\n#${t.index} ${t.title} | 表宽 ${t.tableWidth} / 容器 ${t.wrapWidth} / 溢出 ${over > 0 ? over : 0}`);
    t.cols.forEach((col) => console.log(`   ${String(col.w).padStart(5)}px  ${col.label.padEnd(14)}${col.key ? '[' + col.key + ']' : ''} ${col.thStyle}`));
  }
  await b.close();
})();

/**
 * 货品矩阵地图验证（只读，输出 PASS/FAIL）
 *
 * 契约：
 *   1. products 页矩阵区块存在（data-product-matrix-board），散点 SVG 渲染 ≥1 气泡
 *   2. 分层统计卡 ≥3 层（引流/利润/动销至少三层有数）
 *   3. 状态行含费比口径（推广花费 ÷ GSV）
 *   4. 复盘页货品汇总含「产品分层（按推广角色 · 本复盘周期）」区块（复盘页引用侧）
 *   5. 无横向溢出、无 pageerror
 *
 * 用法：
 *   NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/verify_product_matrix.cjs
 *   （BASE 默认 http://127.0.0.1:5000）
 */
const { chromium } = require('playwright-core');

const BASE = process.env.BASE || 'http://127.0.0.1:5000';

const PROBE = () => {
  const board = document.querySelector('[data-product-matrix-board]');
  const scatter = document.querySelector('[data-matrix-scatter]');
  return {
    boardVisible: !!(board && board.getClientRects().length),
    circles: document.querySelectorAll('[data-matrix-scatter] circle').length,
    statRows: [...document.querySelectorAll('[data-matrix-stats] > div')].length,
    status: (document.querySelector('[data-matrix-status]') || {}).textContent || '',
    hasCaliber: ((document.querySelector('[data-matrix-status]') || {}).textContent || '')
      .includes('推广花费 ÷ GSV'),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PW_CHROMIUM || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 160)));
  const failures = [];

  await page.goto(`${BASE}/products`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  const probe = await page.evaluate(PROBE);
  console.log('products 页矩阵区块:');
  console.log(`  区块可见 ${probe.boardVisible} / 气泡 ${probe.circles} / 统计行 ${probe.statRows}`);
  console.log(`  状态行: ${probe.status}`);
  console.log(`  溢出 ${probe.overflow}px`);

  if (!probe.boardVisible) failures.push('矩阵区块不可见');
  if (probe.circles < 1) failures.push(`散点无气泡（${probe.circles}）`);
  if (probe.statRows < 3) failures.push(`分层统计行不足 3（${probe.statRows}）`);
  if (!probe.hasCaliber) failures.push('状态行未标注费比口径（推广花费 ÷ GSV）');
  if (probe.overflow > 1) failures.push(`横向溢出 ${probe.overflow}px`);

  // 复盘页引用侧：货品汇总面板应含产品分层块
  await page.goto(`${BASE}/period-review`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  await page.click('[data-pr-workbench-tab="diagnosis"]');
  await page.waitForTimeout(1500);
  const seg = await page.evaluate(() => {
    const panels = [...document.querySelectorAll('.ui-panel')];
    const target = panels.find((p) => ((p.querySelector('.panel__title') || {}).textContent || '') === '货品汇总');
    if (!target) return { found: false };
    const blocks = [...target.querySelectorAll('.pr-material__title')].map((t) => t.textContent);
    const hasSegments = blocks.some((t) => t.includes('产品分层'));
    return { found: true, blocks, hasSegments };
  });
  console.log('复盘页货品汇总:');
  console.log(`  面板 ${seg.found ? 'found' : 'missing'} / 区块 ${(seg.blocks || []).join(' | ')}`);
  if (!seg.found) failures.push('复盘页未找到货品汇总面板');
  else if (!seg.hasSegments) failures.push('货品汇总缺少产品分层块');
  if (errors.length) failures.push(`pageerror: ${errors.join('; ')}`);

  await browser.close();
  console.log('');
  if (failures.length) {
    console.log('product matrix contract: FAIL');
    failures.forEach((f) => console.log(`  - ${f}`));
    process.exit(1);
  }
  console.log('product matrix contract: PASS');
})().catch((error) => {
  console.error('probe crashed:', error);
  process.exit(1);
});

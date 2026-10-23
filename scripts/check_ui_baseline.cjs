#!/usr/bin/env node
/**
 * UI 基线比对（回归防线 #3）
 *
 * 读 `.tmp/ui-audit/` 下三遍探针的产物，对照 `docs/UI_REMEDIATION_PLAN_20261001.md`
 * 第 1 节的验收基线，逐格输出 PASS/FAIL，并给出「比基线更好/更差」的方向。
 *
 * 用法：
 *   NODE_PATH=E:/www/tmall-dashboard/desktop/node_modules node scripts/check_ui_baseline.cjs
 *   node scripts/check_ui_baseline.cjs --dir .tmp/ui-audit --strict
 *
 * 退出码：0 = 全部达标；1 = 有未达标项（`--strict` 时连「回退」也算失败）。
 *
 * 为什么要有这个脚本：DOM 节点数与可交互元素数是最容易悄悄涨回去的两个指标，
 * 靠人眼比对 JSON 不可持续。把阈值写成脚本之后，「有没有变好」不靠感觉。
 */
const fs = require('node:fs');
const path = require('node:path');

const args = process.argv.slice(2);
const getArg = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const STRICT = args.includes('--strict');
const DIR = path.resolve(getArg('--dir', '.tmp/ui-audit'));

/**
 * 三份探针产物必须来自同一次采集。
 *
 * 为什么要有这道闸：三个脚本跑完的时间差通常在分钟级，但一旦有人只重跑了其中
 * 一个（例如改完 CSS 只重跑 audit_ui_layout），比对表就会把 10-02 的布局数据
 * 和 10-03 的 DOM 数据拼在一起，得出一张看起来正常、实则跨代码版本的表。
 * 库里确实发生过：验收报告记的 4,283px 与产物里的 4,295px 对不上，无人察觉。
 */
const MAX_BATCH_SKEW_MS = 30 * 60 * 1000;

const readJson = (file) => {
  const p = path.join(DIR, file);
  if (!fs.existsSync(p)) {
    console.error(`缺少探针产物：${p}\n先跑第 7 节的 audit_ui_dom / audit_ui_layout / audit_ui_deep。`);
    process.exit(2);
  }
  const stat = fs.statSync(p);
  return { data: JSON.parse(fs.readFileSync(p, 'utf8')), file, mtimeMs: stat.mtimeMs };
};

const probes = {
  dom: readJson('dom.json'),
  layout: readJson('audit.json'),
  deep: readJson('deep.json'),
};

{
  const stamps = Object.values(probes).map((p) => p.mtimeMs);
  const skew = Math.max(...stamps) - Math.min(...stamps);
  if (skew > MAX_BATCH_SKEW_MS) {
    const detail = Object.values(probes)
      .map((p) => `  ${p.file}  ${new Date(p.mtimeMs).toISOString()}`)
      .join('\n');
    console.error(
      `探针产物不属于同一次采集：最大时间差 ${(skew / 60000).toFixed(1)} 分钟`
      + `（上限 ${MAX_BATCH_SKEW_MS / 60000} 分钟）。\n${detail}\n`
      + '三份产物跨了不同的采集批次，比对结论不成立。请重跑全部三个探针后再比对。',
    );
    process.exit(2);
  }
}

const dom = probes.dom.data;
const layout = probes.layout.data;
const deep = probes.deep.data;

const viewportsOf = (source, name) => Object.values(source?.pages?.[name]?.viewports || {});
const allViewports = (source) => Object.entries(source?.pages || {}).flatMap(
  ([name, page]) => Object.entries(page.viewports || {}).map(([vp, data]) => ({ name, vp, data })),
);

const results = [];
const record = (id, label, actual, target, pass, note = '') => {
  results.push({ id, label, actual, target, pass, note });
};

// ── 1. 横向溢出页面数（3 视口）目标 0 ───────────────────────────────
{
  const bad = allViewports(layout).filter((x) => x.data.horizontalOverflow);
  record('overflow', '横向溢出页面数（3 视口）', bad.length, '0', bad.length === 0,
    bad.length ? bad.map((x) => `${x.name}/${x.vp} +${x.data.overflowPx}px`).join(', ') : '');
}

// ── 2. 接口 4xx 目标 0 ────────────────────────────────────────────
{
  const bad = allViewports(deep).filter((x) => (x.data.httpErrors || []).length);
  const total = bad.reduce((sum, x) => sum + x.data.httpErrors.length, 0);
  record('http4xx', '接口 4xx（22 页加载）', total, '0', total === 0,
    bad.map((x) => `${x.name}/${x.vp}×${x.data.httpErrors.length}`).join(', '));
}

// ── 3. 控制台错误 目标 0 ──────────────────────────────────────────
{
  const bad = allViewports(deep).filter((x) => (x.data.consoleErrors || []).length);
  const total = bad.reduce((sum, x) => sum + x.data.consoleErrors.length, 0);
  record('console', '控制台错误', total, '0', total === 0,
    bad.map((x) => `${x.name}/${x.vp}×${x.data.consoleErrors.length}`).join(', '));
}

// ── 4. 每页恰好 1 个 h1 ──────────────────────────────────────────
{
  const bad = [];
  for (const { name, vp, data } of allViewports(deep)) {
    if (vp !== 'desktop') continue;
    const h1 = (data.headings || []).filter((h) => h.level === 1).length;
    if (h1 !== 1) bad.push(`${name}(${h1})`);
  }
  record('h1', '每页 <h1> 数量', bad.length ? bad.join(', ') : '全部恰好 1', '恰好 1', bad.length === 0);
}

// ── 5. 单页 DOM 节点峰值 < 8000 ───────────────────────────────────
{
  const entries = Object.entries(dom).map(([name, d]) => ({ name, v: d.allEl }));
  const worst = entries.reduce((a, b) => (b.v > a.v ? b : a), { name: '-', v: 0 });
  record('dom', '单页 DOM 节点峰值', `${worst.name} ${worst.v}`, '< 8000', worst.v < 8000);
}

// ── 6. 单页可交互元素峰值 < 100 ───────────────────────────────────
{
  const entries = Object.entries(dom).map(([name, d]) => ({ name, v: d.interactive }));
  const worst = entries.reduce((a, b) => (b.v > a.v ? b : a), { name: '-', v: 0 });
  record('interactive', '单页可交互元素峰值', `${worst.name} ${worst.v}`, '< 100', worst.v < 100);
}

// ── 7. 桌面页高峰值 < 3000px ──────────────────────────────────────
{
  const entries = allViewports(layout).filter((x) => x.vp === 'desktop')
    .map((x) => ({ name: x.name, v: x.data.bodyHeight }));
  const worst = entries.reduce((a, b) => (b.v > a.v ? b : a), { name: '-', v: 0 });
  record('desktopH', '桌面页高峰值', `${worst.name} ${worst.v}px`, '< 3000px', worst.v < 3000);
}

// ── 8. 移动页高峰值 < 6000px ──────────────────────────────────────
{
  const entries = allViewports(layout).filter((x) => x.vp === 'mobile')
    .map((x) => ({ name: x.name, v: x.data.bodyHeight }));
  const worst = entries.reduce((a, b) => (b.v > a.v ? b : a), { name: '-', v: 0 });
  record('mobileH', '移动页高峰值', `${worst.name} ${worst.v}px`, '< 6000px', worst.v < 6000);
}

// ── 9. keyword-promotion 内联样式 = 0 ─────────────────────────────
{
  const v = deep?.pages?.['keyword-promotion']?.viewports?.desktop?.inlineStyled ?? 0;
  record('inline', 'keyword-promotion 内联样式', v, '0', v === 0);
}

// ── 10. TmallUI.audit() 问题数 = 0 ────────────────────────────────
{
  const bad = allViewports(deep).filter((x) => (x.data.auditIssues || []).length);
  const total = bad.reduce((sum, x) => sum + x.data.auditIssues.length, 0);
  record('audit', 'TmallUI.audit() 问题数', total, '0', total === 0,
    bad.slice(0, 4).map((x) => `${x.name}/${x.vp}: ${x.data.auditIssues[0]?.message || ''}`).join(' | '));
}

// ── 11. 表格横滚页数（参考项，非硬门禁）─────────────────────────────
// 方案第 1 节写的是「1440 下需横滚的表格 5 页 → 0」。批次 3 的 5-3 结论是：
// 页面级横滚已全部归零（见上第 1 项），残留的是**表格容器内**的 sticky 横向滚动，
// products 刻意保留（428 → 158px），用于宽表列不换行。因此这一项按「参考」输出，
// 只有 --strict 时才计入失败。
{
  const perPage = new Map();
  for (const { name, vp, data } of allViewports(deep)) {
    if (vp !== 'desktop') continue;
    const n = (data.tables || []).filter((t) => t.needsScroll).length;
    if (n) perPage.set(name, n);
  }
  const pages = perPage.size;
  const info = [...perPage.entries()].map(([k, v]) => `${k}×${v}`).join(', ');
  results.push({
    id: 'tableScroll', label: '桌面表格容器内横滚页数（参考）',
    actual: pages, target: '参考', pass: !STRICT, note: info,
  });
}

// ── 输出 ─────────────────────────────────────────────────────────
const pad = (s, n) => String(s).padEnd(n, ' ');
console.log(`UI 基线比对  dir=${DIR}\n`);
console.log(`${pad('项', 30)} ${pad('实测', 26)} ${pad('目标', 12)} 结果`);
console.log('-'.repeat(88));
for (const r of results) {
  console.log(`${pad(r.label, 30)} ${pad(r.actual, 26)} ${pad(r.target, 12)} ${r.pass ? 'PASS' : 'FAIL'}${r.note ? '  ' + r.note : ''}`);
}
const failed = results.filter((r) => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} 项达标`);
if (failed.length) {
  console.log('\n未达标：');
  failed.forEach((r) => console.log(`  - ${r.label}：实测 ${r.actual}，目标 ${r.target}`));
}
process.exitCode = failed.length ? 1 : 0;

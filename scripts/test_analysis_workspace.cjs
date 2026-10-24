'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const i = process.argv.indexOf('--root');
const root = path.resolve(i < 0 ? path.join(__dirname, '..') : process.argv[i + 1]);
const read = p => fs.readFileSync(path.join(root, p), 'utf8');
const html = read('frontend/ui_demo/pages/analysis.html').replace(/<!--[^]*?-->/g, '');
const css = read('frontend/ui_demo/assets/themes/analysis-workspace.css');
const js = read('frontend/ui_demo/assets/analysis-live.js');
const tests = [
  ['six native keyboard-operable templates with one selected state', () => {
    const buttons = [...html.matchAll(/<button\b[^>]*data-template="([^"]+)"[^>]*>/g)];
    assert.equal(buttons.length, 6);
    assert.ok(buttons.every(m => m[0].includes('type="button"') && m[0].includes('aria-pressed=')));
    assert.equal(buttons.filter(m => m[0].includes('aria-pressed="true"')).length, 1);
  }],
  ['all original IDs remain unique', () => {
    const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
    assert.equal(ids.length, 22); assert.equal(new Set(ids).size, 22);
    for (const id of ['analysisTemplates','analysisCharts','runAnalysisBtn','saveAnalysisBtn','categoryAnalysisConfig','categoryCompareDates','savedAnalysisSection','savedAnalysisList']) assert.ok(ids.includes(id));
  }],
  ['six legacy fields have explicit label associations', () => {
    for (const id of ['metricSelect','dimensionSelect','chartTypeSelect','startDate','endDate','topNSelect']) assert.ok(html.includes(`for="${id}"`));
  }],
  ['inspector and result sections have accessible names', () => {
    assert.ok(html.includes('analysis-workspace__inspector" aria-label="分析配置"'));
    assert.ok(html.includes('analysis-workspace__results" aria-label="分析结果"'));
  }],
  ['page adapter loads after shared theme', () => {
    const links = [...html.matchAll(/<link[^>]*rel="stylesheet"[^>]*>/g)].map(m => m[0]);
    assert.ok(links.at(-2).includes('macos-content.css')); assert.ok(links.at(-1).includes('analysis-workspace.css'));
  }],
  ['desktop-only layout and original palette', () => {
    assert.ok(css.includes('@media (min-width: 960px)'));
    assert.ok(css.includes('grid-template-columns: 248px minmax(0, 1fr)'));
    assert.ok(!/!important|backdrop-filter|#[a-f\d]{3,8}\b|rgba?\(/i.test(css));
    assert.ok(!css.includes('[hidden]')); assert.ok(css.includes('display: contents;'));
  }],
  ['quiet selection and separate keyboard focus', () => {
    assert.ok(css.includes('background: var(--brand-tint); color: var(--brand-text)'));
    assert.ok(css.includes('.analysis-template:focus-visible { outline: 2px solid var(--focus-ring)'));
    assert.ok(js.includes("t.setAttribute('aria-pressed', 'false')"));
    assert.ok(js.includes("tpl.setAttribute('aria-pressed', 'true')"));
  }],
  ['chart initialization waits for mounting and skips superseded cards', () => {
    const fn = js.slice(js.indexOf('  function createChartCard('), js.indexOf('  function buildChartOption('));
    assert.ok(fn.indexOf('requestAnimationFrame') < fn.indexOf('echarts.init'));
    assert.ok(fn.indexOf('if (!canvas.isConnected) return;') < fn.indexOf('echarts.init'));
    assert.ok(fn.includes('chartResizeHandlers.set(chart, resizeHandler)'));
  }],
];
let failed = 0;
for (const [name, run] of tests) {
  try { run(); console.log('PASS ' + name); }
  catch (error) { failed++; console.error('FAIL ' + name + ': ' + error.message); }
}
console.log(`RESULT ${tests.length-failed}/${tests.length} passed; ${failed} failed`);
process.exitCode = failed ? 1 : 0;

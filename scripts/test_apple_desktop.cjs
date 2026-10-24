#!/usr/bin/env node
'use strict';
// Static contract; browser geometry and interaction are verified separately.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const arg = process.argv.indexOf('--root');
const root = path.resolve(arg >= 0 ? process.argv[arg + 1] : path.join(__dirname, '..'));
const cssPath = 'frontend/ui_demo/assets/themes/overview-domain.css';
const htmlPath = 'frontend/ui_demo/pages/overview.html';
const css = fs.readFileSync(path.join(root, cssPath), 'utf8');
const html = fs.readFileSync(path.join(root, htmlPath), 'utf8');
const marker = '/* Desktop hierarchy: preserve the existing palette';
const offset = css.indexOf(marker);
const addition = offset >= 0 ? css.slice(offset) : '';
const rules = [];
function parse(text, media = '') {
  text = text.replace(/\/\*[\s\S]*?\*\//g, '');
  let start = 0;
  while (start < text.length) {
    const open = text.indexOf('{', start);
    if (open < 0) break;
    const selector = text.slice(start, open).trim();
    let depth = 1, end = open + 1;
    for (; end < text.length && depth; end++) {
      if (text[end] === '{') depth++;
      if (text[end] === '}') depth--;
    }
    assert.equal(depth, 0, 'balanced CSS blocks');
    const body = text.slice(open + 1, end - 1);
    if (selector.startsWith('@media')) parse(body, selector);
    else {
      const values = Object.fromEntries(body.split(';').filter(x => x.includes(':')).map(x => {
        const colon = x.indexOf(':');
        return [x.slice(0, colon).trim(), x.slice(colon + 1).trim()];
      }));
      for (const single of selector.split(',')) rules.push({ selector: single.trim(), media, values });
    }
    start = end;
  }
}
parse(addition);
const prefix = 'body[data-page="overview"] ';
function value(selector, property, narrow = false) {
  let result;
  for (const rule of rules) {
    if (rule.selector === prefix + selector && (narrow || !rule.media.includes('max-width'))) {
      if (property in rule.values) result = rule.values[property];
    }
  }
  return result;
}
const tests = [
  ['1024 toolbar has two explicit rows with every control retained', () => {
    assert.equal(value('.demo-topbar', 'display', true), 'grid');
    assert.equal(value('.demo-topbar', 'grid-template-rows', true), 'auto auto');
    assert.equal(value('.demo-topbar__filters', 'display', true), 'contents');
    for (const s of ['.demo-sidebar-toggle', '.demo-category', '.demo-topbar__tools']) assert.equal(value(s, 'grid-row', true), '1');
    assert.equal(value('.demo-topbar__filters > .demo-period', 'grid-row', true), '2');
    assert.equal(value('.demo-topbar__filters > .demo-period', 'grid-column', true), '1 / -1');
    assert.equal(value('.demo-period__inline', 'flex-wrap', true), 'nowrap');
    assert.equal(value('.demo-overview-action span', 'display', true), 'inline');
  }],
  ['desktop-only, homepage-only override', () => {
    assert.ok(rules.length > 20, 'desktop rules must exist');
    assert.ok(rules.every(r => r.media.includes('(min-width: 960px)') && r.selector.startsWith(prefix)));
  }],
  ['core KPI order precedes compact decision summary', () => {
    assert.equal(value('.overview-decision__kpis', 'order'), '2');
    assert.equal(value('.overview-decision__secondary', 'order'), '3');
    assert.equal(value('.overview-decision__items', 'order'), '4');
    assert.equal(value('.overview-decision__focus', 'order'), '5');
  }],
  ['unified four-column surface and hairline separators', () => {
    assert.equal(value('.overview-decision__kpis', 'gap'), '0');
    assert.equal(value('.overview-decision__kpis', 'grid-template-columns'), 'repeat(4, minmax(0, 1fr))');
    assert.equal(value('.overview-v2-kpi', 'border-right'), '1px solid var(--border-default)');
    assert.equal(value('.overview-v2-kpi', 'border-radius'), '0');
  }],
  ['no nested shadows or hover lift in KPI states', () => {
    for (const s of ['.overview-v2-kpi', '.overview-v2-kpi[data-overview-kpi-select]:hover', '.overview-v2-kpi[data-overview-kpi-select].is-selected']) {
      assert.equal(value(s, 'box-shadow'), 'none');
      assert.equal(value(s, 'transform'), 'none');
    }
  }],
  ['selection and keyboard focus remain visible', () => {
    // 2026-10-17: selected near-white surface replaced by existing brand-tint; retain separate hover contract.
    // Superseded: assert.equal(value('.overview-v2-kpi[data-overview-kpi-select].is-selected', 'background'), 'var(--surface-selected)');
    assert.equal(value('.overview-v2-kpi[data-overview-kpi-select].is-selected', 'background'), 'var(--brand-tint)');
    assert.equal(value('.overview-v2-kpi[data-overview-kpi-select].is-selected', 'border-bottom-color'), 'transparent');
    assert.equal(value('.overview-v2-kpi[data-overview-kpi-select]:focus-visible', 'outline'), '2px solid var(--focus-ring)');
  }],
  ['quiet decoration, tabular values, unbroken buttons', () => {
    assert.equal(value('.overview-v2-kpi__icon', 'display'), 'none');
    assert.equal(value('.overview-v2-kpi__bar', 'display'), 'none');
    assert.equal(value('.overview-v2-kpi .metric-card__value', 'font-variant-numeric'), 'tabular-nums');
    assert.equal(value('.ui-button', 'white-space'), 'nowrap');
  }],
  ['desktop action form has a single scrolling body', () => {
    assert.equal(value('.overview-action-dialog', 'overflow'), 'hidden');
    assert.equal(value('.overview-action-dialog form', 'overflow'), 'hidden');
    assert.equal(value('.overview-action-dialog form', 'grid-template-rows'), 'auto minmax(0, 1fr) auto');
    assert.equal(value('.overview-action-dialog .modal-form__body', 'overflow-y'), 'auto');
    assert.equal(value('.overview-action-dialog .modal-form__footer', 'position'), 'static');
  }],
  ['1024 desktop uses single-column supporting regions', () => {
    assert.equal(value('.overview-v2-main-grid', 'grid-template-columns', true), '1fr');
    assert.equal(value('.operations-center__layout', 'grid-template-columns', true), '1fr');
  }],
  ['existing palette definitions retained; no glass or raw colors added', () => {
    assert.ok(addition.length > 0);
    assert.ok(!/(?:#[a-f\d]{3,8}\b|rgba?\(|hsla?\(|backdrop-filter|--[\w-]+\s*:)/i.test(addition));
  }],
  ['HTML hooks retained and stylesheet cache version advanced', () => {
    assert.ok(html.includes('overview-domain.css?v=20261017-desktop'));
    for (const hook of ['data-overview-kpi-select="net_sales"', 'data-overview-quality', 'data-overview-data-scope', 'data-overview-action-form', 'data-overview-action-submit', 'data-overview-matrix-columns-open', 'data-operations-calendar-grid']) assert.ok(html.includes(hook), hook);
  }],
];
let failures = 0;
for (const [name, run] of tests) {
  try { run(); console.log(`PASS ${name}`); }
  catch (e) { failures++; console.log(`FAIL ${name}: ${e.message.split('\n')[0]}`); }
}
console.log(`RESULT ${tests.length - failures}/${tests.length} passed; ${failures} failed`);
process.exitCode = failures ? 1 : 0;

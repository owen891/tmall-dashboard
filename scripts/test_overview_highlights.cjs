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
 ['primary and secondary share selected tint without underline',()=>{
  for(const s of ['.overview-v2-kpi','.overview-decision__secondary-item']){
   const selected=s+'[data-overview-kpi-select].is-selected';
   for(const state of [selected,selected+':hover']){
    assert.equal(value(state,'background'),'var(--brand-tint)');
    assert.equal(value(state,'border-bottom-color'),'transparent');
    assert.equal(value(state,'box-shadow'),'none');
   }
  }
 }],
 ['hover does not impersonate selected',()=>{
  for(const s of ['.overview-v2-kpi','.overview-decision__secondary-item'])assert.equal(value(s+'[data-overview-kpi-select]:not(.is-selected):hover','background'),'var(--surface-muted)');
 }],
 ['labels emphasize selection but numeric/semantic values are untouched',()=>{
  for(const s of ['.overview-v2-kpi[data-overview-kpi-select].is-selected .metric-card__label','.overview-decision__secondary-item[data-overview-kpi-select].is-selected > span']){
   assert.equal(value(s,'color'),'var(--brand-text)');assert.equal(value(s,'font-weight'),'600');
  }
  const extra=css.split('/* Desktop highlight refinement:')[1];assert.ok(extra);assert.ok(!extra.includes('metric-card__value'));assert.ok(!extra.includes('is-up'));assert.ok(!extra.includes('is-down'));
 }],
 ['focus ring distinct and no selection size jump on secondary',()=>{
  for(const s of ['.overview-v2-kpi','.overview-decision__secondary-item']){
   assert.equal(value(s+'[data-overview-kpi-select]:focus-visible','outline'),'2px solid var(--focus-ring)');assert.equal(value(s+'[data-overview-kpi-select]:focus-visible','outline-offset'),'-4px');
  }
  assert.equal(value('.overview-decision__secondary-item[data-overview-kpi-select]','border-bottom'),'2px solid transparent');
 }],
 ['homepage desktop only, existing colors only',()=>{
  assert.ok(rules.every(r=>r.media.includes('(min-width: 960px)') && r.selector.startsWith(prefix)));
  assert.ok(!/(?:#[a-f\d]{3,8}\b|rgba?\(|hsla?\(|backdrop-filter|--[\w-]+\s*:)/i.test(addition));
 }],
];
let failures = 0;
for (const [name, run] of tests) {
  try { run(); console.log(`PASS ${name}`); }
  catch (e) { failures++; console.log(`FAIL ${name}: ${e.message.split('\n')[0]}`); }
}
console.log(`RESULT ${tests.length - failures}/${tests.length} passed; ${failures} failed`);
process.exitCode = failures ? 1 : 0;

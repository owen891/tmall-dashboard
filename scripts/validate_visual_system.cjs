const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', 'frontend', 'ui_demo', 'assets');
const tokens = fs.readFileSync(path.join(root, 'tokens.css'), 'utf8');
const shared = ['shell.css', 'components.css']
  .map((file) => ({ file, css: fs.readFileSync(path.join(root, file), 'utf8') }));
const errors = [];

function assert(condition, message) {
  if (!condition) errors.push(message);
}

function hasRawBoxShadow(css) {
  return [...css.matchAll(/box-shadow:\s*([^;]+)/g)]
    .some((match) => !/^(?:var\(|none\b)/.test(match[1].trim()));
}

for (const name of [
  '--color-orange-600', '--surface-page', '--text-primary', '--border-default',
  '--font-size-body', '--font-size-meta', '--font-size-title', '--font-size-kpi',
  '--icon-control', '--button-primary-bg', '--panel-radius', '--dialog-shadow',
  '--focus-ring', '--overlay-backdrop', '--icon-button-size', '--control-height',
]) {
  assert(tokens.includes(name), `tokens.css: missing ${name}`);
}

for (const { file, css } of shared) {
  assert(!/font-weight:\s*650\b/.test(css), `${file}: unsupported font-weight 650`);
  assert(!/font-size:\s*(?:9|10|25)px\b/.test(css), `${file}: unsupported font-size`);
  assert(!/font:\s*(?:[4-9]00\s+)?(?:9|10|25)px\b/.test(css), `${file}: unsupported font shorthand`);
  assert(!/#[0-9a-f]{3,8}\b/i.test(css), `${file}: raw hex color outside token source`);
  assert(!/rgb\(/i.test(css), `${file}: raw rgb color outside token source`);
  assert(!hasRawBoxShadow(css), `${file}: raw box-shadow outside token source`);
  assert(!/border-radius:\s*(?:2|3|4|99)px\b/.test(css), `${file}: raw radius outside token source`);
}

assert(
  /\.demo-tool\s*\{[\s\S]*?width:\s*var\(--icon-button-size\)/.test(shared[0].css),
  'shell.css: icon buttons must use a shared size token',
);
assert(
  /\.button\s*\{[\s\S]*?min-height:\s*var\(--control-height\)/.test(shared[1].css),
  'components.css: buttons must use shared control height',
);
assert(
  /\.metric-card__value\s*\{[\s\S]*?font-size:\s*var\(--font-size-kpi\)/.test(shared[1].css),
  'components.css: KPI values must use the KPI token',
);

if (errors.length) {
  console.error(`${errors.length} visual-system error(s)`);
  errors.forEach((message) => console.error(`- ${message}`));
  process.exitCode = 1;
} else {
  console.log('Visual-system static contract validated');
}

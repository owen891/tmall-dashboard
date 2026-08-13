const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', 'frontend', 'ui_demo');
const pagesDir = path.join(root, 'pages');
const required = ['overview', 'products', 'promotion', 'lifecycle', 'reviews', 'data-center', 'settings'];
const errors = [];
const read = (file) => {
  try { return fs.readFileSync(file, 'utf8'); }
  catch { errors.push(`missing file: ${path.relative(root, file)}`); return ''; }
};
const assert = (condition, message) => { if (!condition) errors.push(message); };

for (const name of required) {
  const file = path.join(pagesDir, `${name}.html`);
  const html = read(file);
  const relative = path.relative(root, file);
  if (!html) continue;
  assert(/<title>[^<]+<\/title>/i.test(html), `${relative}: missing title`);
  assert(/<main\b/i.test(html), `${relative}: missing main landmark`);
  assert(new RegExp(`data-page=["']${name}["']`).test(html), `${relative}: wrong data-page`);
  assert(html.includes('../assets/api.js'), `${relative}: missing API client`);
  assert(html.includes('../assets/shell.js'), `${relative}: missing shared shell`);
  assert(!html.includes('api-with-mock-fallback'), `${relative}: mock fallback is forbidden`);
  assert(!/DemoApi\.optional\(/.test(html), `${relative}: optional API fallback is forbidden`);
  assert(!/<svg\b/i.test(html), `${relative}: inline SVG is forbidden`);
  const ids = [...html.matchAll(/(?<![\w-])id=["']([^"']+)["']/gi)].map((match) => match[1]);
  const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
  assert(!duplicates.length, `${relative}: duplicate ids: ${[...new Set(duplicates)].join(', ')}`);
}

const lifecycle = read(path.join(pagesDir, 'lifecycle.html'));
assert(lifecycle.includes("DemoApi.request('/api/lifecycle?limit=2000')"), 'lifecycle: missing API summary request');
assert(!lifecycle.includes('733037806819'), 'lifecycle: embedded product data remains');
assert(lifecycle.includes('../assets/lifecycle-live.js'), 'lifecycle: missing live adapter');
assert(lifecycle.includes('data-lifecycle-list') && lifecycle.includes('data-lifecycle-detail'), 'lifecycle: missing list/detail workflow');

const overview = read(path.join(pagesDir, 'overview.html'));
const overviewAdapter = read(path.join(root, 'assets', 'overview-live.js'));
const apiClient = read(path.join(root, 'assets', 'api.js'));
assert(overview.includes('../assets/overview-live.js'), 'overview: missing live adapter');
assert(apiClient.includes('domainRequest'), 'api client: missing standard-envelope request helper');
assert(overviewAdapter.includes("DemoApi.domainRequest('/api/overview?"), 'overview adapter: KPI must use the standard overview contract');
assert(overviewAdapter.includes('字段缺失'), 'overview adapter: unavailable metrics must disclose missing fields');
assert(overviewAdapter.includes('/api/trend?dim=daily'), 'overview adapter: missing date-filtered trend API request');
assert(overviewAdapter.includes('/api/products?dim=daily'), 'overview adapter: missing date-filtered product API request');
for (const hook of ['data-overview-targets', 'data-overview-anomalies', 'data-overview-funnel', 'data-overview-customers', 'data-overview-report', 'data-overview-events']) {
  assert(overview.includes(hook), `overview: missing workflow hook ${hook}`);
}

const products = read(path.join(pagesDir, 'products.html'));
for (const hook of ['data-products-status', 'data-products-starred', 'data-products-reset', 'data-products-batch', 'data-product-drawer', 'data-products-pagination']) {
  assert(products.includes(hook), `products: missing workflow hook ${hook}`);
}

const promotion = read(path.join(pagesDir, 'promotion.html'));
assert(promotion.includes('../assets/promotion-live.js'), 'promotion: missing live adapter');
assert(!promotion.includes('../assets/promotion.js'), 'promotion: legacy interaction module must not load');
for (const hook of ['data-promotion-alerts', 'data-promotion-tabs', 'data-promotion-drawer', 'data-promotion-drill']) {
  assert(promotion.includes(hook), `promotion: missing workflow hook ${hook}`);
}

const reviews = read(path.join(pagesDir, 'reviews.html'));
assert(reviews.includes('data-reviews-list'), 'reviews: missing action-review surface');
assert(reviews.includes('../assets/reviews-live.js'), 'reviews: missing review API adapter');

const dataCenter = read(path.join(pagesDir, 'data-center.html'));
assert(dataCenter.includes('data-import-file'), 'data-center: missing import surface');
assert(dataCenter.includes('data-import-fields'), 'data-center: missing field-mapping disclosure');
assert(dataCenter.includes('../assets/data-center-live.js'), 'data-center: missing import API adapter');

const settings = read(path.join(pagesDir, 'settings.html'));
assert(settings.includes('Asia/Shanghai'), 'settings: missing default timezone disclosure');
assert(settings.includes('核心指标公式不可'), 'settings: missing formula edit boundary');

const shell = read(path.join(root, 'assets', 'shell.js'));
const shellCss = read(path.join(root, 'assets', 'shell.css'));
for (const value of ['today', 'yesterday', '7d', '30d', '90d', 'custom']) {
  assert(shell.includes(`value="${value}"`), `shell: missing date preset ${value}`);
}
for (const value of ['none', 'previous_period', 'year_over_year']) {
  assert(shell.includes(`value="${value}"`), `shell: missing compare mode ${value}`);
}
assert(shell.includes("DemoApi.request('/api/periods?dim=daily')"), 'shell: date anchor must come from the database');
assert(shell.includes("new CustomEvent('tmall:date-range-change'"), 'shell: missing shared date range event');
assert(shell.includes("new CustomEvent('tmall:refresh'"), 'shell: missing shared refresh event');
assert(shell.includes('data-demo-export'), 'shell: missing functional export control');
assert(shell.includes('data-demo-theme'), 'shell: missing functional theme control');
assert(shell.includes('role="dialog"') && shell.includes('aria-modal="true"'), 'shell: toolbox must expose modal dialog semantics');
assert(shell.includes("event.key === 'Escape'"), 'shell: drawers must close with Escape');
for (const removed of ['health', 'review', 'market', 'keywords', 'traffic', 'postmortem', 'compare', 'manage']) {
  assert(!new RegExp(`\\['${removed}'`).test(shell), `shell: removed module ${removed} remains in navigation`);
}
assert(shell.includes('data-calendar-month="0"') && shell.includes('data-calendar-month="1"'), 'shell: custom picker must render two calendar months');
assert(!shell.includes('data-period="60d"'), 'shell: obsolete 60-day shortcut remains');
assert(!shell.includes('data-period-start') && !shell.includes('data-period-end'), 'shell: native date input demo remains');
assert(/\.toolbox-drawer\s*{[^}]*display:\s*flex/i.test(shellCss), 'shell.css: toolbox drawer must use a flex column shell');
assert(/\.toolbox-drawer\s*{[^}]*overflow:\s*hidden/i.test(shellCss), 'shell.css: toolbox drawer itself must not create page-level scrollbars');
assert(/\.toolbox-drawer__body\s*{[^}]*overflow-y:\s*auto/i.test(shellCss), 'shell.css: toolbox body must own vertical scrolling');
assert(/\.toolbox-drawer__body\s*{[^}]*overflow-x:\s*hidden/i.test(shellCss), 'shell.css: toolbox body must prevent drawer-wide horizontal overflow');
assert(/\.toolbox-drawer\s+\.data-table\s*{[^}]*min-width:\s*100%/i.test(shellCss), 'shell.css: toolbox tables must fit the drawer by default');
assert(/\.demo-tool\s*{[^}]*height:\s*32px/i.test(shellCss), 'shell.css: topbar icon buttons must have fixed height');
assert(/\.demo-tool\s+\.lucide\s*{[^}]*width:\s*18px/i.test(shellCss), 'shell.css: lucide topbar icons must use a consistent size');

for (const adapter of ['overview-live.js', 'products-live.js', 'promotion-live.js', 'lifecycle-live.js']) {
  const source = read(path.join(root, 'assets', adapter));
  assert(source.includes('DemoApi.request('), `assets/${adapter}: must use required API requests`);
  assert(!source.includes('DemoApi.optional('), `assets/${adapter}: fallback is forbidden`);
}

for (const adapter of ['overview-live.js', 'products-live.js', 'promotion-live.js', 'compare-live.js']) {
  const source = read(path.join(root, 'assets', adapter));
  assert(source.includes("addEventListener('tmall:date-range-change'"), `assets/${adapter}: date changes do not refresh data`);
}

const manifestSource = read(path.resolve(root, '..', '..', 'app.py'));
assert(manifestSource.includes("'data_mode': 'api'"), 'app.py: manifest must declare API mode');

if (errors.length) {
  console.error(`${errors.length} UI validation error(s)`);
  errors.forEach((error) => console.error(`- ${error}`));
  process.exitCode = 1;
} else {
  console.log(`${required.length} API-backed pages validated`);
}

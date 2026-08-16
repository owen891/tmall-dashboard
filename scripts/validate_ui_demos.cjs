const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..', 'frontend', 'ui_demo');
const pagesDir = path.join(root, 'pages');
const required = ['overview', 'products', 'promotion', 'lifecycle', 'reviews', 'data-center', 'settings'];
const errors = [];
const read = (file) => {
  try { return fs.readFileSync(file, 'utf8').replace(/\r\n?/g, '\n'); }
  catch { errors.push(`missing file: ${path.relative(root, file)}`); return ''; }
};
const assert = (condition, message) => { if (!condition) errors.push(message); };

for (const name of required) {
  const file = path.join(pagesDir, `${name}.html`);
  const html = read(file);
  const relative = path.relative(root, file);
  if (!html) continue;
  assert(/<title>[^<]+(?:<\/title>|\/title>)/i.test(html), `${relative}: missing title`);
  assert(/<main\b/i.test(html), `${relative}: missing main landmark`);
  assert(new RegExp(`data-page=["']${name}["']`).test(html), `${relative}: wrong data-page`);
  assert(html.includes('../assets/api.js'), `${relative}: missing API client`);
  assert(html.includes('../assets/shell.js'), `${relative}: missing shared shell`);
  assert(!html.includes('api-with-mock-fallback'), `${relative}: mock fallback is forbidden`);
  assert(!/DemoApi\.optional\(/.test(html), `${relative}: optional API fallback is forbidden`);
  assert(!/<svg\b/i.test(html), `${relative}: inline SVG is forbidden`);
  assert(!html.includes('cdn.jsdelivr.net/npm/echarts'), `${relative}: ECharts must not depend on the external CDN`);
  if (html.includes('echarts')) {
    assert(html.includes('../assets/echarts-5.5.1.min.js'), `${relative}: ECharts must use the local bundled asset`);
  }
  assert(!html.includes('unpkg.com/lucide'), `${relative}: Lucide must not depend on the external CDN`);
  assert(html.includes('../assets/lucide-1.8.0.min.js'), `${relative}: Lucide must use the local bundled asset`);
  assert(/data-right-rail/.test(html), `${relative}: missing right-rail contract`);
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
assert(apiClient.includes('renderDataState'), 'api client: missing shared data state renderer');
assert(overviewAdapter.includes("DemoApi.domainRequest('/api/overview?"), 'overview adapter: KPI must use the standard overview contract');
assert(overviewAdapter.includes('字段缺失'), 'overview adapter: unavailable metrics must disclose missing fields');
assert(overviewAdapter.includes('/api/trend?dim=daily'), 'overview adapter: missing date-filtered trend API request');
assert(overviewAdapter.includes('/api/products?dim=daily'), 'overview adapter: missing date-filtered product API request');
for (const hook of ['data-overview-home-targets', 'data-overview-home-actions', 'data-overview-home-anomalies', 'data-overview-home-matrix', 'data-overview-home-products', 'data-overview-home-report']) {
  assert(overview.includes(hook), `overview: missing workflow hook ${hook}`);
}
assert(overview.includes('data-overview-decision'), 'overview: missing decision-first summary region');
assert(overview.includes('data-overview-secondary-kpis'), 'overview: missing secondary KPI disclosure region');
assert(overviewAdapter.includes('data-overview-retry'), 'overview adapter: failed regions must expose local retry');
assert(!overview.includes('overview-legacy'), 'overview: legacy analysis block remains');

const products = read(path.join(pagesDir, 'products.html'));
const productsAdapter = read(path.join(root, 'assets', 'products-live.js'));
for (const hook of ['data-products-status', 'data-products-starred', 'data-products-reset', 'data-products-batch', 'data-products-pagination']) {
  assert(products.includes(hook), `products: missing workflow hook ${hook}`);
}
assert(products.includes('data-products-mobile-summary'), 'products: missing mobile summary workflow hook');
assert(products.includes('data-table-wrap--discoverable'), 'products: missing horizontal scroll affordance hook');
assert(products.includes('../assets/product-detail-dialog.js'), 'products: non-list surfaces must keep the shared product detail dialog dependency');
assert(productsAdapter.includes('new URL(`/products/${id}`, window.location.origin)'), 'products: product rows must open the standalone detail workbench');
assert(productsAdapter.includes("['preset', 'promotion_channel']") && productsAdapter.includes("['tier', 'lifecycle_stage']"), 'products: detail navigation must preserve supported context');
for (const hook of ['data-products-alert', 'data-products-coverage', 'data-products-issues', 'data-products-health', 'data-products-action']) {
  assert(products.includes(hook), `products: missing operations region hook ${hook}`);
}

const promotion = read(path.join(pagesDir, 'promotion.html'));
assert(promotion.includes('../assets/promotion-live.js'), 'promotion: missing live adapter');
assert(!promotion.includes('../assets/promotion.js'), 'promotion: legacy interaction module must not load');
for (const hook of ['data-promotion-alerts', 'data-promotion-tabs', 'data-promotion-dialog', 'data-promotion-drill']) {
  assert(promotion.includes(hook), `promotion: missing workflow hook ${hook}`);
}
const promotionAdapter = read(path.join(root, 'assets', 'promotion-live.js'));
assert(promotionAdapter.includes("DemoApi.domainRequest('/api/promotion?"), 'promotion: primary data must use the promotion domain API');

const reviews = read(path.join(pagesDir, 'reviews.html'));
assert(reviews.includes('data-reviews-list'), 'reviews: missing action-review surface');
assert(reviews.includes('../assets/reviews-live.js'), 'reviews: missing review API adapter');

const dataCenter = read(path.join(pagesDir, 'data-center.html'));
assert(dataCenter.includes('data-import-file'), 'data-center: missing import surface');
assert(dataCenter.includes('data-import-fields'), 'data-center: missing field-mapping disclosure');
assert(dataCenter.includes('../assets/data-center-live.js'), 'data-center: missing import API adapter');
assert(dataCenter.includes('data-governance-disclosure'), 'data-center: governance maps must be collapsible');
assert(dataCenter.includes('aria-current="step"'), 'data-center: current import step must be announced');

const settings = read(path.join(pagesDir, 'settings.html'));
assert(settings.includes('Asia/Shanghai'), 'settings: missing default timezone disclosure');
assert(settings.includes('核心指标公式不可'), 'settings: missing formula edit boundary');
assert(settings.includes('data-settings-savebar'), 'settings: missing sticky save bar');
assert(settings.includes('data-settings-dirty'), 'settings: missing unsaved-change status hook');

const settingsAdapter = read(path.join(root, 'assets', 'settings-live.js'));
assert(!settingsAdapter.includes('window.prompt('), 'settings: template management must use in-page controls, not prompt dialogs');
assert(settingsAdapter.includes('data-settings-dirty'), 'settings adapter: missing dirty-state behavior');
const alertRules = read(path.join(root, 'assets', 'alert-rules.js'));
assert(alertRules.includes('data-alert-rules-retry'), 'alert rules: failed loading must expose local retry');
for (const hook of ['data-template-map-key', 'data-template-map-column', 'data-template-view-columns']) {
  assert(settingsAdapter.includes(hook), `settings: missing structured template control ${hook}`);
}

const shell = read(path.join(root, 'assets', 'shell.js'));
const shellCss = read(path.join(root, 'assets', 'shell.css'));
for (const value of ['today', 'yesterday', '7d', '30d', '90d', 'this_week', 'last_week', 'this_month', 'last_month', 'custom']) {
  assert(shell.includes(`value="${value}"`), `shell: missing date preset ${value}`);
}
for (const value of ['none', 'previous_period', 'year_over_year']) {
  assert(shell.includes(`value="${value}"`), `shell: missing compare mode ${value}`);
}
assert(shell.includes("DemoApi.request('/api/periods?dim=daily')"), 'shell: date anchor must come from the database');
assert(shell.includes("new CustomEvent('tmall:date-range-change'"), 'shell: missing shared date range event');
assert(shell.includes('compareMode'), 'shell: missing compare mode state');
for (const state of ['loading', 'no-data', 'insufficient-data', 'missing-fields', 'calculation-failed', 'source-unavailable', 'partial']) {
  assert(shell.includes(state), `shell: missing data state ${state}`);
}
assert(shell.includes("new CustomEvent('tmall:refresh'"), 'shell: missing shared refresh event');
assert(shell.includes("setAttribute('aria-label', `字段映射："), 'shell: dynamic import mappings must expose row-level accessible names');
assert(shell.includes('data-demo-export'), 'shell: missing functional export control');
assert(shell.includes('data-demo-theme'), 'shell: missing functional theme control');
assert(shell.includes('<dialog class="toolbox-dialog" data-toolbox-dialog') && shell.includes('data-modal-kind="flow"'), 'shell: toolbox must expose native modal dialog semantics');
assert(shell.includes("event.key === 'Escape'"), 'shell: drawers must close with Escape');
for (const removed of ['health', 'review', 'market', 'keywords', 'traffic', 'postmortem', 'compare', 'manage']) {
  assert(!new RegExp(`\\['${removed}'`).test(shell), `shell: removed module ${removed} remains in navigation`);
}
assert(shell.includes('data-calendar-month="0"') && shell.includes('data-calendar-month="1"'), 'shell: custom picker must render two calendar months');
assert(shell.includes("draftStart ? formatDate(draftStart) : state.startDate") && shell.includes("draftStart ? '' : state.endDate"), 'shell: calendar must render the pending custom range instead of the previously applied range');
assert(shell.includes('renderCalendar();') && shell.includes('请选择结束日期'), 'shell: choosing a custom start date must immediately refresh the calendar and prompt for an end date');
assert(shell.includes("event.stopPropagation();") && shell.includes("event.target.closest('[data-calendar-date]')"), 'shell: calendar date clicks must not be mistaken for outside clicks after the calendar rerenders');
assert(shell.includes('当前范围：') && shell.includes('点击任意日期重新选择'), 'shell: an applied custom range must have an unambiguous reopening prompt');
assert(shell.includes("event.key !== 'Escape'") && shell.includes('trigger.focus()'), 'shell: the custom picker must close and return focus on Escape');
assert(shell.includes("closePopover(true)") && shell.includes("trigger.addEventListener('click'"), 'shell: closing the custom picker from its trigger must clear a half-selected range');
assert(shell.includes("if (resetDraft) {\n      resetDraftRange();\n      presetSelect.value = state.preset;"), 'shell: cancelling a custom range must restore the previously applied shortcut');
assert(shell.includes("if (preset === 'custom') { openPopover(); return; }\n    closePopover(true);"), 'shell: selecting a shortcut must discard a half-selected custom range');
assert(shell.includes("window.addEventListener('popstate'"), 'shell: browser history navigation must restore the active date range');
assert(!shell.includes('data-period="60d"'), 'shell: obsolete 60-day shortcut remains');
assert(!shell.includes('data-period-start') && !shell.includes('data-period-end'), 'shell: native date input demo remains');
assert(/\.toolbox-dialog\s*{[^}]*max-height:\s*calc\(100dvh - 24px\)/i.test(shellCss), 'shell.css: toolbox dialog must be bounded by the viewport');
assert(/\.toolbox-dialog__body\s*{[^}]*overflow-y:\s*auto/i.test(shellCss), 'shell.css: toolbox body must own vertical scrolling');
assert(/\.toolbox-dialog__body\s*{[^}]*overflow-x:\s*hidden/i.test(shellCss), 'shell.css: toolbox body must prevent dialog-wide horizontal overflow');
assert(/\.toolbox-dialog\s+\.data-table\s*{[^}]*min-width:\s*100%/i.test(shellCss), 'shell.css: toolbox tables must fit the dialog by default');
assert(/\.demo-tool\s*{[^}]*height:\s*var\(--icon-button-size\)/i.test(shellCss), 'shell.css: topbar icon buttons must use the shared size token');
assert(/\.demo-tool\s+\.lucide\s*{[^}]*width:\s*var\(--icon-control\)/i.test(shellCss), 'shell.css: Lucide topbar icons must use the shared icon token');

for (const adapter of ['overview-live.js', 'products-live.js', 'promotion-live.js', 'lifecycle-live.js']) {
  const source = read(path.join(root, 'assets', adapter));
  assert(source.includes('DemoApi.request(') || source.includes('DemoApi.domainRequest('), `assets/${adapter}: must use required API requests`);
  assert(!source.includes('DemoApi.optional('), `assets/${adapter}: fallback is forbidden`);
}

for (const adapter of ['overview-live.js', 'products-live.js', 'promotion-live.js', 'lifecycle-live.js', 'reviews-live.js', 'data-center-live.js', 'settings-live.js', 'goals-live.js']) {
  const source = read(path.join(root, 'assets', adapter));
  assert(source.includes('DemoApi.renderDataState('), `assets/${adapter}: must render shared data states`);
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

const visualGate = spawnSync(process.execPath, [path.resolve(__dirname, 'validate_visual_system.cjs')], { stdio: 'inherit' });
if (visualGate.status !== 0) process.exitCode = 1;

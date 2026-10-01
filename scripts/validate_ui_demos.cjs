const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..', 'frontend', 'ui_demo');
const pagesDir = path.join(root, 'pages');
const required = ['overview', 'products', 'promotion', 'new-products', 'lifecycle', 'reviews', 'data-center', 'settings', 'creative-board'];
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
    assert(html.includes('../assets/echarts-custom.min.js'), `${relative}: ECharts must use the local bundled asset`);
  }
  assert(!html.includes('unpkg.com/lucide'), `${relative}: Lucide must not depend on the external CDN`);
  assert(html.includes('../assets/lucide-custom.min.js'), `${relative}: Lucide must use the local bundled asset`);
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
for (const hook of ['data-overview-home-targets', 'data-overview-home-matrix', 'data-overview-operations-center', 'data-operations-feed', 'data-operations-calendar-grid']) {
  assert(overview.includes(hook), `overview: missing workflow hook ${hook}`);
}
const operationsCenter = read(path.join(root, 'assets', 'operations-center.js'));
assert(overview.includes('../assets/operations-center.js'), 'overview: missing operations center adapter');
assert(!overview.includes('../assets/action-calendar.js'), 'overview: legacy action calendar adapter remains');
assert(!overview.includes('../assets/action-log.js'), 'overview: legacy action log adapter remains');
for (const hook of ['data-operations-filter', 'data-operations-refresh', 'data-operations-calendar-prev', 'data-operations-calendar-next', 'data-operations-calendar-today']) {
  assert(overview.includes(hook), `operations center: missing ${hook}`);
}
for (const contract of ['/api/actions?limit=200', '/api/actions/calendar?', '/api/logs?limit=12', 'Promise.allSettled', 'mergeActions', 'buildAnomalyItem', 'tmall:overview-anomalies-ready']) {
  assert(operationsCenter.includes(contract), `operations center: missing ${contract}`);
}
assert(operationsCenter.includes("setAttribute('aria-label'"), 'operations center: calendar count must expose aria-label');
// 4-4：日历月初/月末的补位格子原来既无文本也无 aria-label，读屏只能念出「按钮」。
assert(operationsCenter.includes("setAttribute('aria-label', '空白格')"), 'operations center: calendar placeholder cells must expose an accessible name');
assert(operationsCenter.includes('calendarToken'), 'operations center: calendar requests need a race token');
assert(overview.includes('data-overview-decision'), 'overview: missing decision-first summary region');
// 批次 1/2（首屏决策区）已把「更多经营指标」从 <details data-overview-secondary-kpis> 改为
// 决策区内的 .overview-decision__secondary，原断言指向已不存在的旧标记，按现状更新。
assert(overview.includes('overview-decision__secondary'), 'overview: missing secondary KPI region');
assert(overviewAdapter.includes('data-overview-retry'), 'overview adapter: failed regions must expose local retry');
assert(!overview.includes('overview-legacy'), 'overview: legacy analysis block remains');

const products = read(path.join(pagesDir, 'products.html'));
const productsAdapter = read(path.join(root, 'assets', 'products-live.js'));
for (const hook of ['data-products-status', 'data-products-starred', 'data-products-reset', 'data-products-batch', 'data-products-pagination']) {
  assert(products.includes(hook), `products: missing workflow hook ${hook}`);
}
assert(products.includes('data-products-mobile-summary'), 'products: missing mobile summary workflow hook');
assert(products.includes('ui-table-wrap--discoverable'), 'products: missing horizontal scroll affordance hook');
assert(products.includes('../assets/product-detail-dialog.js'), 'products: non-list surfaces must keep the shared product detail dialog dependency');
assert(productsAdapter.includes('new URL(`/products/${id}`, window.location.origin)'), 'products: product rows must open the standalone detail workbench');
assert(productsAdapter.includes("['preset', 'promotion_channel']") && productsAdapter.includes("['tier', 'lifecycle_stage']"), 'products: detail navigation must preserve supported context');

const promotion = read(path.join(pagesDir, 'promotion.html'));
assert(promotion.includes('../assets/promotion-live.js'), 'promotion: missing live adapter');
assert(!promotion.includes('../assets/promotion.js"') && !promotion.includes("../assets/promotion.js'"), 'promotion: legacy interaction module must not load');
assert(!fs.existsSync(path.join(root, 'assets', 'promotion.js')), 'promotion: legacy interaction module must be removed');
for (const hook of ['data-promotion-alerts', 'data-promotion-tabs', 'data-promotion-dialog-template', 'data-promotion-drill']) {
  assert(promotion.includes(hook), `promotion: missing workflow hook ${hook}`);
}
const promotionAdapter = read(path.join(root, 'assets', 'promotion-live.js'));
assert(promotionAdapter.includes("DemoApi.domainRequest('/api/promotion?"), 'promotion: primary data must use the promotion domain API');

const newProducts = read(path.join(pagesDir, 'new-products.html'));
const newProductsAdapter = read(path.join(root, 'assets', 'new-products-live.js'));
for (const hook of ['data-promotion-new-funnel', 'data-promotion-new-kpi', 'data-promotion-new-launch-body', 'data-promotion-new-body', 'data-promotion-structure-template', 'data-new-products-image-dialog', 'data-new-products-image-preview']) {
  assert(newProducts.includes(hook), `new-products: missing workflow hook ${hook}`);
}
assert(newProducts.includes('../assets/creative-board.css?'), 'new-products: missing creative detail styles');
assert(newProducts.includes('../assets/new-products-live.js'), 'new-products: missing live adapter');
assert(newProductsAdapter.includes('/api/promotion/new-products?'), 'new-products: missing API request');
assert(newProductsAdapter.includes('/api/creative-board?'), 'new-products: missing inline creative API request');
assert(newProductsAdapter.includes('renderCreativePanel'), 'new-products: missing inline creative renderer');
assert(newProductsAdapter.includes('data-new-products-image'), 'new-products: missing creative preview hook');
assert(!newProductsAdapter.includes('window.location.href = `/creative-board?'), 'new-products: creative tab must not navigate away');
assert(newProductsAdapter.includes("addEventListener('tmall:date-range-change'"), 'new-products: missing date range listener');
assert(newProducts.includes('data-promotion-new-launch-toggle'), 'new-products: missing launch expand control');
assert(newProductsAdapter.includes('total_product_count'), 'new-products: missing complete launch count');
assert(newProductsAdapter.includes('promotion_coverage'), 'new-products: missing launch coverage metric');
assert(newProductsAdapter.includes('launchesExpanded'), 'new-products: missing launch expand state');
assert(newProductsAdapter.includes('cb-creative-table'), 'new-products: missing creative table');
assert(newProductsAdapter.includes('data-new-products-creative-sort'), 'new-products: missing creative sort controls');
assert(newProductsAdapter.includes("creativeSort: { key: 'clicks', direction: 'desc' }"), 'new-products: missing default creative sort');
assert(read(path.join(root, 'assets', 'creative-board.css')).includes('.cb-creative-table'), 'new-products: missing creative table styles');
assert(!promotion.includes('new-products'), 'promotion: new-products must be a standalone page');

const creativeBoard = read(path.join(pagesDir, 'creative-board.html'));
const creativeBoardAdapter = read(path.join(root, 'assets', 'creative-board-live.js'));
const creativeBoardStyles = read(path.join(root, 'assets', 'creative-board.css'));
assert(creativeBoard.includes('data-page="creative-board"'), 'creative-board: wrong data-page');
assert(creativeBoard.includes('../assets/creative-board-live.js'), 'creative-board: missing live adapter');
assert(creativeBoardAdapter.includes("DemoApi.domainRequest('/api/creative-board'") , 'creative-board: missing API request');
assert(creativeBoardStyles.includes('@media (max-width: 900px)'), 'creative-board: missing narrow layout contract');
assert(creativeBoardStyles.includes('@media (max-width: 560px)'), 'creative-board: missing mobile layout contract');

const reviews = read(path.join(pagesDir, 'reviews.html'));
assert(reviews.includes('data-reviews-list'), 'reviews: missing action-review surface');
assert(reviews.includes('../assets/reviews-live.js'), 'reviews: missing review API adapter');

const dataCenter = read(path.join(pagesDir, 'data-center.html'));
assert(dataCenter.includes('data-import-file'), 'data-center: missing import surface');
assert(dataCenter.includes('data-import-fields'), 'data-center: missing field-mapping disclosure');
assert(dataCenter.includes('../assets/pages/data-center/import-workflow.js'), 'data-center: missing import workflow module');
assert(dataCenter.includes('../assets/pages/data-center/identity-review.js'), 'data-center: missing identity review module');
assert(dataCenter.includes('../assets/pages/data-center/capability-map.js'), 'data-center: missing capability map module');
assert(dataCenter.includes('../assets/pages/data-center/page-capabilities.js'), 'data-center: missing page capabilities module');
assert(dataCenter.includes('data-identity-review') && dataCenter.includes('data-identity-rows'), 'data-center: missing product identity review surface');
assert(dataCenter.includes('data-governance-disclosure'), 'data-center: governance maps must be collapsible');
assert(dataCenter.includes('aria-current="step"'), 'data-center: current import step must be announced');
const dataCenterAdapter = read(path.join(root, 'assets', 'pages', 'data-center', 'identity-review.js'));
assert(dataCenterAdapter.includes("/api/product-identities?status=unresolved"), 'data-center: identity queue must use the review API');
assert(dataCenterAdapter.includes("/api/product-identities/${encodeURIComponent(item.external_product_id)}/resolve"), 'data-center: identity resolution must use the audited API');
assert(dataCenterAdapter.includes("/api/products?"), 'data-center: identity review must use existing product master candidates');

const settings = read(path.join(pagesDir, 'settings.html'));
// 4-8：compare / manage 已退役（页面文件删除，路由保留 302 到 /reviews 与 /settings）。
// 原此处对 compare.html / compare-live.js 的断言随之移除。

assert(settings.includes('Asia/Shanghai'), 'settings: missing default timezone disclosure');
assert(settings.includes('核心指标公式不可'), 'settings: missing formula edit boundary');
assert(settings.includes('data-settings-savebar'), 'settings: missing sticky save bar');
assert(settings.includes('data-scan-environment'), 'settings: missing scan environment disclosure');
assert(settings.includes('IMPORT_SCAN_ALLOWED_ROOTS'), 'settings: missing scan root boundary disclosure');

const settingsAdapter = read(path.join(root, 'assets', 'settings-live.js'));
assert(!settingsAdapter.includes('window.prompt('), 'settings: template management must use in-page controls, not prompt dialogs');
assert(settingsAdapter.includes('data-settings-dirty'), 'settings adapter: missing dirty-state behavior');
const alertRules = read(path.join(root, 'assets', 'alert-rules.js'));
assert(alertRules.includes('data-alert-rules-retry'), 'alert rules: failed loading must expose local retry');
for (const hook of ['data-template-map-key', 'data-template-map-column']) {
  assert(settingsAdapter.includes(hook), `settings: missing import mapping control ${hook}`);
}
assert(settings.includes('导入规则'), 'settings: missing import rules workspace');
assert(settings.includes('href="/products"'), 'settings: missing products template ownership link');
assert(!settingsAdapter.includes('data-settings-view-field-selector'), 'settings: duplicate product view editor remains');
assert(!settingsAdapter.includes('view_templates'), 'settings: product view templates must remain on products page');
assert(settingsAdapter.includes('mapping_templates: clone(templateDraft.mapping_templates)'), 'settings: import rules must save a minimal mapping payload');
const shell = read(path.join(root, 'assets', 'shell.js'));
const shellCss = read(path.join(root, 'assets', 'shell.css'));
const dateRangeStore = read(path.join(root, 'assets', 'runtime', 'date-range-store.js'));
for (const value of ['today', 'yesterday', '7d', '30d', '90d', 'this_week', 'last_week', 'this_month', 'last_month', 'custom']) {
  assert(shell.includes(`value="${value}"`), `shell: missing date preset ${value}`);
}
for (const value of ['none', 'previous_period', 'year_over_year']) {
  assert(shell.includes(`value="${value}"`), `shell: missing compare mode ${value}`);
}
assert(shell.includes('runtime/date-range-store.js'), 'shell: missing date-range-store module bootstrap');
assert(shell.includes('createDateRangeStore({'), 'shell: date range store must be wired with explicit deps');
assert(dateRangeStore.includes("DemoApi.request('/api/periods?dim=daily')"), 'date-range-store: date anchor must come from the database');
assert(dateRangeStore.includes("new CustomEvent('tmall:date-range-change'"), 'date-range-store: missing shared date range event');
assert(dateRangeStore.includes('compareMode'), 'date-range-store: missing compare mode state');
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
assert(dateRangeStore.includes("draftStart ? formatDate(draftStart) : state.startDate") && dateRangeStore.includes("draftStart ? '' : state.endDate"), 'date-range-store: calendar must render the pending custom range instead of the previously applied range');
assert(dateRangeStore.includes('renderCalendar();') && dateRangeStore.includes('请选择结束日期'), 'date-range-store: choosing a custom start date must immediately refresh the calendar and prompt for an end date');
assert(dateRangeStore.includes("event.stopPropagation();") && dateRangeStore.includes("event.target.closest('[data-calendar-date]')"), 'date-range-store: calendar date clicks must not be mistaken for outside clicks after the calendar rerenders');
assert(dateRangeStore.includes('当前范围：') && dateRangeStore.includes('点击任意日期重新选择'), 'date-range-store: an applied custom range must have an unambiguous reopening prompt');
assert(dateRangeStore.includes("event.key !== 'Escape'") && dateRangeStore.includes('trigger.focus()'), 'date-range-store: the custom picker must close and return focus on Escape');
assert(dateRangeStore.includes("closePopover(true)") && dateRangeStore.includes("trigger.addEventListener('click'"), 'date-range-store: closing the custom picker from its trigger must clear a half-selected range');
assert(dateRangeStore.includes("if (resetDraft) {\n      resetDraftRange();\n      presetSelect.value = state.preset;") || dateRangeStore.includes("if (resetDraft) {\n        resetDraftRange();\n        presetSelect.value = state.preset;"), 'date-range-store: cancelling a custom range must restore the previously applied shortcut');
assert(dateRangeStore.includes("if (preset === 'custom') { openPopover(); return; }\n    closePopover(true);") || dateRangeStore.includes("if (preset === 'custom') { openPopover(); return; }\n      closePopover(true);"), 'date-range-store: selecting a shortcut must discard a half-selected custom range');
assert(dateRangeStore.includes("addEventListener('popstate'"), 'date-range-store: browser history navigation must restore the active date range');
assert(!shell.includes('data-period="60d"'), 'shell: obsolete 60-day shortcut remains');
assert(!shell.includes('data-period-start') && !shell.includes('data-period-end'), 'shell: native date input demo remains');
assert(/\.toolbox-dialog\s*{[^}]*max-height:\s*calc\(100dvh - 24px\)/i.test(shellCss), 'shell.css: toolbox dialog must be bounded by the viewport');
assert(/\.toolbox-dialog__body\s*{[^}]*overflow-y:\s*auto/i.test(shellCss), 'shell.css: toolbox body must own vertical scrolling');
assert(/\.toolbox-dialog__body\s*{[^}]*overflow-x:\s*hidden/i.test(shellCss), 'shell.css: toolbox body must prevent dialog-wide horizontal overflow');
assert(/\.toolbox-dialog\s+\.ui-data-table\s*\{[^}]*min-width:\s*100%/i.test(shellCss), 'shell.css: toolbox tables must fit the dialog by default');
assert(/\.demo-tool\s*{[^}]*height:\s*var\(--icon-button-size\)/i.test(shellCss), 'shell.css: topbar icon buttons must use the shared size token');
assert(/\.demo-tool\s+\.lucide\s*{[^}]*width:\s*var\(--icon-control\)/i.test(shellCss), 'shell.css: Lucide topbar icons must use the shared icon token');

const dataCenterModules = ['import-workflow.js', 'identity-review.js', 'capability-map.js', 'page-capabilities.js'];

for (const adapter of ['overview-live.js', 'products-live.js', 'promotion-live.js', 'lifecycle-live.js', 'creative-board-live.js', ...dataCenterModules.map((name) => `pages/data-center/${name}`)]) {
  const source = read(path.join(root, 'assets', adapter));
  assert(source.includes('DemoApi.request(') || source.includes('DemoApi.domainRequest('), `assets/${adapter}: must use required API requests`);
  assert(!source.includes('DemoApi.optional('), `assets/${adapter}: fallback is forbidden`);
}

// 4-3：区域级空态/错误态/加载态必须走共享渲染器；analysis / data-collection
// 曾手拼 <div>，已迁移。表格单元格内的 <td colspan> 占位行是表格语义的合法形态，
// 不在本断言范围（下方有专项防线禁止其逃逸出表格语义）。
for (const adapter of ['overview-live.js', 'products-live.js', 'promotion-live.js', 'lifecycle-live.js', 'reviews-live.js', 'pages/data-center/import-workflow.js', 'pages/data-center/capability-map.js', 'pages/data-center/page-capabilities.js', 'settings-live.js', 'goals-live.js', 'analysis-live.js', 'data-collection-live.js']) {
  const source = read(path.join(root, 'assets', adapter));
  assert(source.includes('DemoApi.renderDataState('), `assets/${adapter}: must render shared data states`);
}

for (const adapter of ['overview-live.js', 'products-live.js', 'promotion-live.js']) {
  const source = read(path.join(root, 'assets', adapter));
  assert(source.includes("addEventListener('tmall:date-range-change'"), `assets/${adapter}: date changes do not refresh data`);
}

// 4-3 防线：状态 UI 不允许手拼 —— 自定义空态类与内联样式的「加载失败/暂无」
// 块一律禁止（表格 <td> 占位除外，上面注释已约定）。
for (const file of fs.readdirSync(path.join(root, 'assets')).filter((f) => f.endsWith('.js'))) {
  const source = read(path.join(root, 'assets', file));
  assert(!source.includes('analysis-empty'), `assets/${file}: hand-built analysis-empty state is forbidden; use DemoApi.renderDataState`);
  assert(!/<div(?![^>]*ui-empty-state)[^>]*style="[^"]*padding:\s*\d+px[^"]*">(加载失败|暂无)/.test(source), `assets/${file}: inline-styled state div is forbidden; use DemoApi.renderDataState`);
}

if (errors.length) {
  console.error(`${errors.length} UI validation error(s)`);
  errors.forEach((error) => console.error(`- ${error}`));
  process.exitCode = 1;
} else {
  console.log(`${required.length} API-backed pages validated`);
}

const visualGate = spawnSync(process.execPath, [path.resolve(__dirname, 'validate_visual_system.cjs')], { stdio: 'inherit' });
if (visualGate.status !== 0) process.exitCode = 1;

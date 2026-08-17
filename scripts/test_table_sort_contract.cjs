const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const controls = fs.readFileSync(path.join(root, 'frontend', 'ui_demo', 'assets', 'table-controls.js'), 'utf8');
const products = fs.readFileSync(path.join(root, 'frontend', 'ui_demo', 'assets', 'products-live.js'), 'utf8');
const components = fs.readFileSync(path.join(root, 'frontend', 'ui_demo', 'assets', 'components.css'), 'utf8');
const productsPage = fs.readFileSync(path.join(root, 'frontend', 'ui_demo', 'pages', 'products.html'), 'utf8');
const lifecyclePage = fs.readFileSync(path.join(root, 'frontend', 'ui_demo', 'pages', 'lifecycle.html'), 'utf8');
const overview = fs.readFileSync(path.join(root, 'frontend', 'ui_demo', 'pages', 'overview.html'), 'utf8');
const overviewLive = fs.readFileSync(path.join(root, 'frontend', 'ui_demo', 'assets', 'overview-live.js'), 'utf8');
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

assert(/dataset\.sortValue/.test(controls), 'table controls must honor explicit data-sort-value');
assert(/selectedOptions/.test(controls), 'table controls must sort selects by the selected option');
assert(/querySelector\(['"]input/.test(controls), 'table controls must sort editable inputs by their current value');
assert(/createElement\('colgroup'\)/.test(controls), 'sticky table headers must preserve original column widths with a colgroup');
assert(/\.table-sticky-head__table th\.num \.table-sort-button \{ justify-content: flex-end; text-align: right; \}/.test(components), 'sticky numeric headers must align with right-aligned numeric table cells');
assert(/table-sticky-scrollbar/.test(controls), 'table controls must provide a shared sticky horizontal scrollbar');
assert(/table-sticky-scrollbar__range/.test(controls), 'sticky horizontal scrolling must expose a usable range control instead of only a native scrollbar');
assert(/new ResizeObserver/.test(controls), 'sticky headers must resync after dynamic column-width changes');
assert(/function getStickyViewport/.test(controls), 'sticky controls must use the dialog viewport when a table is inside a modal');
assert(/viewport\.bottom/.test(controls), 'sticky controls must anchor to the active viewport bottom');
assert(/is-table-sticky-footer/.test(controls), 'table controls must promote pagination while its table is in view');
assert(/findAssociatedControls/.test(controls), 'server-rendered and generated pagination must use the same sticky-footer behavior');
assert(/health\.sortValue/.test(products), 'product health must expose a stable business sort value');
assert(/dataset\.sortValue/.test(products), 'product cells must expose a stable sort value');
assert(!/healthReason\.textContent/.test(products), 'product table health cells must not render secondary reason text');
assert(/product-title__link/.test(products), 'product title must provide the detail drill-down entry');
assert(!/action\.textContent = '操作'/.test(products), 'product table must not render a separate action column');
assert(/function classificationValues/.test(products), 'product dropdowns must use a complete classification value source');
assert(/data-field-key="health"/.test(components), 'product health column must have a compact width rule');
assert(/data-field-key="tier"/.test(components) && /data-field-key="style"/.test(components), 'product classification columns must have compact width rules');
assert(/class="[^"]*table-controls[^"]*" data-products-pagination/.test(productsPage), 'product pagination must use the shared compact controls layout');
assert(/class="[^"]*table-controls[^"]*" data-lifecycle-pagination/.test(lifecyclePage), 'lifecycle pagination must use the shared compact controls layout');
assert(productsPage.indexOf('data-products-page-summary') < productsPage.indexOf('class="table-controls__nav"'), 'product page summary must sit outside the right-aligned controls group');
assert(lifecyclePage.indexOf('data-lifecycle-page-summary') < lifecyclePage.indexOf('class="table-controls__nav"'), 'lifecycle page summary must sit outside the right-aligned controls group');
assert(/nav\.append\(previous, next\)/.test(controls), 'shared table controls must keep only previous and next in the right-aligned navigation group');
assert(/controls\.append\(summary, pageSizeLabel, nav\)/.test(controls), 'shared table controls must place the page summary before the right-aligned controls');
assert(/data-page-size="7"/.test(overview) && /data-page-sizes="7,14,30,50,100"/.test(overview), 'daily matrix must default to seven daily rows with explicit page-size choices');
assert(/data-overview-matrix-columns-open/.test(overview) && /data-overview-matrix-columns-dialog/.test(overview), 'daily matrix must expose field settings');
assert(/field-selector\.js/.test(overview), 'daily matrix field settings must use the shared field selector');
assert(/matrixVisibleColumns/.test(overviewLive) && /renderMatrixHeader/.test(overviewLive), 'daily matrix must render its visible columns dynamically');

console.log('table sort contract: PASS');

# Product Detail Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing product detail route into a token-consistent third-level workbench and make product-list detail actions navigate to it while preserving the existing detail API and shared preview dialog.

**Architecture:** Keep `/api/products/<product_id>/detail` as the single data contract. The standalone page owns page layout, tabs, back navigation, date-range loading, export, and action creation; the reusable dialog remains a compact preview for lifecycle/promotion surfaces and links to the workbench.

**Tech Stack:** Flask static demo routes, semantic HTML, existing CSS custom properties, vanilla JavaScript, Playwright smoke gates, Python `unittest` contracts.

---

### Task 1: Lock the navigation contract

**Files:**
- Modify: `tests/test_navigation_contract.py`
- Modify: `frontend/ui_demo/assets/products-live.js`

- [ ] **Step 1: Add a source contract for default list-to-detail navigation**

Add a test that reads `products-live.js` and asserts the list handler builds a `/products/<id>` URL through `DemoNavigation` or `location.assign`, while the shared dialog remains referenced by `product-detail-dialog.js` for non-list previews.

- [ ] **Step 2: Run the focused contract test and confirm it fails**

Run: `python -m unittest tests.test_navigation_contract -v`

Expected: the new navigation assertion fails against the current `window.ProductDetailDialog.open(...)` list handler.

- [ ] **Step 3: Navigate from the product list to the standalone page**

Replace `openProductDetail` in `products-live.js` with:

```js
async function openProductDetail(item) {
  const id = encodeURIComponent(productId(item));
  const url = new URL(`/products/${id}`, window.location.origin);
  const params = new URLSearchParams(window.location.search);
  ['start', 'end', 'preset', 'compare', 'tier', 'lifecycle_stage', 'promotion_channel'].forEach((key) => {
    const value = params.get(key);
    if (value) url.searchParams.set(key, value);
  });
  window.location.assign(`${url.pathname}${url.search}`);
}
```

Update both desktop and mobile detail button listeners to call `openProductDetail(item)` without the dialog trigger argument. Leave `product-detail-dialog.js` untouched so promotion/lifecycle quick previews continue to work.

- [ ] **Step 4: Run the focused contract test and confirm it passes**

Run: `python -m unittest tests.test_navigation_contract -v`

Expected: PASS, including the existing shell/navigation assertions.

- [ ] **Step 5: Commit the navigation slice**

```bash
git add tests/test_navigation_contract.py frontend/ui_demo/assets/products-live.js
git commit -m "feat: open product details as standalone workbench"
```

### Task 2: Build the standalone workbench layout

**Files:**
- Modify: `frontend/ui_demo/pages/product-detail.html`
- Modify: `frontend/ui_demo/assets/components.css`

- [ ] **Step 1: Add semantic workbench regions while preserving existing data hooks**

Keep all existing `data-product-detail-*` selectors used by `product-detail-live.js`. Restructure the page into:

```html
<div class="product-workbench__crumb" data-product-detail-breadcrumb></div>
<header class="product-workbench__header">...</header>
<section class="metric-grid product-workbench__kpis">...</section>
<nav class="product-workbench__tabs" role="tablist">...</nav>
<section data-product-detail-panel="overview">...</section>
<section data-product-detail-panel="trend" hidden>...</section>
<section data-product-detail-panel="lifecycle" hidden>...</section>
<section data-product-detail-panel="actions" hidden>...</section>
<section data-product-detail-panel="evidence" hidden>...</section>
```

The header must include product identity, a back link with `data-product-detail-back`, export, and create-action controls. Use the existing API data hooks for identity, KPI values, lifecycle values, trend table, history, comparison, evidence, actions, and action form.

- [ ] **Step 2: Add token-based desktop and mobile layout rules**

Add `.product-workbench*` styles to `components.css` using only existing variables: `--surface-page`, `--surface-base`, `--border-default`, `--text-primary`, `--text-secondary`, `--brand`, `--brand-tint`, `--info`, and `--success`. Use a two-column overview grid above 900px, one column below 900px, two KPI columns below 520px, and no fixed-width element wider than its parent.

- [ ] **Step 3: Run the static frontend validation**

Run: `node scripts/validate_ui_demos.cjs`

Expected: PASS with no missing asset or duplicate-id errors.

### Task 3: Wire tabs, back navigation, and page state

**Files:**
- Modify: `frontend/ui_demo/assets/product-detail-live.js`
- Modify: `tests/test_navigation_contract.py`

- [ ] **Step 1: Add tab behavior without changing API loading**

Add a small controller that reads `[data-product-detail-tab]`, toggles `aria-selected`, sets `hidden` on matching `[data-product-detail-panel]`, and mirrors the active tab in `location.hash`. On load, use a valid hash or default to `overview`.

```js
function selectDetailTab(tab) {
  const allowed = new Set(['overview', 'trend', 'lifecycle', 'actions', 'evidence']);
  const active = allowed.has(tab) ? tab : 'overview';
  document.querySelectorAll('[data-product-detail-tab]').forEach((button) => {
    const selected = button.dataset.productDetailTab === active;
    button.setAttribute('aria-selected', String(selected));
  });
  document.querySelectorAll('[data-product-detail-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.productDetailPanel !== active;
  });
  history.replaceState(null, '', `${location.pathname}${location.search}#${active}`);
}
```

- [ ] **Step 2: Preserve list context on back**

Set the back link to `history.back()` only when `document.referrer` is the same-origin `/products` route; otherwise use `/products`. This restores the exact filter and page query when coming from the list without breaking direct links.

- [ ] **Step 3: Keep the date range and export synchronized**

Initialize the page range from `start`/`end` query parameters through the existing shell state, then keep the current `tmall:date-range-change` listener. Ensure the export link is rebuilt with the same range after every load.

- [ ] **Step 4: Add navigation source assertions**

Assert in `tests/test_navigation_contract.py` that the standalone page contains `data-product-detail-tab`, `data-product-detail-panel`, `data-product-detail-back`, and the required navigation helper script.

- [ ] **Step 5: Run focused tests**

Run: `python -m unittest tests.test_navigation_contract tests.test_product_detail_api -v`

Expected: PASS.

- [ ] **Step 6: Commit the workbench slice**

```bash
git add frontend/ui_demo/pages/product-detail.html frontend/ui_demo/assets/components.css frontend/ui_demo/assets/product-detail-live.js tests/test_navigation_contract.py
git commit -m "feat: add token-based product detail workbench"
```

### Task 4: Browser verification

**Files:**
- Test: `scripts/browser_prd_gates.cjs`
- Test: `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: Run the existing frontend gates**

Run: `node scripts/validate_ui_demos.cjs` and `python -m unittest tests.test_navigation_contract tests.test_product_detail_api -v`.

Expected: both commands exit 0.

- [ ] **Step 2: Smoke the page at desktop and mobile widths**

Start the local app, then run the existing Playwright gate against `/products/DEMO-003?start=2026-04-01&end=2026-04-30` at 1366px and 390px. Verify the page has no horizontal overflow, exactly one active tab, visible loading/error states, and an export link containing `start` and `end`.

- [ ] **Step 3: Run the full regression set**

Run: `python -m unittest discover -s tests -p 'test_*.py'`

Expected: all tests pass; report any pre-existing failures separately instead of changing unrelated files.

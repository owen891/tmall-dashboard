# Product Operations Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the product operations page prioritize explainable exceptions and next actions while preserving the existing product list workflows and detail API.

**Architecture:** Keep `/products` as the primary list route. Extend the existing product API view model with explainable coverage/status fields already available from the backend, render an alert summary and actionable issue panel beside the list, and navigate list rows to the standalone product detail workbench while preserving date/filter context. Reuse existing tokens, field-selector, shell, and action APIs.

**Tech Stack:** Flask static demo routes, vanilla JavaScript, existing CSS custom properties, ECharts/Lucide assets, Python `unittest`, Node UI validation and Playwright smoke scripts.

---

### Task 1: Lock the current behavior and navigation contract

**Files:**
- Modify: `tests/test_navigation_contract.py`
- Modify: `tests/test_products_prd.py`
- Modify: `frontend/ui_demo/assets/products-live.js`

- [ ] **Step 1: Add source assertions for list/detail navigation and new first-screen hooks**

Assert that `products-live.js` builds a `/products/<id>` URL, forwards `start` and `end`, and that `products.html` contains hooks for an alert summary, coverage panel, issue list, and actionable status cell.

- [ ] **Step 2: Run focused tests and confirm the new assertions fail**

Run: `python -m unittest tests.test_navigation_contract tests.test_products_prd -v`

Expected: the new hooks/navigation assertions fail before implementation.

- [ ] **Step 3: Implement context-preserving navigation**

Replace the list-row preview-only handler with a standalone navigation helper that forwards `start`, `end`, `preset`, `tier`, `lifecycle_stage`, and `promotion_channel`; retain `product-detail-dialog.js` for non-list previews.

- [ ] **Step 4: Run focused tests and confirm they pass**

Run: `python -m unittest tests.test_navigation_contract tests.test_products_prd -v`

Expected: PASS.

### Task 2: Add explainable alert and coverage data to the page

**Files:**
- Modify: `frontend/ui_demo/pages/products.html`
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/components.css`

- [ ] **Step 1: Add semantic regions**

Add `data-products-alert`, `data-products-coverage`, `data-products-issues`, `data-products-health`, and `data-products-action` hooks between the page intro/KPIs and the table. Keep existing filter, batch, table, pagination, and field-template hooks unchanged.

- [ ] **Step 2: Render status without inventing a composite score**

Derive display states only from existing item fields: missing/partial facts become `不可分析` or `观察`, explicit pending actions become `需处理`, and otherwise show `健康`. Include a short reason and do not coerce missing numeric facts to zero.

- [ ] **Step 3: Render alert summary and issue panel**

Use the filtered result set to count pending actions and coverage gaps. Render the top three explainable items with product id, metric/baseline reason, and links/buttons that open the product detail route or existing action flow.

- [ ] **Step 4: Render coverage panel**

Show product master, product-day, and promotion-day coverage when the API provides them; otherwise show an explicit unavailable state. Keep the copy clear that missing facts are not zero.

- [ ] **Step 5: Add responsive styles**

Use existing tokens and add a single-column lower region below 900px, two KPI columns below 520px, and a compact mobile issue summary without fixed-width overflow.

- [ ] **Step 6: Run static UI validation**

Run: `node scripts/validate_ui_demos.cjs`

Expected: PASS with no missing selectors/assets or duplicate ids.

### Task 3: Preserve filters, templates, and detail context

**Files:**
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/product-detail-live.js`
- Modify: `tests/test_navigation_contract.py`
- Modify: `tests/test_product_detail_api.py`

- [ ] **Step 1: Preserve list query context in detail links**

Ensure desktop rows, mobile summaries, and issue-panel detail buttons all use the same URL builder and carry the current date/filter query.

- [ ] **Step 2: Preserve field-template persistence**

Keep the existing storage keys and column-template API unchanged; add regression assertions that opening the new status/issue regions does not clear visible-column preferences.

- [ ] **Step 3: Verify detail workbench handoff**

Assert the standalone detail page still exposes tabs/back/export hooks and receives `start`/`end` from list navigation.

- [ ] **Step 4: Run focused API and navigation tests**

Run: `python -m unittest tests.test_navigation_contract tests.test_product_detail_api tests.test_products_prd -v`

Expected: PASS.

### Task 4: Browser gates and review fixes

**Files:**
- Test: `scripts/browser_prd_gates.cjs`
- Test: `scripts/validate_ui_demos.cjs`
- Review: all files changed in Tasks 1-3

- [ ] **Step 1: Run the browser PRD gates at desktop and mobile widths**

Run the existing browser gate against `/products?start=2026-07-14&end=2026-08-12` at 1366px and 390px. Verify alert/coverage/issue regions render, no horizontal overflow is introduced, and a detail link preserves the date range.

- [ ] **Step 2: Run the full regression suite**

Run: `python -m unittest discover -s tests -p 'test_*.py'`

Expected: all tests pass; report any pre-existing failures separately.

- [ ] **Step 3: Perform a code review pass**

Check for duplicated URL builders, missing-data-to-zero coercion, stale DOM hooks, accidental fixed-width mobile overflow, and navigation regressions. Fix each finding in the owning file and rerun the focused plus full tests.

- [ ] **Step 4: Commit the implementation**

```bash
git add frontend/ui_demo/pages/products.html frontend/ui_demo/assets/products-live.js frontend/ui_demo/assets/product-detail-live.js frontend/ui_demo/assets/components.css tests/test_navigation_contract.py tests/test_products_prd.py tests/test_product_detail_api.py scripts/browser_prd_gates.cjs
git commit -m "feat: prioritize product operations exceptions and actions"
```

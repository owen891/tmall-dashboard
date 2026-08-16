# Unified Details And Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repeated product drilldowns with one complete dialog and make field templates plus alert rules use server-backed, consistent configuration.

**Architecture:** Keep Flask, SQLite, and native HTML/CSS/JavaScript. Add domain services for field metadata and alert rules, persist promotion templates through settings, and expose one reusable product-detail dialog module consumed by products and promotion pages.

**Tech Stack:** Python 3, Flask, SQLite, native JavaScript, HTML `<dialog>`, CSS, unittest, Node syntax checks, in-app browser verification.

---

### Task 1: Server-backed promotion templates and field metadata

**Files:**
- Create: `services/field_catalog.py`
- Modify: `services/settings_service.py`
- Modify: `api/settings_api.py`
- Modify: `frontend/ui_demo/assets/settings-live.js`
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/promotion-live.js`
- Test: `tests/test_settings_api.py`
- Test: `tests/test_template_integration.py`
- Test: `tests/test_frontend_prd_contract.py`

- [x] **Step 1: Write failing settings tests**

Add tests that assert `/api/settings` returns `promotion_view_templates` and `field_catalog`, accepts valid tab-scoped promotion templates, rejects unknown tabs/fields, and preserves a custom `product_view_template`.

- [x] **Step 2: Run tests and confirm RED**

Run: `py -3 -m unittest tests.test_settings_api tests.test_template_integration -v`

Expected: failures because the new settings keys and metadata do not exist.

- [x] **Step 3: Implement the canonical field catalog**

Create `services/field_catalog.py` with immutable product and promotion field definitions. Export helpers returning serializable metadata and allowed-key sets. Use the same standard keys in settings validation.

- [x] **Step 4: Persist promotion templates through settings**

Add `promotion_view_templates` defaults grouped by `products`, `keywords`, `crowd`, and `site`. Validate `{id: {label, columns}}`, protect built-ins, and reject unsupported keys. Return `field_catalog` as read-only metadata without storing it in `app_settings`.

- [x] **Step 5: Make Settings render custom defaults dynamically**

Rebuild the `product_view_template` select from the returned `view_templates` before assigning its value. Ensure later settings saves preserve a custom default.

- [x] **Step 6: Make Promotion templates server-backed**

Load `/api/settings` before rendering promotion templates, save/delete through `PUT /api/settings`, and retain local storage only for active tab/template preference. Preserve old local templates with a one-time migration when no equivalent server template exists.

- [x] **Step 7: Verify GREEN**

Run the two targeted Python modules, `tests.test_frontend_prd_contract`, and `node --check` for modified JavaScript.

### Task 2: Canonical alert rule API and promotion evaluation

**Files:**
- Create: `repos/alert_rules_repo.py`
- Create: `services/alert_rules_service.py`
- Create: `api/alert_rules_api.py`
- Modify: `db.py`
- Modify: `app.py`
- Modify: `services/promotion_service.py`
- Modify: `api/data_api.py`
- Test: `tests/test_promotion_api.py`
- Test: `tests/test_smoke.py`

- [x] **Step 1: Write failing rule-integration tests**

Add tests that create a `promotion_product` ROI rule, call `/api/promotion`, and assert alerts follow the stored threshold. Add validation tests for unsupported scope, metric, operator, severity, and missing threshold.

- [x] **Step 2: Run tests and confirm RED**

Run: `py -3 -m unittest tests.test_promotion_api -v`

Expected: failures because promotion alerts still use the hardcoded threshold.

- [x] **Step 3: Extend the alert rule schema safely**

Add `name` and `scope` columns through idempotent migration logic. Preserve existing rules as `store` scope. Seed warning and danger promotion ROI defaults only when no promotion rules exist.

- [x] **Step 4: Add repository, service, and blueprint**

Implement list/create/update/delete with the standard API envelope. Restrict metrics by scope and normalize numeric thresholds plus enabled state.

- [x] **Step 5: Connect PromotionService to persisted rules**

Evaluate enabled `promotion_product` rules against each product row. Deduplicate overlapping matches by product and metric, keeping the highest severity. Remove the hardcoded ROI branch.

- [x] **Step 6: Keep legacy endpoints compatible**

Route legacy `/api/alert_rules` behavior through the new service or preserve read/write compatibility while all new frontend code uses the domain blueprint.

- [x] **Step 7: Verify GREEN**

Run promotion, smoke, API contract, and migration-related tests.

### Task 3: Shared alert rule editor

**Files:**
- Create: `frontend/ui_demo/assets/alert-rules.js`
- Modify: `frontend/ui_demo/pages/settings.html`
- Modify: `frontend/ui_demo/pages/promotion.html`
- Modify: `frontend/ui_demo/assets/settings-live.js`
- Modify: `frontend/ui_demo/assets/promotion-live.js`
- Modify: `frontend/ui_demo/assets/components.css`
- Test: `tests/test_frontend_prd_contract.py`

- [x] **Step 1: Write failing frontend contract tests**

Assert both pages load the shared module, Settings contains the canonical rule region, Promotion contains a configuration trigger, and no hardcoded `roi < 3` UI logic remains.

- [x] **Step 2: Run the contract test and confirm RED**

Run: `py -3 -m unittest tests.test_frontend_prd_contract.FrontendPrdContractTests -v`

- [x] **Step 3: Implement the shared editor**

Build a compact dialog with name, scope, metric, operator, threshold, severity, enabled state, inline validation, and delete confirmation. Use the shared API client and return focus on close.

- [x] **Step 4: Mount the editor in both pages**

Settings shows the full rule list. Promotion opens the same dialog filtered to `promotion_product`, then reloads promotion data after changes.

- [x] **Step 5: Verify GREEN and browser behavior**

Run contract tests and manually test create, edit, disable, delete, Escape, focus return, and 390px layout.

### Task 4: One complete product detail dialog

**Files:**
- Create: `frontend/ui_demo/assets/product-detail-dialog.js`
- Modify: `frontend/ui_demo/pages/products.html`
- Modify: `frontend/ui_demo/pages/promotion.html`
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/promotion-live.js`
- Modify: `frontend/ui_demo/assets/components.css`
- Test: `tests/test_frontend_prd_contract.py`
- Test: `tests/test_product_detail_api.py`

- [x] **Step 1: Write failing product-detail contract tests**

Assert Products and Promotion load the shared dialog module, normal actions call the shared opener, and Products no longer contains `data-product-detail-link` or “打开完整详情页”.

- [x] **Step 2: Run tests and confirm RED**

Run the frontend contract and product detail API test modules.

- [x] **Step 3: Build the shared dialog shell**

Use a responsive large `<dialog>` with header, KPI grid, promotion context, product metadata, trend table, lifecycle summary, notes, tags, and action editor. Keep one internal scroll container and stable header/footer.

- [x] **Step 4: Implement partial-failure loading**

Fetch product detail, notes, tags, and actions concurrently. Render available sections even when one optional request fails. Guard stale requests with a token and restore focus on close.

- [x] **Step 5: Replace Products drawer behavior**

Change the row “详情” button to open the shared dialog. Reuse existing note/tag/action write handlers through callbacks and refresh only the affected sections.

- [x] **Step 6: Replace Promotion drawer and product redirect behavior**

Open the same dialog from product rows, alerts, and product-grain results. Pass current promotion metrics as context and remove inline `location.href` navigation. Keep the data-definition drawer separate because it is explanatory content, not product detail.

- [x] **Step 7: Verify GREEN and browser behavior**

Test one-click full detail from both pages, write actions, close methods, focus return, long content scrolling, and desktop/mobile layout.

### Task 5: Documentation, compatibility, and full verification

**Files:**
- Modify: `docs/PRD_KEEP_EXISTING_ARCHITECTURE.md`
- Modify: `docs/FIELD_DICTIONARY.md`
- Modify: `scripts/smoke_core_pages.cjs`
- Modify: `scripts/validate_ui_demos.cjs`

- [x] **Step 1: Update product behavior contracts**

Replace the quick-drawer/second-page requirement with the one-dialog requirement. Document server-backed promotion templates, field metadata authority, and simple scoped alert rules.

- [x] **Step 2: Expand smoke coverage**

Open product detail and alert rule dialogs at 1366px and 390px, assert no page errors or unrecoverable overflow, and verify close/focus behavior.

- [x] **Step 3: Run full verification**

Run:

```powershell
py -3 -m unittest discover -s tests -v
node scripts/validate_ui_demos.cjs
node scripts/smoke_core_pages.cjs
Get-ChildItem frontend/ui_demo/assets/*.js | ForEach-Object { node --check $_.FullName }
```

Expected: all commands exit 0 with no HTTP 500, page errors, or overflow failures.

- [x] **Step 4: Perform final browser audit**

Walk every page and all dialogs, confirm no redundant product down-drill remains, then close temporary tabs and retain no test data created during verification.

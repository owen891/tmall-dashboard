# Inline Field Template Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to edit built-in field templates and delete custom templates directly inside the products, promotion, and lifecycle field dialogs without navigating to settings.

**Architecture:** Keep `/api/settings` as the single persistence boundary. Add a small shared browser utility for template normalization, option rendering, and persistence payloads; each page keeps ownership of its field catalog and applies the shared state to its existing selector. Built-in keys remain stable and cannot be deleted; custom keys can be renamed, updated, and deleted. Deleting the active custom template falls back to the page's primary built-in template.

**Tech Stack:** Vanilla JavaScript, existing Flask settings API, Playwright smoke scripts, pytest frontend contract tests.

---

### Task 1: Lock the template-management contract with tests

**Files:**
- Modify: `tests/test_frontend_prd_contract.py`
- Test: `tests/test_settings_api.py`

- [ ] Add frontend assertions for the shared template utility, inline edit/delete controls, built-in protection, and all three page integrations.
- [ ] Add API regression coverage proving a full `view_templates` payload can update built-in columns/labels while retaining all built-in keys, and that deleting a custom key is accepted.
- [ ] Run the focused tests and confirm they fail before implementation.

### Task 2: Add the shared browser template utility

**Files:**
- Create: `frontend/ui_demo/assets/field-template-manager.js`
- Modify: `frontend/ui_demo/pages/products.html`
- Modify: `frontend/ui_demo/pages/promotion.html`
- Modify: `frontend/ui_demo/pages/lifecycle.html`

- [ ] Implement `DemoFieldTemplateManager.create(options)` with stable APIs for `setTemplates`, `getTemplates`, `renderSelect`, `save`, `update`, and `remove`.
- [ ] Render an edit action for every template and a delete action only for non-built-in templates; use confirmation before deletion.
- [ ] Persist updates through `DemoApi.domainRequest('/api/settings', { method: 'PUT', ... })`, preserving unrelated settings returned by the API.
- [ ] Load the shared script before each page adapter.

### Task 3: Integrate products field dialog

**Files:**
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/pages/products.html`

- [ ] Replace local template-select/save plumbing with the shared manager while retaining the existing `DemoFieldSelector` for field ordering.
- [ ] Add inline template name editing and delete controls to the existing dialog list.
- [ ] Make edit apply the currently selected fields immediately, persist the template, and keep the selector open.
- [ ] Make custom deletion fall back to `operate`, update the select, and persist.

### Task 4: Integrate promotion field dialog

**Files:**
- Modify: `frontend/ui_demo/assets/promotion-live.js`
- Modify: `frontend/ui_demo/pages/promotion.html`

- [ ] Route products/keywords/crowd/site template state through the shared manager using each tab's existing field catalog.
- [ ] Preserve built-in server templates and allow inline edit/delete only according to template ownership.
- [ ] Keep the current active tab and selected fields synchronized after save, edit, delete, and server reload.

### Task 5: Integrate lifecycle field dialog

**Files:**
- Modify: `frontend/ui_demo/assets/lifecycle-live.js`
- Modify: `frontend/ui_demo/pages/lifecycle.html`

- [ ] Move lifecycle template rendering from the hard-coded select into the shared manager.
- [ ] Persist built-in edits and custom templates through `view_templates` without breaking the required-month normalization.
- [ ] Fall back to the lifecycle default when the active custom template is deleted.

### Task 6: Verify the end-to-end behavior

**Files:**
- Modify: `scripts/smoke_core_pages.cjs`

- [ ] Add smoke assertions that open each field dialog, find the edit/delete controls, and verify no horizontal overflow at 1366px and 390px.
- [ ] Run focused pytest, `node scripts/validate_ui_demos.cjs`, `node scripts/smoke_core_pages.cjs`, `node --check` for changed scripts, and `git diff --check`.
- [ ] Manually inspect the settings page to confirm it remains a fallback configuration surface rather than a required navigation step.

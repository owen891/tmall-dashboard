# Core Dashboard Restoration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the six retained dashboard pages to production-usable, API-backed workflows while enforcing one shared visual and interaction language.

**Architecture:** Keep the existing Flask-served vanilla HTML/CSS/JavaScript frontend as the production surface. Reuse the existing API endpoints and the richer `docs/ui_demo` information architecture, but render real database data and mutations through focused page adapters. Shared shell behavior, accessibility, feedback, and export live in `shell.js`; page-specific behavior stays in `*-live.js`.

**Tech Stack:** Flask, vanilla JavaScript, semantic HTML, CSS custom properties, Chart.js, Lucide icons, Node static validation, Python unittest smoke tests, Playwright browser checks.

---

### Task 1: Lock the retained product surface

**Files:**
- Modify: `scripts/validate_ui_demos.cjs`
- Test: `tests/test_app_factory.py`

- [ ] Assert the production navigation exposes exactly `overview`, `products`, `promotion`, `lifecycle`, `compare`, and `manage`.
- [ ] Assert each retained page includes its live adapter and required workflow controls.
- [ ] Assert removed modules do not appear in the production navigation.
- [ ] Run the validator and targeted Python tests and confirm they fail for missing controls before implementation.

### Task 2: Unify shell behavior and accessibility

**Files:**
- Modify: `frontend/ui_demo/assets/tokens.css`
- Modify: `frontend/ui_demo/assets/shell.css`
- Modify: `frontend/ui_demo/assets/components.css`
- Modify: `frontend/ui_demo/assets/shell.js`

- [ ] Implement functional refresh dispatch, page export, theme persistence, toast/status feedback, and mobile overflow behavior.
- [ ] Make the toolbox a modal drawer with Escape close, focus transfer/restore, focus containment, and body scroll lock.
- [ ] Normalize control sizes, focus states, page hierarchy, responsive topbar, compact drawer lists, loading/empty/error states, and missing tokens.
- [ ] Run static validation and browser keyboard checks.

### Task 3: Restore overview and compare analysis

**Files:**
- Modify: `frontend/ui_demo/pages/overview.html`
- Modify: `frontend/ui_demo/assets/overview-live.js`
- Modify: `frontend/ui_demo/pages/compare.html`
- Modify: `frontend/ui_demo/assets/compare-live.js`

- [ ] Overview loads KPI, targets, anomalies, customer mix, funnel, benchmark, report summary, events, trend, and top products from existing APIs.
- [ ] Overview supports report refresh and chart-event creation/deletion.
- [ ] Compare supports period selection, KPI deltas, trend visualization, and a plain-language difference summary.
- [ ] Date range and compare mode changes reload relevant data.

### Task 4: Restore product operations

**Files:**
- Modify: `frontend/ui_demo/pages/products.html`
- Modify: `frontend/ui_demo/assets/products-live.js`

- [ ] Add server-backed pagination, search, tier/style/status/star filters, reset, metric views, and export.
- [ ] Add row selection, batch star, batch tier/style updates, and batch tags.
- [ ] Add product detail drawer with notes, tags, and action history.
- [ ] Add field-template persistence and operation feedback.

### Task 5: Restore promotion analysis

**Files:**
- Modify: `frontend/ui_demo/pages/promotion.html`
- Modify: `frontend/ui_demo/assets/promotion-live.js`
- Modify: `frontend/ui_demo/assets/promotion.js`

- [ ] Render spend, GMV, ROI, product count, performance, alerts, and trend from promotion APIs.
- [ ] Provide product, keyword, audience, creative, and content/region views without double-counting totals.
- [ ] Add filter/alert drawer, field templates, export, and linked-detail drill-down where API data supports it.
- [ ] Clearly label unavailable relationships instead of fabricating attribution.

### Task 6: Connect lifecycle and management workflows

**Files:**
- Modify: `frontend/ui_demo/pages/lifecycle.html`
- Create: `frontend/ui_demo/assets/lifecycle-live.js`
- Modify: `frontend/ui_demo/pages/manage.html`
- Modify: `frontend/ui_demo/assets/manage-live.js`

- [ ] Replace lifecycle mock records with `/api/lifecycle` data, searchable tiers, detail metrics, charts, and export.
- [ ] Add task create/edit/status/delete workflows through `/api/tasks`.
- [ ] Add KPI create/edit/delete workflows through `/api/user_kpis`.
- [ ] Add scheduled task create/edit/toggle/run/delete workflows through `/api/scheduled_tasks`.
- [ ] Render operation logs and clear mutation feedback.

### Task 7: Verify the integrated application

**Files:**
- Modify: `scripts/validate_ui_demos.cjs` as gaps are discovered

- [ ] Run `node scripts/validate_ui_demos.cjs`.
- [ ] Run the complete Python test suite.
- [ ] Start Flask with the explicit Python executable and smoke all six routes and their main interactions in Playwright at desktop and mobile widths.
- [ ] Check browser console errors, horizontal overflow, focus behavior, nonblank charts, and API mutation feedback.
- [ ] Request final code review and fix all critical/important findings.

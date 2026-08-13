# Promotion Drilldown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect verified product-to-plan records into a contextual promotion drill-down and aggregate all records without a verified mapping in an explicit unassigned summary.

**Architecture:** Keep the static demo page and native JavaScript architecture. Store explicit mappings as `{ productId, planId }`, derive the visible product, plan, and detail rows from that mapping, and keep a breadcrumb-like drill context in local page state. Unassigned plan rows remain in a separate summary with a visible data-quality explanation.

**Tech Stack:** HTML, CSS, vanilla JavaScript, existing UI demo validator, browser smoke checks.

---

### Task 1: Lock the drill-down contract with structural tests

**Files:**
- Modify: `scripts/validate_ui_demos.cjs`
- Test: `scripts/validate_ui_demos.cjs`

- [x] Add assertions for the drill root, product/plan/detail levels, explicit linked mapping, unassigned state, context navigation controls, and the unassigned summary.
- [x] Run `node scripts/validate_ui_demos.cjs` and confirm the current page fails only these new assertions.

### Task 2: Add explicit mapping data and drillable markup

**Files:**
- Modify: `docs/ui_demo/pages/promotion.html`

- [ ] Add a `data-drill-root="promotion"` wrapper and a context strip containing the current path, back control, and reset control.
- [ ] Mark product rows with `data-drill-level="product"` and product IDs. Mark linked plan rows with `data-drill-level="plan"`, both `data-product-id` and `data-plan-id`, and `data-mapping-status="linked"`.
- [ ] Add one clearly labeled `data-mapping-status="unassigned"` summary row for plans that cannot be linked to a product.
- [ ] Add downstream detail panels for keywords, audience, creative, and content/region, each carrying the selected product and plan IDs and a `data-drill-level="detail"` marker.

### Task 3: Implement contextual drill state

**Files:**
- Modify: `docs/ui_demo/pages/promotion.html`
- Modify: `docs/ui_demo/assets/components.css`

- [ ] Add a small in-memory state object with `productId`, `planId`, and `detailTab`.
- [ ] On a product action, show only plans linked to that product and update the context strip.
- [ ] On a plan action, retain the product context and switch to the selected detail tab; detail rows must display only the selected plan context.
- [ ] On back/reset, restore the parent scope without reloading the page.
- [ ] Keep the unassigned summary available from the root and prevent it from appearing as a linked product.
- [ ] Add responsive styles for the context strip and drill actions without creating horizontal overflow on mobile.

### Task 4: Verify behavior and presentation

**Files:**
- Test: `scripts/validate_ui_demos.cjs`
- Test: `docs/ui_demo/pages/promotion.html` in the local browser

- [ ] Run `node scripts/validate_ui_demos.cjs` and `git diff --check`.
- [ ] Open the local preview and verify product → plan → keyword/audience/creative/content navigation, back/reset behavior, and the unassigned summary.
- [ ] Check desktop and mobile screenshots for clipped controls or hidden context, and confirm the browser console has no new errors.

### Self-review

- Mapping evidence is explicit and never inferred from a plan name.
- The five promotion views remain available; downstream views are filtered by the selected plan context.
- Missing product-plan mappings are visible as a data-quality summary instead of being dropped or falsely attributed.

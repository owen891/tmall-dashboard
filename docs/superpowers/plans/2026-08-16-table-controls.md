# 全局表格控件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute the steps inline with the existing project patterns and verify each checkpoint.

**Goal:** Add consistent sorting, sticky headers, selectable page sizes, and previous/next pagination to every application data table.

**Architecture:** A shared `table-controls.js` module observes `.data-table` instances and explicitly marked dynamic business tables, enhances dynamic headers and rows, and renders client-side pagination plus a fixed header clone. The server-paginated products table is explicitly excluded from generic pagination and is updated in `products-live.js` with a page-size selector while preserving its API contract.

**Tech Stack:** Vanilla JavaScript, existing CSS tokens, native `MutationObserver`, Playwright smoke checks, existing Python test suites.

---

### Task 1: Add shared table behavior

**Files:**
- Create: `frontend/ui_demo/assets/table-controls.js`
- Modify: `frontend/ui_demo/assets/shell.js`

- [x] Implement table discovery, header enhancement, stable type-aware sorting, and `aria-sort` state.
- [x] Implement client-side page-size selection and previous/next controls for non-server tables.
- [x] Implement fixed header cloning that follows the topbar or open dialog boundary and mirrors horizontal scroll.
- [x] Observe dynamic table headers/bodies and refresh without duplicating controls or losing row listeners.
- [x] Clean up controls and sticky clones when dynamic tables are replaced.
- [x] Load the module from `shell.js` after the shared API/bootstrap code.

### Task 2: Integrate server-paginated products table

**Files:**
- Modify: `frontend/ui_demo/pages/products.html`
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/components.css`

- [x] Mark the products table as server-paginated and add a `20/50/100/200` page-size selector beside existing pagination buttons.
- [x] Replace the fixed `limit` constant with persisted page-size state, pass it to `/api/products`, reset page on changes, and update the summary text.
- [x] Add shared controls and sticky-header styles that match existing panel, button, select, and table tokens.

### Task 3: Verify behavior

**Files:**
- Test: temporary Playwright browser checks (removed after execution)

- [x] Verify representative tables on overview, products, promotion, lifecycle, goals, data-center, reviews, compare, and settings.
- [x] Verify ascending/descending sorting, empty-value ordering, page-size changes, disabled boundaries, sticky header visibility, and row action clicks.
- [x] Verify products API pagination changes when page size changes.
- [x] Run syntax checks, targeted Python tests, UI validation, and diff checks.

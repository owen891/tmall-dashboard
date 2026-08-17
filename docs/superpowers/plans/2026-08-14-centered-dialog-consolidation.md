# 居中弹窗统一重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将数据工具箱、推广口径详情和商品详情统一为居中弹窗，其中商品详情用 Tab 拆分长内容。

**Architecture:** 保留现有原生 HTML/JS 和 API，不新增依赖。全局工具箱由 `shell.js` 动态创建 `<dialog>`，推广详情把现有 drawer DOM 改为 `<dialog>`，共享商品详情弹窗由 `product-detail-dialog.js` 负责 Tab 状态、当前面板渲染和焦点管理。CSS 只复用现有 token，并让每个弹窗的正文区域独立滚动。

**Tech Stack:** Flask 静态页面、原生 JavaScript、原生 `<dialog>`、现有 tokens/components/shell CSS、Playwright smoke、Python unittest。

---

### Task 1: Lock the new dialog contracts with tests

**Files:**
- Modify: `tests/test_frontend_prd_contract.py`
- Modify: `scripts/smoke_core_pages.cjs`

- [x] **Step 1: Add static contract assertions**

Assert that promotion no longer contains `demo-drawer__backdrop` or `data-promotion-drawer`, while it includes `data-promotion-dialog`, `role="tablist"` and the shared product detail asset. Assert that `shell.js` contains a `<dialog data-toolbox-dialog>` and does not create a toolbox overlay/drawer.

- [x] **Step 2: Run the focused contract tests and observe failure**

Run:

```powershell
py -3 -m unittest tests.test_frontend_prd_contract -v
```

Expected: FAIL on the old drawer markers and missing product-detail tab markers.

- [x] **Step 3: Add browser smoke checks for the three workflows**

Extend `scripts/smoke_core_pages.cjs` so the products page opens `.product-detail-dialog`, clicks each `[role="tab"]`, verifies the matching `[role="tabpanel"]` is visible and the dialog remains inside the viewport; the promotion page opens the centered detail dialog; and the shell toolbox opens `[data-toolbox-dialog]` and closes with Escape.

- [x] **Step 4: Run the smoke script before implementation**

Run:

```powershell
$env:TMALL_SMOKE_BASE='http://127.0.0.1:8775'; node scripts/smoke_core_pages.cjs
```

Expected: FAIL because the current implementation still exposes drawer markup and the product detail has no tabs.

### Task 2: Convert the global toolbox to a centered dialog

**Files:**
- Modify: `frontend/ui_demo/assets/shell.js`
- Modify: `frontend/ui_demo/assets/shell.css`

- [x] **Step 1: Replace the injected toolbox shell**

Create `<dialog class="toolbox-dialog" data-toolbox-dialog data-modal-kind="flow">` with the existing import and schedule controls inside a tabpanel. Keep the existing data attributes used by import and schedule API handlers. Replace the two large tool cards with a `role="tablist"` containing two compact buttons and `role="tabpanel"` sections.

- [x] **Step 2: Replace custom drawer open/close state**

Use `dialog.showModal()` and `dialog.close()`. Keep the current return-focus target, Escape handling, and Tab cycling. Remove overlay class toggles, `inert` management, and drawer transform logic. On dialog close, restore focus to the triggering sidebar button.

- [x] **Step 3: Add compact responsive styles**

Define `.toolbox-dialog` using `width: min(720px, calc(100vw - 32px))`, `max-height: calc(100dvh - 24px)`, centered native dialog layout, and a scrollable `.toolbox-dialog__body`. Convert the tool selector to a segmented control; make mobile form fields single-column and preserve table horizontal scrolling.

- [x] **Step 4: Run JS syntax and shell contract checks**

Run:

```powershell
node --check frontend/ui_demo/assets/shell.js
py -3 -m unittest tests.test_frontend_prd_contract -v
```

Expected: syntax passes; only promotion/product tab assertions remain until later tasks.

### Task 3: Convert promotion detail to a centered dialog

**Files:**
- Modify: `frontend/ui_demo/pages/promotion.html`
- Modify: `frontend/ui_demo/assets/promotion-live.js`
- Modify: `frontend/ui_demo/assets/components.css`

- [x] **Step 1: Replace the promotion drawer DOM**

Change the backdrop/aside pair to `<dialog class="promotion-dialog" data-promotion-dialog data-modal-kind="detail">`, keeping the existing title, subtitle and body hooks under dialog-specific names.

- [x] **Step 2: Use native dialog lifecycle in the adapter**

Update `openDrawer`/`closeDrawer` helpers to call `showModal()`/`close()`, preserve trigger focus, close on cancel and backdrop click, and remove overlay/inert/transform assumptions. Keep the existing detail body renderer and API contract unchanged.

- [x] **Step 3: Style the dialog for bounded content**

Replace `.promotion-drawer*` rules with centered `.promotion-dialog*` rules. Give the dialog a max width of 680px, a max height tied to the viewport, and a body that owns vertical scrolling.

- [x] **Step 4: Verify promotion detail behavior**

Run:

```powershell
node --check frontend/ui_demo/assets/promotion-live.js
```

Then run the promotion portion of the smoke script and verify status 200, no page errors and no horizontal overflow.

### Task 4: Split shared product detail into four tabs

**Files:**
- Modify: `frontend/ui_demo/assets/product-detail-dialog.js`
- Modify: `frontend/ui_demo/assets/components.css`
- Modify: `frontend/ui_demo/assets/products-live.js`

- [x] **Step 1: Add tab state and panel renderers**

Define the tab list `overview`, `trend`, `lifecycle`, `collaboration`. Keep `renderMetrics` and `renderIdentity` in overview, move `renderTrend` to trend, `renderLifecycle` to lifecycle, and combine `renderNotes`, `renderTags`, and `renderActions` in collaboration. Render only the active panel after detail data resolves.

- [x] **Step 2: Add accessible tab interaction**

Render `role="tablist"`, `role="tab"`, and `role="tabpanel"` with stable IDs. Implement click and Left/Right/Home/End keyboard navigation, update `aria-selected`, `tabIndex`, and panel visibility, and focus the active tab after keyboard navigation.

- [x] **Step 3: Bound the dialog body**

Keep the shared dialog centered with a max height of `calc(100vh - 24px)`. Make only `.product-detail-dialog__body` scroll, and set the tab panel to `min-height: 0` so switching tabs never keeps all content in layout.

- [x] **Step 4: Remove obsolete product drawer code**

Delete the unused drawer state, renderer, close handlers, and note/tag/action listeners from `products-live.js`; keep the row trigger calling `ProductDetailDialog.open`.

- [x] **Step 5: Verify tab behavior**

Run:

```powershell
node --check frontend/ui_demo/assets/product-detail-dialog.js
node --check frontend/ui_demo/assets/products-live.js
```

Use Playwright smoke to open the dialog, switch all four tabs, and assert exactly one panel is visible at a time.

### Task 5: Full verification and handoff

**Files:**
- Modify: `scripts/validate_ui_demos.cjs` if static drawer expectations remain.

- [x] **Step 1: Run all JavaScript syntax checks**

```powershell
Get-ChildItem frontend/ui_demo/assets/*.js | ForEach-Object { node --check $_.FullName }
```

- [x] **Step 2: Run focused and full Python tests**

```powershell
py -3 -m unittest tests.test_frontend_prd_contract tests.test_product_detail_api tests.test_promotion_api -v
py -3 -m unittest discover -s tests -v
```

- [x] **Step 3: Run UI contract and browser smoke**

```powershell
node scripts/validate_ui_demos.cjs
$env:TMALL_SMOKE_BASE='http://127.0.0.1:8775'; node scripts/smoke_core_pages.cjs
```

Expected: all pages return 200, no page errors, no horizontal overflow, centered dialogs remain inside the viewport, and all product tabs are operable at desktop/tablet/mobile widths.

- [x] **Step 4: Inspect diff and report residual risk**

Run `git diff --check` and `git status --short`. Do not commit; preserve unrelated workspace changes.

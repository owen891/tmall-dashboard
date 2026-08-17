# 工具箱导入预览 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将数据工具箱经营数据导入改为“预览、映射、校验、确认后入库”。

**Architecture:** 复用现有 `POST /api/imports/preview` 和 `POST /api/imports`，只替换 `frontend/ui_demo/assets/shell.js` 中工具箱的旧 `/api/upload/data` 直导逻辑，并在动态弹窗中增加预览和映射区域。后端仅补充必要的预览返回字段，不改变现有业务表和批次协议。

**Tech Stack:** Flask、SQLite、pandas、原生 JavaScript、现有 CSS 变量和组件。

---

### Task 1: 锁定工具箱入口契约

**Files:**
- Modify: `frontend/ui_demo/assets/shell.js`
- Test: `tests/test_frontend_prd_contract.py` or a focused new test in `tests/test_import_workflow.py`

- [x] **Step 1: Write the failing contract assertion**

Assert that the toolbox import markup contains `data-import-preview`, `data-import-confirm`, and `data-import-preview-panel`, and that the direct `/api/upload/data` call is absent from the toolbox handler.

- [x] **Step 2: Run the focused test**

Run: `python -m pytest tests/test_import_workflow.py -q`

Expected: the existing backend tests pass, while the new frontend contract assertion fails because the toolbox still has `data-start-import`.

- [x] **Step 3: Replace the toolbox import markup**

Keep the existing file input and upload zone. Replace the direct-import button with `data-import-preview`, add a hidden preview panel containing:

```html
<div data-import-preview-tabs role="tablist"></div>
<p data-import-quality></p>
<p data-import-quality-detail></p>
<table><tbody data-import-fields></tbody></table>
<button data-import-confirm type="button">确认导入</button>
```

Use the same `data-*` names already consumed by `frontend/ui_demo/assets/data-center-live.js`.

- [x] **Step 4: Run the contract test again**

Run: `python -m pytest tests/test_import_workflow.py -q`

Expected: backend tests remain green; the markup contract passes.

### Task 2: Add toolbox preview state and mapping rendering

**Files:**
- Modify: `frontend/ui_demo/assets/shell.js`

- [x] **Step 1: Add preview state**

Add `previewQueue`, `activePreviewIndex`, `previewErrors`, `settings`, and `importCapabilities` in the toolbox initialization closure. Use `DemoApi.domainRequest` so API failures keep the existing normalized error behavior.

- [x] **Step 2: Add the preview renderer**

Render file tabs, quality summary, invalid-row details, and one mapping row per source column. Each mapping select must remove previous mappings for that source column, update `result.mapping`, recompute `result.required_unmapped`, and update the live status text.

- [x] **Step 3: Replace the direct importer**

The preview button loops through selected files and posts each as `FormData` to:

```js
`/api/imports/preview?source_type=auto`
```

The confirm button must reject pending previews with invalid rows, duplicate keys, or missing required mappings. On success it posts:

```js
{ preview_id: item.id, mapping: item.mapping }
```

to `/api/imports`, then reports aggregate inserted/updated counts.

- [x] **Step 4: Preserve retry behavior**

Keep failed previews in `previewQueue`, keep the confirm button enabled only when retries remain, and reset progress/status after a complete success. Do not call `/api/upload/data` from this toolbox flow.

- [x] **Step 5: Run JavaScript syntax validation**

Run: `node --check frontend/ui_demo/assets/shell.js`

Expected: exit code 0.

### Task 3: Cover the end-to-end import contract

**Files:**
- Modify: `tests/test_import_workflow.py`
- Modify: `tests/test_frontend_prd_contract.py`

- [x] **Step 1: Add a preview-only test**

Upload a minimal product-day workbook to `/api/imports/preview`, assert `required_unmapped`, `fields`, and `mapping_schema`, and assert `daily_data` and `import_batches` remain empty.

- [x] **Step 2: Add a blocked-confirm test**

Preview a workbook with an invalid date or duplicate business key, assert the preview reports the quality failure, and assert confirming it returns `422` without creating an import batch.

- [x] **Step 3: Add a confirmed-import test**

Preview a valid workbook, confirm using the returned mapping, and assert the response reports inserted/updated counts and the existing business table contains the row.

- [x] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_import_workflow.py tests/test_frontend_prd_contract.py -q`

Expected: all focused tests pass.

### Task 4: Browser smoke verification

**Files:**
- No source changes unless smoke testing finds a concrete defect.

- [x] **Step 1: Start the local app**

Run: `python scripts/run_test_server.py`

- [x] **Step 2: Open a data-center page and the toolbox**

Use the existing browser smoke harness or Playwright to click the sidebar “数据工具箱” button and assert the preview button, file input, hidden preview panel, and confirm button are present.

- [x] **Step 3: Check responsive layout**

Verify the dialog at 390x844 and 1440x900. Confirm the preview table scrolls within the dialog and buttons remain reachable.

- [x] **Step 4: Run the complete relevant suite**

Run: `python -m pytest tests/test_import_workflow.py tests/test_frontend_prd_contract.py tests/test_smoke.py -q`

Expected: exit code 0 with no failed tests.

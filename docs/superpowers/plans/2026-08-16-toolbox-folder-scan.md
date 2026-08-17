# Toolbox Folder Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the obsolete toolbox schedule form with the existing folder-scan workflow and native desktop folder selection.

**Architecture:** The toolbox calls `/api/import-scans` directly and renders scan jobs locally. Electron exposes one narrow directory-picker IPC method. The backend keeps strict browser allowlists while desktop mode accepts existing local folders explicitly selected by the desktop user.

**Tech Stack:** Vanilla JavaScript, Flask, Electron, TypeScript, Python unittest/pytest, Vitest

---

### Task 1: Lock the frontend contract

**Files:**
- Modify: `tests/test_frontend_prd_contract.py`
- Modify: `frontend/ui_demo/assets/shell.js`

- [ ] Add a failing contract test requiring “文件夹扫描任务”, folder/source/schedule controls, `/api/import-scans`, and no `/api/manage/schedules` reference in `shell.js`.
- [ ] Run `py -3 -m unittest tests.test_frontend_prd_contract.FrontendPrdContractTests.test_toolbox_uses_folder_scan_jobs` and confirm it fails on the old schedule UI.
- [ ] Replace the toolbox schedule markup and handlers with scan-job create/list/run/toggle behavior.
- [ ] Re-run the targeted test and confirm it passes.

### Task 2: Add secure desktop folder selection

**Files:**
- Modify: `desktop/tests/main-contract.test.ts`
- Modify: `desktop/src/main.ts`
- Modify: `desktop/src/preload.ts`

- [ ] Add a failing Vitest contract requiring `desktop:select-scan-folder`, `showOpenDialog`, `properties: ['openDirectory']`, and `selectScanFolder` in preload.
- [ ] Run `npm test --prefix desktop` and confirm the new contract fails.
- [ ] Register the IPC handler, return `null` on cancellation, and expose it through contextBridge.
- [ ] Re-run Electron tests and TypeScript build.

### Task 3: Preserve path validation in desktop mode

**Files:**
- Modify: `tests/test_import_scan_service.py`
- Modify: `services/import_scan_service.py`

- [ ] Add a failing service test proving an existing local folder outside the configured allowlist is accepted only when `TMALL_DESKTOP_MODE` is enabled.
- [ ] Keep browser mode rejecting the same folder and keep UNC, traversal, missing directory and symlink checks unchanged.
- [ ] Run the targeted service tests and confirm red/green behavior.

### Task 4: Verify the integrated change

**Files:**
- Verify only

- [ ] Run `py -3 -m unittest tests.test_frontend_prd_contract tests.test_import_scan_service tests.test_import_scanner_api`.
- [ ] Run `npm test --prefix desktop`.
- [ ] Run `npm run build --prefix desktop`.
- [ ] Inspect `git diff` to confirm no unrelated user changes were reverted.

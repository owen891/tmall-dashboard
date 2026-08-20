# Web And Desktop Online Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep Web and Electron clients on one release version and provide online update discovery, prompting, and installation/refresh behavior.

**Architecture:** The root `VERSION` file is the single source of truth. Flask exposes it through a no-store `/api/version` endpoint. Web clients carry their build version in a small generated asset and poll the endpoint; Electron continues to use `electron-updater` against GitHub Releases.

**Tech Stack:** Flask, vanilla browser JavaScript, CSS custom properties, Electron, electron-updater, Vitest, unittest/pytest.

---

### Task 1: Unify version metadata

**Files:** `config.py`, `scripts/sync_desktop_version.py`, `frontend/ui_demo/assets/version.js`, `packaging/tmall_dashboard_backend.spec`

- Read `VERSION` with an environment override for packaged/runtime deployments.
- Sync the Web asset and Electron package metadata from `VERSION`.
- Include `VERSION` in the PyInstaller backend bundle.

### Task 2: Add Web version API

**Files:** `app.py`, `tests/test_app_factory.py`

- Add `GET /api/version` returning the application version and update channel.
- Ensure the endpoint is never cached.
- Add a contract test for the response and cache headers.

### Task 3: Add Web update prompt

**Files:** `frontend/ui_demo/assets/version.js`, `frontend/ui_demo/assets/version-check.js`, `frontend/ui_demo/assets/shell.js`, `frontend/ui_demo/assets/shell.css`, all `frontend/ui_demo/pages/*.html`, `frontend/ui_demo/index.html`, `tests/test_update_notifications_ui.py`

- Load the build version on every page.
- Poll `/api/version` at startup and every five minutes.
- Show an accessible banner with refresh and dismiss actions when a newer version exists.
- Avoid prompting in Electron, where the native updater owns update UX.

### Task 4: Verify desktop updater contracts

**Files:** `desktop/tests/updater.test.ts`, `desktop/tests/main-contract.test.ts`

- Assert the shared release feed, automatic startup check, and install-on-quit behavior remain wired.
- Run Python tests, Web UI contracts, TypeScript build, and Electron tests.

# Import Scan Concurrency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make manual and scheduled folder scans share an explicit running state, recover expired leases, and report actionable conflicts.

**Architecture:** Keep the SQLite lease as the single-run guard, but allow active and running rows to be reclaimed only after lease expiry. The service will set `status=running` while work is in progress and restore `active` on release; the API will return structured conflict codes, and the toolbox will render running jobs distinctly.

**Tech Stack:** Flask, SQLite, vanilla JavaScript, unittest.

---

### Task 1: Lock service and API behavior with regression tests

**Files:**
- Modify: `tests/test_import_scan_service.py`
- Modify: `tests/test_import_scanner_api.py`

- [ ] Add tests for a running lease returning `SCAN_RUNNING`, a disabled job returning `SCAN_DISABLED`, and an expired running lease being reclaimable.
- [ ] Run the targeted tests and observe failures against the current generic conflict behavior.

### Task 2: Implement explicit scan state and lease recovery

**Files:**
- Modify: `services/import_scan_service.py`
- Modify: `api/import_scans_api.py`

- [ ] Extend `ImportScanConflictError` with a stable error code.
- [ ] Make acquisition distinguish disabled, active lease, and expired lease; set status to `running` on acquisition.
- [ ] Restore status to `active` when releasing a lease, including failures.
- [ ] Return the stable error code from the API response.

### Task 3: Render scan state in the toolbox

**Files:**
- Modify: `frontend/ui_demo/assets/shell.js`

- [ ] Render `running` distinctly from enabled/disabled and show structured conflict messages from the API.
- [ ] Disable the immediate-run action while a job reports `running`.

### Task 4: Verify

**Files:** verify only

- [ ] Run `py -3 -m unittest tests.test_import_scan_service tests.test_import_scanner_api`.
- [ ] Run the frontend contract tests covering toolbox scan behavior.
- [ ] Inspect the diff for unrelated changes.

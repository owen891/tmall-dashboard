# Goal Configuration Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make goal configuration own annual defaults and growth assumptions, while the operating-goal page generates and adjusts period targets using prior-year same-period sales weights.

**Architecture:** Keep settings as the source of annual defaults (`annual_target_default`, `growth_multiplier`, `overachievement_threshold`). The goals page loads those defaults, shows a read-only suggestion from prior-year net sales, and only then allows period adjustment/locking. Preserve the existing atomic daily-goal model and weighted allocator; correct adjustment locks so they retain the selected period grain.

**Tech Stack:** Flask/Python services and SQLite repositories; static HTML/CSS/JavaScript demo UI; unittest and Node syntax checks.

---

### Task 1: Lock the target configuration contract with tests

**Files:**
- Modify: `tests/test_goals_service.py`
- Modify: `tests/test_frontend_prd_contract.py`

- [ ] Add a service test proving an adjustment with `period_type='month'` and `lock=True` creates a month lock, keeps the annual total unchanged, and appears in `GET /api/goals/<year>`.
- [ ] Add a frontend contract assertion that the goals page exposes a settings/defaults data hook and keeps the suggested annual target read-only.
- [ ] Run `python -m unittest tests.test_goals_service tests.test_frontend_prd_contract -v` and confirm the new lock/default assertions fail before implementation.

### Task 2: Correct period adjustment locking and validation

**Files:**
- Modify: `repos/goals_repo.py:adjust_period`
- Modify: `services/goals_service.py:adjust_period`

- [ ] Pass the requested `period_type` into the repository lock insert instead of hard-coding `'date'`.
- [ ] Validate year, quarter, month, week, and date keys before repository allocation so malformed keys return `422` with a user-facing message rather than a traceback.
- [ ] Keep the annual total invariant and reject adjustments below already locked child-date totals.
- [ ] Run the focused goals tests and verify the new lock test passes.

### Task 3: Make the goals page consume configuration instead of hard-coded assumptions

**Files:**
- Modify: `frontend/ui_demo/pages/goals.html`
- Modify: `frontend/ui_demo/assets/goals-live.js`
- Modify: `frontend/ui_demo/assets/components.css`

- [ ] Add a compact configuration summary showing the configured annual default, growth multiplier, and allocation rule “去年同期销售占比”.
- [ ] Load `/api/settings` before loading the selected goal year; use its annual default and multiplier as initial form values, while keeping the suggestion field read-only.
- [ ] Make the annual target the only editable target value; make “生成建议” a preview/apply action with explicit source text and do not submit the read-only suggestion as a second target.
- [ ] Disable period adjustment controls until the selected year has a generated goal, and reset the period picker when its grain changes.
- [ ] Keep monthly/period data tables as the execution view, with lock buttons reflecting the actual period grain.
- [ ] Run `node --check frontend/ui_demo/assets/goals-live.js` and the frontend contract tests.

### Task 4: Verify the end-to-end target workflow

**Files:**
- No new files.

- [ ] Run `python -m unittest tests.test_goals_service tests.test_settings_api tests.test_frontend_prd_contract -v`.
- [ ] Run `python -m unittest discover -s tests -p 'test_*.py' -v` if the focused suite is green.
- [ ] Start the local app, open `/settings#settings-goals` and `/goals`, and verify defaults load, suggestion uses prior-year net sales, annual generation uses the selected target, and month adjustment lock is rendered as a month lock.

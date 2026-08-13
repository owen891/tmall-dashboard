# Project Process Realignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a traceable requirement-to-release workflow without discarding the current dashboard implementation or user changes.

**Architecture:** Treat the current `refactor/demo-phase1` tree as an uncommitted working set that must be classified before further feature work. Keep backend, frontend, and verification changes in separate commits, use temporary databases for tests, and require a documented gate before each phase is considered complete.

**Tech Stack:** Git, Flask, SQLite, vanilla HTML/CSS/JavaScript, Python `unittest`, Node static validation.

---

### Task 1: Freeze and classify the current working set

**Files:**
- Create: `docs/superpowers/plans/2026-08-13-project-process-realignment.md`
- Inspect: `git status`, `git diff`, `git ls-files`, `docs/superpowers/plans/*`
- Preserve: `source.xlsx`, original PRD artifacts, `data/dashboard.db`

- [ ] **Step 1: Record the current baseline**

Run:

```powershell
git status --short
git branch -vv
git log --oneline --decorate -12
```

Save the output in the task notes or handoff message. Do not modify files during this step.

- [ ] **Step 2: Classify every changed path**

Use four buckets: `backend`, `frontend`, `tests`, and `artifacts/docs`. A database file, source spreadsheet, screenshot, or original PRD is an artifact and must not be mixed into a source-code commit unless the change is explicitly required.

- [ ] **Step 3: Protect original artifacts**

Confirm the original PRD and source spreadsheet exist. If the original PRD is only present as a deleted tracked file, restore it from `HEAD` with a targeted path restore, then verify its hash before continuing. Do not use a repository-wide reset.

- [ ] **Step 4: Create a checkpoint commit**

After classification, stage only the intended current baseline files and commit:

```powershell
git add <classified-baseline-files>
git commit -m "chore: checkpoint current dashboard baseline"
```

The commit must not include a live database mutation, generated screenshots, or unrelated experimental files.

### Task 2: Establish the phase gates

**Files:**
- Modify: `README.md`
- Create: `docs/DEVELOPMENT_WORKFLOW.md`
- Test: `tests/test_app_factory.py`, `tests/test_smoke.py`, `scripts/validate_ui_demos.cjs`

- [ ] **Step 1: Document the required phase order**

Use this order: PRD/acceptance criteria -> API/data contract -> backend implementation -> frontend adapter -> automated tests -> browser smoke -> commit/review. Each phase must name its files, command, and exit criterion.

- [ ] **Step 2: Define the minimum verification gate**

Run:

```powershell
py -3 -m unittest discover -s tests -v
node scripts/validate_ui_demos.cjs
git diff --check
```

The gate fails if any command fails, if the production database is modified by tests, or if a required page has no live adapter.

- [ ] **Step 3: Add a release checklist**

Record the tested routes, desktop/mobile viewport checks, browser console result, database backup status, and rollback commit in `docs/DEVELOPMENT_WORKFLOW.md`.

### Task 3: Split the implementation into reviewable commits

**Files:**
- Backend: `app.py`, `api/`, `services/`, `repos/`, `db.py`, `migrations/`
- Frontend: `frontend/ui_demo/`
- Verification: `tests/`, `scripts/`

- [ ] **Step 1: Commit backend boundaries only**

Stage backend source plus its focused tests. Use:

```powershell
git commit -m "refactor: establish dashboard backend boundaries"
```

- [ ] **Step 2: Verify backend compatibility**

Run the full Python suite and verify the six production routes before touching frontend files.

- [ ] **Step 3: Commit frontend adapters only**

Stage page HTML, live adapters, shared shell assets, and frontend-focused tests. Use:

```powershell
git commit -m "feat: connect dashboard pages to domain APIs"
```

- [ ] **Step 4: Verify frontend behavior**

Run the static validator and browser smoke checks at `1366x768`, `1024x768`, and `390x844`. Record console errors and horizontal overflow results.

- [ ] **Step 5: Commit verification and documentation**

Stage tests, validation scripts, README/workflow docs, and only the screenshots needed as evidence. Use:

```powershell
git commit -m "test: add dashboard release gates"
```

### Task 4: Enforce clean handoff and release state

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Verify: `git status`, `git diff --check`, branch tracking

- [ ] **Step 1: Exclude generated/runtime files**

Ignore Python caches, temporary test directories, generated backups, and local database copies. Keep source fixtures such as `source.xlsx` explicitly tracked only when required by the application.

- [ ] **Step 2: Back up the production database before schema changes**

Run:

```powershell
Copy-Item data/dashboard.db data/dashboard.db.bak
```

Record the backup path and timestamp in the release notes.

- [ ] **Step 3: Confirm the release gate**

Require a clean working tree, a pushed branch, passing automated checks, and a completed browser smoke record before merging.

- [ ] **Step 4: Tag the verified baseline**

After all gates pass, create an annotated tag such as `v0.1.0-dashboard-baseline` and push the branch/tag.

## Self-review

- Requirements, implementation, tests, and browser verification are represented as separate checkpoints.
- The plan does not require destructive repository-wide commands.
- Live SQLite data and original source artifacts are explicitly protected.
- Every implementation phase has a command-based exit criterion and a dedicated commit.

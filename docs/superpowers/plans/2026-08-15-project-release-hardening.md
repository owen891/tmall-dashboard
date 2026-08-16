# Project Release Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 收口当前 TM 1.0 项目的发布、数据隔离和遗留治理边界，不删除现有数据或用户改动。

**Architecture:** 保留 Flask + SQLite + 原生前端。新增只读发布审计工具和显式演示库入口；正式业务继续使用现有能力注册、服务层和兼容 API，不在本阶段重写全部遗留路由。

**Tech Stack:** Python 3.14, Flask, SQLite, unittest, Node.js validation scripts.

---

### Task 1: Add A Read-Only Release Audit

**Files:**
- Create: `scripts/release_audit.py`
- Create: `tests/test_release_audit.py`
- Modify: `README.md`

- [x] **Step 1: Write failing tests**

Test that the audit reports tracked modifications/untracked files, demo batch counts, production data warnings, and exits non-zero only when explicitly requested with `--strict`.

- [x] **Step 2: Verify tests fail**

Run `py -3 -m unittest tests.test_release_audit -v`; expected failure because the audit module does not exist.

- [x] **Step 3: Implement the read-only audit**

Use `git status --porcelain`, SQLite metadata, and `import_batches` provenance. Never modify files or databases. Emit JSON with `worktree`, `database`, `blockers`, and `warnings`.

- [x] **Step 4: Verify audit behavior**

Run the focused test and `py -3 scripts/release_audit.py --database data/dashboard.db`; expected JSON reports the current dirty worktree and demo/real batch mix.

### Task 2: Make Demo Data Explicitly Isolated

**Files:**
- Modify: `scripts/seed_demo_data.py`
- Modify: `tests/test_demo_seed.py`
- Modify: `README.md`

- [x] **Step 1: Write failing tests**

Test that the CLI requires an explicit `--database` or `--demo-database` target when invoked against a non-temporary path, while the Python helper remains backward-compatible for existing tests.

- [x] **Step 2: Verify tests fail**

Run the focused CLI safety test; expected failure because the current CLI accepts the production database by default.

- [x] **Step 3: Implement explicit target handling**

Add `--database` and `--demo-database` mutually exclusive options. Reject the repository production path unless `--allow-production-database` is supplied. Keep seeding idempotent and do not move or delete the current database.

- [x] **Step 4: Verify isolation guard**

Run demo seed tests and a subprocess invocation against the repository database without the override; expected refusal and unchanged database hash.

### Task 3: Document Legacy And Migration Gates

**Files:**
- Create: `docs/RELEASE_STATUS.md`
- Modify: `docs/PRODUCTION_RUNBOOK.md`
- Modify: `README.md`

- [x] **Step 1: Record current gates and blockers**

Document the exact test commands, current 40-table SQLite state, formal seven-page scope, legacy compatibility boundary, and single-store LAN deployment boundary.

- [x] **Step 2: Add migration exit criteria**

Require new writes to use formal domain APIs, require a versioned migration before schema changes, and require production data separation before release.

- [x] **Step 3: Verify documentation references**

Run link/path checks already used by the repository and ensure commands match the actual scripts.

### Task 4: Full Regression And Release Evidence

**Files:**
- No additional source changes unless a named verification fails.

- [x] **Step 1: Run Python regression**

Run `py -3 -m unittest discover -s tests -q`; require zero failures.

- [x] **Step 2: Run frontend and production gates**

Run all formal JavaScript syntax checks, `node scripts/validate_ui_demos.cjs`, and `py -3 scripts/production_preflight.py`.

- [x] **Step 3: Run the read-only audit**

Run `py -3 scripts/release_audit.py --database data/dashboard.db --strict`; report any remaining blockers without mutating the worktree.

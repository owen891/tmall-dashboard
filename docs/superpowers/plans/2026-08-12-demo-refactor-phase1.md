# Demo Refactor Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Flask backend toward the demo's application-factory and domain-layer structure while preserving existing API paths, response contracts, and frontend behavior.

**Architecture:** Keep the current SQLite schema and legacy `api/data_api.py` as a compatibility reference. Introduce a factory-based Flask entry point, shared configuration, repositories, services, and domain blueprints incrementally. Phase 1 migrates KPI and product surfaces first; remaining routes continue through the legacy blueprint until their own migration is verified.

**Tech Stack:** Python 3, Flask 3, SQLite, SQLAlchemy/Flask-SQLAlchemy, Alembic, existing unittest smoke tests, existing vanilla JavaScript frontend.

---

### Task 1: Establish the branch baseline

**Files:**
- Modify: `.gitignore`
- Add: `docs/superpowers/plans/2026-08-12-demo-refactor-phase1.md`
- Preserve: all existing application, demo, data, and test files

- [ ] Run the existing smoke tests: `python -m unittest tests.test_smoke -v`; record any pre-existing failures.
- [ ] Create a checkpoint: `git add -A; git commit -m "chore: checkpoint current dashboard state"`.
- [ ] Create and publish the branch: `git switch -c refactor/demo-phase1; git push -u origin refactor/demo-phase1`.

### Task 2: Add the application factory and configuration boundary

**Files:**
- Create: `config.py`
- Modify: `app.py`
- Create: `models/__init__.py`
- Create: `models/constants.py`
- Create: `tests/test_app_factory.py`

- [ ] Write tests asserting `create_app` returns a Flask app, accepts test configuration, and keeps `/` reachable.
- [ ] Run `python -m unittest tests.test_app_factory -v` and confirm the expected missing-factory failure.
- [ ] Implement `create_app`, shared configuration, database initialization, and module-level `app = create_app()` compatibility.
- [ ] Run `python -m unittest tests.test_app_factory tests.test_smoke -v`; all factory checks and existing routes must pass.

### Task 3: Introduce KPI and product domain boundaries

**Files:**
- Create: `repos/base_repo.py`, `repos/data_repo.py`, `repos/product_repo.py`
- Create: `services/kpi_service.py`, `services/health_service.py`
- Create: `api/kpi_api.py`, `api/product_api.py`
- Create: focused contract tests under `tests/`

- [ ] Add contract tests for `/api/kpi`, `/api/trend`, and `/api/products`, recording status codes and required JSON keys from the current implementation.
- [ ] Run the contract tests against the legacy implementation before migration.
- [ ] Move SQL reads and whitelist-controlled updates into repositories; move aggregation, period selection, formatting, and health calculations into services.
- [ ] Keep blueprints limited to request parsing, service calls, and JSON responses; register migrated routes without duplicate rules.
- [ ] Run focused contracts plus `python -m unittest tests.test_smoke -v`; no route or response contract may regress.

### Task 4: Add ORM/migration scaffolding without mutating existing data

**Files:**
- Create/modify: `models/*.py` for tables used by migrated paths
- Create: `migrations/env.py`, `migrations/alembic.ini`
- Modify: `requirements.txt`
- Add: schema verification coverage under `tests/`

- [ ] Verify current columns read-only with SQLite `PRAGMA table_info` before model initialization.
- [ ] Add SQLAlchemy/Alembic dependencies and model metadata using existing table and column names.
- [ ] Run Alembic autogeneration against a copy/staging database; no destructive migration may be generated.
- [ ] Run `python -c "from app import app, create_app; print(app.name, create_app({'TESTING': True}).testing)"` and `python -m unittest discover -s tests -v`.

### Task 5: Review, push, and prepare the pull request

**Files:**
- Modify: migrated source files and tests only
- Add: migration notes under `docs/` if operator guidance is needed

- [ ] Run `git status --short`, `git diff --stat`, and `git diff --check`; no runtime artifacts or credentials may be newly tracked.
- [ ] Run the complete Python test suite and UI/demo validation when dependencies are available.
- [ ] Commit with `git add <changed-files>; git commit -m "refactor: introduce demo backend boundaries"`.
- [ ] Push with `git push`; prepare a PR from `refactor/demo-phase1` into `main`. Merge only after review and verification.

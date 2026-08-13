# Lightweight Open-Source Project Refactor Plan

> **For agentic workers:** Execute this plan task by task and verify each checkpoint.

**Goal:** Make the streamlined five-page UI demo the product frontend while retaining the existing Flask data/import capabilities behind a maintainable modular-monolith boundary.

**Architecture:** Keep Flask, SQLite, and the current import scripts. Serve `frontend/ui_demo` as the primary frontend, preserve legacy `/` and `/static` routes during migration, and add only the API/service boundaries required by the five active business pages. Remove duplicate demo/prototype assets after route and regression coverage is established.

**Tech Stack:** Python 3, Flask, SQLite, vanilla HTML/CSS/JavaScript, unittest.

### Task 1: Promote the streamlined frontend

- [x] Copy `docs/ui_demo` into `frontend/ui_demo`.
- [x] Add `/demo/` and `/demo/<path>` routes in `app.py`.
- [x] Add route coverage for catalog and five page URLs in `tests/test_app_factory.py`.
- [x] Add root `README.md` with setup, structure, and test commands.

### Task 2: Align backend contracts

- [x] Inventory fields used by `frontend/ui_demo` and map them to existing tables/import outputs.
- [x] Reuse existing API contracts through small frontend adapters for products, promotion, lifecycle, compare, and manage; keep mock fallback for offline preview.
- [x] Keep legacy routes registered until each replacement contract passes.

### Task 3: Clean the repository after migration

- [x] Move the active demo into `frontend/ui_demo` and document the remaining historical paths under `docs/archive/`.
- [x] Audit duplicate prototype exports; preserve them as non-runtime references because historical plans still link to them.
- [x] Run the full Python suite and static asset/API route validation.

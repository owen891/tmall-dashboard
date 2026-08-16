# Data Capability Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only data capability catalog that combines semantic source definitions with live SQLite coverage evidence and exposes that catalog in Data Center.

**Architecture:** Keep the Flask + SQLite + native JavaScript architecture. A focused `data_capability_service` owns domain definitions and performs bounded aggregate queries; a thin API adapter returns the existing response envelope; Data Center renders the catalog as a governance view while request-specific page permissions remain in their existing domain APIs. Metric formulas continue to come from `services/metric_definitions.py`.

**Tech Stack:** Python 3, Flask, SQLite, `unittest`, native JavaScript, existing `DemoApi` and `DemoApi.renderDataState` helpers.

---

## File Map

### Create

- `services/data_capability_service.py`: semantic domain registry, live coverage inspection, availability classification, and unsupported-capability boundaries.
- `api/data_capabilities_api.py`: `GET /api/data-capabilities` query validation and response envelope.
- `tests/test_data_capability_service.py`: service-level coverage, availability, metric metadata, and filtering tests.
- `tests/test_data_capabilities_api.py`: endpoint envelope, filter validation, source-batch, and error tests.

### Modify

- `app.py`: register the new blueprint before `init_db` completes route setup.
- `services/metric_definitions.py`: add non-breaking display metadata and an accessor for labels, formulas, units, and aggregation rules.
- `frontend/ui_demo/pages/data-center.html`: add the capability-map summary, filters, domain table, and detail drawer (`data-modal-kind="detail"`).
- `frontend/ui_demo/assets/data-center-live.js`: load `/api/data-capabilities`, render summary/table/detail states, and preserve the existing import workflow.
- `frontend/ui_demo/assets/components.css`: add only the capability-map layout and responsive rules.
- `tests/test_frontend_prd_contract.py`: static contract for endpoint usage, capability-map hooks, unsupported boundaries, and modal classification.
- `scripts/browser_prd_gates.cjs`: browser checks for catalog states, filters, detail drawer focus/close behavior, and no fabricated coverage.
- `docs/RELEASE_NOTES.md`: record the Phase 2 catalog scope and non-goals after verification.

## Task 1: Extend Canonical Metric Metadata

**Files:**
- Modify: `services/metric_definitions.py`
- Create: `tests/test_data_capability_service.py`

- [x] **Step 1: Write the failing metadata test**

Add a test that imports `metric_metadata()` and requires every existing metric to expose `label`, `formula`, `unit`, `aggregation`, and the same dependency tuple already used by `derive_metrics()`:

```python
def test_metric_metadata_is_complete_and_matches_registry(self):
    from services.metric_definitions import METRIC_DEFINITIONS, metric_metadata

    metadata = metric_metadata()
    self.assertEqual(set(metadata), set(METRIC_DEFINITIONS))
    for name, definition in METRIC_DEFINITIONS.items():
        self.assertEqual(tuple(metadata[name]['dependencies']), tuple(definition))
        for key in ('label', 'formula', 'unit', 'aggregation'):
            self.assertTrue(metadata[name][key], name)
```

- [x] **Step 2: Run the test and confirm RED**

Run `py -3 -m unittest tests.test_data_capability_service.DataCapabilityServiceTests.test_metric_metadata_is_complete_and_matches_registry -v`.

Expected: FAIL with `ImportError` or `AttributeError` because `metric_metadata()` does not exist.

- [x] **Step 3: Implement the smallest metadata accessor**

Keep `METRIC_DEFINITIONS` as the existing ordered mapping of metric name to dependency tuple. Add one private ordered metadata mapping and return defensive copies:

```python
def metric_metadata():
    return {
        name: {**definition, 'dependencies': list(definition['dependencies'])}
        for name, definition in METRIC_METADATA.items()
    }
```

The metadata mapping must contain exactly the seven current metrics and must not change `derive_metrics()` inputs or output.

- [x] **Step 4: Run the focused test and existing metric tests**

Run `py -3 -m unittest tests.test_data_capability_service.DataCapabilityServiceTests.test_metric_metadata_is_complete_and_matches_registry tests.test_metric_definitions -v`.

Expected: all pass.

## Task 2: Build Live Data Capability Service

**Files:**
- Create: `services/data_capability_service.py`
- Modify: `tests/test_data_capability_service.py`

- [x] **Step 1: Write RED tests for empty, seeded, and filtered catalogs**

Use the existing temporary `create_app()` fixture. Assert that an initialized but empty database returns all defined domains with `no-data` coverage and that a seeded `store_daily_facts` row returns `available`, row/entity/date coverage, and the matching `source_batch_id`.

```python
def test_empty_domain_is_no_data_and_not_available(self):
    from services.data_capability_service import build_catalog
    result = build_catalog(self.app.config['DATABASE_PATH'])
    store = next(item for item in result['domains'] if item['key'] == 'store_daily')
    self.assertEqual(store['availability'], 'no-data')
    self.assertEqual(store['coverage']['row_count'], 0)
    self.assertNotIn('trend', store['capabilities'])

def test_seeded_domain_reports_coverage_metrics_and_source_batch(self):
    self._insert_store_fact()
    from services.data_capability_service import build_catalog
    store = next(item for item in build_catalog(self.app.config['DATABASE_PATH'])['domains'] if item['key'] == 'store_daily')
    self.assertEqual(store['availability'], 'available')
    self.assertEqual(store['coverage']['row_count'], 1)
    self.assertEqual(store['coverage']['entity_count'], 1)
    self.assertEqual(store['coverage']['start'], '2026-08-01')
    self.assertEqual(store['source_batches'], ['batch-1'])

def test_catalog_filters_validate_and_return_only_requested_domains(self):
    from services.data_capability_service import build_catalog
    result = build_catalog(self.app.config['DATABASE_PATH'], domain='store_daily', availability='no-data')
    self.assertEqual([item['key'] for item in result['domains']], ['store_daily'])
```

- [x] **Step 2: Run the three tests and confirm RED**

Run `py -3 -m unittest tests.test_data_capability_service -v`.

Expected: import failure because the service does not exist.

- [x] **Step 3: Implement the static domain registry**

Define exactly these domain keys: `store_daily`, `product_master`, `product_daily`, `product_weekly`, `product_monthly`, `promotion_daily`, `reviews`, `product_health`, `lifecycle`, `actions`, `goals`, `imports`, and `market`.

Each definition includes `source_tables`, `grain`, `raw_fields`, `consumer_pages`, `capabilities_when_available`, and `limitations`. Use `services.metric_definitions.metric_metadata()` to attach derived metrics to the relevant domains; do not duplicate formulas.

- [x] **Step 4: Implement bounded SQLite inspection**

For each domain, inspect only known tables and columns. Use quoted identifiers from the internal registry, not user input. Return:

```python
{
    'row_count': 0,
    'entity_count': 0,
    'start': None,
    'end': None,
    'latest_update': None,
}
```

For date-bearing tables, use `MIN`, `MAX`, `COUNT`, and `COUNT(DISTINCT product_id)` (or the domain grain’s entity column). For import-backed tables, collect distinct non-empty `source_batch_id` values and map them to `import_batches.id` where possible.

- [x] **Step 5: Implement availability classification and unsupported boundaries**

Classify a domain as `source-unavailable` when a known table is absent, `no-data` when it exists with zero rows, `partial` when rows exist but required raw fields are absent or coverage has gaps, and `available` only when required evidence exists. Add a fixed `unsupported_capabilities` list with explicit prerequisites for profit, inventory, user cohort, strict causal attribution, and complete market opportunity analysis.

- [x] **Step 6: Run service tests plus the existing metric/API tests**

Run `py -3 -m unittest tests.test_data_capability_service tests.test_metric_definitions tests.test_capability_contract -v`.

Expected: all pass with no fabricated available domains.

## Task 3: Add the Read-Only API

**Files:**
- Create: `api/data_capabilities_api.py`
- Modify: `app.py`
- Create: `tests/test_data_capabilities_api.py`

- [x] **Step 1: Write failing endpoint tests**

Add tests for the standard envelope, valid filters, and invalid filters:

```python
def test_catalog_endpoint_returns_context_and_unsupported_boundaries(self):
    response = self.client.get('/api/data-capabilities')
    self.assertEqual(response.status_code, 200)
    payload = response.get_json()
    self.assertTrue(payload['ok'])
    self.assertIn('domains', payload['data'])
    self.assertIn('unsupported_capabilities', payload['data'])
    for key in ('capabilities', 'filters', 'missing_fields', 'missing_ranges', 'source_batches'):
        self.assertIn(key, payload)

def test_unknown_catalog_filter_is_rejected(self):
    response = self.client.get('/api/data-capabilities?availability=unknown')
    self.assertEqual(response.status_code, 422)
    self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')
```

- [x] **Step 2: Run API tests and confirm RED**

Run `py -3 -m unittest tests.test_data_capabilities_api -v`.

Expected: `404` for the missing route.

- [x] **Step 3: Implement the blueprint and register it**

Use the existing `success()` and `failure()` helpers. Validate `domain` against the registry and `availability` against `AVAILABILITY_VALUES`; return `VALIDATION_ERROR` with the accepted values for unknown filters. Set endpoint capabilities to:

```python
{
    'can_export': bool(data['domains']),
    'can_view_schema': True,
    'can_edit_catalog': False,
    'can_design_pages': any(item['availability'] in {'available', 'partial'} for item in data['domains']),
}
```

Register `data_capabilities_bp` in `app.py` alongside the other API blueprints.

- [x] **Step 4: Run API tests and route smoke tests**

Run `py -3 -m unittest tests.test_data_capabilities_api tests.test_app_factory -v` and `py -3 scripts/production_preflight.py`.

Expected: endpoint tests and all eight page routes pass.

## Task 4: Add the Data Center Capability Map

**Files:**
- Modify: `frontend/ui_demo/pages/data-center.html`
- Modify: `frontend/ui_demo/assets/data-center-live.js`
- Modify: `frontend/ui_demo/assets/components.css`
- Modify: `tests/test_frontend_prd_contract.py`

- [x] **Step 1: Write failing static frontend tests**

Require the page and adapter to contain `/api/data-capabilities`, `data-capability-summary`, `data-capability-filter`, `data-capability-table`, `data-capability-detail`, and `data-modal-kind="detail"`. Also require explicit unsupported-boundary rendering and the existing import endpoint hooks.

- [x] **Step 2: Run the static tests and confirm RED**

Run `py -3 -m unittest tests.test_frontend_prd_contract.FrontendPrdContractTests.test_data_center_exposes_capability_map -v`.

Expected: `AttributeError` or assertion failure because the hooks do not exist.

- [x] **Step 3: Add the unframed capability-map markup**

Place the section above import operations. Add summary counters, a search input, an availability select, a table body, an empty-state status region, and a detail drawer. Keep the existing import preview/history sections unchanged.

- [x] **Step 4: Implement the adapter rendering**

On load, request `/api/data-capabilities`; use `DemoApi.renderDataState()` for loading/no-data/partial/failure. Render only API-provided counts and labels. Filter the in-memory domain list by search and availability. Opening a row fills source tables, grain, coverage, raw fields, derived metric formulas, consumer pages, and limitations, then opens the detail drawer and focuses its close button. Closing restores the triggering row focus.

- [x] **Step 5: Add responsive styles**

Use the existing table-wrap and modal tokens. On narrow screens, stack summary counters, allow table horizontal scrolling, and make the detail drawer fit `calc(100vw - 16px)` without page-level horizontal overflow.

- [x] **Step 6: Run frontend contract, syntax, and static validation**

Run:

```powershell
py -3 -m unittest tests.test_frontend_prd_contract tests.test_navigation_contract -v
Get-ChildItem frontend/ui_demo/assets -Filter *.js | ForEach-Object { node --check $_.FullName }
node scripts/validate_ui_demos.cjs
```

Expected: all pass and all seven primary pages remain validated.

## Task 5: Browser and Release Verification

**Files:**
- Modify: `scripts/browser_prd_gates.cjs`
- Modify: `tests/test_release_gates.py`
- Modify: `docs/RELEASE_NOTES.md`

- [x] **Step 1: Add browser-gate assertions**

With the test server running on `TMALL_SMOKE_BASE`, assert that Data Center shows four summary state counters, filtering changes the visible domain rows, a domain detail drawer declares `data-modal-kind="detail"`, and an empty market domain displays its limitation rather than a fabricated opportunity.

- [x] **Step 2: Run the targeted browser gate and fix only named failures**

Run `node scripts/browser_prd_gates.cjs` and, when diagnosing, use the test server from `scripts/run_test_server.py` so `/api/test/availability/<state>` exists. Do not loosen assertions to accommodate missing catalog behavior.

- [x] **Step 3: Run the complete verification matrix**

Run:

```powershell
py -3 -m unittest discover -s tests -p "test_*.py" -v
node scripts/validate_ui_demos.cjs
$env:TMALL_SMOKE_BASE = 'http://127.0.0.1:8773'; node scripts/browser_prd_gates.cjs
$env:TMALL_SMOKE_BASE = 'http://127.0.0.1:8773'; node scripts/smoke_core_pages.cjs
py -3 scripts/production_preflight.py
```

Expected: zero failures, zero errors, all catalog states rendered, and all eight route checks HTTP 200.

- [x] **Step 4: Record scope**

Add a Phase 2 release-note entry stating that the catalog is read-only, evidence-backed, and does not introduce profit, inventory, customer cohort, strict causal attribution, or full market opportunity features.

## Self-Review

- Spec coverage: model, domains, API, Data Center surface, errors, tests, and non-goals are covered by Tasks 1–5.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: `build_catalog(db_path, domain=None, availability=None)` returns `{summary, domains, unsupported_capabilities}`; the API passes those keys directly into `success()` and the frontend consumes the same names.

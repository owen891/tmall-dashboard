# TM Data Capability and Page System Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify metric calculation, availability/capability contracts, action ownership, page state handling, navigation context, and modal boundaries for the current single-store operating loop.

**Architecture:** Keep the existing Flask + SQLite + native JavaScript structure. Add one canonical metric derivation service and one response-context contract, then migrate domain APIs and page adapters incrementally. Preserve legacy read endpoints, make legacy action writes read-only, and use shared frontend helpers for capability gating, cross-page filters, and data states.

**Tech Stack:** Python 3, Flask, SQLite, `unittest`, native JavaScript, ECharts, existing browser/static validation scripts.

**Workspace note:** Implementation, focused verification, and release-gate steps are complete. Commit-only checklist steps remain unchecked intentionally because this worktree contains operator-owned changes and the task contract forbids staging or committing them.

---

## File Structure

### Create

- `services/metric_definitions.py`: canonical formulas, dependencies, units, and aggregation rules.
- `frontend/ui_demo/assets/navigation.js`: shared URL/filter serialization for cross-page drilldowns.
- `tests/test_metric_definitions.py`: exact formula, missing-field, and divide-by-zero coverage.
- `tests/test_capability_contract.py`: API capability and provenance contract coverage.
- `tests/test_navigation_contract.py`: navigation and modal-kind static contract coverage.

### Modify

- `api/api_response.py`: extend the success envelope with deterministic context defaults.
- `services/metrics_service.py`: derive overview metrics through the canonical registry.
- `api/overview_api.py`: expose filters, capabilities, missing fields/ranges, and source batches.
- `api/product_detail_api.py`: remove duplicate metric formulas and expose conditional capabilities.
- `api/promotion_api.py`: expose grain-aware capabilities and attribution availability.
- `api/lifecycle_api.py`: expose assessment sufficiency and edit/lock capabilities.
- `api/data_api.py`: make legacy action mutations read-only and keep legacy reads compatible.
- `frontend/ui_demo/assets/api.js`: normalize response context and provide capability helpers.
- `frontend/ui_demo/assets/shell.js`: keep seven primary domains and load the navigation helper.
- `frontend/ui_demo/assets/overview-live.js`: render contract states and preserve drilldown filters.
- `frontend/ui_demo/assets/products-live.js`: gate editing/actions/export from capabilities.
- `frontend/ui_demo/assets/product-detail-live.js`: consume canonical metrics and action capabilities.
- `frontend/ui_demo/assets/promotion-live.js`: hide unsupported attribution tabs and gate drilldowns.
- `frontend/ui_demo/assets/lifecycle-live.js`: render accumulation/seasonality states and edit capability.
- `frontend/ui_demo/assets/reviews-live.js`: consume the unified action workflow only.
- `frontend/ui_demo/pages/*.html`: declare modal kinds and include `navigation.js` on context pages.
- `tests/test_api_response.py`: extended envelope tests.
- `tests/test_action_workflow.py`: legacy read-only and unified action tests.
- `tests/test_frontend_prd_contract.py`: shared capability, state, navigation, and modal contracts.
- `scripts/browser_prd_gates.cjs`: browser assertions for capability-gated controls and retained filters.

## Task 1: Standardize the API Response Context

**Files:**
- Modify: `api/api_response.py`
- Modify: `tests/test_api_response.py`
- Create: `tests/test_capability_contract.py`

- [x] **Step 1: Write failing envelope tests**

Add these cases to `tests/test_api_response.py`:

```python
def test_success_includes_empty_context_defaults(self):
    from flask import Flask
    from api.api_response import success
    app = Flask(__name__)
    with app.test_request_context('/'):
        response, status = success({'rows': []}, availability='no-data')
        payload = response.get_json()
    self.assertEqual(status, 200)
    self.assertEqual(payload['capabilities'], {})
    self.assertEqual(payload['filters'], {})
    self.assertEqual(payload['missing_fields'], [])
    self.assertEqual(payload['missing_ranges'], [])
    self.assertEqual(payload['source_batches'], [])

def test_success_preserves_declared_context(self):
    from flask import Flask
    from api.api_response import success
    app = Flask(__name__)
    with app.test_request_context('/'):
        response, _ = success(
            {}, capabilities={'can_export': True}, filters={'product_id': 'P-1'},
            missing_fields=['payment_buyers'],
            missing_ranges=[{'start': '2026-08-01', 'end': '2026-08-02'}],
            source_batches=[{'id': 'batch-1'}],
        )
        payload = response.get_json()
    self.assertTrue(payload['capabilities']['can_export'])
    self.assertEqual(payload['filters']['product_id'], 'P-1')
    self.assertEqual(payload['missing_fields'], ['payment_buyers'])
```

- [x] **Step 2: Run tests and confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_api_response -v
```

Expected: FAIL because the five context keys are absent or `success()` rejects the new keyword arguments.

- [x] **Step 3: Extend `success()` with explicit defaults**

Replace the current `success` signature and payload assembly in `api/api_response.py` with:

```python
AVAILABILITY_VALUES = {
    'available', 'no-data', 'insufficient-data', 'missing-fields',
    'calculation-failed', 'source-unavailable', 'partial',
}


def success(data, availability='available', status=200, *, capabilities=None,
            filters=None, missing_fields=None, missing_ranges=None, source_batches=None):
    normalized = availability if availability in AVAILABILITY_VALUES else 'calculation-failed'
    return jsonify({
        'ok': True,
        'data': data,
        'availability': normalized,
        'capabilities': dict(capabilities or {}),
        'filters': dict(filters or {}),
        'missing_fields': list(missing_fields or []),
        'missing_ranges': list(missing_ranges or []),
        'source_batches': list(source_batches or []),
        'requestId': uuid4().hex,
    }), status
```

- [x] **Step 4: Run the response tests**

Run the Step 2 command. Expected: all `ApiResponseTests` pass.

- [x] **Step 5: Add a domain contract test**

In `tests/test_capability_contract.py`, create an app with a temporary database, call `/api/overview`, `/api/promotion`, and `/api/lifecycle/assessments`, and assert all successful domain responses contain the five context keys and a non-empty `requestId`.

- [ ] **Step 6: Commit the response contract**

```powershell
git add api/api_response.py tests/test_api_response.py tests/test_capability_contract.py
git commit -m "feat: standardize domain response context"
```

## Task 2: Create the Canonical Metric Registry

**Files:**
- Create: `services/metric_definitions.py`
- Create: `tests/test_metric_definitions.py`
- Modify: `services/metrics_service.py`
- Modify: `api/product_detail_api.py`

- [x] **Step 1: Write exact formula tests**

Create `tests/test_metric_definitions.py` with cases for complete input, missing dependencies, and zero denominators:

```python
import unittest

from services.metric_definitions import derive_metrics


class MetricDefinitionTests(unittest.TestCase):
    def test_derives_sum_then_ratio_metrics(self):
        result = derive_metrics({
            'payment_amount': 1000, 'successful_refund_amount': 100,
            'product_visitors': 200, 'payment_buyers': 20,
            'returning_payment_buyers': 5, 'ad_spend': 80,
            'attributed_payment_amount': 240,
        })
        self.assertEqual(result['values']['net_sales'], 900.0)
        self.assertEqual(result['values']['refund_rate'], 0.1)
        self.assertEqual(result['values']['payment_conversion_rate'], 0.1)
        self.assertEqual(result['values']['average_order_value'], 50.0)
        self.assertEqual(result['values']['expense_ratio'], 0.08)
        self.assertEqual(result['values']['ad_roi'], 3.0)
        self.assertEqual(result['values']['returning_buyer_ratio'], 0.25)
        self.assertEqual(result['missing_fields'], [])

    def test_marks_missing_dependencies_without_fabricating_zero(self):
        result = derive_metrics({'payment_amount': 1000})
        self.assertIsNone(result['values']['payment_conversion_rate'])
        self.assertIn('payment_buyers', result['missing_fields'])
        self.assertIn('product_visitors', result['missing_fields'])

    def test_zero_denominator_is_not_a_metric_value(self):
        result = derive_metrics({'payment_amount': 0, 'successful_refund_amount': 0, 'ad_spend': 0})
        self.assertIsNone(result['values']['refund_rate'])
        self.assertIsNone(result['values']['expense_ratio'])
```

- [x] **Step 2: Run the metric tests and confirm import failure**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_metric_definitions -v
```

Expected: ERROR because `services.metric_definitions` does not exist.

- [x] **Step 3: Implement the registry and derivation result**

Create `services/metric_definitions.py` with immutable metric definitions for `net_sales`, `refund_rate`, `payment_conversion_rate`, `average_order_value`, `expense_ratio`, `ad_roi`, and `returning_buyer_ratio`. Implement `derive_metrics(totals)` to return:

```python
{
    'values': {'net_sales': 900.0, 'refund_rate': 0.1},
    'metric_availability': {'ad_roi': 'missing-fields'},
    'missing_fields': ['attributed_payment_amount'],
}
```

Use a private `_ratio()` that returns `None` for `None` or zero denominators and rounds to six decimal places.

- [x] **Step 4: Replace duplicate formulas**

Update `services/metrics_service.py::build_overview()` and `api/product_detail_api.py::product_detail()` to call `derive_metrics()`. Preserve existing response keys and expose `metric_availability` from the registry.

- [x] **Step 5: Run focused metric and product-detail tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_metric_definitions tests.test_product_detail_api tests.test_api_contract -v
```

Expected: all tests pass and product-detail payloads retain their existing keys.

- [ ] **Step 6: Commit canonical metrics**

```powershell
git add services/metric_definitions.py services/metrics_service.py api/product_detail_api.py tests/test_metric_definitions.py
git commit -m "refactor: centralize operating metric formulas"
```

## Task 3: Add Domain Capabilities and Provenance

**Files:**
- Modify: `api/overview_api.py`
- Modify: `api/promotion_api.py`
- Modify: `api/lifecycle_api.py`
- Modify: `repos/metrics_repo.py`
- Modify: `services/promotion_service.py`
- Modify: `services/lifecycle_service.py`
- Modify: `tests/test_capability_contract.py`
- Modify: `tests/test_promotion_api.py`
- Modify: `tests/test_lifecycle_api.py`

- [x] **Step 1: Write failing capability tests**

Cover these exact rules:

```python
self.assertTrue(overview['capabilities']['can_export'])
self.assertEqual(overview['filters']['product_id'], 'P-1')
self.assertIsInstance(overview['source_batches'], list)
self.assertFalse(promotion_no_rows['capabilities']['can_drilldown'])
self.assertFalse(promotion_missing_unit['capabilities']['can_group_by_unit'])
self.assertFalse(lifecycle_short_history['capabilities']['can_edit_stage'])
self.assertEqual(lifecycle_short_history['availability'], 'insufficient-data')
```

- [x] **Step 2: Run the focused tests and confirm missing keys**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_capability_contract tests.test_promotion_api tests.test_lifecycle_api -v
```

Expected: FAIL on missing `capabilities`, `filters`, or provenance fields.

- [x] **Step 3: Return domain-specific capabilities**

Use these keys:

```python
OVERVIEW_CAPABILITIES = {
    'can_export': True, 'can_drilldown': True,
    'can_edit': False, 'can_create_action': True,
}
PROMOTION_CAPABILITIES = {
    'can_export': bool(rows), 'can_drilldown': bool(rows),
    'can_group_by_campaign': has_campaign,
    'can_group_by_unit': has_unit,
    'can_group_by_product': has_product,
}
LIFECYCLE_CAPABILITIES = {
    'can_export': bool(rows), 'can_edit_stage': enough_days,
    'can_lock_stage': enough_days, 'can_infer_seasonality': complete_months >= 12,
}
```

Pass the accepted filters, missing dependencies, date gaps, and source batches through `success()` instead of embedding them in UI-specific strings.

- [x] **Step 4: Verify capability behavior**

Run the Step 2 command. Expected: all focused tests pass.

- [ ] **Step 5: Commit domain context**

```powershell
git add api/overview_api.py api/promotion_api.py api/lifecycle_api.py repos/metrics_repo.py services/promotion_service.py services/lifecycle_service.py tests/test_capability_contract.py tests/test_promotion_api.py tests/test_lifecycle_api.py
git commit -m "feat: expose data capabilities and provenance"
```

## Task 4: Make the New Action Workflow the Only Write Path

**Files:**
- Modify: `api/data_api.py`
- Modify: `services/actions_service.py`
- Modify: `tests/test_action_workflow.py`
- Modify: `tests/test_api_contract.py`

- [x] **Step 1: Add failing legacy-write tests**

Add tests asserting:

```python
for method, path in (
    ('POST', '/api/legacy/actions'),
    ('PUT', '/api/legacy/actions/1'),
    ('DELETE', '/api/legacy/actions/1'),
):
    status, payload = self.request(method, path, json={})
    self.assertEqual(status, 409)
    self.assertEqual(payload['code'], 'LEGACY_READ_ONLY')
```

Also assert `GET /api/legacy/actions` remains available and `POST /api/actions` creates only a `product_actions` row.

- [x] **Step 2: Run action tests and confirm legacy writes still succeed or validate differently**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_workflow tests.test_api_contract -v
```

Expected: FAIL on legacy mutation status/code.

- [x] **Step 3: Reject legacy mutations without deleting history**

Replace the three legacy mutation route bodies with:

```python
return failure(
    'LEGACY_READ_ONLY',
    '历史动作仅供读取；请使用 /api/actions 创建和推进运营动作。',
    details={'replacement': '/api/actions'},
    status=409,
)
```

Keep the legacy GET response unchanged. Do not migrate or delete the 99 historical rows in this phase.

- [x] **Step 4: Align transition constants with the design**

Keep the existing legal chain and exceptional states. Add a unit assertion that `completed` can only be reached through `ActionsService.review()` and that observation-window failures never set `completed`.

- [x] **Step 5: Run action tests**

Run the Step 2 command. Expected: all action and API contract tests pass.

- [ ] **Step 6: Commit action ownership**

```powershell
git add api/data_api.py services/actions_service.py tests/test_action_workflow.py tests/test_api_contract.py
git commit -m "fix: make legacy actions read only"
```

## Task 5: Normalize Frontend State and Capability Gating

**Files:**
- Modify: `frontend/ui_demo/assets/api.js`
- Modify: `frontend/ui_demo/assets/overview-live.js`
- Modify: `frontend/ui_demo/assets/products-live.js`
- Modify: `frontend/ui_demo/assets/product-detail-live.js`
- Modify: `frontend/ui_demo/assets/promotion-live.js`
- Modify: `frontend/ui_demo/assets/lifecycle-live.js`
- Modify: `frontend/ui_demo/assets/compare-live.js`
- Modify: `frontend/ui_demo/assets/data-center-live.js`
- Modify: `frontend/ui_demo/assets/goals-live.js`
- Modify: `frontend/ui_demo/assets/reviews-live.js`
- Modify: `frontend/ui_demo/assets/settings-live.js`
- Modify: `frontend/ui_demo/assets/manage-live.js`
- Modify: `tests/test_frontend_prd_contract.py`

- [x] **Step 1: Add failing static frontend contracts**

Require the shared client to expose these helpers:

```javascript
DemoApi.can(payload, 'can_export')
DemoApi.context(payload)
DemoApi.renderDataState(container, payload.availability, details)
```

Require product action controls, promotion drilldowns, lifecycle editing, goal adjustment/locking, import confirmation/revert, settings save, task/schedule operations, and export buttons to check `DemoApi.can(...)` before enabling the action.

- [x] **Step 2: Run frontend contract tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_prd_contract -v
```

Expected: FAIL because `can` and `context` do not exist and page adapters do not gate controls.

- [x] **Step 3: Implement shared normalization**

Add to `frontend/ui_demo/assets/api.js`:

```javascript
function context(payload = {}) {
  return {
    availability: payload.availability || 'calculation-failed',
    capabilities: payload.capabilities || {},
    filters: payload.filters || {},
    missingFields: payload.missing_fields || [],
    missingRanges: payload.missing_ranges || [],
    sourceBatches: payload.source_batches || []
  };
}
function can(payload, name) {
  return payload?.capabilities?.[name] === true;
}
```

Export both functions on `window.DemoApi`.

- [x] **Step 4: Gate page operations**

For each adapter, set `disabled`, `hidden`, and an explanatory state message from the response contract. Do not infer support from row count or optional fields when a capability key exists. Preserve the existing row-count behavior only as a fallback for legacy endpoints.

- [x] **Step 5: Run JavaScript syntax and contract tests**

```powershell
node --check frontend/ui_demo/assets/api.js
node --check frontend/ui_demo/assets/overview-live.js
node --check frontend/ui_demo/assets/products-live.js
node --check frontend/ui_demo/assets/product-detail-live.js
node --check frontend/ui_demo/assets/promotion-live.js
node --check frontend/ui_demo/assets/lifecycle-live.js
node --check frontend/ui_demo/assets/compare-live.js
node --check frontend/ui_demo/assets/data-center-live.js
node --check frontend/ui_demo/assets/goals-live.js
node --check frontend/ui_demo/assets/reviews-live.js
node --check frontend/ui_demo/assets/settings-live.js
node --check frontend/ui_demo/assets/manage-live.js
.\.venv\Scripts\python.exe -m unittest tests.test_frontend_prd_contract -v
```

Expected: every command exits 0.

- [ ] **Step 6: Commit frontend capability gating**

```powershell
git add frontend/ui_demo/assets/api.js frontend/ui_demo/assets/overview-live.js frontend/ui_demo/assets/products-live.js frontend/ui_demo/assets/product-detail-live.js frontend/ui_demo/assets/promotion-live.js frontend/ui_demo/assets/lifecycle-live.js frontend/ui_demo/assets/compare-live.js frontend/ui_demo/assets/data-center-live.js frontend/ui_demo/assets/goals-live.js frontend/ui_demo/assets/reviews-live.js frontend/ui_demo/assets/settings-live.js frontend/ui_demo/assets/manage-live.js tests/test_frontend_prd_contract.py
git commit -m "feat: gate page operations by data capability"
```

## Task 6: Preserve Context Across Pages and Classify Modals

**Files:**
- Create: `frontend/ui_demo/assets/navigation.js`
- Create: `tests/test_navigation_contract.py`
- Modify: `frontend/ui_demo/assets/shell.js`
- Modify: `frontend/ui_demo/pages/overview.html`
- Modify: `frontend/ui_demo/pages/products.html`
- Modify: `frontend/ui_demo/pages/product-detail.html`
- Modify: `frontend/ui_demo/pages/promotion.html`
- Modify: `frontend/ui_demo/pages/lifecycle.html`
- Modify: `frontend/ui_demo/pages/goals.html`
- Modify: `frontend/ui_demo/pages/reviews.html`
- Modify: `frontend/ui_demo/pages/data-center.html`
- Modify: `frontend/ui_demo/pages/settings.html`

- [x] **Step 1: Write navigation and modal contract tests**

Assert that `navigation.js` serializes only supported filter keys and that every dialog/drawer declares one of:

```text
data-modal-kind="detail"
data-modal-kind="edit"
data-modal-kind="config"
data-modal-kind="flow"
```

Assert that the primary nav remains exactly: overview, products, promotion, lifecycle, reviews, data-center, settings.

- [x] **Step 2: Run navigation tests and confirm failure**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_navigation_contract -v
```

Expected: FAIL because the helper and modal-kind attributes do not exist.

- [x] **Step 3: Implement the navigation helper**

Create `frontend/ui_demo/assets/navigation.js`:

```javascript
(function () {
  const allowed = new Set(['start', 'end', 'preset', 'compare', 'product_id', 'tier', 'lifecycle_stage', 'promotion_channel', 'action_id']);
  function build(path, values = {}) {
    const url = new URL(path, window.location.origin);
    Object.entries(values).forEach(([key, value]) => {
      if (allowed.has(key) && value != null && value !== '') url.searchParams.set(key, value);
    });
    return `${url.pathname}${url.search}`;
  }
  window.DemoNavigation = { build };
})();
```

- [x] **Step 4: Wire contextual links**

Use `DemoNavigation.build()` for overview-to-products, products-to-promotion, products-to-lifecycle, product-detail-to-reviews, and target-to-overview links. Preserve incoming query parameters when a context page returns to its source.

- [x] **Step 5: Add modal-kind declarations**

Classify existing product/lifecycle/promotion detail drawers as `detail`; column/field settings as `config`; lifecycle/event edits as `edit`; imports, target locks, transitions, and reviews as `flow`.

- [x] **Step 6: Run navigation, frontend contract, and syntax tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_navigation_contract tests.test_frontend_prd_contract -v
node --check frontend/ui_demo/assets/navigation.js
node --check frontend/ui_demo/assets/shell.js
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit context navigation and modal boundaries**

```powershell
git add frontend/ui_demo/assets/navigation.js frontend/ui_demo/assets/shell.js frontend/ui_demo/pages/overview.html frontend/ui_demo/pages/products.html frontend/ui_demo/pages/product-detail.html frontend/ui_demo/pages/promotion.html frontend/ui_demo/pages/lifecycle.html frontend/ui_demo/pages/goals.html frontend/ui_demo/pages/reviews.html frontend/ui_demo/pages/data-center.html frontend/ui_demo/pages/settings.html tests/test_navigation_contract.py tests/test_frontend_prd_contract.py
git commit -m "feat: preserve drilldown context across pages"
```

## Task 7: Run the Release Verification Matrix

**Files:**
- Modify: `scripts/browser_prd_gates.cjs`
- Modify: `tests/test_release_gates.py`
- Modify: `docs/RELEASE_NOTES.md`

- [x] **Step 1: Add release-gate assertions**

Add browser assertions for:

- unsupported promotion tabs are disabled with a reason;
- lifecycle edit controls are disabled for insufficient data;
- overview drilldowns preserve filters in the destination URL;
- flow modals expose their impact text;
- all seven primary pages render `available`, `no-data`, and `partial` without console errors.

- [x] **Step 2: Run the new gate and confirm any missing behavior**

```powershell
node scripts/browser_prd_gates.cjs
```

Expected before final fixes: the script identifies any page that does not retain filters or explain a disabled capability.

- [x] **Step 3: Fix only failures introduced or exposed by this phase**

Update the adapter or page named by each assertion. Do not add new product capabilities or dependencies.

- [x] **Step 4: Run the complete backend suite**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Expected: exit 0, zero failures and zero errors.

- [x] **Step 5: Run static and browser verification**

```powershell
node scripts/validate_ui_demos.cjs
node scripts/browser_prd_gates.cjs
node scripts/smoke_core_pages.cjs
```

Expected: every command exits 0 and reports all configured pages checked.

- [x] **Step 6: Run the production preflight**

```powershell
.\.venv\Scripts\python.exe scripts/production_preflight.py
```

Expected: exit 0 with database integrity, migration, API, browser, and release-gate checks passing.

- [x] **Step 7: Record the delivered scope**

Add one release-note entry stating that Phase 1 standardizes metric formulas, capability/provenance contracts, action write ownership, data states, cross-page context, and modal classification. State explicitly that profit, inventory, user cohort, strict attribution, and full market opportunity analysis remain out of scope.

- [ ] **Step 8: Commit release evidence**

```powershell
git add scripts/browser_prd_gates.cjs tests/test_release_gates.py docs/RELEASE_NOTES.md
git commit -m "test: gate data capability page system"
```

## Completion Criteria

- All new domain responses expose consistent context keys.
- Overview and product-detail metrics come from one formula registry.
- Legacy action history remains readable and legacy mutation endpoints are read-only.
- Frontend controls follow explicit capability flags and render all data states.
- Cross-page drilldowns retain supported filters.
- Every modal/drawer has one declared modal kind.
- Full backend, static, browser, smoke, and production-preflight commands exit 0.
- No market, profit, inventory, user cohort, or causal-attribution feature is introduced.

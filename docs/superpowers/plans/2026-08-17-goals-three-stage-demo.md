# 经营目标三段式 Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付中文三段式经营目标页面，使年度目标按去年同期销售占比预览并分配，且每个月可行内修改和独立锁定。

**Architecture:** 后端新增只读分配预览，直接复用年度保存使用的 `_allocate()` 日级算法并按月汇总，保证预览金额与保存后的月度金额一致。周期接口保留既有审计和锁定语义，补充每月来源；前端将旧的周期调整表单替换为行内月度编辑表。

**Tech Stack:** Flask、SQLite、Python unittest、原生 HTML/CSS/JavaScript。

---

### Task 1: 分配预览 API

**Files:**
- Modify: `api/goals_api.py`
- Modify: `services/goals_service.py`
- Test: `tests/test_goals_service.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_allocation_preview_uses_store_daily_sales_proportion(self):
    self.seed_store_daily_fact('2025-01-01', 100)
    self.seed_store_daily_fact('2025-02-01', 300)
    status, preview = self.request('GET', '/api/goals/2026/allocation-preview?annual_target=1200')
    self.assertEqual(status, 200)
    months = preview['data']['months']
    self.assertEqual(months[0]['suggested_target'], 300.0)
    self.assertEqual(months[1]['suggested_target'], 900.0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_goals_service.GoalsServiceTest.test_allocation_preview_uses_store_daily_sales_proportion -v`

Expected: `FAIL` because `/allocation-preview` does not exist.

- [ ] **Step 3: Implement one shared preview allocation path**

```python
def allocation_preview(self, year, annual_target):
    days = _days_for_year(year)
    weights = GoalsRepo.prior_year_daily_weights(year)
    allocated = _allocate(annual_target, days, weights)
    return _monthly_preview(year, annual_target, allocated, weights)
```

Expose it from `GET /api/goals/<year>/allocation-preview`; validate `annual_target` as a non-negative number. `_monthly_preview` must aggregate the allocated day amounts by `YYYY-MM`, aggregate historical net sales by the same day mapping, calculate percentage from the positive historical total, and return `allocation_basis` as `去年同期销售占比` or `按天均分兜底`.

- [ ] **Step 4: Run focused tests**

Run: `python -m unittest tests.test_goals_service -v`

Expected: all goal-service tests pass.

### Task 2: 保存与预览一致性、月度来源

**Files:**
- Modify: `repos/goals_repo.py`
- Modify: `services/goals_service.py`
- Test: `tests/test_goals_service.py`

- [ ] **Step 1: Write failing behavior tests**

```python
def test_allocation_preview_matches_saved_month_totals_without_history(self):
    _, preview = self.request('GET', '/api/goals/2026/allocation-preview?annual_target=36500')
    self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
    _, periods = self.request('GET', '/api/goals/2026/periods')
    self.assertEqual(
        [row['suggested_target'] for row in preview['data']['months']],
        [row['target_amount'] for row in periods['data']['months']],
    )

def test_periods_marks_adjusted_month_as_manual(self):
    _, created = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
    self.request('POST', '/api/goals/2026/adjustments', json={
        'version': created['data']['version'], 'period_type': 'month', 'period_key': '2026-01',
        'target_amount': 4000, 'operator': '运营人员', 'reason': '月度调整',
    })
    _, periods = self.request('GET', '/api/goals/2026/periods')
    self.assertEqual(periods['data']['months'][0]['source'], 'manual')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_goals_service.GoalsServiceTest.test_allocation_preview_matches_saved_month_totals_without_history tests.test_goals_service.GoalsServiceTest.test_periods_marks_adjusted_month_as_manual -v`

Expected: `FAIL` because preview and monthly source are missing.

- [ ] **Step 3: Implement data contract**

```python
months = GoalsRepo.periods(year)['months']
manual_months = GoalsRepo.manual_months(year)
for month in months:
    month['source'] = 'manual' if month['period_key'] in manual_months else 'automatic'
```

Implement `GoalsRepo.manual_months(year)` with a grouped `goal_adjustments` query filtered to `period_type = 'month'`. Do not infer manual status from raw daily rows because a user adjustment is an auditable period event.

- [ ] **Step 4: Run focused tests**

Run: `python -m unittest tests.test_goals_service -v`

Expected: all goal-service tests pass.

### Task 3: 中文三段式页面与行内编辑

**Files:**
- Modify: `frontend/ui_demo/pages/goals.html`
- Modify: `frontend/ui_demo/assets/goals-live.js`
- Modify: `frontend/ui_demo/assets/components.css`
- Modify: `tests/test_frontend_prd_contract.py`

- [ ] **Step 1: Write a failing frontend contract test**

```python
def test_goals_page_uses_three_stage_monthly_editing(self):
    page = self.read('frontend/ui_demo/pages/goals.html')
    adapter = self.read('frontend/ui_demo/assets/goals-live.js')
    self.assertIn('自动分配依据', page)
    self.assertIn('data-goals-allocation-preview', page)
    self.assertIn('data-goals-month-target', adapter)
    self.assertNotIn('data-goals-adjust-form', page)
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `python -m unittest tests.test_frontend_prd_contract.FrontendPrdContractTest.test_goals_page_uses_three_stage_monthly_editing -v`

Expected: `FAIL` because the old independent adjustment form is still present.

- [ ] **Step 3: Replace the page markup and controller**

```javascript
input.name = 'target_amount';
input.dataset.goalsMonthTarget = month.period_key;
input.disabled = locked;
saveButton.addEventListener('click', () => saveMonth(month.period_key, input));
lockButton.addEventListener('click', () => lockMonth(month.period_key));
```

Render the three named sections in Chinese. Request the preview when the annual target input changes; submit the annual form only through `POST /api/goals`. Render twelve preview rows and twelve executable monthly rows. A completely locked month is disabled; an unlocked month posts `period_type: 'month'`, `operator: '运营人员'`, and a clear Chinese reason. Remove old period filter/level browser and the old adjustment form. Use document scrolling only; no fixed-height or nested vertical overflow on goals panels.

- [ ] **Step 4: Run the frontend contract test**

Run: `python -m unittest tests.test_frontend_prd_contract -v`

Expected: all frontend contract tests pass after updating obsolete assertions to the new contract.

### Task 4: End-to-end verification

**Files:**
- Test: `tests/test_goals_service.py`

- [ ] **Step 1: Run relevant API and frontend tests**

Run: `python -m unittest tests.test_goals_service tests.test_frontend_prd_contract -v`

Expected: pass.

- [ ] **Step 2: Run the full suite**

Run: `python -m unittest discover -s tests -v`

Expected: pass.

- [ ] **Step 3: Browser smoke test**

Open `http://127.0.0.1:8770/goals` at 1440px and 390px. Confirm preview changes after typing an annual target, an unlocked month is editable and saves, a quarter lock disables its three months, and mouse-wheel scrolling reaches every section.

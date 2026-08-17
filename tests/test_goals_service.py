import os
import sys
import tempfile
import unittest
from datetime import date


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class GoalsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-goals-tests-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from app import create_app

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def request(self, method, path, **kwargs):
        response = self.client.open(path, method=method, **kwargs)
        payload = response.get_json()
        status = response.status_code
        response.close()
        return status, payload

    def test_create_leap_year_allocation_conserves_annual_total(self):
        status, payload = self.request(
            'POST', '/api/goals', json={'year': 2024, 'annual_target': 36600},
        )

        self.assertEqual(status, 201)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['version'], 1)
        self.assertEqual(payload['data']['day_count'], 366)
        self.assertEqual(payload['data']['annual_total'], 36600.0)

        status, details = self.request('GET', '/api/goals/2024')
        self.assertEqual(status, 200)
        self.assertEqual(details['data']['annual_total'], 36600.0)
        self.assertEqual(sum(day['target_amount'] for day in details['data']['days']), 36600.0)
        self.assertEqual(len(details['data']['days']), 366)

    def test_allocation_uses_prior_year_daily_sales_weights_when_available(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.executemany(
                "INSERT INTO daily_data (product_id, date, payment_amount) VALUES ('weight-a', ?, ?)",
                [('2025-01-01', 100), ('2025-01-02', 300)],
            )
            connection.commit()
        status, _ = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        self.assertEqual(status, 201)
        _, details = self.request('GET', '/api/goals/2026')
        values = {row['goal_date']: row['target_amount'] for row in details['data']['days']}
        self.assertGreater(values['2026-01-02'], values['2026-01-01'])

    def test_allocation_uses_store_daily_weights_when_store_facts_are_authoritative(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.executemany(
                "INSERT INTO store_daily_facts (shop_id, date, payment_amount, successful_refund_amount) VALUES ('default', ?, ?, ?)",
                [('2025-01-01', 100, 0), ('2025-01-02', 300, 0)],
            )
            connection.executemany(
                "INSERT INTO daily_data (product_id, date, payment_amount, refund_amount) VALUES ('weight-conflict', ?, ?, 0)",
                [('2025-01-01', 900), ('2025-01-02', 100)],
            )
            connection.commit()

        status, _ = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 1000})
        self.assertEqual(status, 201)
        _, details = self.request('GET', '/api/goals/2026')
        values = {row['goal_date']: row['target_amount'] for row in details['data']['days']}
        self.assertEqual(values['2026-01-01'], 250.0)
        self.assertEqual(values['2026-01-02'], 750.0)
        self.assertEqual(values['2026-01-03'], 0.0)

    def test_allocation_preview_uses_store_daily_sales_proportion(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.executemany(
                "INSERT INTO store_daily_facts (shop_id, date, payment_amount, successful_refund_amount) VALUES ('default', ?, ?, 0)",
                [('2025-01-01', 100), ('2025-02-01', 300)],
            )
            connection.executemany(
                "INSERT INTO daily_data (product_id, date, payment_amount, refund_amount) VALUES ('preview-conflict', ?, ?, 0)",
                [('2025-01-01', 900), ('2025-02-01', 100)],
            )
            connection.commit()

        status, preview = self.request('GET', '/api/goals/2026/allocation-preview?annual_target=1200')

        self.assertEqual(status, 200)
        months = preview['data']['months']
        self.assertEqual(months[0]['suggested_target'], 300.0)
        self.assertEqual(months[1]['suggested_target'], 900.0)
        self.assertEqual(months[0]['prior_year_net_sales'], 100.0)
        self.assertEqual(months[1]['prior_year_net_sales'], 300.0)
        self.assertEqual(preview['data']['allocation_basis'], '去年同期销售占比')

    def test_allocation_preview_matches_saved_month_totals_without_history(self):
        status, preview = self.request('GET', '/api/goals/2026/allocation-preview?annual_target=36500')
        self.assertEqual(status, 200)
        status, _ = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        self.assertEqual(status, 201)
        status, periods = self.request('GET', '/api/goals/2026/periods')
        self.assertEqual(status, 200)
        self.assertEqual(
            [row['suggested_target'] for row in preview['data']['months']],
            [row['target_amount'] for row in periods['data']['months']],
        )
        self.assertEqual(preview['data']['allocation_basis'], '按天均分兜底')

    def test_weighted_allocation_never_creates_negative_day_target(self):
        from services.goals_service import _allocate
        from repos.goals_repo import GoalsRepo
        days = [date(2026, 1, index) for index in range(1, 5)]
        weights = {'01-01': 51, '01-02': 51, '01-03': 51, '01-04': 47}

        allocation = _allocate(0.02, days, weights)
        rows = [{'goal_date': day.isoformat(), 'target_amount': weight / 100} for day, weight in zip(days, (51, 51, 51, 47))]
        adjusted = GoalsRepo._allocate_rows(rows, 0.02, 2, 2026, '边界测试')

        self.assertEqual(sum(amount for _, amount in allocation), 0.02)
        self.assertGreaterEqual(min(amount for _, amount in allocation), 0)
        self.assertEqual(round(sum(value[0] for value in adjusted), 2), 0.02)
        self.assertGreaterEqual(min(value[0] for value in adjusted), 0)

    def test_goal_amounts_are_normalized_to_cents(self):
        status, payload = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 0.001})

        self.assertEqual(status, 201)
        self.assertEqual(payload['data']['annual_total'], 0.0)
        status, details = self.request('GET', '/api/goals/2026')
        self.assertEqual(status, 200)
        self.assertEqual(details['data']['annual_total'], 0.0)
        self.assertEqual(details['data']['annual_target'], 0.0)

    def test_stale_version_and_cross_month_week_lock_are_rejected(self):
        status, created = self.request(
            'POST', '/api/goals', json={'year': 2026, 'annual_target': 36500},
        )
        self.assertEqual(status, 201)
        version = created['data']['version']

        status, locked = self.request(
            'POST', '/api/goals/2026/locks',
            json={'version': version, 'period_type': 'month', 'period_key': '2026-03'},
        )
        self.assertEqual(status, 201)
        self.assertTrue(locked['ok'])

        status, conflict = self.request(
            'POST', '/api/goals/2026/locks',
            json={'version': version, 'period_type': 'week', 'period_key': '2026-W14'},
        )
        self.assertEqual(status, 409)
        self.assertEqual(conflict['code'], 'CONFLICT')

        status, stale = self.request(
            'POST', '/api/goals',
            json={'year': 2026, 'annual_target': 40000, 'version': version - 1},
        )
        self.assertEqual(status, 409)
        self.assertEqual(stale['code'], 'CONFLICT')

    def test_period_endpoint_aggregates_atomic_daily_goals(self):
        status, _ = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        self.assertEqual(status, 201)
        status, periods = self.request('GET', '/api/goals/2026/periods')
        self.assertEqual(status, 200)
        self.assertEqual(sum(row['target_amount'] for row in periods['data']['months']), 36500.0)
        self.assertEqual(len(periods['data']['months']), 12)
        self.assertEqual({row['source'] for row in periods['data']['months']}, {'automatic'})

    def test_periods_marks_adjusted_month_as_manual(self):
        _, created = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        status, _ = self.request('POST', '/api/goals/2026/adjustments', json={
            'version': created['data']['version'], 'period_type': 'month', 'period_key': '2026-01',
            'target_amount': 4000, 'operator': '运营人员', 'reason': '月度调整',
        })
        self.assertEqual(status, 200)
        status, periods = self.request('GET', '/api/goals/2026/periods')
        self.assertEqual(status, 200)
        self.assertEqual(periods['data']['months'][0]['source'], 'manual')

    def test_locked_year_cannot_be_reallocated(self):
        _, created = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        status, _ = self.request('POST', '/api/goals/2026/locks', json={
            'version': created['data']['version'], 'period_type': 'month', 'period_key': '2026-04',
        })
        self.assertEqual(status, 201)
        status, response = self.request('POST', '/api/goals', json={
            'year': 2026, 'annual_target': 40000, 'version': created['data']['version'],
        })
        self.assertEqual(status, 409)
        self.assertEqual(response['code'], 'CONFLICT')

    def test_orphan_locks_do_not_block_initializing_missing_daily_goals(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.execute(
                'INSERT INTO goal_versions (year, version, annual_target) VALUES (?, ?, ?)',
                (2026, 1, 8800000),
            )
            connection.executemany(
                'INSERT INTO goal_locks (year, period_type, period_key, version) VALUES (?, ?, ?, ?)',
                [(2026, 'month', '2026-01', 1), (2026, 'month', '2026-08', 1)],
            )
            connection.commit()

        status, payload = self.request('POST', '/api/goals', json={
            'year': 2026, 'annual_target': 2000000, 'version': 1,
        })

        self.assertEqual(status, 201)
        self.assertEqual(payload['data']['annual_total'], 2000000.0)
        status, periods = self.request('GET', '/api/goals/2026/periods')
        self.assertEqual(status, 200)
        self.assertEqual(len(periods['data']['months']), 12)
        self.assertEqual(periods['data']['locked_months'], [])

    def test_adjust_period_redistributes_only_unlocked_days_and_keeps_audit(self):
        _, created = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        status, adjusted = self.request('POST', '/api/goals/2026/adjustments', json={
            'version': created['data']['version'], 'period_type': 'date', 'period_key': '2026-01-01',
            'target_amount': 200, 'operator': 'operator', 'reason': '大促预留', 'lock': True,
        })
        self.assertEqual(status, 200)
        self.assertTrue(adjusted['ok'])
        status, details = self.request('GET', '/api/goals/2026')
        self.assertEqual(status, 200)
        self.assertEqual(details['data']['days'][0]['target_amount'], 200)
        self.assertTrue(details['data']['days'][0]['locked'])
        self.assertEqual(round(details['data']['annual_total'], 2), 36500)
        self.assertEqual(len(details['data']['adjustments']), 1)

    def test_all_five_period_levels_can_be_adjusted_or_locked(self):
        _, created = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        version = created['data']['version']
        status, updated = self.request('POST', '/api/goals/2026/adjustments', json={
            'version': version, 'period_type': 'quarter', 'period_key': '2026-Q1',
            'target_amount': 9500, 'operator': 'operator', 'reason': 'quarter plan', 'lock': False,
        })
        self.assertEqual(status, 200)
        status, details = self.request('GET', '/api/goals/2026')
        self.assertEqual(status, 200)
        self.assertEqual(round(details['data']['annual_total'], 2), 36500)
        status, locked = self.request('POST', '/api/goals/2026/locks', json={
            'version': updated['data']['version'], 'period_type': 'quarter', 'period_key': '2026-Q1',
        })
        self.assertEqual(status, 201)
        self.assertTrue(locked['data']['locked'])

    def test_adjustment_lock_preserves_selected_period_grain(self):
        _, created = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        status, adjusted = self.request('POST', '/api/goals/2026/adjustments', json={
            'version': created['data']['version'], 'period_type': 'month', 'period_key': '2026-03',
            'target_amount': 3200, 'operator': 'operator', 'reason': '三月活动', 'lock': True,
        })
        self.assertEqual(status, 200)
        status, details = self.request('GET', '/api/goals/2026')
        self.assertEqual(status, 200)
        self.assertEqual(round(details['data']['annual_total'], 2), 36500)
        self.assertIn({'period_type': 'month', 'period_key': '2026-03', 'version': adjusted['data']['version']}, details['data']['locks'])

    def test_period_lock_marks_all_covered_days_and_months_as_locked(self):
        _, created = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        status, _ = self.request('POST', '/api/goals/2026/locks', json={
            'version': created['data']['version'], 'period_type': 'quarter', 'period_key': '2026-Q1',
        })
        self.assertEqual(status, 201)

        status, details = self.request('GET', '/api/goals/2026')
        self.assertEqual(status, 200)
        days = {row['goal_date']: row for row in details['data']['days']}
        self.assertTrue(days['2026-01-01']['locked'])
        self.assertTrue(days['2026-03-31']['locked'])
        self.assertFalse(days['2026-04-01']['locked'])

        status, periods = self.request('GET', '/api/goals/2026/periods')
        self.assertEqual(status, 200)
        self.assertEqual(periods['data']['locked_months'], ['2026-01', '2026-02', '2026-03'])

    def test_lock_rejects_impossible_calendar_date_and_month(self):
        _, created = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        version = created['data']['version']

        status, response = self.request('POST', '/api/goals/2026/locks', json={
            'version': version, 'period_type': 'date', 'period_key': '2026-99-99',
        })
        self.assertEqual(status, 422)
        self.assertEqual(response['code'], 'VALIDATION_ERROR')

        status, response = self.request('POST', '/api/goals/2026/locks', json={
            'version': version, 'period_type': 'month', 'period_key': '2026-13',
        })
        self.assertEqual(status, 422)
        self.assertEqual(response['code'], 'VALIDATION_ERROR')

    def test_growth_multiplier_generates_suggested_and_annual_target_from_prior_net_sales(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.executemany(
                "INSERT INTO daily_data (product_id, date, payment_amount, refund_amount) VALUES ('growth-a', ?, ?, ?)",
                [('2025-01-01', 100, 10), ('2025-01-02', 200, 20)],
            )
            connection.commit()

        status, payload = self.request(
            'POST', '/api/goals',
            json={'year': 2026, 'growth_multiplier': 1.25},
        )
        self.assertEqual(status, 201)
        self.assertEqual(payload['data']['prior_year_net_sales'], 270.0)
        self.assertEqual(payload['data']['growth_multiplier'], 1.25)
        self.assertEqual(payload['data']['suggested_annual_target'], 337.5)
        self.assertEqual(payload['data']['annual_total'], 337.5)

    def test_goal_inputs_reject_non_finite_numbers(self):
        for payload in (
            {'year': 2026, 'annual_target': 'NaN'},
            {'year': 2026, 'annual_target': 'Infinity'},
            {'year': 2026, 'growth_multiplier': 'NaN'},
        ):
            with self.subTest(payload=payload):
                status, response = self.request('POST', '/api/goals', json=payload)
                self.assertEqual(status, 422)
                self.assertEqual(response['code'], 'VALIDATION_ERROR')

        status, response = self.request(
            'GET', '/api/goals/2026/suggestion?growth_multiplier=Infinity'
        )
        self.assertEqual(status, 422)
        self.assertEqual(response['code'], 'VALIDATION_ERROR')

        status, response = self.request(
            'GET', '/api/goals/2026/allocation-preview?annual_target=NaN'
        )
        self.assertEqual(status, 422)
        self.assertEqual(response['code'], 'VALIDATION_ERROR')

        self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        status, response = self.request('POST', '/api/goals/2026/adjustments', json={
            'version': 1, 'period_type': 'month', 'period_key': '2026-01',
            'target_amount': 'NaN', 'operator': 'operator', 'reason': 'invalid',
        })
        self.assertEqual(status, 422)
        self.assertEqual(response['code'], 'VALIDATION_ERROR')


if __name__ == '__main__':
    unittest.main(verbosity=2)

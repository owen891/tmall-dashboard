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


if __name__ == '__main__':
    unittest.main(verbosity=2)

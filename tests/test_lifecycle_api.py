import os
import sys
import tempfile
import unittest
from datetime import date, timedelta


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class LifecycleApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-lifecycle-tests-')
        from app import create_app
        from db import get_db
        self.path = os.path.join(self.temp_dir.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()
        self.get_db = get_db
        with get_db(self.path) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('life-a', '生命周期商品')")
            connection.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_insufficient_data_does_not_invent_stage_or_seasonality(self):
        response = self.client.get('/api/lifecycle/assessments')
        self.assertEqual(response.status_code, 200)
        item = response.get_json()['data'][0]
        response.close()
        self.assertEqual(item['stage'], 'data_accumulating')
        self.assertIsNone(item['seasonal_attribute'])

    def test_manual_lock_is_versioned_and_preserves_history(self):
        initial = self.client.get('/api/lifecycle/assessments').get_json()['data'][0]
        response = self.client.put('/api/lifecycle/life-a', json={
            'version': initial['version'], 'manual_stage': 'growth', 'seasonal_attribute': 'manual',
            'reason': '新品上架策略', 'operator': 'operator', 'lock': True,
        })
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_sufficient_daily_and_monthly_data_returns_explained_stage_and_seasonality(self):
        with self.get_db(self.path) as connection:
            start = date(2026, 1, 1)
            for offset in range(60):
                amount = 100 if offset < 30 else 150
                connection.execute(
                    '''INSERT INTO daily_data (product_id, date, payment_amount, ipv, buyers, ad_spend)
                       VALUES ('life-a', ?, ?, 100, 10, 10)''',
                    ((start + timedelta(days=offset)).isoformat(), amount),
                )
            for month in range(1, 13):
                amount = 200 if month in {3, 4, 5, 9, 10, 11} else 100
                connection.execute(
                    "INSERT INTO monthly_data (product_id, month, payment_amount) VALUES ('life-a', ?, ?)",
                    (f'2025-{month:02d}', amount),
                )
            connection.commit()
        response = self.client.get('/api/lifecycle/assessments')
        item = response.get_json()['data'][0]; response.close()
        self.assertEqual(item['recommended_stage'], 'growth')
        self.assertEqual(item['seasonal_attribute'], 'double_peak')
        self.assertEqual(item['seasonal_source'], 'product')
        self.assertIn('支付金额', item['rationale'])

    def test_manual_lock_history_is_preserved(self):
        initial = self.client.get('/api/lifecycle/assessments').get_json()['data'][0]
        response = self.client.put('/api/lifecycle/life-a', json={
            'version': initial['version'], 'manual_stage': 'growth', 'seasonal_attribute': 'manual',
            'reason': 'manual override', 'operator': 'operator', 'lock': True,
        })
        self.assertEqual(response.status_code, 200); response.close()
        response = self.client.get('/api/lifecycle/life-a/history')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data'][0]['manual_stage'], 'growth')
        response.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)

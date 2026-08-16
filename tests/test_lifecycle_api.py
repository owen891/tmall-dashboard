import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch


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
        payload = response.get_json()
        item = payload['data'][0]
        response.close()
        self.assertEqual(item['stage'], 'data_accumulating')
        self.assertIsNone(item['seasonal_attribute'])
        self.assertEqual(payload['availability'], 'insufficient-data')
        self.assertFalse(payload['capabilities']['can_edit_stage'])
        self.assertFalse(payload['capabilities']['can_lock_stage'])

    def test_sufficient_history_enables_manual_stage_capabilities(self):
        with self.get_db(self.path) as connection:
            start = date(2026, 1, 1)
            for offset in range(60):
                connection.execute(
                    """INSERT INTO daily_data (
                        product_id, date, payment_amount, ipv, buyers, ad_spend
                    ) VALUES ('life-a', ?, 100, 100, 10, 10)""",
                    ((start + timedelta(days=offset)).isoformat(),),
                )
            connection.commit()

        response = self.client.get('/api/lifecycle/assessments')
        payload = response.get_json()
        response.close()

        self.assertEqual(payload['availability'], 'available')
        self.assertTrue(payload['capabilities']['can_edit_stage'])
        self.assertTrue(payload['capabilities']['can_lock_stage'])
        self.assertEqual(payload['data'][0]['data_cutoff_date'], '2026-03-01')

    def test_assessment_list_uses_bulk_data_instead_of_per_product_queries(self):
        from repos.lifecycle_repo import LifecycleRepo
        with patch.object(LifecycleRepo, 'daily_rows', side_effect=AssertionError('per-product query used')):
            response = self.client.get('/api/lifecycle/assessments')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data'][0]['product_id'], 'life-a')
        response.close()

    def test_assessment_list_loads_classification_dictionary_once(self):
        from services.lifecycle_service import settings_service
        with self.get_db(self.path) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('life-b', '另一个商品')")
            connection.commit()
        with patch.object(settings_service, 'get', wraps=settings_service.get) as get_settings:
            response = self.client.get('/api/lifecycle/assessments')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_settings.call_count, 1)
        response.close()

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
            cursor = date(2025, 1, 1)
            while cursor < date(2026, 1, 1):
                connection.execute(
                    '''INSERT INTO daily_data (product_id, date, payment_amount)
                       VALUES ('life-a', ?, 100)''', (cursor.isoformat(),),
                )
                cursor += timedelta(days=1)
            connection.commit()
        response = self.client.get('/api/lifecycle/assessments')
        item = response.get_json()['data'][0]; response.close()
        self.assertEqual(item['recommended_stage'], 'growth')
        self.assertEqual(item['seasonal_attribute'], 'double_peak')
        self.assertEqual(item['seasonal_source'], 'product')
        self.assertIn('支付金额', item['rationale'])

    def test_twelve_partial_months_do_not_produce_natural_seasonality(self):
        with self.get_db(self.path) as connection:
            for month in range(1, 13):
                connection.execute(
                    "INSERT INTO monthly_data (product_id, month, payment_amount) VALUES ('life-a', ?, 100)",
                    (f'2025-{month:02d}',),
                )
                connection.execute(
                    "INSERT INTO daily_data (product_id, date, payment_amount) VALUES ('life-a', ?, 100)",
                    (f'2025-{month:02d}-01',),
                )
            connection.commit()
        item = self.client.get('/api/lifecycle/assessments').get_json()['data'][0]
        self.assertEqual(item['complete_months'], 0)
        self.assertIsNone(item['seasonal_attribute'])

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

    def test_assessments_support_product_and_stage_filters(self):
        with self.get_db(self.path) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('life-b', 'other')")
            connection.commit()
        initial = self.client.get('/api/lifecycle/assessments').get_json()['data'][0]
        self.client.put('/api/lifecycle/life-a', json={
            'version': initial['version'], 'manual_stage': 'growth', 'seasonal_attribute': 'manual',
            'reason': 'filter fixture', 'operator': 'operator', 'lock': True,
        })
        data = self.client.get('/api/lifecycle/assessments?productId=life-a&lifecycleStage=growth').get_json()['data']
        self.assertEqual([item['product_id'] for item in data], ['life-a'])

    def test_custom_enabled_stage_and_seasonality_can_be_saved_manually(self):
        settings = self.client.get('/api/settings').get_json()['data']
        dictionaries = settings['classification_dictionaries']
        dictionaries['lifecycle_stages'].append({
            'value': 'relaunch', 'label': '焕新期', 'enabled': True, 'system': False,
        })
        dictionaries['seasonal_attributes'].append({
            'value': 'school_opening', 'label': '开学季', 'enabled': True, 'system': False,
        })
        response = self.client.put('/api/settings', json={
            'classification_dictionaries': dictionaries,
        })
        self.assertEqual(response.status_code, 200)
        response.close()

        initial = self.client.get('/api/lifecycle/assessments').get_json()['data'][0]
        response = self.client.put('/api/lifecycle/life-a', json={
            'version': initial['version'], 'manual_stage': 'relaunch',
            'seasonal_attribute': 'school_opening', 'reason': '运营人工判断',
            'operator': 'operator', 'lock': True,
        })
        self.assertEqual(response.status_code, 200)
        item = response.get_json()['data']
        self.assertEqual(item['stage'], 'relaunch')
        self.assertEqual(item['stage_label'], '焕新期')
        self.assertEqual(item['seasonal_label'], '开学季')
        response.close()

    def test_disabled_or_unknown_custom_classification_is_rejected(self):
        settings = self.client.get('/api/settings').get_json()['data']
        dictionaries = settings['classification_dictionaries']
        dictionaries['lifecycle_stages'].append({
            'value': 'paused_stage', 'label': '暂停经营', 'enabled': False, 'system': False,
        })
        self.client.put('/api/settings', json={'classification_dictionaries': dictionaries}).close()
        initial = self.client.get('/api/lifecycle/assessments').get_json()['data'][0]
        for stage in ('paused_stage', 'unknown_stage'):
            response = self.client.put('/api/lifecycle/life-a', json={
                'version': initial['version'], 'manual_stage': stage,
                'seasonal_attribute': None, 'reason': '无效值测试',
                'operator': 'operator', 'lock': True,
            })
            self.assertEqual(response.status_code, 422)
            response.close()

    def test_data_accumulating_cannot_be_saved_as_a_manual_stage(self):
        initial = self.client.get('/api/lifecycle/assessments').get_json()['data'][0]
        response = self.client.put('/api/lifecycle/life-a', json={
            'version': initial['version'], 'manual_stage': 'data_accumulating',
            'seasonal_attribute': None, 'reason': '不应允许的人工阶段',
            'operator': 'operator', 'lock': True,
        })
        self.assertEqual(response.status_code, 422)
        response.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)

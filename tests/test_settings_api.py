import os
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-settings-tests-')
        from app import create_app
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db')})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def request(self, method, path, **kwargs):
        response = self.client.open(path, method=method, **kwargs)
        result = response.status_code, response.get_json()
        response.close()
        return result

    def test_defaults_and_allowed_settings_are_persisted(self):
        status, defaults = self.request('GET', '/api/settings')
        self.assertEqual(status, 200)
        self.assertEqual(defaults['data']['timezone'], 'Asia/Shanghai')

        status, updated = self.request('PUT', '/api/settings', json={
            'shop_name': '旗舰店', 'currency': 'CNY', 'week_starts_on': 'monday',
            'annual_target_default': 1200000,
        })
        self.assertEqual(status, 200)
        self.assertEqual(updated['data']['shop_name'], '旗舰店')
        self.assertEqual(updated['data']['annual_target_default'], 1200000.0)

        status, rejected = self.request('PUT', '/api/settings', json={'formula': 'payment_amount / 2'})
        self.assertEqual(status, 422)
        self.assertEqual(rejected['code'], 'VALIDATION_ERROR')

    def test_mapping_and_view_templates_persist_and_thresholds_are_validated(self):
        status, updated = self.request('PUT', '/api/settings', json={
            'mapping_templates': {'promotion_campaign_day': {'campaign_id': '计划ID'}},
            'view_templates': {'selection': ['net_sales', 'roi']},
            'lifecycle_thresholds': {'continuous_days': 60, 'seasonal_months': 12},
        })
        self.assertEqual(status, 200)
        self.assertEqual(updated['data']['mapping_templates']['promotion_campaign_day']['campaign_id'], '计划ID')
        status, rejected = self.request('PUT', '/api/settings', json={
            'lifecycle_thresholds': {'continuous_days': 30, 'seasonal_months': 12},
        })
        self.assertEqual(status, 422)
        self.assertEqual(rejected['code'], 'VALIDATION_ERROR')


if __name__ == '__main__':
    unittest.main(verbosity=2)

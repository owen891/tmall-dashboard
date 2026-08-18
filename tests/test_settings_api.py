import os
import sys
import tempfile
import unittest
from unittest.mock import patch


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

    def test_growth_and_overachievement_settings_are_persisted_and_validated(self):
        status, defaults = self.request('GET', '/api/settings')
        self.assertEqual(status, 200)
        self.assertEqual(defaults['data']['growth_multiplier'], 1.0)
        self.assertEqual(defaults['data']['overachievement_threshold'], 1.0)

        status, updated = self.request('PUT', '/api/settings', json={
            'growth_multiplier': 1.25,
            'overachievement_threshold': 1.1,
        })
        self.assertEqual(status, 200)
        self.assertEqual(updated['data']['growth_multiplier'], 1.25)
        self.assertEqual(updated['data']['overachievement_threshold'], 1.1)

        status, rejected = self.request('PUT', '/api/settings', json={'growth_multiplier': 0})
        self.assertEqual(status, 422)
        self.assertEqual(rejected['code'], 'VALIDATION_ERROR')
        self.assertEqual(rejected['message'], '增长倍率必须大于 0')

    def test_settings_reject_non_finite_numbers_and_malformed_thresholds(self):
        for payload in (
            {'annual_target_default': 'NaN'},
            {'growth_multiplier': 'Infinity'},
            {'overachievement_threshold': '-Infinity'},
            {'growth_multiplier': True},
            {'lifecycle_thresholds': {'continuous_days': 'abc', 'seasonal_months': 12}},
        ):
            status, rejected = self.request('PUT', '/api/settings', json=payload)
            self.assertEqual(status, 422)
            self.assertEqual(rejected['code'], 'VALIDATION_ERROR')

    def test_settings_validation_messages_are_user_facing_chinese(self):
        cases = [
            ({'annual_target_default': -1}, '年度目标默认值不能为负数'),
            ({'growth_multiplier': 'bad'}, '增长倍率必须是数字'),
            ({'mapping_templates': {'unknown_source': {'date': '日期'}}}, '导入映射包含不支持的报表类型'),
            ({'lifecycle_thresholds': {'continuous_days': 30, 'seasonal_months': 12}}, '生命周期阈值不能低于系统安全下限'),
        ]
        for payload, message in cases:
            status, rejected = self.request('PUT', '/api/settings', json=payload)
            self.assertEqual(status, 422)
            self.assertEqual(rejected['message'], message)

    def test_classification_dictionaries_have_chinese_defaults_and_persist_custom_items(self):
        status, payload = self.request('GET', '/api/settings')
        self.assertEqual(status, 200)
        dictionaries = payload['data']['classification_dictionaries']
        self.assertEqual(set(dictionaries), {
            'tiers', 'styles', 'lifecycle_stages', 'seasonal_attributes',
        })
        lifecycle = {item['value']: item for item in dictionaries['lifecycle_stages']}
        self.assertEqual(lifecycle['growth']['label'], '成长期')
        self.assertTrue(lifecycle['growth']['system'])

        dictionaries['tiers'].append({
            'value': 'high_margin', 'label': '高毛利款', 'enabled': True, 'system': False,
        })
        lifecycle['growth']['label'] = '快速成长期'
        status, updated = self.request('PUT', '/api/settings', json={
            'classification_dictionaries': dictionaries,
        })
        self.assertEqual(status, 200)
        saved = updated['data']['classification_dictionaries']
        self.assertIn('高毛利款', [item['label'] for item in saved['tiers']])
        self.assertEqual(
            next(item for item in saved['lifecycle_stages'] if item['value'] == 'growth')['label'],
            '快速成长期',
        )

    def test_classification_dictionaries_reject_invalid_and_destructive_changes(self):
        dictionaries = self.request('GET', '/api/settings')[1]['data']['classification_dictionaries']
        invalid_cases = []

        duplicate = {key: [dict(item) for item in items] for key, items in dictionaries.items()}
        duplicate['tiers'].append({
            'value': duplicate['tiers'][0]['value'], 'label': '重复', 'enabled': True, 'system': False,
        })
        invalid_cases.append(duplicate)

        empty_label = {key: [dict(item) for item in items] for key, items in dictionaries.items()}
        empty_label['tiers'].append({
            'value': 'empty_label', 'label': '  ', 'enabled': True, 'system': False,
        })
        invalid_cases.append(empty_label)

        missing_system = {key: [dict(item) for item in items] for key, items in dictionaries.items()}
        missing_system['lifecycle_stages'] = [
            item for item in missing_system['lifecycle_stages'] if item['value'] != 'growth'
        ]
        invalid_cases.append(missing_system)

        changed_system_code = {key: [dict(item) for item in items] for key, items in dictionaries.items()}
        changed_system_code['seasonal_attributes'][0]['value'] = 'renamed_system_code'
        invalid_cases.append(changed_system_code)

        for invalid in invalid_cases:
            status, payload = self.request('PUT', '/api/settings', json={
                'classification_dictionaries': invalid,
            })
            self.assertEqual(status, 422)
            self.assertEqual(payload['code'], 'VALIDATION_ERROR')

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

    def test_custom_product_view_persists_extended_metric_columns(self):
        status, updated = self.request('PUT', '/api/settings', json={
            'view_templates': {
                'custom_growth': {
                    'label': '增长诊断',
                    'columns': ['search_conversion', 'paid_ipv', 'direct_gmv', 'cart_cost', 'click_rate'],
                },
            },
        })
        self.assertEqual(status, 200)
        self.assertEqual(
            updated['data']['view_templates']['custom_growth']['columns'],
            ['search_conversion', 'paid_ipv', 'direct_gmv', 'cart_cost', 'click_rate'],
        )

    def test_builtin_product_view_template_can_be_edited_but_not_removed(self):
        current = self.client.get('/api/settings').get_json()['data']['view_templates']
        current['operate'] = {'label': '经营总览改版', 'columns': ['product_id', 'title', 'net_sales']}
        current.pop('select')
        response = self.client.put('/api/settings', json={'view_templates': current})
        self.assertEqual(response.status_code, 200)
        saved = response.get_json()['data']['view_templates']
        self.assertEqual(saved['operate']['label'], '经营总览改版')
        self.assertIn('select', saved)

    def test_promotion_templates_and_field_catalog_are_server_backed(self):
        status, payload = self.request('GET', '/api/settings')
        self.assertEqual(status, 200)
        self.assertIn('promotion_view_templates', payload['data'])
        self.assertIn('products', payload['data']['promotion_view_templates'])
        for tab in ('keywords', 'crowd', 'creative', 'site'):
            self.assertIn(tab, payload['data']['promotion_view_templates'])
        self.assertIn('field_catalog', payload['data'])
        self.assertIn('products', payload['data']['field_catalog'])
        self.assertIn('promotion', payload['data']['field_catalog'])
        self.assertTrue(any(item['key'] == 'ad_spend' for item in payload['data']['field_catalog']['promotion']))

        templates = payload['data']['promotion_view_templates']
        templates['products']['custom_server'] = {
            'label': '服务端模板',
            'columns': ['product', 'ad_spend', 'roi'],
        }
        status, updated = self.request('PUT', '/api/settings', json={
            'promotion_view_templates': templates,
        })
        self.assertEqual(status, 200)
        self.assertEqual(
            updated['data']['promotion_view_templates']['products']['custom_server']['columns'],
            ['product', 'ad_spend', 'roi'],
        )

        status, rejected = self.request('PUT', '/api/settings', json={
            'promotion_view_templates': {
                'not_a_tab': {'bad': {'label': 'bad', 'columns': ['product']}},
            },
        })
        self.assertEqual(status, 422)
        self.assertEqual(rejected['code'], 'VALIDATION_ERROR')

    def test_promotion_templates_accept_extended_product_efficiency_fields(self):
        current = self.client.get('/api/settings').get_json()['data']['promotion_view_templates']
        current['products']['custom-efficiency-fields'] = {
            'label': '扩展效率',
            'columns': [
            'product', 'ad_spend', 'attributed_payment_amount', 'expense_ratio',
            'roi', 'cart_cost', 'new_customer_cost', 'action',
            ],
        }
        response = self.client.put('/api/settings', json={'promotion_view_templates': current})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()['data']['promotion_view_templates']['products']['custom-efficiency-fields']['columns'],
            current['products']['custom-efficiency-fields']['columns'],
        )

    def test_lifecycle_templates_cover_operating_sections_and_extended_monthly_fields(self):
        status, payload = self.request('GET', '/api/settings')
        self.assertEqual(status, 200)
        templates = payload['data']['lifecycle_view_templates']
        self.assertTrue({'complete', 'scale', 'traffic', 'efficiency', 'afterSales'} <= set(templates))
        complete = templates['complete']['columns']
        self.assertEqual(complete[0], 'month')
        self.assertGreaterEqual(len(complete), 20)
        self.assertTrue({'net_sales', 'visitors', 'payment_conversion', 'refund_rate', 'repurchase_rate'} <= set(complete))

        custom = dict(templates)
        custom['custom_monthly'] = {
            'label': '自定义月度分析',
            'columns': ['month', 'net_sales', 'visitors', 'refund_rate'],
        }
        status, updated = self.request('PUT', '/api/settings', json={'lifecycle_view_templates': custom})
        self.assertEqual(status, 200)
        self.assertEqual(
            updated['data']['lifecycle_view_templates']['custom_monthly']['columns'],
            ['month', 'net_sales', 'visitors', 'refund_rate'],
        )

    def test_mapping_templates_reject_unknown_source_field_and_empty_column(self):
        invalid_templates = [
            {'unknown_source': {'date': '日期'}},
            {'product_day': {'drop_table': '日期'}},
            {'product_day': {'date': '  '}},
        ]
        for templates in invalid_templates:
            status, payload = self.request('PUT', '/api/settings', json={'mapping_templates': templates})
            self.assertEqual(status, 422)
            self.assertEqual(payload['code'], 'VALIDATION_ERROR')

    def test_settings_and_audit_are_committed_atomically(self):
        with patch('services.settings_service.AuditRepo.record', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.client.put('/api/settings', json={'shop_name': '不应落库'})
        status, payload = self.request('GET', '/api/settings')
        self.assertEqual(status, 200)
        self.assertEqual(payload['data']['shop_name'], '')


if __name__ == '__main__':
    unittest.main(verbosity=2)

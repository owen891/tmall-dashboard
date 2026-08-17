import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TemplateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tmall-template-')
        from app import create_app
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.join(self.tmp.name, 'dashboard.db')})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_settings_normalizes_view_template_schema_and_rejects_unknown_columns(self):
        response = self.client.put('/api/settings', json={'view_templates': {
            'selection': {'label': 'Selection', 'columns': ['product_id', 'net_sales']},
        }})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['view_templates']['selection']['columns'], ['product_id', 'net_sales'])

        invalid = self.client.put('/api/settings', json={'view_templates': {
            'selection': {'label': 'bad', 'columns': ['drop_table']},
        }})
        self.assertEqual(invalid.status_code, 422)

    def test_default_templates_include_five_ga_views(self):
        payload = self.client.get('/api/settings').get_json()['data']
        for key in ('operate', 'select', 'paid', 'refund', 'lifecycle'):
            self.assertIn(key, payload['view_templates'])

    def test_existing_promotion_templates_are_merged_with_new_defaults(self):
        from repos.settings_repo import SettingsRepo
        from services.settings_service import settings_service

        with self.app.app_context():
            defaults = settings_service.get()['promotion_view_templates']
            legacy = {
                tab: templates
                for tab, templates in defaults.items()
                if tab != 'creative'
            }
            SettingsRepo.upsert({'promotion_view_templates': legacy})

        payload = self.client.get('/api/settings').get_json()['data']['promotion_view_templates']
        self.assertIn('creative', payload)
        for tab, template_ids in {
            'products': ('products-efficiency', 'products-action'),
            'keywords': ('keywords-traffic', 'keywords-scale'),
            'crowd': ('crowd-reach', 'crowd-value'),
            'creative': ('creative-reach', 'creative-test'),
            'site': ('site-reach', 'site-cost'),
        }.items():
            for template_id in template_ids:
                self.assertIn(template_id, payload[tab])

    def test_builtin_templates_cannot_be_deleted_but_can_be_renamed(self):
        current = self.client.get('/api/settings').get_json()['data']
        without_builtin = {
            key: value for key, value in current['view_templates'].items()
            if key != 'operate'
        }
        response = self.client.put('/api/settings', json={'view_templates': without_builtin})
        self.assertEqual(response.status_code, 200)
        self.assertIn('operate', response.get_json()['data']['view_templates'])

        renamed = dict(current['view_templates'])
        renamed['operate'] = {**renamed['operate'], 'label': 'Renamed builtin'}
        response = self.client.put('/api/settings', json={'view_templates': renamed})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['view_templates']['operate']['label'], 'Renamed builtin')

    def test_user_template_can_be_added_renamed_deleted_and_set_as_default(self):
        current = self.client.get('/api/settings').get_json()['data']
        templates = dict(current['view_templates'])
        templates['custom'] = {'label': 'Custom', 'columns': ['product_id', 'net_sales']}
        added = self.client.put('/api/settings', json={
            'view_templates': templates,
            'product_view_template': 'custom',
        })
        self.assertEqual(added.status_code, 200)
        self.assertEqual(added.get_json()['data']['product_view_template'], 'custom')

        refreshed = self.client.get('/api/settings').get_json()['data']
        self.assertEqual(refreshed['view_templates']['custom']['columns'], ['product_id', 'net_sales'])
        self.assertEqual(refreshed['product_view_template'], 'custom')

        refreshed['view_templates']['custom']['label'] = 'Renamed'
        renamed = self.client.put('/api/settings', json={'view_templates': refreshed['view_templates']})
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.get_json()['data']['view_templates']['custom']['label'], 'Renamed')

        del refreshed['view_templates']['custom']
        deleted = self.client.put('/api/settings', json={
            'view_templates': refreshed['view_templates'],
            'product_view_template': 'operate',
        })
        self.assertEqual(deleted.status_code, 200)
        self.assertNotIn('custom', deleted.get_json()['data']['view_templates'])

    def test_default_view_must_reference_a_persisted_template(self):
        response = self.client.put('/api/settings', json={'product_view_template': 'missing'})
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()

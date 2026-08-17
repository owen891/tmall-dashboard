import os
import tempfile
import unittest


class PageCapabilitiesApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-page-capabilities-api-')
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db'),
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_endpoint_returns_registry_and_release_context(self):
        response = self.client.get('/api/page-capabilities')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['summary']['page_count'], 11)
        self.assertIn('surfaces', payload['data'])
        self.assertIn('unsupported_capabilities', payload['data'])
        self.assertTrue(payload['capabilities']['can_view_registry'])
        self.assertFalse(payload['capabilities']['can_edit_registry'])
        self.assertIn('limitations', payload)

    def test_endpoint_applies_exact_filters_and_rejects_unknown_values(self):
        response = self.client.get('/api/page-capabilities?page=promotion&modal_kind=detail')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([item['key'] for item in payload['data']['pages']], ['promotion'])
        self.assertTrue(all(item['modal_kind'] == 'detail' for item in payload['data']['surfaces']))

        invalid = self.client.get('/api/page-capabilities?page=not-real')
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.get_json()['code'], 'VALIDATION_ERROR')


if __name__ == '__main__':
    unittest.main()

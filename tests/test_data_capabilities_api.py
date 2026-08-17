import os
import tempfile
import unittest


class DataCapabilitiesApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-data-capabilities-api-')
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db'),
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_catalog_endpoint_returns_context_and_unsupported_boundaries(self):
        response = self.client.get('/api/data-capabilities')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['ok'])
        self.assertIn('domains', payload['data'])
        self.assertIn('unsupported_capabilities', payload['data'])
        for key in ('capabilities', 'filters', 'missing_fields', 'missing_ranges', 'source_batches'):
            self.assertIn(key, payload)
        self.assertTrue(payload['capabilities']['can_view_schema'])
        self.assertFalse(payload['capabilities']['can_edit_catalog'])

    def test_catalog_endpoint_exposes_structured_data_health_context(self):
        response = self.client.get('/api/data-capabilities')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload['evidence_level'], 'insufficient')
        self.assertIsInstance(payload['limitations'], list)
        self.assertGreater(len(payload['limitations']), 0)
        self.assertIsInstance(payload['freshness'], dict)
        self.assertIsInstance(payload['evidence'], list)

    def test_valid_filters_are_returned_and_applied(self):
        response = self.client.get('/api/data-capabilities?domain=store_daily&availability=no-data')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['filters'], {'domain': 'store_daily', 'availability': 'no-data'})
        self.assertEqual([item['key'] for item in payload['data']['domains']], ['store_daily'])

    def test_unknown_catalog_filter_is_rejected(self):
        response = self.client.get('/api/data-capabilities?availability=unknown')
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')


if __name__ == '__main__':
    unittest.main()

import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class CapabilityContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-capability-tests-')
        from app import create_app

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db')})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_domain_success_responses_expose_context_contract(self):
        responses = [
            self.client.get('/api/overview?start=2026-08-01&end=2026-08-02'),
            self.client.get('/api/promotion?start=2026-08-01&end=2026-08-02'),
            self.client.get('/api/lifecycle/assessments'),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload['ok'])
            self.assertTrue(payload['requestId'])
            self.assertIn('capabilities', payload)
            self.assertIn('filters', payload)
            self.assertIn('missing_fields', payload)
            self.assertIn('missing_ranges', payload)
            self.assertIn('source_batches', payload)
            self.assertIn(payload['evidence_level'], {'full', 'partial', 'insufficient'})
            for key in ('missing_inputs', 'limitations', 'evidence', 'assumptions', 'unknowns'):
                self.assertIn(key, payload)
            self.assertIsInstance(payload['freshness'], dict)
        self.assertEqual(responses[0].get_json()['evidence_level'], 'insufficient')
        self.assertEqual(responses[1].get_json()['evidence_level'], 'insufficient')
        self.assertEqual(responses[2].get_json()['evidence_level'], 'insufficient')

    def test_overview_declares_filters_capabilities_and_provenance(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                """INSERT INTO import_batches (
                    id, source_type, source_filename, source_hash, status, completed_at
                ) VALUES ('batch-1', 'store_day', 'store.xlsx', 'hash-1', 'completed', CURRENT_TIMESTAMP)"""
            )
            connection.execute(
                """INSERT INTO store_daily_facts (
                    date, payment_amount, successful_refund_amount, ad_spend,
                    product_visitors, payment_buyers, returning_payment_buyers, source_batch_id
                ) VALUES ('2026-08-01', 100, 10, 5, 20, 4, 1, 'batch-1')"""
            )
            connection.commit()

        response = self.client.get('/api/overview?start=2026-08-01&end=2026-08-02&product_id=P-1')
        payload = response.get_json()
        response.close()

        self.assertTrue(payload['capabilities']['can_export'])
        self.assertTrue(payload['capabilities']['can_drilldown'])
        self.assertEqual(payload['filters']['product_id'], 'P-1')
        self.assertEqual(payload['missing_ranges'], [
            {'start': '2026-08-01', 'end': '2026-08-02'},
        ])
        self.assertIsInstance(payload['source_batches'], list)
        self.assertEqual(payload['evidence_level'], 'partial')
        self.assertIsInstance(payload['missing_inputs'], list)
        self.assertTrue(payload['limitations'])
        self.assertTrue(payload['evidence'])

    def test_reviews_action_list_reports_evidence_for_empty_source(self):
        payload = self.client.get('/api/actions').get_json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['evidence_level'], 'insufficient')
        self.assertIn('actions', payload['missing_inputs'])
        self.assertTrue(payload['limitations'])
        self.assertEqual(payload['evidence'][0]['source'], 'product_actions')

    def test_goals_imports_and_reviews_do_not_promote_empty_collections_to_full(self):
        cases = (
            ('/api/goals/2026/periods', 'insufficient', 'goal_versions'),
            ('/api/imports', 'insufficient', 'import_batches'),
            ('/api/period-reviews', 'insufficient', 'period_reviews'),
        )
        for path, expected_level, source in cases:
            with self.subTest(path=path):
                payload = self.client.get(path).get_json()
                self.assertTrue(payload['ok'])
                self.assertEqual(payload['evidence_level'], expected_level)
                self.assertEqual(payload['evidence'][0]['source'], source)
                self.assertTrue(payload['missing_inputs'])

    def test_settings_are_a_full_configuration_evidence_source(self):
        payload = self.client.get('/api/settings').get_json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['evidence_level'], 'full')
        self.assertEqual(payload['evidence'][0]['source'], 'settings')
        self.assertIsInstance(payload['freshness'], dict)

    def test_industry_benchmark_uses_context_envelope_without_zero_fallback(self):
        payload = self.client.get(
            '/api/industry_benchmark?dim=monthly&period=2099-12'
        ).get_json()

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['availability'], 'no-data')
        self.assertEqual(payload['evidence_level'], 'insufficient')
        self.assertIsNone(payload['data']['shop_ctr'])
        self.assertIsNone(payload['data']['industry_ctr'])
        self.assertEqual(payload['data']['trend'], [])
        self.assertIn('industry_benchmark', payload['missing_inputs'])
        self.assertTrue(payload['limitations'])
        self.assertTrue(payload['requestId'])

    def test_industry_benchmark_treats_imported_zero_as_missing_evidence(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                "INSERT INTO monthly_data (product_id, month, click_rate, industry_ctr) VALUES (?, ?, ?, ?)",
                ('benchmark-product', '2026-08', 0, 0),
            )
            connection.commit()

        payload = self.client.get(
            '/api/industry_benchmark?dim=monthly&period=2026-08'
        ).get_json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['availability'], 'missing-fields')
        self.assertIsNone(payload['data']['shop_ctr'])
        self.assertIsNone(payload['data']['industry_ctr'])
        self.assertIn('shop_ctr', payload['missing_inputs'])
        self.assertIn('industry_ctr', payload['missing_inputs'])


if __name__ == '__main__':
    unittest.main()

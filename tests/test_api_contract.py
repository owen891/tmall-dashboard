import os
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class OverviewContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-overview-tests-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from app import create_app
        from db import get_db

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        self.client = self.app.test_client()
        with get_db(self.database_path) as connection:
            connection.executemany(
                'INSERT INTO products (product_id, title, status) VALUES (?, ?, ?)',
                [('overview-a', '总览商品 A', 'active'), ('overview-b', '总览商品 B', 'active')],
            )
            connection.executemany(
                '''
                INSERT INTO daily_data (
                    product_id, date, payment_amount, refund_amount,
                    ipv, buyers, ad_spend
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    ('overview-a', '2026-04-01', 100, 10, 10, 2, 20),
                    ('overview-b', '2026-04-02', 100, 40, 30, 8, 20),
                ],
            )
            connection.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_overview_uses_sum_then_derive_and_reports_unsupported_shop_metrics(self):
        response = self.client.get('/api/overview?start=2026-04-01&end=2026-04-02')
        payload = response.get_json()
        response.close()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['availability'], 'insufficient-data')
        self.assertTrue(payload['requestId'])
        self.assertEqual(payload['data']['payment_amount'], 200.0)
        self.assertEqual(payload['data']['successful_refund_amount'], 50.0)
        self.assertEqual(payload['data']['net_sales'], 150.0)
        self.assertEqual(payload['data']['ad_spend'], 40.0)
        self.assertEqual(payload['data']['refund_rate'], 0.25)
        self.assertEqual(payload['data']['expense_ratio'], 0.2)
        self.assertIsNone(payload['data']['payment_conversion_rate'])
        self.assertIsNone(payload['data']['average_order_value'])
        self.assertIsNone(payload['data']['returning_buyer_ratio'])
        self.assertEqual(
            payload['data']['metric_availability']['payment_conversion_rate'],
            'missing-fields',
        )

    def test_overview_returns_no_data_without_inventing_zero_metrics(self):
        response = self.client.get('/api/overview?start=2026-05-01&end=2026-05-02')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        response.close()

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['availability'], 'no-data')
        self.assertIsNone(payload['data']['payment_amount'])
        self.assertIsNone(payload['data']['refund_rate'])

    def test_daily_matrix_uses_imported_facts_without_zero_fallback(self):
        response = self.client.get('/api/overview/daily-matrix?start=2026-04-01&end=2026-04-02')
        payload = response.get_json()
        response.close()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(len(payload['data']['rows']), 2)
        self.assertEqual(payload['data']['rows'][0]['payment_amount'], 100.0)

    def test_overview_prefers_store_daily_facts_over_product_rollups(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO store_daily_facts (
                    date, payment_amount, successful_refund_amount, ad_spend,
                    product_visitors, payment_buyers, returning_payment_buyers
                ) VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('2026-04-01', 500, 50, 60, 100, 25, 8),
            )
            connection.commit()

        overview = self.client.get('/api/overview?start=2026-04-01&end=2026-04-02').get_json()
        matrix = self.client.get('/api/overview/daily-matrix?start=2026-04-01&end=2026-04-02').get_json()

        self.assertEqual(overview['data']['payment_amount'], 500.0)
        self.assertEqual(overview['data']['net_sales'], 450.0)
        self.assertEqual(matrix['data']['rows'][0]['payment_amount'], 500.0)
        self.assertEqual(matrix['data']['rows'][0]['buyers'], 25)
        self.assertEqual(matrix['data']['rows'][0]['data_source'], 'store_daily_facts')


if __name__ == '__main__':
    unittest.main(verbosity=2)

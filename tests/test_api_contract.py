import os
import csv
import io
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

    def test_demo_assets_are_revalidated_after_local_edits(self):
        response = self.client.get('/assets/overview-live.js')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-cache', response.headers.get('Cache-Control', ''))
        response.close()

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

    def test_legacy_anomalies_handles_missing_previous_period_metrics(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO monthly_data
                   (product_id, month, payment_amount, visitors, buyers)
                   VALUES (?, ?, ?, ?, ?)''',
                ('overview-a', '2026-08', 100, 0, 0),
            )
            connection.commit()

        response = self.client.get('/api/anomalies?dim=monthly&period=2026-08&prev_period=2026-07')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['anomalies'], [])

    def test_legacy_report_renders_missing_average_order_value(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO monthly_data
                   (product_id, month, payment_amount, visitors, buyers)
                   VALUES (?, ?, ?, ?, ?)''',
                ('overview-a', '2026-08', 100, 0, 0),
            )
            connection.commit()

        response = self.client.get('/api/report?dim=monthly&period=2026-08')

        self.assertEqual(response.status_code, 200)
        self.assertIn('客单价：--', response.get_json()['report'])

    def test_daily_matrix_uses_imported_facts_without_zero_fallback(self):
        response = self.client.get('/api/overview/daily-matrix?start=2026-04-01&end=2026-04-02')
        payload = response.get_json()
        response.close()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(len(payload['data']['rows']), 2)
        self.assertEqual(payload['data']['rows'][0]['payment_amount'], 100.0)

    def test_daily_matrix_fallback_exposes_returning_ratio_and_source_metadata(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute(
                'INSERT INTO products (product_id, title, status) VALUES (?, ?, ?)',
                ('overview-c', '总览商品 C', 'active'),
            )
            connection.execute(
                '''INSERT INTO daily_data (
                    product_id, date, payment_amount, refund_amount,
                    ipv, buyers, returning_payment_buyers, ad_spend, data_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                ('overview-c', '2026-04-03', 120, 5, 100, 10, 3, 12, 'product-day-2026-04-03.xls'),
            )
            connection.execute(
                '''INSERT INTO import_batches (
                    id, source_type, source_filename, source_hash, status,
                    total_rows, valid_rows, invalid_rows, inserted_count, updated_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                ('batch-product-day', 'product_day', 'product-day-2026-04-03.xls', 'hash-product-day',
                 'completed', 1, 1, 0, 1, 0),
            )
            connection.execute(
                '''INSERT INTO daily_data_observations (
                    product_id, date, source_system, source_type, source_batch_id,
                    source_filename, payload_json, field_presence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                ('overview-c', '2026-04-03', 'business_advisor', 'product_day',
                 'batch-product-day', 'product-day-2026-04-03.xls',
                 '{"payment_buyers": 10, "returning_payment_buyers": 3}',
                 '{"payment_buyers": true, "returning_payment_buyers": true}'),
            )
            connection.commit()

        matrix = self.client.get(
            '/api/overview/daily-matrix?start=2026-04-03&end=2026-04-03'
        ).get_json()['data']
        row = matrix['rows'][0]

        self.assertAlmostEqual(row['returning_buyer_ratio'], 3 / 10)
        self.assertEqual(row['source_batch_id'], 'batch-product-day')
        self.assertEqual(row['source_detail']['source_filename'], 'product-day-2026-04-03.xls')

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

    def test_daily_matrix_exposes_returning_ratio_changes_missing_range_and_batch(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.execute('INSERT INTO store_daily_facts (date,payment_amount,successful_refund_amount,ad_spend,product_visitors,payment_buyers,returning_payment_buyers,source_batch_id) VALUES (?,?,?,?,?,?,?,?)', ('2026-04-01', 500, 50, 60, 100, 25, 8, 'batch-a'))
            connection.execute('INSERT INTO store_daily_facts (date,payment_amount,successful_refund_amount,ad_spend,product_visitors,payment_buyers,returning_payment_buyers,source_batch_id) VALUES (?,?,?,?,?,?,?,?)', ('2026-04-03', 300, 30, 30, 100, 30, 10, 'batch-b'))
            connection.commit()
        matrix = self.client.get('/api/overview/daily-matrix?start=2026-04-01&end=2026-04-03').get_json()['data']
        first, third = matrix['rows'][0], matrix['rows'][-1]
        self.assertAlmostEqual(first['returning_buyer_ratio'], 8 / 25)
        self.assertEqual(first['source_batch_id'], 'batch-a')
        self.assertIsNotNone(third['changes']['payment_amount'])
        self.assertEqual(matrix['missing_date_ranges'], [{'start': '2026-04-02', 'end': '2026-04-02'}])

    def test_daily_matrix_export_returns_all_filtered_rows_and_source_fields(self):
        response = self.client.get('/api/overview/daily-matrix/export?start=2026-04-01&end=2026-04-02')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response.content_type)
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True).lstrip('\ufeff'))))
        response.close()

        self.assertEqual(len(rows), 2)
        self.assertIn('returning_buyer_ratio', rows[0])
        self.assertIn('source_batch_id', rows[0])

    def test_overview_and_matrix_apply_product_tier_lifecycle_and_channel_filters(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.execute("UPDATE products SET tier = 'A' WHERE product_id = 'overview-a'")
            connection.execute("UPDATE products SET tier = 'B' WHERE product_id = 'overview-b'")
            connection.execute(
                "INSERT INTO lifecycle_profiles (product_id, recommended_stage) VALUES ('overview-a', 'growth')"
            )
            connection.execute(
                '''INSERT INTO promotion_daily_facts
                   (date, channel, product_id, campaign_id, unit_id, ad_spend, attributed_payment_amount)
                   VALUES ('2026-04-01', 'search', 'overview-a', '', '', 20, 100)'''
            )
            connection.commit()

        query = ('start=2026-04-01&end=2026-04-02&product_id=overview-a&tier=A'
                 '&lifecycle_stage=growth&promotion_channel=search')
        overview = self.client.get(f'/api/overview?{query}').get_json()
        matrix = self.client.get(f'/api/overview/daily-matrix?{query}').get_json()

        self.assertEqual(overview['data']['payment_amount'], 100.0)
        self.assertEqual(overview['data']['net_sales'], 90.0)
        self.assertEqual(len(matrix['data']['rows']), 1)
        self.assertEqual(matrix['data']['rows'][0]['date'], '2026-04-01')


if __name__ == '__main__':
    unittest.main(verbosity=2)

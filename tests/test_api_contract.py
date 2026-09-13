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

    def test_overview_marks_monthly_fallback_as_partial_evidence(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute('DELETE FROM daily_data')
            connection.execute(
                'INSERT INTO monthly_data (product_id, month, payment_amount, refund_amount, visitors, buyers) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                ('overview-a', '2026-03', 100, 10, 100, 5),
            )
            connection.commit()

        payload = self.client.get(
            '/api/overview?start=2026-08-15&end=2026-09-13'
        ).get_json()

        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['fallback_reason'], 'daily_facts_unavailable')
        self.assertEqual(payload['data']['data_grain'], 'monthly')
        self.assertEqual(payload['evidence_level'], 'partial')
        self.assertEqual(payload['missing_ranges'], [
            {'start': '2026-08-15', 'end': '2026-09-13'},
        ])
        self.assertTrue(payload['limitations'])
        latest_import = payload['data']['context']['latest_import']
        self.assertEqual(latest_import['source_type'], 'product_month')
        self.assertEqual(latest_import['source_filename'], '商品月度数据')
        self.assertNotIn('paimi', str(payload).lower())
        self.assertNotIn('派米', str(payload))

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

    def test_legacy_anomalies_marks_missing_current_period_as_no_data(self):
        payload = self.client.get(
            '/api/anomalies?dim=monthly&period=2099-12&prev_period=2099-11'
        ).get_json()

        self.assertEqual(payload['availability'], 'no-data')
        self.assertFalse(payload['has_anomalies'])

    def test_legacy_kpi_does_not_return_zero_aggregate_without_period_data(self):
        payload = self.client.get('/api/kpi?dim=monthly&period=2099-12').get_json()

        self.assertEqual(payload['availability'], 'no-data')
        self.assertIsNone(payload['current'])
        self.assertIsNone(payload['previous'])
        self.assertEqual(payload['changes'], {})

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

    def test_legacy_report_returns_not_found_without_period_data(self):
        response = self.client.get('/api/report?dim=monthly&period=2099-12')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['error'], 'no data for period')

    def test_legacy_review_rejects_malformed_period_instead_of_raising(self):
        response = self.client.get('/api/review?dim=monthly&period=not-a-date')

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_legacy_review_rejects_unknown_dimension(self):
        response = self.client.get('/api/review?dim=quarter&period=2026-08')

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_legacy_review_marks_empty_period_as_no_data(self):
        payload = self.client.get(
            '/api/review?dim=monthly&period=2099-12'
        ).get_json()

        self.assertEqual(payload['availability'], 'no-data')
        self.assertTrue(all(metric['value'] is None for metric in payload['metrics']))

    def test_target_progress_does_not_promote_empty_aggregate_to_zero_actual(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute(
                "INSERT INTO shop_targets (period, target_gsv, target_ad_spend) VALUES (?, ?, ?)",
                ('2099-12', 1000, 100),
            )
            connection.commit()

        payload = self.client.get('/api/target_progress?dim=monthly&period=2099-12').get_json()

        self.assertIsNotNone(payload['target'])
        self.assertIsNone(payload['actual'])
        self.assertNotIn('gsv_progress', payload)

    def test_daily_trend_reports_payment_count_from_daily_facts(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO daily_data (
                       product_id, date, payment_amount, payment_qty, ipv
                   ) VALUES (?, ?, ?, ?, ?)''',
                ('trend-a', '2026-04-03', 240, 7, 80),
            )
            connection.commit()

        payload = self.client.get(
            '/api/trend?dim=daily&start=2026-04-03&end=2026-04-03'
        ).get_json()

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['payment_count'], 7)

    def test_product_target_progress_does_not_zero_fill_missing_actual(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute(
                "INSERT INTO products (product_id, title, status) VALUES (?, ?, ?)",
                ('target-a', '目标商品', 'active'),
            )
            connection.execute(
                '''INSERT INTO product_targets (
                       product_id, period, target_gsv, target_ad_spend
                   ) VALUES (?, ?, ?, ?)''',
                ('target-a', '2099-12', 1000, 100),
            )
            connection.commit()

        payload = self.client.get(
            '/api/product_target_progress?period=2099-12'
        ).get_json()

        self.assertEqual(len(payload), 1)
        self.assertIsNone(payload[0]['actual_gsv'])
        self.assertIsNone(payload[0]['actual_ad_spend'])
        self.assertIsNone(payload[0].get('gsv_progress'))
        self.assertIsNone(payload[0].get('ad_progress'))

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

    def test_legacy_keywords_exposes_no_data_for_unknown_date(self):
        payload = self.client.get('/api/keywords?date=2099-12-01').get_json()

        self.assertEqual(payload['availability'], 'no-data')
        self.assertEqual(payload['items'], [])
        self.assertEqual(payload['total'], 0)

    def test_reviews_summary_exposes_no_data_without_reviews(self):
        payload = self.client.get('/api/reviews/summary').get_json()

        self.assertEqual(payload['availability'], 'no-data')
        self.assertIsNone(payload['stats']['avg_rating'])
        self.assertEqual(payload['stats']['total'], 0)

    def test_traffic_structure_does_not_show_historical_trend_for_missing_period(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO monthly_data
                   (product_id, month, payment_amount, visitors)
                   VALUES (?, ?, ?, ?)''',
                ('overview-a', '2026-04', 100, 20),
            )
            connection.commit()

        payload = self.client.get(
            '/api/traffic_structure?dim=monthly&period=2099-12'
        ).get_json()

        self.assertEqual(payload['availability'], 'no-data')
        self.assertEqual(payload['structure'], {})
        self.assertEqual(payload['trend'], [])

    def test_refund_alert_applies_requested_rate_threshold(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.executemany(
                '''INSERT INTO monthly_data
                   (product_id, month, payment_amount, refund_amount, refund_rate)
                   VALUES (?, ?, ?, ?, ?)''',
                [
                    ('overview-a', '2026-04', 100, 30, 0.30),
                    ('overview-b', '2026-04', 100, 5, 0.05),
                ],
            )
            connection.commit()

        payload = self.client.get(
            '/api/refund_alert?dim=monthly&period=2026-04&threshold=0.20'
        ).get_json()

        self.assertEqual([row['product_id'] for row in payload], ['overview-a'])

    def test_refund_alert_rejects_invalid_threshold_dimension_and_period(self):
        for query in (
            '/api/refund_alert?threshold=not-a-number',
            '/api/refund_alert?threshold=NaN',
            '/api/refund_alert?threshold=1.1',
            '/api/refund_alert?dim=quarter',
            '/api/refund_alert?dim=monthly&period=not-a-date',
        ):
            with self.subTest(query=query):
                response = self.client.get(query)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_legacy_compatibility_endpoints_reject_unknown_dimensions(self):
        for path in (
            '/api/traffic_structure?dim=quarter',
            '/api/alert_checks?dim=quarter',
            '/api/product_tags?dim=quarter',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_alert_checks_do_not_trigger_rules_for_missing_period(self):
        response = self.client.post(
            '/api/alert_rules',
            json={'metric': 'gmv', 'operator': 'lt', 'threshold': 100},
        )
        self.assertEqual(response.status_code, 200)

        payload = self.client.get(
            '/api/alert_checks?dim=monthly&period=2099-12'
        ).get_json()

        self.assertEqual(payload, [])

    def test_target_progress_rejects_unknown_dimension(self):
        response = self.client.get(
            '/api/target_progress?dim=quarter&period=2026-04'
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_alerts_do_not_generate_target_warnings_without_period_facts(self):
        from datetime import datetime
        from db import get_db

        period = datetime.now().strftime('%Y-%m')
        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO shop_targets
                   (period, target_gsv, target_ad_spend, target_ad_ratio)
                   VALUES (?, ?, ?, ?)''',
                (period, 1000, 100, 0.1),
            )
            connection.commit()

        payload = self.client.get(f'/api/alerts?period={period}').get_json()

        self.assertEqual(payload, [])

    def test_alerts_order_critical_before_high_before_warning(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.executemany(
                '''INSERT INTO alerts
                   (alert_date, alert_type, severity, title, period)
                   VALUES (date('now'), ?, ?, ?, ?)''',
                [
                    ('warning-test', 'warning', '普通', '2026-04'),
                    ('critical-test', 'critical', '紧急', '2026-04'),
                    ('high-test', 'high', '重要', '2026-04'),
                ],
            )
            connection.commit()

        payload = self.client.get('/api/alerts?period=2026-04').get_json()

        self.assertEqual([item['severity'] for item in payload], ['critical', 'high', 'warning'])

    def test_target_progress_does_not_invent_yoy_without_previous_facts(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute(
                "INSERT INTO shop_targets (period, target_gsv, target_ad_spend) VALUES (?, ?, ?)",
                ('2026-08', 1000, 100),
            )
            connection.execute(
                '''INSERT INTO monthly_data
                   (product_id, month, payment_amount, refund_amount, ad_spend)
                   VALUES (?, ?, ?, ?, ?)''',
                ('overview-a', '2026-08', 100, 0, 10),
            )
            connection.commit()

        payload = self.client.get(
            '/api/target_progress?dim=monthly&period=2026-08'
        ).get_json()

        self.assertNotIn('yoy_gsv', payload)
        self.assertNotIn('yoy_ad', payload)

    def test_compare_does_not_promote_missing_periods_to_zero_sales(self):
        payload = self.client.get(
            '/api/compare?dim=monthly&period_a=2099-01&period_b=2099-02'
        ).get_json()

        self.assertEqual(payload['availability'], 'no-data')
        self.assertEqual(payload['trend_compare']['series_a'], [None])
        self.assertEqual(payload['trend_compare']['series_b'], [None])

    def test_compare_does_not_mark_products_changed_when_one_period_is_missing(self):
        from db import get_db

        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO monthly_data
                   (product_id, month, payment_amount, refund_amount, visitors)
                   VALUES (?, ?, ?, ?, ?)''',
                ('overview-a', '2026-04', 100, 0, 10),
            )
            connection.commit()

        payload = self.client.get(
            '/api/compare?dim=monthly&period_a=2026-04&period_b=2099-02'
        ).get_json()

        self.assertEqual(payload['availability'], 'partial')
        self.assertEqual(payload['kpi_compare'], {})
        self.assertEqual(payload['product_changes'], [])

    def test_compare_rejects_malformed_periods(self):
        response = self.client.get(
            '/api/compare?dim=monthly&period_a=not-a-date&period_b=2026-04'
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_health_exposes_no_data_for_unknown_period(self):
        payload = self.client.get('/api/health?period=2099-12').get_json()

        self.assertEqual(payload['availability'], 'no-data')
        self.assertEqual(payload['products'], [])
        self.assertEqual(payload['stats'], [])

    def test_trend_rejects_malformed_date_range(self):
        response = self.client.get(
            '/api/trend?dim=daily&start=2026-02-30&end=2026-03-01'
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_legacy_reads_reject_malformed_explicit_periods(self):
        for path in (
            '/api/kpi?dim=monthly&period=not-a-date',
            '/api/kpi?dim=monthly&prev_period=not-a-date',
            '/api/products?dim=monthly&period=not-a-date',
            '/api/ad_performance?dim=monthly&period=not-a-date',
            '/api/anomalies?dim=monthly&period=not-a-date',
            '/api/industry_benchmark?dim=monthly&period=not-a-date',
            '/api/product_tags?dim=monthly&period=not-a-date',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_target_and_report_reads_reject_malformed_explicit_periods(self):
        for path in (
            '/api/target_progress?dim=monthly&period=not-a-date',
            '/api/product_target_progress?period=not-a-date',
            '/api/alerts?period=not-a-date',
            '/api/health?period=not-a-date',
            '/api/alert_checks?dim=monthly&period=not-a-date',
            '/api/report?dim=monthly&period=not-a-date',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_core_legacy_reads_reject_unknown_dimensions_consistently(self):
        for path in (
            '/api/kpi?dim=quarter',
            '/api/trend?dim=quarter',
            '/api/products?dim=quarter',
            '/api/periods?dim=quarter',
            '/api/ad_performance?dim=quarter',
            '/api/anomalies?dim=quarter',
            '/api/report?dim=quarter&period=2026-04',
            '/api/customer_analysis?dim=quarter',
            '/api/funnel?dim=quarter',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')


if __name__ == '__main__':
    unittest.main(verbosity=2)

import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class DataCapabilityServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-data-capability-tests-')
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db'),
        })

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_store_fact(self):
        from db import get_db

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                """INSERT INTO import_batches (
                    id, source_type, source_filename, source_hash, status, completed_at
                ) VALUES ('batch-1', 'store_day', 'store.xlsx', 'hash-1', 'completed', CURRENT_TIMESTAMP)"""
            )
            connection.execute(
                """INSERT INTO store_daily_facts (
                    shop_id, date, payment_amount, successful_refund_amount,
                    product_visitors, payment_buyers, returning_payment_buyers,
                    ad_spend, source_batch_id
                ) VALUES ('default', '2026-08-01', 100, 10, 20, 4, 1, 5, 'batch-1')"""
            )
            connection.commit()

    def test_metric_metadata_is_complete_and_matches_registry(self):
        from services.metric_definitions import METRIC_DEFINITIONS, metric_metadata

        metadata = metric_metadata()
        self.assertEqual(set(metadata), set(METRIC_DEFINITIONS))
        for name, definition in METRIC_DEFINITIONS.items():
            self.assertEqual(tuple(metadata[name]['dependencies']), tuple(definition))
            for key in ('label', 'formula', 'unit', 'aggregation'):
                self.assertTrue(metadata[name][key], name)

    def test_empty_domain_is_no_data_and_not_available(self):
        from services.data_capability_service import build_catalog

        result = build_catalog(self.app.config['DATABASE_PATH'])
        store = next(item for item in result['domains'] if item['key'] == 'store_daily')
        self.assertEqual(store['availability'], 'no-data')
        self.assertEqual(store['coverage']['row_count'], 0)
        self.assertNotIn('trend', store['capabilities'])

    def test_domain_and_metric_entries_expose_evidence_context(self):
        from services.data_capability_service import build_catalog

        result = build_catalog(self.app.config['DATABASE_PATH'], domain='store_daily')
        store = result['domains'][0]
        self.assertEqual(store['evidence_level'], 'insufficient')
        self.assertIn('missing_inputs', store)
        self.assertIn('freshness', store)
        self.assertIn('latest_update', store['freshness'])
        metric = next(item for item in store['derived_metrics'] if item['key'] == 'net_sales')
        self.assertEqual(metric['evidence_level'], 'insufficient')
        self.assertIn('missing_inputs', metric)

    def test_seeded_domain_reports_coverage_metrics_and_source_batch(self):
        self._insert_store_fact()
        from services.data_capability_service import build_catalog

        result = build_catalog(self.app.config['DATABASE_PATH'])
        store = next(item for item in result['domains'] if item['key'] == 'store_daily')
        self.assertEqual(store['availability'], 'available')
        self.assertEqual(store['coverage']['row_count'], 1)
        self.assertEqual(store['coverage']['entity_count'], 1)
        self.assertEqual(store['coverage']['start'], '2026-08-01')
        self.assertEqual(store['source_batches'], ['batch-1'])

    def test_catalog_filters_validate_and_return_only_requested_domains(self):
        from services.data_capability_service import build_catalog

        result = build_catalog(
            self.app.config['DATABASE_PATH'],
            domain='store_daily',
            availability='no-data',
        )
        self.assertEqual([item['key'] for item in result['domains']], ['store_daily'])

    def test_product_fact_metric_evidence_uses_actual_source_columns(self):
        from db import get_db
        from services.data_capability_service import build_catalog

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                """INSERT INTO products (product_id, title) VALUES ('P-1', 'Product 1')"""
            )
            connection.execute(
                """INSERT INTO daily_data (
                    product_id, date, payment_amount, refund_amount, net_sales,
                    ipv, payment_conversion, ad_spend, ad_roi, buyers, avg_order_value
                ) VALUES ('P-1', '2026-08-01', 100, 10, 90, 20, 0.2, 5, 18, 4, 25)"""
            )
            connection.commit()

        product_daily = build_catalog(
            self.app.config['DATABASE_PATH'], domain='product_daily'
        )['domains'][0]
        metrics = {item['key']: item for item in product_daily['derived_metrics']}
        self.assertEqual(product_daily['availability'], 'available')
        for key in ('net_sales', 'refund_rate', 'payment_conversion_rate', 'average_order_value', 'expense_ratio', 'ad_roi'):
            self.assertEqual(metrics[key]['availability'], 'available', key)
            self.assertEqual(metrics[key]['evidence_level'], 'full', key)
            self.assertTrue(metrics[key]['evidence_fields'], key)

    def test_multi_table_domain_is_partial_when_only_secondary_source_has_data(self):
        from db import get_db
        from services.data_capability_service import build_catalog

        with get_db(self.app.config['DATABASE_PATH']) as connection:
            connection.execute(
                """INSERT INTO keyword_metrics (date, keyword, popularity)
                   VALUES ('2026-08-01', 'summer dress', 100)"""
            )
            connection.commit()

        market = build_catalog(
            self.app.config['DATABASE_PATH'], domain='market'
        )['domains'][0]
        self.assertEqual(market['availability'], 'partial')
        self.assertEqual(market['coverage']['row_count'], 1)
        coverage = {item['table']: item['coverage']['row_count'] for item in market['source_coverage']}
        self.assertEqual(coverage['market_analysis'], 0)
        self.assertEqual(coverage['keyword_metrics'], 1)


if __name__ == '__main__':
    unittest.main()

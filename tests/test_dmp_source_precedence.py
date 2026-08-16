import os
import tempfile
import unittest


class DmpSourcePrecedenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-source-resolution-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from db import get_connection, init_db
        init_db(self.database_path)
        self.connection = get_connection(self.database_path)

    def tearDown(self):
        self.connection.close()
        self.temp_dir.cleanup()

    def _record(self, row, source_type, batch):
        from services.source_resolution_service import record_daily_observation
        return record_daily_observation(
            self.connection,
            row,
            source_type=source_type,
            source_filename=f'{source_type}.xlsx',
            source_batch_id=batch,
        )

    def test_business_advisor_remains_primary_and_dmp_fills_missing_fields(self):
        self._record({
            'product_id': 'source-a', 'date': '2026-04-01',
            'payment_amount': 100, 'product_visitors': 20, 'payment_buyers': 5,
        }, 'product_day', 'business-batch')
        self._record({
            'product_id': 'source-a', 'date': '2026-04-01',
            'payment_amount': 200, 'product_visitors': 99,
            'paid_visitors': 8, 'search_visitors': 4, 'presale_amount': 12,
        }, 'dmp_product_day', 'dmp-batch')
        self.connection.commit()

        row = self.connection.execute(
            '''SELECT payment_amount, ipv, paid_ipv, search_visitors, presale_amount
               FROM daily_data WHERE product_id = 'source-a' AND date = '2026-04-01' '''
        ).fetchone()
        self.assertEqual(tuple(row), (100, 20, 8, 4, 12))
        lineage = self.connection.execute(
            '''SELECT field_key, effective_source_system, fallback_used
               FROM fact_field_lineage WHERE product_id = 'source-a' AND date = '2026-04-01'
               ORDER BY field_key'''
        ).fetchall()
        by_field = {item['field_key']: (item['effective_source_system'], item['fallback_used']) for item in lineage}
        self.assertEqual(by_field['payment_amount'], ('business_advisor', 0))
        self.assertEqual(by_field['paid_visitors'], ('dmp_product_day', 1))
        self.assertEqual(by_field['presale_amount'], ('dmp_product_day', 0))

    def test_promotion_tool_overrides_dmp_for_ad_fields(self):
        self._record({
            'product_id': 'source-b', 'date': '2026-04-01',
            'ad_spend': 100, 'ad_roi': 2,
        }, 'dmp_product_day', 'dmp-batch')
        self._record({
            'product_id': 'source-b', 'date': '2026-04-01',
            'ad_spend': 12, 'ad_roi': 5,
        }, 'promotion_product_day', 'promotion-batch')
        self.connection.commit()

        row = self.connection.execute(
            '''SELECT ad_spend, ad_roi FROM daily_data
               WHERE product_id = 'source-b' AND date = '2026-04-01' '''
        ).fetchone()
        self.assertEqual(tuple(row), (12, 5))

    def test_zero_is_a_valid_primary_value_and_does_not_fallback(self):
        self._record({
            'product_id': 'source-c', 'date': '2026-04-01',
            'payment_amount': 0, 'product_visitors': 0,
        }, 'product_day', 'business-batch')
        self._record({
            'product_id': 'source-c', 'date': '2026-04-01',
            'payment_amount': 88, 'product_visitors': 10,
        }, 'dmp_product_day', 'dmp-batch')
        self.connection.commit()

        row = self.connection.execute(
            '''SELECT payment_amount, ipv FROM daily_data
               WHERE product_id = 'source-c' AND date = '2026-04-01' '''
        ).fetchone()
        self.assertEqual(tuple(row), (0, 0))


if __name__ == '__main__':
    unittest.main()

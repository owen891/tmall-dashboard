import os
import tempfile
import unittest


class SourceResolutionTests(unittest.TestCase):
    def setUp(self):
        from db import init_db
        self.tmp = tempfile.TemporaryDirectory(prefix="tmall-source-resolution-")
        self.db_path = os.path.join(self.tmp.name, "dashboard.db")
        init_db(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_smart_selection_filename_is_a_dmp_supplement_not_paid_media(self):
        from services.source_resolution_service import source_system_for

        self.assertEqual(
            source_system_for('product_day', '智能选款_2026-08-18~2026-08-18.csv'),
            'dmp_product_day',
        )
        self.assertEqual(
            source_system_for('promotion_product_day', '商品报表_20260819.csv'),
            'promotion_tool',
        )

    def test_business_advisor_wins_and_dmp_is_kept_as_reference_with_conflict(self):
        from services.source_resolution_service import SourceResolutionService

        service = SourceResolutionService(db_path=self.db_path)
        service.record_observation("p-1", "2026-08-01", "payment_amount", 100, "business_advisor", "ba-1")
        service.record_observation("p-1", "2026-08-01", "payment_amount", 80, "dmp_product_day", "dmp-1")

        result = service.resolve_field("p-1", "2026-08-01", "payment_amount")

        self.assertEqual(result["value"], 100)
        self.assertEqual(result["effective_source"], "business_advisor")
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["resolution_status"], "primary_kept")
        self.assertTrue(result["conflict_status"] == "conflict")
        with service.connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM daily_data_observations").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM reconciliation_results").fetchone()[0], 1)

    def test_zero_is_not_treated_as_missing_when_dmp_has_nonzero(self):
        from services.source_resolution_service import SourceResolutionService

        service = SourceResolutionService(db_path=self.db_path)
        service.record_observation("p-2", "2026-08-01", "payment_amount", 0, "business_advisor", "ba-1")
        service.record_observation("p-2", "2026-08-01", "payment_amount", 80, "dmp_product_day", "dmp-1")

        result = service.resolve_field("p-2", "2026-08-01", "payment_amount")

        self.assertEqual(result["value"], 0)
        self.assertEqual(result["effective_source"], "business_advisor")
        self.assertFalse(result["fallback_used"])
        self.assertEqual(result["resolution_status"], "primary_kept")

    def test_dmp_fills_missing_primary_and_unique_field_is_effective(self):
        from services.source_resolution_service import SourceResolutionService

        service = SourceResolutionService(db_path=self.db_path)
        service.record_observation("p-3", "2026-08-01", "payment_amount", None, "business_advisor", "ba-1")
        service.record_observation("p-3", "2026-08-01", "payment_amount", 80, "dmp_product_day", "dmp-1")
        fallback = service.resolve_field("p-3", "2026-08-01", "payment_amount")
        self.assertEqual(fallback["value"], 80)
        self.assertEqual(fallback["resolution_status"], "fallback_filled")
        self.assertTrue(fallback["fallback_used"])

        service.record_observation("p-3", "2026-08-01", "presale_qty", 2, "dmp_product_day", "dmp-1")
        unique = service.resolve_field("p-3", "2026-08-01", "presale_qty")
        self.assertEqual(unique["value"], 2)
        self.assertEqual(unique["resolution_status"], "effective_unique")
        self.assertEqual(unique["effective_source"], "dmp_product_day")

    def test_dmp_quality_rejects_total_blank_product_and_date_rows(self):
        from services.source_resolution_service import SourceResolutionService

        service = SourceResolutionService(db_path=self.db_path)
        report = service.validate_dmp_rows([
            {"product_id": "总计", "date": "2026-08-01", "payment_amount": 100},
            {"product_id": "", "date": "2026-08-01", "payment_amount": 100},
            {"product_id": "p-4", "date": "", "payment_amount": 100},
            {"product_id": "p-4", "date": "2026-08-01", "payment_amount": "-", "presale_qty": "--"},
        ])

        self.assertEqual(report["summary_rows"], 1)
        self.assertEqual(report["invalid_rows"], 2)
        self.assertEqual(report["valid_rows"], 1)
        self.assertIsNone(report["valid_rows_detail"][0]["payment_amount"])
        self.assertIsNone(report["valid_rows_detail"][0]["presale_qty"])

    def test_dmp_quality_isolates_an_invalid_percentage_field(self):
        from services.source_resolution_service import SourceResolutionService

        service = SourceResolutionService(db_path=self.db_path)
        report = service.validate_dmp_rows([{
            "product_id": "p-quality",
            "date": "2026-08-01",
            "payment_amount": "100",
            "IPV": "20",
            "presale_qty": "2",
            "favorite_cart_rate": "766.67%",
        }])

        self.assertEqual(report["invalid_rows"], 0)
        self.assertEqual(report["valid_rows"], 1)
        self.assertEqual(report["invalid_field_count"], 1)
        self.assertEqual(report["field_warnings"][0]["standard_field"], "favorite_cart_rate")

    def test_dmp_invalid_percentage_is_not_written_but_valid_fields_are(self):
        from services.import_service import ImportService
        import pandas as pd

        frame = pd.DataFrame([{
            "product_id": "p-quality", "date": "2026-08-01",
            "payment_amount": "100", "product_visitors": "20",
            "presale_qty": "2", "favorite_cart_rate": "766.67%",
        }])
        mapping = {column: column for column in frame.columns}
        quality = ImportService._quality(frame, mapping, "dmp_product_day")
        self.assertEqual(quality["invalid_rows"], 0)
        self.assertEqual(quality["invalid_field_count"], 1)

    def test_same_batch_field_observations_are_merged_not_replaced(self):
        from services.source_resolution_service import SourceResolutionService

        service = SourceResolutionService(db_path=self.db_path)
        service.record_observations([
            {
                "product_id": "p-merge", "date": "2026-08-01",
                "standard_key": "payment_amount", "value": 100,
                "source_system": "business_advisor", "source_batch_id": "ba-merge",
            },
            {
                "product_id": "p-merge", "date": "2026-08-01",
                "standard_key": "product_visitors", "value": 20,
                "source_system": "business_advisor", "source_batch_id": "ba-merge",
            },
        ])

        with service.connection() as connection:
            payload = connection.execute(
                "SELECT payload_json FROM daily_data_observations WHERE source_batch_id = 'ba-merge'"
            ).fetchone()[0]
        self.assertIn('payment_amount', payload)
        self.assertIn('product_visitors', payload)

    def test_optional_blank_is_missing_and_numeric_percent_is_not_scaled_twice(self):
        from services.import_service import ImportService, ImportValidationError

        self.assertIsNone(ImportService._optional_number('', percentage=False))
        self.assertIsNone(ImportService._optional_number('--', percentage=False))
        self.assertIsNone(ImportService._optional_number('nan', percentage=False))
        with self.assertRaises(ValueError):
            ImportService._optional_number('inf', percentage=False)
        with self.assertRaises(ImportValidationError):
            ImportService._number('nan', 'payment_amount')
        for overflowing_value in ('1e309', '-1e309'):
            with self.subTest(overflowing_value=overflowing_value):
                with self.assertRaises(ImportValidationError):
                    ImportService._number(overflowing_value, 'payment_amount')
        self.assertEqual(ImportService._optional_number(0.02, percentage=True), 0.02)
        self.assertEqual(ImportService._optional_number('2%', percentage=True), 0.02)

        import pandas as pd
        frame = pd.DataFrame([{
            'date': '2026-08-01', 'product_id': 'non-finite',
            'payment_amount': 'nan', 'product_visitors': 10,
        }])
        quality = ImportService._quality(
            frame, {column: column for column in frame.columns}, 'product_day',
        )
        self.assertEqual(quality['invalid_rows'], 1)

    def test_promotion_attribution_is_retained_for_derived_roi(self):
        from db import get_connection
        from services.source_resolution_service import record_daily_observation

        connection = get_connection(self.db_path)
        try:
            record_daily_observation(
                connection,
                {'product_id': 'p-roi', 'date': '2026-08-01', 'ad_spend': 12,
                 'attributed_payment_amount': 60},
                source_type='promotion_product_day', source_batch_id='promotion-1',
                source_system='promotion_tool', shop_id='default',
            )
            row = connection.execute(
                "SELECT ad_spend, ad_roi FROM daily_data WHERE product_id = 'p-roi'"
            ).fetchone()
            payload = connection.execute(
                "SELECT payload_json FROM daily_data_observations WHERE product_id = 'p-roi'"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(tuple(row), (12.0, 5.0))
        self.assertIn('attributed_payment_amount', payload)

    def test_lineage_and_reconciliation_respect_shop_id(self):
        from services.source_resolution_service import SourceResolutionService

        first = SourceResolutionService(db_path=self.db_path, shop_id='shop-a')
        second = SourceResolutionService(db_path=self.db_path, shop_id='shop-b')
        first.record_observation('p-shop', '2026-08-01', 'payment_amount', 100, 'business_advisor', 'a-1')
        second.record_observation('p-shop', '2026-08-01', 'payment_amount', 200, 'business_advisor', 'b-1')

        with first.connection() as connection:
            lineage = connection.execute(
                "SELECT shop_id, effective_value_json FROM fact_field_lineage WHERE product_id = 'p-shop'"
            ).fetchall()
        self.assertEqual({(row['shop_id'], row['effective_value_json']) for row in lineage},
                         {('shop-a', '100'), ('shop-b', '200')})

    def test_daily_fact_isolated_by_shop_id(self):
        from db import get_connection
        from services.source_resolution_service import record_daily_observation

        connection = get_connection(self.db_path)
        try:
            record_daily_observation(
                connection,
                {'product_id': 'p-same', 'date': '2026-08-01', 'payment_amount': 100, 'product_visitors': 10},
                source_type='product_day', source_batch_id='shop-a-1',
                source_system='business_advisor', shop_id='shop-a',
            )
            record_daily_observation(
                connection,
                {'product_id': 'p-same', 'date': '2026-08-01', 'payment_amount': 200, 'product_visitors': 20},
                source_type='product_day', source_batch_id='shop-b-1',
                source_system='business_advisor', shop_id='shop-b',
            )
            rows = connection.execute(
                "SELECT shop_id, payment_amount FROM daily_data WHERE product_id = 'p-same' ORDER BY shop_id"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual([(row['shop_id'], row['payment_amount']) for row in rows],
                         [('shop-a', 100.0), ('shop-b', 200.0)])

    def test_reverting_one_shop_batch_preserves_other_shop_fact(self):
        import json
        from app import create_app
        from db import get_connection
        from repos.import_repo import ImportRepo

        def batch(batch_id):
            return {
                'id': batch_id, 'source_type': 'product_day',
                'source_filename': f'{batch_id}.xlsx', 'source_hash': batch_id,
                'total_rows': 1, 'valid_rows': 1, 'invalid_rows': 0,
                'quality_summary': json.dumps({'invalid_rows': 0}),
            }

        app = create_app({'TESTING': True, 'DATABASE_PATH': self.db_path})
        with app.app_context():
            ImportRepo.complete_product_daily_batch(batch('shop-a-batch'), [{
                'shop_id': 'shop-a', 'product_id': 'p-revert-shop', 'date': '2026-08-01',
                'payment_amount': 100, 'product_visitors': 10,
            }])
            ImportRepo.complete_product_daily_batch(batch('shop-b-batch'), [{
                'shop_id': 'shop-b', 'product_id': 'p-revert-shop', 'date': '2026-08-01',
                'payment_amount': 200, 'product_visitors': 20,
            }])

            result = ImportRepo.revert_batch('shop-a-batch')

        connection = get_connection(self.db_path)
        try:
            facts = connection.execute(
                "SELECT shop_id, payment_amount FROM daily_data WHERE product_id = 'p-revert-shop' ORDER BY shop_id"
            ).fetchall()
            observations = connection.execute(
                "SELECT shop_id FROM daily_data_observations WHERE product_id = 'p-revert-shop' ORDER BY shop_id"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(result['skipped_count'], 0)
        self.assertEqual([(row['shop_id'], row['payment_amount']) for row in facts], [('shop-b', 200.0)])
        self.assertEqual([row['shop_id'] for row in observations], ['shop-b'])

    def test_observation_lineage_preserves_source_type_and_batch_for_each_grain(self):
        from db import get_connection
        from services.source_resolution_service import record_daily_observation

        connection = get_connection(self.db_path)
        try:
            record_daily_observation(
                connection,
                {'product_id': 'p-product', 'date': '2026-08-12',
                 'payment_amount': 100, 'product_visitors': 10},
                source_type='product_day', source_filename='product.xlsx',
                source_batch_id='product-batch', source_system='business_advisor',
                shop_id='shop-a',
            )
            record_daily_observation(
                connection,
                {'product_id': 'p-dmp', 'date': '2026-08-12',
                 'payment_amount': 80, 'product_visitors': 8},
                source_type='dmp_product_day', source_filename='dmp.xlsx',
                source_batch_id='dmp-batch', source_system='dmp_product_day',
                shop_id='shop-a',
            )
            record_daily_observation(
                connection,
                {'product_id': 'p-promotion', 'date': '2026-08-12',
                 'ad_spend': 12, 'attributed_payment_amount': 60},
                source_type='promotion_product_day', source_filename='promotion.xlsx',
                source_batch_id='promotion-batch', source_system='promotion_tool',
                shop_id='shop-a',
            )
            rows = connection.execute(
                '''SELECT product_id, shop_id, source_type, source_batch_id
                   FROM daily_data_observations
                   WHERE shop_id = 'shop-a' ORDER BY product_id'''
            ).fetchall()
        finally:
            connection.close()

        self.assertEqual(
            [tuple(row) for row in rows],
            [
                ('p-dmp', 'shop-a', 'dmp_product_day', 'dmp-batch'),
                ('p-product', 'shop-a', 'product_day', 'product-batch'),
                ('p-promotion', 'shop-a', 'promotion_product_day', 'promotion-batch'),
            ],
        )


if __name__ == "__main__":
    unittest.main()

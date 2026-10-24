import os
import tempfile
import unittest
from services.snapshot_source_types import SNAPSHOT_SOURCE_TYPES

# The authoritative snapshot source_type is a deployment-private token; the
# public checkout falls back to a neutral value. Pin it here so the precedence
# assertions never depend on which deployment runs the suite.
SNAPSHOT_TYPE = next(iter(SNAPSHOT_SOURCE_TYPES))
SNAPSHOT_OVERVIEW_TYPE = f'{SNAPSHOT_TYPE.rsplit("_", 2)[0]}_overview'
assert SNAPSHOT_TYPE in SNAPSHOT_SOURCE_TYPES


class SourceResolutionTests(unittest.TestCase):
    def setUp(self):
        from db import init_db
        self.tmp = tempfile.TemporaryDirectory(prefix="tmall-source-resolution-")
        self.db_path = os.path.join(self.tmp.name, "dashboard.db")
        init_db(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

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

    def test_snapshot_overrides_older_promotion_value_when_present(self):
        from db import get_connection
        from services.source_resolution_service import record_daily_observation

        connection = get_connection(self.db_path)
        try:
            record_daily_observation(
                connection,
                {'product_id': 'p-snapshot', 'date': '2026-08-18', 'ad_spend': 12},
                source_type='promotion_product_day', source_batch_id='promotion-1',
                source_system='promotion_tool', shop_id='default',
            )
            record_daily_observation(
                connection,
                {'product_id': 'p-snapshot', 'date': '2026-08-18', 'ad_spend': 8},
                source_type=SNAPSHOT_TYPE, source_batch_id='snapshot-1',
                source_system='business_advisor', shop_id='default',
            )
            fact = connection.execute(
                "SELECT ad_spend, recommend_ipv, paid_ipv, organic_ipv, order_amount FROM daily_data WHERE product_id = 'p-snapshot'"
            ).fetchone()
            lineage = connection.execute(
                "SELECT effective_source_type FROM fact_field_lineage WHERE product_id = 'p-snapshot' AND field_key = 'ad_spend'"
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(fact['ad_spend'], 8.0)
        self.assertIsNone(fact['recommend_ipv'])
        self.assertIsNone(fact['paid_ipv'])
        self.assertIsNone(fact['organic_ipv'])
        self.assertIsNone(fact['order_amount'])
        self.assertEqual(lineage['effective_source_type'], SNAPSHOT_TYPE)

    def test_missing_refund_is_derived_from_payment_minus_net_sales(self):
        """退款字段窗口兜底：BI 近 ~13 天不返回退款，按恒等式=支付−净销 推导占位。

        实测（2026-09）：退款缺失让 09-29/30 等窗口内日期退款长期留空；
        恒等式逐行 99.4% 成立。真实退款随窗口后重采覆盖此推导值。
        """
        from db import get_connection
        from services.source_resolution_service import record_daily_observation

        connection = get_connection(self.db_path)
        try:
            # 缺退款 → 推导 100-78=22
            record_daily_observation(
                connection,
                {'product_id': 'p-refund', 'date': '2026-09-29',
                 'payment_amount': 100, 'net_sales': 78},
                source_type=SNAPSHOT_TYPE, source_batch_id='bi-1',
                source_system='business_advisor', shop_id='default',
            )
            # 退款已存在 → 不覆盖
            record_daily_observation(
                connection,
                {'product_id': 'p-refund', 'date': '2026-09-28',
                 'payment_amount': 100, 'net_sales': 78, 'successful_refund_amount': 30},
                source_type=SNAPSHOT_TYPE, source_batch_id='bi-1',
                source_system='business_advisor', shop_id='default',
            )
            # 净销>支付（异常行）→ 不推导出负退款
            record_daily_observation(
                connection,
                {'product_id': 'p-refund', 'date': '2026-09-27',
                 'payment_amount': 50, 'net_sales': 78},
                source_type=SNAPSHOT_TYPE, source_batch_id='bi-1',
                source_system='business_advisor', shop_id='default',
            )
            # 缺净销 → 无从推导
            record_daily_observation(
                connection,
                {'product_id': 'p-refund', 'date': '2026-09-26', 'payment_amount': 100},
                source_type=SNAPSHOT_TYPE, source_batch_id='bi-1',
                source_system='business_advisor', shop_id='default',
            )
            facts = {
                row['date']: row['refund_amount']
                for row in connection.execute(
                    "SELECT date, refund_amount FROM daily_data WHERE product_id = 'p-refund'"
                )
            }
        finally:
            connection.close()

        self.assertAlmostEqual(facts['2026-09-29'], 22.0, places=4)
        self.assertAlmostEqual(facts['2026-09-28'], 30.0, places=4)
        self.assertIsNone(facts['2026-09-27'])
        self.assertIsNone(facts['2026-09-26'])

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

    def test_complete_bi_snapshot_beats_newer_partial_api_snapshot(self):
        """Excel 快照优先于更晚观测的 API 快照（防回归）。

        BI 的 overViewPageList 接口从不返回成本键，成本只存在于用户导出的
        商品总览 Excel。两个写入者共用 source_type=SNAPSHOT_TYPE 与
        source_system='business_advisor'（SOURCE_PRIORITY 同为 30），因此修复前
        由 observed_at 决定胜者：滚动重采写下的 API 观测会把 Excel 的
        operating_profit 覆盖掉，而 Excel 的成本列因逐字段 NULL 保护仍在，
        利润恒等式（净销−成本=利润）随之被破坏，前端显示「部分口径」。

        修复后按 batch_id 前缀（bi_api_）识别 API 快照并在同优先级内降级。
        这里刻意让 API 观测后写入（observed_at 更新），断言 Excel 仍然胜出。
        """
        from db import get_connection
        from services.source_resolution_service import record_daily_observation

        connection = get_connection(self.db_path)
        try:
            # Excel：完整快照（含成本桶与自洽的利润）
            record_daily_observation(
                connection,
                {'product_id': 'p-tie', 'date': '2026-09-13',
                 'net_sales': 3968.22, 'operating_profit': 86.4104,
                 'product_cost': 1520.9, 'sales_cost': 976.39,
                 'custom_cost': 1134.08, 'logistics_cost': 250.44, 'other_cost': 0.0},
                source_type=SNAPSHOT_TYPE,
                source_filename='商品总览_天猫_Primeet派米旗舰店_2026-09-13.xlsx',
                source_batch_id='5442cf7e5ba3d32db15cd9ecaa80238c',
                source_system='business_advisor', shop_id='default',
            )
            # API：稍后观测，但缺全部成本键，利润与 Excel 不一致
            record_daily_observation(
                connection,
                {'product_id': 'p-tie', 'date': '2026-09-13',
                 'net_sales': 3968.0, 'operating_profit': -516.0},
                source_type=SNAPSHOT_TYPE,
                source_filename='bi_api_full_2026-09-13.json',
                source_batch_id='bi_api_full_2026-09-13.json',
                source_system='business_advisor', shop_id='default',
            )
            fact = connection.execute(
                '''SELECT net_sales, operating_profit, product_cost, sales_cost,
                          custom_cost, logistics_cost, other_cost
                   FROM daily_data WHERE product_id = 'p-tie' AND date = '2026-09-13' '''
            ).fetchone()
            lineage = connection.execute(
                '''SELECT source_batch_id FROM fact_field_lineage
                   WHERE product_id = 'p-tie' AND date = '2026-09-13'
                     AND field_key = 'operating_profit' '''
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(fact['operating_profit'], 86.4104)
        self.assertEqual(fact['product_cost'], 1520.9)
        self.assertEqual(lineage['source_batch_id'], '5442cf7e5ba3d32db15cd9ecaa80238c')
        identity_gap = (
            fact['net_sales']
            - (fact['product_cost'] + fact['sales_cost'] + fact['custom_cost']
               + fact['logistics_cost'] + fact['other_cost'])
            - fact['operating_profit']
        )
        self.assertLess(abs(identity_gap), abs(fact['net_sales']) * 0.005)

    def test_api_snapshot_still_used_when_no_excel_snapshot_exists(self):
        """无 Excel 快照时 API 观测必须照常生效（修复不得让字段落空）。"""
        from db import get_connection
        from services.source_resolution_service import record_daily_observation

        connection = get_connection(self.db_path)
        try:
            record_daily_observation(
                connection,
                {'product_id': 'p-api-only', 'date': '2026-10-13',
                 'net_sales': 100.0, 'operating_profit': 25.0},
                source_type=SNAPSHOT_TYPE,
                source_filename='bi_api_full_2026-10-13.json',
                source_batch_id='bi_api_full_2026-10-13.json',
                source_system='business_advisor', shop_id='default',
            )
            fact = connection.execute(
                '''SELECT net_sales, operating_profit FROM daily_data
                   WHERE product_id = 'p-api-only' AND date = '2026-10-13' '''
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(fact['net_sales'], 100.0)
        self.assertEqual(fact['operating_profit'], 25.0)


if __name__ == "__main__":
    unittest.main()

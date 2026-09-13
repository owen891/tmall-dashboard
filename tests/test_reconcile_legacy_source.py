import os
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from db import get_db, init_db
from scripts.reconcile_legacy_source import (
    LegacySourceMatchError,
    _source_rows,
    apply_plan,
    plan,
)


class ReconcileLegacySourceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-reconcile-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        init_db(self.database_path)

    def tearDown(self):
        for handle in getattr(self, '_open_handles', []):
            handle.close()
        self.temp_dir.cleanup()

    def _workbook(self, rows):
        path = Path(self.temp_dir.name) / 'source.xlsx'
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = '生意参谋平台-1'
        sheet.append([])
        sheet.append([])
        sheet.append([])
        sheet.append(['统计日期', '商品ID', '支付金额', '成功退款金额', '支付件数',
                      '商品访客数', '商品浏览量', '商品支付转化率', '商品详情页跳出率',
                      '平均停留时长', '支付买家数', '客单价'])
        sheet.append(['统计日期', '商品ID', '支付金额', '成功退款金额', '支付件数',
                      '商品访客数', '商品浏览量', '商品支付转化率', '商品详情页跳出率',
                      '平均停留时长', '支付买家数', '客单价'])
        for row in rows:
            sheet.append(row)
        workbook.save(path)
        workbook.close()
        self._open_handles = getattr(self, '_open_handles', [])
        return path

    def _insert_fact(self, product_id='p-1', payment=100):
        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO daily_data
                   (shop_id, product_id, date, payment_amount, refund_amount, net_sales,
                    payment_qty, ipv, pv, payment_conversion, bounce_rate,
                    avg_stay_duration, buyers, avg_order_value)
                   VALUES ('default', ?, '2026-04-19', ?, 10, ?, 2, 20, 40,
                           0.1, 0.2, 15, 2, ?)''',
                (product_id, payment, payment - 10, payment / 2),
            )
            connection.commit()

    def test_real_workbook_recognizes_all_daily_rows(self):
        rows = [
            ['2026-04-19', f'p-{index}', 100, 10, 2, 20, 40, 0.1, 0.2, 15, 2, 50]
            for index in range(760)
        ]
        source = self._workbook(rows)
        self.assertEqual(len(_source_rows(source, {'2026-04-19'})), 760)

    def test_missing_source_refuses_apply(self):
        self._insert_fact()
        report = plan(self.database_path, self._workbook([
            ['2026-04-19', 'other-product', 100, 10, 2, 20, 40, 0.1, 0.2, 15, 2, 50],
        ]))
        self.assertFalse(report['eligible'])
        with self.assertRaises(LegacySourceMatchError):
            apply_plan(report)
        with get_db(self.database_path) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM import_batches').fetchone()[0], 0)

    def test_core_mismatch_refuses_apply(self):
        self._insert_fact(payment=100)
        report = plan(self.database_path, self._workbook([
            ['2026-04-19', 'p-1', 101, 10, 2, 20, 40, 0.1, 0.2, 15, 2, 50.5],
        ]))
        self.assertFalse(report['eligible'])
        self.assertEqual(report['mismatches'][0]['fields'][0]['field'], 'payment_amount')
        with self.assertRaises(LegacySourceMatchError):
            apply_plan(report)

    def test_apply_is_idempotent(self):
        self._insert_fact()
        report = plan(self.database_path, self._workbook([
            ['2026-04-19', 'p-1', 100, 10, 2, 20, 40, 0.1, 0.2, 15, 2, 50],
        ]))
        self.assertTrue(report['eligible'])
        first = apply_plan(report)
        second = apply_plan(report)
        self.assertEqual(first['written'], 1)
        self.assertEqual(second['written'], 0)
        self.assertTrue(second['already_applied'])
        with get_db(self.database_path) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM import_batches').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM daily_data_observations').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM fact_field_lineage').fetchone()[0], 11)

    def test_empty_database_is_a_successful_noop(self):
        source = self._workbook([])
        report = plan(self.database_path, source)
        self.assertTrue(report['eligible'])
        result = apply_plan(report)
        self.assertTrue(result['no_op'])
        self.assertIsNone(result['batch_id'])


if __name__ == '__main__':
    unittest.main()

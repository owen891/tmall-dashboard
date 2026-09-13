import gc
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _workbook_bytes(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


class LegacyImportCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            prefix='tmall-legacy-cli-', ignore_cleanup_errors=True
        )
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from app import create_app

        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': self.database_path,
        })

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    def _run(self, filename, source_type, headers, rows):
        from scripts.legacy_import_cli import run_legacy_import

        path = os.path.join(self.temp_dir.name, filename)
        with open(path, 'wb') as output:
            output.write(_workbook_bytes(headers, rows))
        with patch('scripts.legacy_import_cli.create_app', return_value=self.app):
            status = run_legacy_import([path], source_type)
        return status

    def test_daily_cli_writes_fact_batch_observation_and_lineage(self):
        status = self._run(
            'smart-selection-2026-04-22.xlsx',
            'product_day',
            ['商品ID', '支付金额', '退款金额', '商品访客数', '支付买家数'],
            [['legacy-daily', 120, 4, 30, 3]],
        )
        self.assertEqual(status, 0)

        from db import get_db

        with get_db(self.database_path) as connection:
            fact = connection.execute(
                '''SELECT shop_id, product_id, date, payment_amount,
                          refund_amount, ipv, buyers
                   FROM daily_data'''
            ).fetchone()
            batch = connection.execute(
                '''SELECT id, source_type, source_filename, status
                   FROM import_batches'''
            ).fetchone()
            observation = connection.execute(
                '''SELECT source_batch_id, source_type, source_filename, payload_json
                   FROM daily_data_observations'''
            ).fetchone()
            lineage_count = connection.execute(
                '''SELECT COUNT(*) FROM fact_field_lineage
                   WHERE product_id = 'legacy-daily' AND date = '2026-04-22' '''
            ).fetchone()[0]

        self.assertEqual(tuple(fact), ('default', 'legacy-daily', '2026-04-22', 120.0, 4.0, 30, 3))
        self.assertEqual(batch['source_type'], 'product_day')
        self.assertEqual(batch['source_filename'], 'smart-selection-2026-04-22.xlsx')
        self.assertEqual(batch['status'], 'completed')
        self.assertEqual(observation['source_batch_id'], batch['id'])
        self.assertEqual(observation['source_type'], 'product_day')
        self.assertEqual(observation['source_filename'], batch['source_filename'])
        self.assertEqual(json.loads(observation['payload_json'])['payment_amount'], 120.0)
        self.assertGreater(lineage_count, 0)

    def test_monthly_cli_allows_missing_optional_ad_spend(self):
        status = self._run(
            'smart-selection-2026-04-22.xlsx',
            'product_month',
            ['商品ID', '支付金额', '退款金额', '商品访客数', '支付买家数'],
            [['legacy-month', 220, 8, 40, 4]],
        )
        self.assertEqual(status, 0)

        from db import get_db

        with get_db(self.database_path) as connection:
            row = connection.execute(
                '''SELECT product_id, month, payment_amount, refund_amount,
                          net_sales, visitors, ad_spend
                   FROM monthly_data'''
            ).fetchone()
            batch_count = connection.execute(
                "SELECT COUNT(*) FROM import_batches WHERE source_type = 'product_month'"
            ).fetchone()[0]

        self.assertEqual(tuple(row), ('legacy-month', '2026-04', 220.0, 8.0, 212.0, 40, None))
        self.assertEqual(batch_count, 1)

    def test_weekly_cli_allows_missing_optional_ad_spend(self):
        status = self._run(
            'smart-selection-2026-04-22.xlsx',
            'product_week',
            ['商品ID', '支付金额', '退款金额', '商品访客数', '支付买家数'],
            [['legacy-week', 180, 6, 35, 3]],
        )
        self.assertEqual(status, 0)

        from db import get_db

        with get_db(self.database_path) as connection:
            row = connection.execute(
                '''SELECT product_id, week_start, payment_amount, refund_amount,
                          net_sales, ipv, ad_spend
                   FROM weekly_data'''
            ).fetchone()

        self.assertEqual(tuple(row), ('legacy-week', '2026-04-22', 180.0, 6.0, 174.0, 35, None))

    def test_invalid_date_or_quality_error_does_not_write_business_facts(self):
        status = self._run(
            'smart-selection-without-date.xlsx',
            'product_day',
            ['商品ID', '支付金额', '退款金额', '商品访客数', '支付买家数'],
            [['legacy-invalid', 120, 4, 30, 3]],
        )
        self.assertEqual(status, 1)

        status = self._run(
            'smart-selection-2026-04-22.xlsx',
            'product_day',
            ['商品ID', '支付金额', '退款金额', '商品访客数', '支付买家数'],
            [['legacy-quality-error', 'not-a-number', 4, 30, 3]],
        )
        self.assertEqual(status, 1)

        from db import get_db

        with get_db(self.database_path) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM daily_data').fetchone()[0], 0)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM import_batches').fetchone()[0], 0)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM import_previews').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()

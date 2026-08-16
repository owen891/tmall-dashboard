"""Behavior locks for the two business-import entry points.

These tests deliberately execute the canonical HTTP flow and the historical
``scripts.import_data.import_excel_file`` flow against separate databases.
The legacy function does not create import batches, so metadata assertions
make that difference explicit instead of accidentally treating it as parity.
The promotion case also records the currently proven gap: the old dispatcher
does not write promotion facts at all.
"""

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
    sheet.title = 'Sheet'
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


class ImportLegacyParityTests(unittest.TestCase):
    def setUp(self):
        # ``import_excel_file`` leaves pandas' ExcelFile handle to be finalized
        # by the interpreter on Windows. Ignore cleanup errors for this
        # process-local fixture directory; no repository files are touched.
        self.temp_dir = tempfile.TemporaryDirectory(
            prefix='tmall-import-parity-', ignore_cleanup_errors=True
        )
        self.canonical_db = os.path.join(self.temp_dir.name, 'canonical.db')
        self.legacy_db = os.path.join(self.temp_dir.name, 'legacy.db')

        from app import create_app

        self.canonical_app = create_app({
            'TESTING': True,
            'DATABASE_PATH': self.canonical_db,
        })
        self.legacy_app = create_app({
            'TESTING': True,
            'DATABASE_PATH': self.legacy_db,
        })

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    @staticmethod
    def _quality_summary(database_path):
        from db import get_db

        with get_db(database_path) as connection:
            row = connection.execute(
                'SELECT quality_summary FROM import_batches ORDER BY created_at DESC LIMIT 1'
            ).fetchone()
        if row is None:
            return None
        quality = json.loads(row['quality_summary'])
        return {
            key: quality.get(key)
            for key in ('total_rows', 'valid_rows', 'invalid_rows', 'duplicate_keys')
        }

    @staticmethod
    def _observation(database_path, product_id):
        from db import get_db

        with get_db(database_path) as connection:
            row = connection.execute(
                '''SELECT shop_id, product_id, date, source_type, source_filename,
                          source_batch_id, payload_json
                   FROM daily_data_observations
                   WHERE product_id = ?
                   ORDER BY id DESC LIMIT 1''',
                (product_id,),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item['payload'] = json.loads(item.pop('payload_json'))
        return item

    @staticmethod
    def _legacy_quality(result):
        """Translate the old result shape into the canonical summary fields."""
        successful_rows = sum(
            int(detail.get('rows') or 0)
            for detail in result.get('details', [])
            if detail.get('status') == 'success'
        )
        return {
            'total_rows': int(result.get('total_rows') or 0),
            'valid_rows': successful_rows,
            'invalid_rows': 0,
            'duplicate_keys': 0,
        }

    def _run_canonical(self, filename, source_type, headers, rows):
        client = self.canonical_app.test_client()
        response = client.post(
            f'/api/imports/preview?source_type={source_type}',
            data={'file': (_workbook_bytes(headers, rows), filename)},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        preview = response.get_json()['data']
        self.assertEqual(preview['required_unmapped'], [])

        response = client.post(
            '/api/imports',
            json={'preview_id': preview['id'], 'mapping': preview['mapping']},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()['data']

    def _run_legacy(self, filename, headers, rows):
        from scripts.import_data import import_excel_file

        path = os.path.join(self.temp_dir.name, filename)
        with open(path, 'wb') as output:
            output.write(_workbook_bytes(headers, rows).read())

        # The historical function also performs a process-wide backup and
        # recalculation. They are unrelated to entry-point parity and would
        # write outside the temporary database, so keep this test hermetic.
        with self.legacy_app.app_context(), \
                patch('scripts.import_data.backup_database'), \
                patch('scripts.import_data.recalc_action_effects'), \
                patch('scripts.import_data.log_import'):
            result = import_excel_file(path)
        gc.collect()
        return result

    def test_product_day_core_values_and_lineage_match_legacy(self):
        filename = 'product-\u65e5.xlsx'
        headers = [
            '\u65e5\u671f', '\u5546\u54c1ID', '\u652f\u4ed8\u91d1\u989d',
            '\u6210\u529f\u9000\u6b3e\u91d1\u989d', '\u5546\u54c1\u8bbf\u5ba2\u6570',
            '\u652f\u4ed8\u4e70\u5bb6\u6570',
        ]
        rows = [['2026-04-01', 'product-parity', '123.40', '3.40', '20', '2']]

        report = self._run_canonical(filename, 'product_day', headers, rows)
        legacy = self._run_legacy(filename, headers, rows)
        canonical_observation = self._observation(self.canonical_db, 'product-parity')
        legacy_observation = self._observation(self.legacy_db, 'product-parity')

        self.assertEqual(legacy['total_rows'], 1)
        self.assertEqual(canonical_observation['product_id'], legacy_observation['product_id'])
        self.assertEqual(canonical_observation['shop_id'], 'default')
        self.assertEqual(legacy_observation['shop_id'], 'default')
        self.assertEqual(canonical_observation['shop_id'], legacy_observation['shop_id'])
        self.assertEqual(canonical_observation['date'], legacy_observation['date'])
        self.assertEqual(canonical_observation['source_type'], 'product_day')
        self.assertEqual(legacy_observation['source_type'], 'product_day')
        self.assertEqual(canonical_observation['source_filename'], filename)
        self.assertEqual(legacy_observation['source_filename'], filename)
        self.assertEqual(
            canonical_observation['payload'], legacy_observation['payload']
        )
        self.assertEqual(
            self._quality_summary(self.canonical_db),
            self._legacy_quality(legacy),
        )

        # The canonical batch id is persisted and linked to the observation;
        # legacy behavior uses the filename as its source batch id and has no
        # import_batches row. This is the metadata migration lock for Task 6.
        self.assertTrue(canonical_observation['source_batch_id'])
        self.assertEqual(legacy_observation['source_batch_id'], filename)
        self.assertNotEqual(
            canonical_observation['source_batch_id'],
            legacy_observation['source_batch_id'],
        )
        self.assertEqual(report['quality_conclusion'], 'passed')

    def test_dmp_product_day_core_values_and_lineage_match_legacy(self):
        filename = 'dmp-daily.xlsx'
        headers = [
            '\u5b9d\u8d1dID', '\u5b9d\u8d1d\u540d\u79f0', '\u65e5\u671f',
            '\u652f\u4ed8\u91d1\u989d', 'IPV', '\u8425\u9500\u63a8\u5e7fIPV',
            '\u975e\u63a8\u5e7fIPV', '\u8425\u9500\u63a8\u5e7f\u6d88\u8017',
            '\u9884\u552e\u9500\u91cf',
        ]
        rows = [['dmp-parity', 'DMP product', '2026-04-01', '300', '100', '20', '80', '30', '2']]

        report = self._run_canonical(filename, 'dmp_product_day', headers, rows)
        legacy = self._run_legacy(filename, headers, rows)
        canonical_observation = self._observation(self.canonical_db, 'dmp-parity')
        legacy_observation = self._observation(self.legacy_db, 'dmp-parity')

        self.assertEqual(legacy['total_rows'], 1)
        self.assertEqual(canonical_observation['product_id'], legacy_observation['product_id'])
        self.assertEqual(canonical_observation['shop_id'], 'default')
        self.assertEqual(legacy_observation['shop_id'], 'default')
        self.assertEqual(canonical_observation['shop_id'], legacy_observation['shop_id'])
        self.assertEqual(canonical_observation['date'], legacy_observation['date'])
        self.assertEqual(canonical_observation['source_type'], 'dmp_product_day')
        self.assertEqual(legacy_observation['source_type'], 'dmp_product_day')
        for field in (
            'payment_amount', 'product_visitors', 'paid_visitors',
            'organic_visitors', 'ad_spend', 'presale_qty',
        ):
            self.assertEqual(
                canonical_observation['payload'].get(field),
                legacy_observation['payload'].get(field),
                field,
            )
        self.assertEqual(
            self._quality_summary(self.canonical_db),
            self._legacy_quality(legacy),
        )
        self.assertTrue(canonical_observation['source_batch_id'])
        self.assertEqual(legacy_observation['source_batch_id'], 'legacy-dmp-daily')
        self.assertNotEqual(
            canonical_observation['source_batch_id'],
            legacy_observation['source_batch_id'],
        )
        self.assertEqual(report['quality_conclusion'], 'passed')

    def test_promotion_product_day_records_the_legacy_dispatcher_gap(self):
        """The old dispatcher has no promotion target and silently drops it."""
        filename = 'promotion-\u65e5.xlsx'
        headers = [
            '\u65e5\u671f', '\u6e20\u9053', '\u5546\u54c1ID',
            '\u63a8\u5e7f\u82b1\u8d39', '\u63a8\u5e7f\u6210\u4ea4\u91d1\u989d',
        ]
        rows = [['2026-04-01', 'search', 'promotion-parity', '12', '60']]

        report = self._run_canonical(filename, 'promotion_product_day', headers, rows)
        legacy = self._run_legacy(filename, headers, rows)

        from db import get_db

        with get_db(self.canonical_db) as connection:
            canonical_fact = connection.execute(
                '''SELECT shop_id, date, channel, product_id, ad_spend,
                          attributed_payment_amount, source_batch_id
                   FROM promotion_daily_facts'''
            ).fetchone()
        with get_db(self.legacy_db) as connection:
            legacy_fact = connection.execute(
                'SELECT 1 FROM promotion_daily_facts LIMIT 1'
            ).fetchone()
            legacy_observation = connection.execute(
                'SELECT 1 FROM daily_data_observations LIMIT 1'
            ).fetchone()
            legacy_batch = connection.execute(
                'SELECT 1 FROM import_batches LIMIT 1'
            ).fetchone()

        self.assertEqual(legacy['total_rows'], 1)
        self.assertEqual(report['source_type'], 'promotion_product_day')
        self.assertEqual(tuple(canonical_fact[:6]), (
            'default', '2026-04-01', 'search', 'promotion-parity', 12.0, 60.0,
        ))
        self.assertTrue(canonical_fact['source_batch_id'])
        # Proven baseline divergence: legacy import_excel_file reports a row,
        # but its date/product fallback has no promotion branch, so no
        # promotion fact, observation lineage, or quality batch is created.
        self.assertIsNone(legacy_fact)
        self.assertIsNone(legacy_observation)
        self.assertIsNone(legacy_batch)
        self.assertEqual(
            self._quality_summary(self.canonical_db),
            self._legacy_quality(legacy),
        )


if __name__ == '__main__':
    unittest.main()

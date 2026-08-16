import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from openpyxl import Workbook


def workbook_bytes(rows):
    book = Workbook()
    sheet = book.active
    sheet.append(['date', 'product_id', 'payment_amount', 'product_visitors'])
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


class ImportScanServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tmall-import-scan-')
        self.db_path = os.path.join(self.tmp.name, 'scan.db')
        self.inbox = os.path.join(self.tmp.name, 'inbox')
        os.makedirs(self.inbox)
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': self.db_path,
            'IMPORT_SCAN_ALLOWED_ROOTS': [self.inbox],
        })
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()
        self.tmp.cleanup()

    def test_job_rejects_path_outside_allowed_root(self):
        from services.import_scan_service import ImportScanValidationError, ImportScanService
        with self.assertRaises(ImportScanValidationError):
            ImportScanService.create_job({
                'task_name': 'bad',
                'folder_path': self.tmp.name,
                'source_type': 'product_day',
                'cron_expr': '* * * * *',
            })

    def test_run_once_imports_stable_file_and_is_idempotent(self):
        from services.import_scan_service import ImportScanService
        path = os.path.join(self.inbox, 'daily.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'p-1', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'daily',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        first = ImportScanService.run_job_once(job['id'])
        self.assertEqual(first['imported_count'], 0)
        second = ImportScanService.run_job_once(job['id'])
        self.assertEqual(second['imported_count'], 1)
        third = ImportScanService.run_job_once(job['id'])
        self.assertEqual(third['imported_count'], 0)
        files = ImportScanService.list_files(job['id'])
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['status'], 'imported')
        self.assertIsNotNone(files[0]['batch_id'])

    def test_invalid_preview_is_blocked_without_business_write(self):
        from services.import_scan_service import ImportScanService
        path = os.path.join(self.inbox, 'invalid.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', '', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'invalid',
            'folder_path': self.inbox,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        result = ImportScanService.run_job_once(job['id'])
        self.assertEqual(result['blocked_count'], 1)
        self.assertEqual(ImportScanService.list_files(job['id'])[0]['status'], 'blocked')

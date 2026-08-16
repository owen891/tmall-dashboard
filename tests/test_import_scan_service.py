import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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

    def test_combined_patterns_match_supported_import_formats(self):
        from services.import_scan_service import DEFAULT_FILE_PATTERN, _matches_pattern

        self.assertEqual(DEFAULT_FILE_PATTERN, '*.xlsx;*.xls;*.csv;*.zip')
        for filename in ('daily.xlsx', 'legacy.xls', 'promotion.csv', 'reports.zip'):
            self.assertTrue(_matches_pattern(filename, DEFAULT_FILE_PATTERN))
        self.assertFalse(_matches_pattern('notes.pdf', DEFAULT_FILE_PATTERN))

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

    def test_scan_uses_cron_expression_when_scheduling_next_run(self):
        from services.import_scan_service import ImportScanService

        fixed_now = datetime(2026, 8, 16, 9, 15, tzinfo=timezone.utc)
        with patch('services.import_scan_service._utc_now', return_value=fixed_now):
            job = ImportScanService.create_job({
                'task_name': 'morning',
                'folder_path': self.inbox,
                'source_type': 'product_day',
                'cron_expr': '0 8 * * *',
            })
            self.assertEqual(job['next_run'], '2026-08-17T08:00:00+00:00')
            self.assertEqual(ImportScanService.run_due_jobs(now=fixed_now + timedelta(hours=1)), [])
            ImportScanService.run_job_once(job['id'])

        scheduled = ImportScanService.get_job(job['id'])['next_run']
        self.assertEqual(scheduled, '2026-08-17T08:00:00+00:00')

    def test_update_uses_cron_expression_when_scheduling_next_run(self):
        from services.import_scan_service import ImportScanService

        fixed_now = datetime(2026, 8, 16, 9, 15, tzinfo=timezone.utc)
        with patch('services.import_scan_service._utc_now', return_value=fixed_now):
            job = ImportScanService.create_job({
                'task_name': 'morning',
                'folder_path': self.inbox,
                'source_type': 'product_day',
                'cron_expr': '* * * * *',
            })
            updated = ImportScanService.update_job(job['id'], {'cron_expr': '30 9 * * *'})

        self.assertEqual(updated['next_run'], '2026-08-16T09:30:00+00:00')

    def test_run_due_jobs_continues_after_one_job_has_an_invalid_directory(self):
        from services.import_scan_service import ImportScanService

        broken_folder = os.path.join(self.inbox, 'broken')
        healthy_folder = os.path.join(self.inbox, 'healthy')
        os.makedirs(broken_folder)
        os.makedirs(healthy_folder)
        broken = ImportScanService.create_job({
            'task_name': 'broken',
            'folder_path': broken_folder,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        healthy = ImportScanService.create_job({
            'task_name': 'healthy',
            'folder_path': healthy_folder,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        os.rmdir(broken_folder)

        results = ImportScanService.run_due_jobs(now=datetime.now(timezone.utc) + timedelta(minutes=1))

        self.assertEqual([result['job_id'] for result in results], [healthy['id']])

    def test_repeated_scan_of_same_file_version_does_not_create_second_batch(self):
        from db import get_db
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'same-version.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'same-version', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'same-version',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        ImportScanService.run_job_once(job['id'])

        with get_db(self.db_path) as connection:
            batch_count = connection.execute(
                'SELECT COUNT(*) FROM import_batches WHERE source_filename = ?',
                ('same-version.xlsx',),
            ).fetchone()[0]
            connection.execute(
                "UPDATE import_scan_files SET status='discovered' WHERE job_id=?",
                (job['id'],),
            )
            connection.commit()

        ImportScanService.run_job_once(job['id'])

        with get_db(self.db_path) as connection:
            self.assertEqual(
                connection.execute(
                    'SELECT COUNT(*) FROM import_batches WHERE source_filename = ?',
                    ('same-version.xlsx',),
                ).fetchone()[0],
                batch_count,
            )

    def test_existing_importing_file_is_skipped_by_overlapping_worker(self):
        from db import get_db
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'in-progress.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'in-progress', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'in-progress',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        source_hash = ImportScanService._file_hash(path)
        with get_db(self.db_path) as connection:
            connection.execute(
                "UPDATE import_scan_files SET source_hash=?, status='importing' WHERE job_id=?",
                (source_hash, job['id']),
            )
            connection.commit()

        result = ImportScanService.run_job_once(job['id'])

        self.assertEqual(result['imported_count'], 0)
        self.assertEqual(result['discovered_count'], 0)
        self.assertEqual(ImportScanService.list_files(job['id'])[0]['status'], 'importing')

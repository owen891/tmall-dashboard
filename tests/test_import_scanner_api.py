import os
import tempfile
import unittest

from openpyxl import Workbook


def workbook_bytes(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    from io import BytesIO
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


class ImportScannerApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tmall-import-scan-api-')
        self.db_path = os.path.join(self.tmp.name, 'api.db')
        self.inbox = os.path.join(self.tmp.name, 'inbox')
        os.mkdir(self.inbox)
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': self.db_path,
            'IMPORT_SCAN_ALLOWED_ROOTS': [self.inbox],
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()

    def tearDown(self):
        self.ctx.pop()
        self.tmp.cleanup()

    def test_crud_and_legacy_schedule_migration_contract(self):
        created = self.client.post('/api/import-scans', json={
            'task_name': 'daily', 'folder_path': self.inbox,
            'source_type': 'product_day', 'cron_expr': '* * * * *',
        })
        self.assertEqual(created.status_code, 201)
        job_id = created.get_json()['data']['id']
        listed = self.client.get('/api/import-scans')
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()['data'][0]['id'], job_id)
        updated = self.client.put(f'/api/import-scans/{job_id}', json={'enabled': False})
        self.assertEqual(updated.status_code, 200)
        deleted = self.client.delete(f'/api/import-scans/{job_id}')
        self.assertEqual(deleted.status_code, 200)
        old = self.client.get('/api/manage/schedules')
        self.assertEqual(old.status_code, 410)
        self.assertEqual(old.get_json()['code'], 'LEGACY_SCHEDULE_REMOVED')

    def test_invalid_local_path_returns_422(self):
        response = self.client.post('/api/import-scans', json={
            'task_name': 'bad', 'folder_path': os.path.dirname(self.inbox),
            'source_type': 'product_day', 'cron_expr': '* * * * *',
        })
        self.assertEqual(response.status_code, 422)

    def test_manual_run_can_force_scan_and_returns_import_counters(self):
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'manual.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes(['date', 'product_id', 'payment_amount', 'product_visitors'], [
                ['2026-08-01', 'manual', 100, 10],
            ]).getvalue())
        job = ImportScanService.create_job({
            'task_name': 'manual', 'folder_path': self.inbox,
            'file_pattern': '*.xlsx', 'source_type': 'product_day', 'cron_expr': '* * * * *',
        })

        response = self.client.post(f"/api/import-scans/{job['id']}/run", json={'force': True})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()['data']
        self.assertEqual(result['discovered_count'], 1)
        self.assertEqual(result['imported_count'], 1)

    def test_manual_run_conflict_exposes_structured_code(self):
        from db import get_db
        from services.import_scan_service import ImportScanService

        job = ImportScanService.create_job({
            'task_name': 'busy', 'folder_path': self.inbox,
            'source_type': 'product_day', 'cron_expr': '* * * * *',
        })
        token = ImportScanService._acquire_lease(job['id'])
        response = self.client.post(f"/api/import-scans/{job['id']}/run", json={'force': True})
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload['code'], 'SCAN_RUNNING')
        ImportScanService._release_lease(job['id'], token)

    def test_blocked_scan_file_can_be_requeued_through_an_explicit_api(self):
        from datetime import datetime, timedelta, timezone
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'blocked.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes(['date', 'product_id', 'payment_amount', 'product_visitors'], [
                ['2026-08-01', '', 100, 10],
            ]).getvalue())
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'blocked-retry',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        ImportScanService.run_job_once(job['id'])
        file_row = ImportScanService.list_files(job['id'])[0]
        self.assertEqual(file_row['status'], 'blocked')

        response = self.client.post(f"/api/import-scans/{job['id']}/files/{file_row['id']}/retry")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()['data']
        self.assertEqual(payload['status'], 'discovered')
        self.assertIsNone(payload['preview_id'])
        self.assertIsNone(payload['error_code'])
        self.assertLessEqual(ImportScanService.get_job(job['id'])['next_run'], datetime.now(timezone.utc).isoformat())

    def test_failed_scan_file_can_be_requeued_through_an_explicit_api(self):
        from datetime import datetime, timedelta, timezone
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'failed.xlsx')
        with open(path, 'wb') as handle:
            handle.write(b'not an excel workbook')
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'failed-retry',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        ImportScanService.run_job_once(job['id'])
        file_row = ImportScanService.list_files(job['id'])[0]
        self.assertEqual(file_row['status'], 'failed')

        response = self.client.post(f"/api/import-scans/{job['id']}/files/{file_row['id']}/retry")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()['data']
        self.assertEqual(payload['status'], 'discovered')
        self.assertIsNone(payload['error_code'])

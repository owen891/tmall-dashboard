import os
import tempfile
import unittest


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
        self.client = self.app.test_client()

    def tearDown(self):
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


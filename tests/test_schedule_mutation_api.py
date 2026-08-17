import os
import tempfile
import unittest


class ScheduleMutationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-schedule-mutations-')
        from app import create_app
        self.path = os.path.join(self.temp.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_schedule_api_returns_migration_contract(self):
        requests = [
            ('get', '/api/manage/schedules'),
            ('post', '/api/manage/schedules'),
            ('put', '/api/manage/schedules/1'),
            ('delete', '/api/manage/schedules/1'),
            ('post', '/api/manage/schedules/1/run'),
        ]
        for method, path in requests:
            response = getattr(self.client, method)(path, json={})
            self.assertEqual(response.status_code, 410)
            self.assertEqual(response.get_json()['code'], 'LEGACY_SCHEDULE_REMOVED')

    def test_new_scan_api_replaces_schedule_creation(self):
        root = os.path.join(self.temp.name, 'inbox')
        os.mkdir(root)
        response = self.client.post('/api/import-scans', json={
            'task_name': 'daily',
            'folder_path': root,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        self.assertEqual(response.status_code, 422)
        # The default allowed root does not include arbitrary temp folders.
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')


if __name__ == '__main__':
    unittest.main()

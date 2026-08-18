import os
import tempfile
import unittest


class ManageMutationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-manage-mutations-')
        from app import create_app

        self.path = os.path.join(self.temp.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_task_lifecycle_returns_evidence_and_audit(self):
        created = self.client.post('/api/manage/tasks', json={
            'title': '补齐数据', 'description': '验证正式任务接口', 'priority': 'P1',
            'operator': '店长', 'reason': '建立待办',
        })
        payload = created.get_json()
        self.assertEqual(created.status_code, 201)
        self.assertEqual(payload['evidence'][0]['source'], 'task_items')
        task_id = payload['data']['id']

        updated = self.client.put(f'/api/manage/tasks/{task_id}', json={
            'status': 'done', 'operator': '店长', 'reason': '已完成补数',
        })
        updated_payload = updated.get_json()
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated_payload['data']['status'], 'done')
        self.assertEqual(updated_payload['evidence'][0]['source'], 'task_items')

        listed = self.client.get('/api/manage/tasks?status=done')
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()['data'][0]['id'], task_id)

        deleted = self.client.delete(f'/api/manage/tasks/{task_id}', json={
            'operator': '店长', 'reason': '清理已完成任务',
        })
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.get_json()['data']['deleted_count'], 1)

    def test_kpi_lifecycle_returns_evidence_and_audit(self):
        created = self.client.post('/api/manage/kpis', json={
            'user_name': '运营A', 'period': '2026-08', 'target_gmv': 100000,
            'actual_gmv': 80000, 'achievement_rate': 0.8, 'rating': 'B',
            'operator': '店长', 'reason': '建立月度 KPI',
        })
        payload = created.get_json()
        self.assertEqual(created.status_code, 201)
        self.assertEqual(payload['evidence'][0]['source'], 'user_kpis')
        kpi_id = payload['data']['id']

        listed = self.client.get('/api/manage/kpis?period=2026-08')
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()['data'][0]['id'], kpi_id)

        updated = self.client.put(f'/api/manage/kpis/{kpi_id}', json={
            'actual_gmv': 90000, 'achievement_rate': 0.9,
            'operator': '店长', 'reason': '更新实际完成值',
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()['data']['actual_gmv'], 90000)

        deleted = self.client.delete(f'/api/manage/kpis/{kpi_id}', json={
            'operator': '店长', 'reason': '删除测试 KPI',
        })
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.get_json()['data']['deleted_count'], 1)

    def test_task_fields_are_validated_before_write(self):
        for payload in (
            {'title': 'bad status', 'status': 'finished'},
            {'title': 'bad priority', 'priority': 'P9'},
            {'title': 'bad date', 'due_date': '2026/08/01'},
        ):
            with self.subTest(payload=payload):
                response = self.client.post('/api/manage/tasks', json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

        for payload in ({'title': None}, {'title': '   '}, {'title': 'bad compact date', 'due_date': '20260801'}):
            response = self.client.post('/api/manage/tasks', json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

        created = self.client.post('/api/manage/tasks', json={'title': 'valid'}).get_json()['data']['id']
        for payload in ({'title': None}, {'title': '   '}):
            response = self.client.put(f'/api/manage/tasks/{created}', json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

        for query in ('status=bad', 'priority=P9'):
            response = self.client.get(f'/api/manage/tasks?{query}')
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_ad_trend_rejects_invalid_count_without_server_error(self):
        for count in ('abc', '0', '-5', '25'):
            response = self.client.get(f'/api/ad_trend?count={count}')
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')


if __name__ == '__main__':
    unittest.main()

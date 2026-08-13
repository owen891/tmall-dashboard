import io
import os
import sys
import tempfile
import unittest

from openpyxl import Workbook


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def xlsx(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['日期', '商品ID', '商品名称', '支付金额', '退款金额', '商品访客数', '支付买家数', '推广花费'])
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


class ClosedLoopE2ETests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-e2e-')
        from app import create_app
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db')})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def json(self, method, path, **kwargs):
        response = self.client.open(path, method=method, **kwargs)
        body = response.get_json()
        status = response.status_code
        response.close()
        self.assertTrue(body['ok'], body)
        return status, body['data']

    def test_import_to_overview_goal_action_recalculation_and_review(self):
        rows = [
            ['2026-04-01', 'e2e-product', '闭环商品', 100, 10, 20, 2, 10],
            ['2026-04-02', 'e2e-product', '闭环商品', 200, 20, 30, 3, 20],
            ['2026-04-04', 'e2e-product', '闭环商品', 150, 15, 25, 2, 15],
            ['2026-04-05', 'e2e-product', '闭环商品', 250, 25, 35, 4, 25],
        ]
        status, preview = self.json('POST', '/api/imports/preview', data={
            'file': (xlsx(rows), 'closed-loop.xlsx'),
        }, content_type='multipart/form-data')
        self.assertEqual(status, 200)
        status, imported = self.json('POST', '/api/imports', json={'preview_id': preview['id'], 'mapping': preview['mapping']})
        self.assertEqual(status, 201)
        self.assertEqual(imported['inserted_count'], 4)

        _, overview = self.json('GET', '/api/overview?start=2026-04-01&end=2026-04-05')
        self.assertEqual(overview['payment_amount'], 700.0)
        self.assertEqual(overview['net_sales'], 630.0)

        _, goal = self.json('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        _, locked = self.json('POST', '/api/goals/2026/locks', json={
            'version': goal['version'], 'period_type': 'month', 'period_key': '2026-04',
        })
        self.assertTrue(locked['locked'])

        _, action = self.json('POST', '/api/actions', json={
            'product_id': 'e2e-product', 'purpose_type': 'increase_sales',
            'purpose_note': '优化商品主图', 'action_type': 'image_change',
            'action_detail': '替换主图', 'target_metric': 'payment_amount',
            'planned_at': '2026-04-03', 'observer_window_days': 2, 'assigned_to': 'operator',
        })
        for state in ('pending_execution', 'executing', 'observing'):
            _, listed = self.json('GET', '/api/actions?product_id=e2e-product')
            current = next(item for item in listed if item['id'] == action['id'])
            self.json('POST', f"/api/actions/{action['id']}/transition", json={'status': state, 'version': current['version']})
        _, recalculated = self.json('POST', '/api/actions/recalculate')
        self.assertEqual(recalculated['updated_count'], 1)
        self.assertEqual(recalculated['actions'][0]['status'], 'pending_review')
        _, reviewed = self.json('POST', f"/api/actions/{action['id']}/review", json={
            'version': recalculated['actions'][0]['version'], 'effective': True, 'reason': '日均支付金额上升', 'conclusion': '保留新主图',
            'next_action': '扩大素材测试', 'reviewer': 'operator',
        })
        self.assertEqual(reviewed['status'], 'completed')


if __name__ == '__main__':
    unittest.main(verbosity=2)

import json
import os
import tempfile
import unittest


class AuditContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-audit-')
        self.path = os.path.join(self.temp.name, 'dashboard.db')
        from app import create_app

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def _latest(self, entity_type):
        from db import get_db

        with get_db(self.path) as connection:
            row = connection.execute(
                '''SELECT entity_type, entity_id, action, operator, reason, before_value, after_value
                   FROM audit_logs WHERE entity_type = ? ORDER BY id DESC LIMIT 1''',
                (entity_type,),
            ).fetchone()
        return dict(row) if row else None

    def test_settings_write_records_actor_reason_before_and_after(self):
        response = self.client.put('/api/settings', json={
            'shop_name': '演示旗舰店',
            'operator': '店长',
            'reason': '初始化店铺名称',
        })
        self.assertEqual(response.status_code, 200)
        audit = self._latest('settings')
        self.assertEqual(audit['operator'], '店长')
        self.assertEqual(audit['reason'], '初始化店铺名称')
        self.assertEqual(json.loads(audit['before_value'])['shop_name'], '')
        self.assertEqual(json.loads(audit['after_value'])['shop_name'], '演示旗舰店')

    def test_period_review_write_records_actor_reason_before_and_after(self):
        payload = {
            'summary': '经营稳定', 'conclusions': '推广有效',
            'next_actions': '继续观察', 'reviewer': '运营主管',
            'reason': '完成日复盘',
        }
        response = self.client.put('/api/period-reviews/day/2026-08-12', json=payload)
        self.assertEqual(response.status_code, 200)
        audit = self._latest('period_review')
        self.assertEqual(audit['operator'], '运营主管')
        self.assertEqual(audit['reason'], '完成日复盘')
        self.assertIsNone(json.loads(audit['before_value']))
        self.assertEqual(json.loads(audit['after_value'])['summary'], '经营稳定')

    def test_lifecycle_write_records_structured_audit(self):
        from db import get_db

        with get_db(self.path) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('audit-product', '审计商品')")
            for index in range(60):
                connection.execute(
                    "INSERT INTO daily_data (product_id, date, payment_amount) VALUES ('audit-product', date('2026-01-01', ?), 100)",
                    (f'+{index} day',),
                )
            connection.commit()
        current = self.client.get('/api/lifecycle/assessments?product_id=audit-product').get_json()['data'][0]
        response = self.client.put('/api/lifecycle/audit-product', json={
            'version': current['version'], 'manual_stage': 'growth', 'stage_locked': True,
            'operator': '商品经理', 'reason': '人工确认增长期',
        })
        self.assertEqual(response.status_code, 200)
        audit = self._latest('lifecycle')
        self.assertEqual(audit['operator'], '商品经理')
        self.assertEqual(audit['reason'], '人工确认增长期')
        self.assertEqual(json.loads(audit['after_value'])['manual_stage'], 'growth')

    def test_goal_creation_records_structured_audit(self):
        response = self.client.post('/api/goals', json={
            'year': 2027, 'annual_target': 365000, 'version': 0,
            'operator': '店长', 'reason': '制定年度目标',
        })
        self.assertEqual(response.status_code, 201)
        audit = self._latest('goal')
        self.assertEqual(audit['entity_id'], '2027')
        self.assertEqual(audit['operator'], '店长')
        self.assertEqual(audit['reason'], '制定年度目标')
        self.assertEqual(json.loads(audit['after_value'])['annual_target'], 365000.0)


if __name__ == '__main__':
    unittest.main()

import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def workbook_bytes(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


class WriteEvidenceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-write-evidence-')
        self.path = os.path.join(self.temp.name, 'dashboard.db')
        from app import create_app

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_import_preview_and_confirm_expose_quality_and_batch_evidence(self):
        preview_response = self.client.post(
            '/api/imports/preview',
            data={'file': (workbook_bytes(
                ['date', 'product_id', 'payment_amount'],
                [['2026-08-01', 'evidence-product', 100]],
            ), 'evidence.xlsx')},
            content_type='multipart/form-data',
        )
        preview = preview_response.get_json()
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview['availability'], 'missing-fields')
        self.assertEqual(preview['evidence_level'], 'partial')
        self.assertIn('product_visitors', preview['missing_inputs'])
        self.assertEqual(preview['evidence'][0]['source'], 'import_preview')

        full_preview_response = self.client.post(
            '/api/imports/preview',
            data={'file': (workbook_bytes(
                ['date', 'product_id', 'payment_amount', 'product_visitors'],
                [['2026-08-01', 'evidence-product', 100, 20]],
            ), 'evidence-full.xlsx')},
            content_type='multipart/form-data',
        )
        full_preview = full_preview_response.get_json()['data']
        confirmed_response = self.client.post('/api/imports', json={
            'preview_id': full_preview['id'], 'mapping': full_preview['mapping'],
        })
        confirmed = confirmed_response.get_json()
        self.assertEqual(confirmed_response.status_code, 201)
        self.assertEqual(confirmed['evidence_level'], 'full')
        self.assertEqual(confirmed['source_batches'][0]['id'], confirmed['data']['id'])
        self.assertEqual(confirmed['evidence'][0]['source'], 'import_batches')

    def test_goal_write_exposes_versioned_goal_evidence(self):
        response = self.client.post('/api/goals', json={
            'year': 2027, 'annual_target': 365000,
            'operator': '店长', 'reason': '年度规划',
        })
        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(payload['evidence_level'], 'full')
        self.assertEqual({item['source'] for item in payload['evidence']}, {'goal_versions', 'daily_goals'})
        self.assertEqual(payload['freshness']['period'], '2027')

    def test_alert_rule_write_exposes_table_evidence_and_audit(self):
        response = self.client.post('/api/alert-rules', json={
            'name': '低 ROI', 'scope': 'promotion_product', 'metric': 'roi',
            'operator': 'lt', 'threshold': 3, 'level': 'warning',
            'actor': '推广运营', 'reason': '建立推广门槛',
        })
        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(payload['evidence'][0]['source'], 'alert_rules')

        from db import get_db
        with get_db(self.path) as connection:
            row = connection.execute(
                "SELECT operator, reason, after_value FROM audit_logs WHERE entity_type = 'alert_rule' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(row['operator'], '推广运营')
        self.assertEqual(row['reason'], '建立推广门槛')
        self.assertEqual(json.loads(row['after_value'])['metric'], 'roi')

    def test_action_writes_expose_product_action_evidence(self):
        from db import get_db
        with get_db(self.path) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('evidence-action', '证据动作商品')")
            connection.commit()
        response = self.client.post('/api/actions', json={
            'product_id': 'evidence-action', 'purpose_type': 'increase_sales',
            'purpose_note': '验证证据', 'action_type': 'image_change',
            'action_detail': '更换主图', 'target_metric': 'payment_amount',
            'planned_at': '2026-08-01', 'observer_window_days': 2,
            'operator': '商品运营', 'reason': '创建动作',
        })
        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(payload['evidence_level'], 'full')
        self.assertEqual(payload['evidence'][0]['source'], 'product_actions')
        self.assertEqual(payload['evidence'][0]['action'], 'create')
        with get_db(self.path) as connection:
            audit = connection.execute(
                "SELECT operator, reason FROM audit_logs WHERE entity_type = 'action' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(audit['operator'], '商品运营')
        self.assertEqual(audit['reason'], '创建动作')

    def test_insufficient_lifecycle_update_reports_the_data_gate(self):
        from db import get_db
        with get_db(self.path) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('evidence-life', '证据生命周期商品')")
            connection.commit()
        current = self.client.get('/api/lifecycle/assessments?product_id=evidence-life').get_json()['data'][0]
        response = self.client.put('/api/lifecycle/evidence-life', json={
            'version': current['version'], 'manual_stage': 'growth', 'stage_locked': True,
            'operator': '商品运营', 'reason': '人工标记',
        })
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['availability'], 'insufficient-data')
        self.assertIn('product_daily.date_coverage_60d', payload['missing_inputs'])
        self.assertEqual(payload['evidence'][0]['source'], 'lifecycle_profiles')

    def test_period_review_write_exposes_persisted_review_evidence(self):
        response = self.client.put('/api/period-reviews/day/2026-08-01', json={
            'summary': '经营稳定', 'conclusions': '继续观察', 'next_actions': '保持',
            'reviewer': '店长', 'reason': '日复盘',
        })
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['evidence_level'], 'full')
        self.assertEqual(payload['freshness']['period_key'], '2026-08-01')
        self.assertEqual(payload['evidence'][0]['source'], 'period_reviews')


class AlertRuleAuditAtomicityTests(unittest.TestCase):
    """TX-01：告警规则改动与审计记录必须落在同一个事务里。

    原先规则先自行 commit，审计再另开连接提交；审计插入失败时规则已经生效，
    接口却返回 5xx，于是留下「改动已生效但没有审计证据」的状态。这三个测试
    注入审计失败，断言业务写入连同审计一起回滚。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-alert-rule-tx-')
        self.path = os.path.join(self.temp.name, 'dashboard.db')
        from app import create_app

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def rule_payload(self, **overrides):
        payload = {
            'name': '低 ROI', 'scope': 'promotion_product', 'metric': 'roi',
            'operator': 'lt', 'threshold': 3, 'level': 'warning',
            'actor': '推广运营', 'reason': '建立推广门槛',
        }
        payload.update(overrides)
        return payload

    def rule_count(self):
        from db import get_db
        with get_db(self.path) as connection:
            return connection.execute('SELECT COUNT(*) FROM alert_rules').fetchone()[0]

    def create_rule(self):
        response = self.client.post('/api/alert-rules', json=self.rule_payload())
        self.assertEqual(response.status_code, 201)
        return response.get_json()['data']['id']

    def assert_no_audit_rows(self):
        from db import get_db
        with get_db(self.path) as connection:
            rows = connection.execute("SELECT COUNT(*) FROM audit_logs WHERE entity_type = 'alert_rule'").fetchone()[0]
        self.assertEqual(rows, 0)

    def test_failed_audit_rolls_back_rule_creation(self):
        # 库里有迁移期播种的默认规则，所以断言增量而不是绝对条数。
        before = self.rule_count()
        with patch('services.alert_rules_service.AuditRepo.record', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/alert-rules', json=self.rule_payload())
        self.assertEqual(self.rule_count(), before)
        self.assert_no_audit_rows()

    def test_failed_audit_rolls_back_rule_update(self):
        rule_id = self.create_rule()
        with patch('services.alert_rules_service.AuditRepo.record', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.client.put(f'/api/alert-rules/{rule_id}', json=self.rule_payload(
                    name='改过的名字', threshold=9, reason='更新门槛',
                ))
        from db import get_db
        with get_db(self.path) as connection:
            row = connection.execute('SELECT name, threshold FROM alert_rules WHERE id = ?', (rule_id,)).fetchone()
        self.assertEqual(row['name'], '低 ROI')
        self.assertEqual(row['threshold'], 3)

    def test_failed_audit_rolls_back_rule_deletion(self):
        rule_id = self.create_rule()
        before = self.rule_count()
        with patch('services.alert_rules_service.AuditRepo.record', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.client.delete(f'/api/alert-rules/{rule_id}?reason=删除门槛')
        self.assertEqual(self.rule_count(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)

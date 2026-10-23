import json
import os
import tempfile
import unittest


class FormalMutationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-formal-mutations-')
        from app import create_app
        from db import get_db

        self.path = os.path.join(self.temp.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()
        with get_db(self.path) as connection:
            connection.executemany(
                'INSERT INTO products (product_id, title, tier, style) VALUES (?, ?, ?, ?)',
                [
                    ('formal-001', '正式接口商品一', 'A', '简约'),
                    ('formal-002', '正式接口商品二', 'B', '复古'),
                ],
            )
            connection.commit()

    def tearDown(self):
        self.temp.cleanup()

    def test_product_metadata_update_returns_evidence_and_audit(self):
        response = self.client.put('/api/products/formal-001/metadata', json={
            'field': 'tier', 'value': 'S', 'operator': '商品运营', 'reason': '季度分层调整',
        })
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['product_id'], 'formal-001')
        self.assertEqual(payload['data']['field'], 'tier')
        self.assertEqual(payload['data']['value'], 'S')
        self.assertEqual(payload['evidence_level'], 'full')
        self.assertEqual(payload['evidence'][0]['source'], 'products')

        from db import get_db
        with get_db(self.path) as connection:
            audit = connection.execute(
                "SELECT operator, reason, before_value, after_value FROM audit_logs "
                "WHERE entity_type = 'product' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(audit['operator'], '商品运营')
        self.assertEqual(audit['reason'], '季度分层调整')
        self.assertEqual(json.loads(audit['before_value'])['tier'], 'A')
        self.assertEqual(json.loads(audit['after_value'])['tier'], 'S')

    def test_product_batch_mutations_return_counts_and_evidence(self):
        update = self.client.post('/api/products/batch-update', json={
            'product_ids': ['formal-001', 'formal-002'],
            'field': 'style', 'value': '自然', 'operator': '商品运营', 'reason': '统一风格',
        })
        update_payload = update.get_json()
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update_payload['data']['updated_count'], 2)
        self.assertEqual(update_payload['evidence'][0]['source'], 'products')

        tags = self.client.post('/api/products/batch-tags', json={
            'product_ids': ['formal-001', 'formal-002'], 'tag': '重点观察',
            'operator': '商品运营', 'reason': '建立观察组',
        })
        tags_payload = tags.get_json()
        self.assertEqual(tags.status_code, 200)
        self.assertEqual(tags_payload['data']['affected_count'], 2)
        self.assertEqual(tags_payload['evidence'][0]['source'], 'product_tags')

        removed = self.client.delete('/api/products/batch-tags', json={
            'product_ids': ['formal-001'], 'tag': '重点观察',
            'operator': '商品运营', 'reason': '移出观察组',
        })
        removed_payload = removed.get_json()
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed_payload['data']['deleted_count'], 1)
        self.assertEqual(removed_payload['evidence'][0]['source'], 'product_tags')

    def test_product_star_toggle_returns_structured_state(self):
        response = self.client.post('/api/products/formal-001/star', json={
            'starred': 1, 'operator': '商品运营', 'reason': '加入重点清单',
        })
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['data'], {'product_id': 'formal-001', 'starred': 1})
        self.assertEqual(payload['evidence'][0]['source'], 'products')

    def test_product_star_rejects_malformed_boolean(self):
        response = self.client.post('/api/products/formal-001/star', json={'starred': 'maybe'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_metadata_tier_update_marks_source_manual(self):
        """人工改档位必须同时写 tier_source='manual'。

        否则脚本看到「有档位、来源空」，一边判成人工锁定永久跳过，
        一边又当空值覆盖——两个算法对同一个空值的语义相反。
        """
        response = self.client.put('/api/products/formal-001/metadata', json={
            'field': 'tier', 'value': '利润款', 'operator': '商品运营', 'reason': '人工分层',
        })
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['data']['tier_source'], 'manual')

        from db import get_db
        with get_db(self.path) as connection:
            row = connection.execute(
                'SELECT tier, tier_source FROM products WHERE product_id = ?', ('formal-001',)
            ).fetchone()
            audit = connection.execute(
                "SELECT before_value, after_value FROM audit_logs "
                "WHERE entity_type = 'product' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(row['tier'], '利润款')
        self.assertEqual(row['tier_source'], 'manual')
        self.assertEqual(json.loads(audit['after_value'])['tier_source'], 'manual')

    def test_metadata_style_update_keeps_existing_tier_source(self):
        """改非档位字段不能动 tier_source，否则会把算法自填的行误锁成人工。"""
        from db import get_db
        with get_db(self.path) as connection:
            connection.execute(
                "UPDATE products SET tier = '引流款', tier_source = 'five-dim-auto' "
                "WHERE product_id = ?", ('formal-001',)
            )
            connection.commit()

        response = self.client.put('/api/products/formal-001/metadata', json={
            'field': 'style', 'value': '日式', 'operator': '商品运营', 'reason': '风格修正',
        })
        self.assertEqual(response.status_code, 200)

        with get_db(self.path) as connection:
            row = connection.execute(
                'SELECT tier, tier_source FROM products WHERE product_id = ?', ('formal-001',)
            ).fetchone()
        self.assertEqual(row['tier_source'], 'five-dim-auto')

    def test_batch_tier_update_marks_source_manual(self):
        response = self.client.post('/api/products/batch-update', json={
            'product_ids': ['formal-001', 'formal-002'],
            'field': 'tier', 'value': '动销款', 'operator': '商品运营', 'reason': '批量分层',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['updated_count'], 2)

        from db import get_db
        with get_db(self.path) as connection:
            rows = connection.execute(
                'SELECT tier, tier_source FROM products '
                'WHERE product_id IN (?, ?) ORDER BY product_id', ('formal-001', 'formal-002')
            ).fetchall()
        for row in rows:
            self.assertEqual(row['tier'], '动销款')
            self.assertEqual(row['tier_source'], 'manual')

    def test_batch_style_update_keeps_tier_source(self):
        from db import get_db
        with get_db(self.path) as connection:
            connection.execute(
                "UPDATE products SET tier = '利润款', tier_source = 'matrix-auto' "
                "WHERE product_id = ?", ('formal-001',)
            )
            connection.commit()

        response = self.client.post('/api/products/batch-update', json={
            'product_ids': ['formal-001'], 'field': 'style', 'value': '极简',
            'operator': '商品运营', 'reason': '统一风格',
        })
        self.assertEqual(response.status_code, 200)

        with get_db(self.path) as connection:
            row = connection.execute(
                'SELECT tier_source FROM products WHERE product_id = ?', ('formal-001',)
            ).fetchone()
        self.assertEqual(row['tier_source'], 'matrix-auto')

    def test_legacy_field_tier_update_marks_source_manual(self):
        response = self.client.put('/api/products/formal-002/field', json={
            'field': 'tier', 'value': '潜力款', 'operator': '商品运营', 'reason': '人工分层',
        })
        self.assertEqual(response.status_code, 200)
        # 这个旧接口返回扁平结构（success/field/value/tier_source），没有 data 包装。
        self.assertEqual(response.get_json()['tier_source'], 'manual')

        from db import get_db
        with get_db(self.path) as connection:
            row = connection.execute(
                'SELECT tier, tier_source FROM products WHERE product_id = ?', ('formal-002',)
            ).fetchone()
        self.assertEqual(row['tier'], '潜力款')
        self.assertEqual(row['tier_source'], 'manual')

    def test_overview_event_mutations_return_structured_evidence(self):
        created = self.client.post('/api/overview/events', json={
            'event_date': '2026-08-10', 'title': '活动开始',
            'description': '验证正式事件接口', 'color': '#2563EB', 'chart_type': 'sales',
            'operator': '店长', 'reason': '记录经营背景',
        })
        created_payload = created.get_json()
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created_payload['data']['id'])
        self.assertEqual(created_payload['evidence'][0]['source'], 'chart_events')

        event_id = created_payload['data']['id']
        listed = self.client.get('/api/overview/events?chart_type=sales')
        listed_payload = listed.get_json()
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed_payload['data'][0]['id'], event_id)
        self.assertEqual(listed_payload['evidence'][0]['source'], 'chart_events')

        deleted = self.client.delete(f'/api/overview/events/{event_id}', json={
            'operator': '店长', 'reason': '移除过期背景',
        })
        deleted_payload = deleted.get_json()
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted_payload['data']['deleted_count'], 1)
        self.assertEqual(deleted_payload['evidence'][0]['source'], 'chart_events')


if __name__ == '__main__':
    unittest.main()

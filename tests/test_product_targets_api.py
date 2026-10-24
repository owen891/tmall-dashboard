"""商品目标 API 契约（product_targets，2026-10-24 商品列表参考 BI 重构补全）。

口径要点：
- period 支持 YYYY-MM（月窗口）与 YYYY-MM-DD（日窗口），其余 422；
- 达成值按同窗口从 daily_data 聚合（先聚合再相比），店铺维度沿用请求作用域；
- upsert 以 (product_id, period) 为键；PUT 需至少一个目标值；
- 写操作走与目录变更相同的 guard + AuditRepo 审计。
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class ProductTargetsApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tmall-product-targets-')
        from app import create_app
        from db import get_db
        self.db = os.path.join(self.tmp.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.db})
        self.client = self.app.test_client()
        with get_db(self.db) as c:
            c.execute("INSERT INTO products (product_id, title, status) VALUES ('p-1', '目标商品', 'active')")
            c.executemany(
                "INSERT INTO daily_data (shop_id, product_id, date, payment_amount, ad_spend, net_sales) "
                "VALUES ('default', 'p-1', ?, ?, ?, ?)",
                [
                    ('2026-10-01', 1000, 100, 900),
                    ('2026-10-02', 1200, 200, 1000),
                    ('2026-09-15', 500, 50, 450),
                ],
            )
            c.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def test_put_then_get_with_month_window_achievement(self):
        put = self.client.put('/api/products/p-1/target', json={
            'period': '2026-10', 'target_gsv': 2200, 'target_ad_ratio': 0.2,
            'operator': '测试', 'reason': '月目标',
        })
        self.assertEqual(put.status_code, 200)
        listing = self.client.get('/api/products/p-1/targets').get_json()
        rows = listing['data']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['period'], '2026-10')
        # 月窗口 10-01~10-02：achieved_gsv=2200 → 达成率 100%
        self.assertAlmostEqual(row['achieved_gsv'], 2200.0)
        self.assertAlmostEqual(row['achievement_rate'], 1.0)
        # 费比 = 300 / 1900（先聚合再相除）
        self.assertAlmostEqual(row['achieved_expense_ratio'], 300 / 1900, places=6)
        # 9 月事实不计入 10 月窗口
        self.assertNotAlmostEqual(row['achieved_gsv'], 2700.0)

    def test_put_accepts_single_day_period(self):
        put = self.client.put('/api/products/p-1/target', json={'period': '2026-10-01', 'target_gsv': 1000, 'operator': '测试'})
        self.assertEqual(put.status_code, 200)
        listing = self.client.get('/api/products/p-1/targets').get_json()
        self.assertAlmostEqual(listing['data'][0]['achieved_gsv'], 1000.0)

    def test_put_rejects_bad_period_and_empty_targets(self):
        for payload in (
            {'period': '2026/10', 'target_gsv': 1},
            {'period': '10月', 'target_gsv': 1},
            {'period': '2026-10'},
            {'period': '2026-10', 'target_gsv': -5},
            {'period': '2026-10', 'target_gsv': 'abc'},
        ):
            resp = self.client.put('/api/products/p-1/target', json=payload)
            self.assertEqual(resp.status_code, 422, payload)

    def test_put_upserts_by_period_without_duplicates(self):
        for gsv in (1000, 2500):
            resp = self.client.put('/api/products/p-1/target', json={'period': '2026-10', 'target_gsv': gsv, 'operator': '测试'})
            self.assertEqual(resp.status_code, 200)
        listing = self.client.get('/api/products/p-1/targets').get_json()
        self.assertEqual(len(listing['data']), 1)
        self.assertAlmostEqual(listing['data'][0]['target_gsv'], 2500.0)

    def test_delete_removes_only_matching_period(self):
        self.client.put('/api/products/p-1/target', json={'period': '2026-10', 'target_gsv': 2200, 'operator': '测试'})
        self.client.put('/api/products/p-1/target', json={'period': '2026-11', 'target_gsv': 3000, 'operator': '测试'})
        deleted = self.client.delete('/api/products/p-1/target', json={'period': '2026-10', 'operator': '测试'})
        self.assertEqual(deleted.status_code, 200)
        listing = self.client.get('/api/products/p-1/targets').get_json()
        self.assertEqual([row['period'] for row in listing['data']], ['2026-11'])

    def test_delete_missing_period_is_404(self):
        resp = self.client.delete('/api/products/p-1/target', json={'period': '2025-01', 'operator': '测试'})
        self.assertEqual(resp.status_code, 404)

    def test_targets_for_unknown_product_is_404(self):
        resp = self.client.get('/api/products/ghost/targets')
        self.assertEqual(resp.status_code, 404)

    def test_audit_trail_records_target_changes(self):
        from db import get_db
        self.client.put('/api/products/p-1/target', json={'period': '2026-10', 'target_gsv': 2200, 'operator': '审计员', 'reason': '月度对齐'})
        with get_db(self.db) as c:
            rows = c.execute(
                "SELECT entity_type, action, operator FROM audit_logs WHERE entity_type = 'product_target' ORDER BY id DESC LIMIT 1"
            ).fetchall()
        self.assertTrue(rows, '目标写入必须留审计')
        self.assertEqual(rows[0]['action'], 'create')


if __name__ == '__main__':
    unittest.main()

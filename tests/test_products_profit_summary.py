"""商品列表接口的利润字段、区间筛选与汇总行契约（2026-10-24 参考边界 BI 重构）。

口径要点：
- operating_profit / product_cost 为源列直取，真实 0 是盈亏平衡真值，不得 NULLIF；
- profit_rate 必须"先聚合再相除"（daily 区间 SUM 后相除，禁止逐日平均）；
- 无事实行的商品利润保持 NULL（前端渲染 `--`），不得伪造 0；
- min_/max_ 区间筛选只接受白名单字段，非法值静默忽略（不可 500）；
- summary 聚合尊重全部筛选条件（含区间）但不含分页。
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class ProductsProfitSummaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tmall-products-profit-')
        from app import create_app
        from db import get_db
        self.db = os.path.join(self.tmp.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.db})
        self.client = self.app.test_client()
        with get_db(self.db) as c:
            c.executemany('INSERT INTO products (product_id,title,status) VALUES (?,?,?)', [
                ('p-profit', 'Profitable', 'active'),
                ('p-nofact', 'NoFact', 'active'),
            ])
            # 两天日事实：p-profit 逐日利润率 200/900 与 -50/700，SUM 口径 = 150/1600
            c.executemany(
                '''INSERT INTO daily_data (shop_id, product_id, date, payment_amount, refund_amount,
                   net_sales, ad_spend, operating_profit, product_cost, ipv, buyers)
                   VALUES ('default', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                [
                    ('p-profit', '2026-04-01', 1000, 100, 900, 90, 200, 300, 100, 10),
                    ('p-profit', '2026-04-02', 1000, 300, 700, 210, -50, 400, 100, 10),
                ],
            )
            c.execute(
                '''INSERT INTO monthly_data (product_id, month, payment_amount, refund_amount,
                   net_sales, ad_spend, operating_profit, product_cost)
                   VALUES ('p-profit', '2026-04', 2400, 100, 2000, 300, 500, 800)'''
            )
            c.execute(
                '''INSERT INTO weekly_data (product_id, week_start, payment_amount, refund_amount,
                   net_sales, ad_spend) VALUES ('p-profit', '2026-03-30', 500, 20, 480, 60)'''
            )
            c.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def test_monthly_exposes_profit_columns_with_ratio(self):
        payload = self.client.get('/api/products?dim=monthly&period=2026-04').get_json()
        self.assertTrue(payload['ok'])
        row = next(r for r in payload['data']['rows'] if r['product_id'] == 'p-profit')
        self.assertEqual(row['operating_profit'], 500)
        self.assertEqual(row['product_cost'], 800)
        self.assertAlmostEqual(row['profit_rate'], 0.25, places=6)

    def test_daily_range_profit_rate_is_sum_then_divide(self):
        payload = self.client.get(
            '/api/products?dim=daily&start=2026-04-01&end=2026-04-02&sort=operating_profit'
        ).get_json()
        row = next(r for r in payload['data']['rows'] if r['product_id'] == 'p-profit')
        self.assertEqual(row['operating_profit'], 150)
        self.assertAlmostEqual(row['profit_rate'], 150 / 1600, places=6)
        # 逐日平均的错误口径是 (200/900 + -50/700) / 2 ≈ 0.0758，必须不相等
        self.assertNotAlmostEqual(row['profit_rate'], (200 / 900 - 50 / 700) / 2, places=3)
        self.assertAlmostEqual(row['expense_ratio'], 300 / 1600, places=6)

    def test_rows_without_fact_keep_profit_null(self):
        payload = self.client.get('/api/products?dim=monthly&period=2026-04').get_json()
        row = next(r for r in payload['data']['rows'] if r['product_id'] == 'p-nofact')
        self.assertIsNone(row['operating_profit'])
        self.assertIsNone(row['product_cost'])
        self.assertIsNone(row['profit_rate'])

    def test_weekly_profit_columns_stay_null(self):
        payload = self.client.get('/api/products?dim=weekly&period=2026-03-30').get_json()
        self.assertTrue(payload['ok'])
        row = next(r for r in payload['data']['rows'] if r['product_id'] == 'p-profit')
        self.assertIsNone(row['operating_profit'])
        self.assertIsNone(row['profit_rate'])

    def test_range_filters_narrow_and_respect_null(self):
        # min_operating_profit=0：p-profit 命中；p-nofact 利润 NULL 不落在区间内
        payload = self.client.get(
            '/api/products?dim=monthly&period=2026-04&min_operating_profit=0'
        ).get_json()
        self.assertEqual(payload['data']['total'], 1)
        self.assertEqual(payload['data']['rows'][0]['product_id'], 'p-profit')
        # max_refund_rate=0.05：p-profit 退款率 100/2400≈0.042 命中
        payload = self.client.get(
            '/api/products?dim=monthly&period=2026-04&max_refund_rate=0.05'
        ).get_json()
        self.assertEqual(payload['data']['total'], 1)

    def test_range_filters_ignore_unknown_fields_and_bad_values(self):
        # 白名单外字段（title 可排序但不在区间白名单）与非法数值都必须被静默忽略
        for qs in ('min_title=1', 'min_payment_amount=abc',
                   'min_payment_amount=1) OR 1=1--', 'max_operating_profit='):
            payload = self.client.get(f'/api/products?dim=monthly&period=2026-04&{qs}').get_json()
            self.assertTrue(payload['ok'], qs)
            self.assertEqual(payload['data']['total'], 2, qs)

    def test_summary_aggregates_filtered_set_without_pagination(self):
        payload = self.client.get(
            '/api/products?dim=daily&start=2026-04-01&end=2026-04-02&limit=1&min_operating_profit=0'
        ).get_json()
        summary = payload['data']['summary']
        # 分页 limit=1 只影响 rows；summary 仍覆盖全部命中行
        self.assertEqual(summary['rows_count'], 1)
        self.assertEqual(len(payload['data']['rows']), 1)
        self.assertEqual(summary['payment_amount'], 2000)
        self.assertEqual(summary['net_sales'], 1600)
        self.assertEqual(summary['operating_profit'], 150)
        self.assertAlmostEqual(summary['profit_rate'], 150 / 1600, places=6)
        self.assertAlmostEqual(summary['expense_ratio'], 300 / 1600, places=6)
        self.assertAlmostEqual(summary['refund_rate'], 400 / 2000, places=6)
        self.assertAlmostEqual(summary['conversion'], 20 / 200, places=6)

    def test_summary_includes_null_fact_rows_as_zero_not_null(self):
        payload = self.client.get('/api/products?dim=monthly&period=2026-04').get_json()
        summary = payload['data']['summary']
        self.assertEqual(summary['rows_count'], 2)
        self.assertEqual(summary['payment_amount'], 2400)
        # SUM(operating_profit) 跳过 NULL：p-nofact 不贡献也不清零
        self.assertEqual(summary['operating_profit'], 500)
        self.assertAlmostEqual(summary['profit_rate'], 500 / 2000, places=6)

    def test_daily_changes_carry_profit_metrics_against_previous_window(self):
        payload = self.client.get('/api/products?dim=daily&start=2026-04-02&end=2026-04-02').get_json()
        row = payload['data']['rows'][0]
        self.assertEqual(row['product_id'], 'p-profit')
        changes = row['changes']
        self.assertAlmostEqual(changes['payment_amount'], 0.0, places=6)
        # 上一窗口（4/1）：利润率 200/900；本期（4/2）：-50/700
        self.assertAlmostEqual(changes['profit_rate'], ((-50 / 700) - (200 / 900)) / (200 / 900) * 100, places=1)
        self.assertAlmostEqual(changes['operating_profit'], ((-50) - 200) / 200 * 100, places=1)
        self.assertAlmostEqual(changes['expense_ratio'], ((210 / 700) - (90 / 900)) / (90 / 900) * 100, places=1)


if __name__ == '__main__':
    unittest.main()

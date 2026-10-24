"""推广转化回填（promotion_item_metrics_enrichment）的契约测试。

背景：商品列表「推广与付费」分组的展现量/点击量/点击率/点击单价/千次展现花费/
直接与归因成交/加购次数/加购成本/新买家/新买家占比/点击转化率，原先取自
`paid_detail`，而该表实测 0 行，所以这些列长期是 `--`。真实数据在
`promotion_daily_facts` 的 grain='product' + channel='全部' 汇总里。

这里锁定几条容易退化的契约：
1. 只取 grain='product' + channel='全部'，其它粒度/渠道不得混入（否则重复计数）。
2. 负 product_id（占位/未识别）必须排除。
3. 只填 NULL，主源已有值不覆盖。
4. 归因成交不含间接成交 → indirect_gmv 保持 None，不伪造成 0。
5. 单位成本（cart_cost）由 花费/加购次数 推导，不能按行求和。
6. 没有推广行的商品不出现，对应字段保持 NULL（"没投" ≠ "投了为 0"）。
"""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.promotion_item_metrics_enrichment import (  # noqa: E402
    enrich_rows,
    fetch_promotion_metrics,
)

PROMOTION_DDL = '''
CREATE TABLE promotion_daily_facts (
    shop_id TEXT,
    date TEXT,
    channel TEXT,
    campaign_id TEXT,
    unit_id TEXT,
    product_id TEXT,
    ad_spend REAL,
    attributed_payment_amount REAL,
    impressions REAL,
    clicks REAL,
    payment_buyers REAL,
    direct_payment_amount REAL,
    indirect_payment_amount REAL,
    source_batch_id TEXT,
    grain TEXT,
    campaign_name TEXT,
    cart_adds REAL,
    cart_cost REAL,
    new_buyers REAL
)
'''


def _insert(conn, product_id, day, *, channel='全部', grain='product',
            ad_spend=100.0, attr=500.0, direct=300.0, indirect=None,
            impressions=10000.0, clicks=500.0, buyers=20.0,
            cart_adds=50.0, new_buyers=10.0):
    conn.execute(
        '''INSERT INTO promotion_daily_facts
           (shop_id, date, channel, campaign_id, unit_id, product_id, ad_spend,
            attributed_payment_amount, impressions, clicks, payment_buyers,
            direct_payment_amount, indirect_payment_amount, source_batch_id, grain,
            campaign_name, cart_adds, cart_cost, new_buyers)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        ('shop-1', day, channel, 'c1', 'u1', product_id, ad_spend, attr,
         impressions, clicks, buyers, direct, indirect, 'batch-1', grain,
         '计划1', cart_adds, None, new_buyers),
    )


class PromotionItemMetricsTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(PROMOTION_DDL)

    def tearDown(self):
        self.conn.close()

    def test_only_product_grain_and_all_channel_are_used(self):
        # 同一商品：正确的 product/全部 行 + 会被重复计数的 campaign 行
        # + 会被重复计数的具名渠道行。
        _insert(self.conn, 'p1', '2026-10-12', impressions=10000.0, clicks=500.0)
        _insert(self.conn, 'p1', '2026-10-12', grain='campaign', impressions=99999.0, clicks=9999.0)
        _insert(self.conn, 'p1', '2026-10-12', channel='关键词推广', impressions=88888.0, clicks=8888.0)
        metrics = fetch_promotion_metrics(self.conn, ['p1'], '2026-10-12', '2026-10-18')
        self.assertIn('p1', metrics)
        self.assertEqual(metrics['p1']['impressions'], 10000.0)
        self.assertEqual(metrics['p1']['clicks'], 500.0)

    def test_negative_product_ids_are_excluded(self):
        _insert(self.conn, '-998', '2026-10-12')
        _insert(self.conn, '-1', '2026-10-12')
        metrics = fetch_promotion_metrics(self.conn, ['-998', '-1'], '2026-10-12', '2026-10-18')
        self.assertEqual(metrics, {})

    def test_date_range_is_respected(self):
        _insert(self.conn, 'p1', '2026-10-11')  # 区间外
        _insert(self.conn, 'p1', '2026-10-12')
        metrics = fetch_promotion_metrics(self.conn, ['p1'], '2026-10-12', '2026-10-18')
        self.assertEqual(metrics['p1']['fact_rows'], 1)

    def test_derived_metrics(self):
        _insert(self.conn, 'p1', '2026-10-12', ad_spend=100.0, impressions=10000.0,
                clicks=500.0, buyers=20.0, cart_adds=50.0, new_buyers=10.0)
        m = fetch_promotion_metrics(self.conn, ['p1'], '2026-10-12', '2026-10-18')['p1']
        self.assertAlmostEqual(m['ctr'], 0.05)
        self.assertAlmostEqual(m['cpc'], 0.2)
        self.assertAlmostEqual(m['cpm'], 10.0)
        # 单位成本：花费/加购次数，不是按行求和。
        self.assertAlmostEqual(m['cart_cost'], 2.0)
        self.assertAlmostEqual(m['new_buyer_ratio'], 0.5)
        self.assertAlmostEqual(m['click_conversion'], 0.04)

    def test_indirect_gmv_stays_null_when_source_is_empty(self):
        _insert(self.conn, 'p1', '2026-10-12', indirect=None)
        m = fetch_promotion_metrics(self.conn, ['p1'], '2026-10-12', '2026-10-18')['p1']
        self.assertIsNone(m['indirect_gmv'])

    def test_enrich_fills_only_missing_and_keeps_primary_values(self):
        _insert(self.conn, 'p1', '2026-10-12', impressions=10000.0, clicks=500.0)
        rows = [
            {'product_id': 'p1', 'impressions': None, 'clicks': None, 'ctr': None},
            {'product_id': 'p2', 'impressions': None, 'clicks': None, 'ctr': None},
        ]
        result = enrich_rows(self.conn, rows, '2026-10-12', '2026-10-18')
        self.assertTrue(result['applied'])
        self.assertEqual(rows[0]['impressions'], 10000.0)
        self.assertEqual(rows[0]['clicks'], 500.0)
        # 没有推广行的商品保持 NULL。
        self.assertIsNone(rows[1]['impressions'])

    def test_primary_value_is_not_overwritten(self):
        _insert(self.conn, 'p1', '2026-10-12', impressions=10000.0)
        rows = [{'product_id': 'p1', 'impressions': 777.0}]
        enrich_rows(self.conn, rows, '2026-10-12', '2026-10-18')
        self.assertEqual(rows[0]['impressions'], 777.0)

    def test_row_without_field_is_not_given_new_key(self):
        """导出接口允许只挑几列，凭空加键会把表头和数据列数撑错位。"""
        _insert(self.conn, 'p1', '2026-10-12')
        rows = [{'product_id': 'p1'}]
        enrich_rows(self.conn, rows, '2026-10-12', '2026-10-18')
        self.assertEqual(set(rows[0].keys()), {'product_id'})

    def test_missing_source_table_is_tolerated(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        try:
            metrics = fetch_promotion_metrics(conn, ['p1'], '2026-10-12', '2026-10-18')
            self.assertEqual(metrics, {})
            result = enrich_rows(conn, [{'product_id': 'p1', 'impressions': None}],
                                 '2026-10-12', '2026-10-18')
            self.assertFalse(result['applied'])
        finally:
            conn.close()

    def test_zero_impressions_does_not_produce_division_errors(self):
        _insert(self.conn, 'p1', '2026-10-12', impressions=0.0, clicks=0.0,
                ad_spend=0.0, cart_adds=0.0, buyers=0.0, new_buyers=0.0)
        m = fetch_promotion_metrics(self.conn, ['p1'], '2026-10-12', '2026-10-18')['p1']
        self.assertIsNone(m['ctr'])
        self.assertIsNone(m['cpc'])
        self.assertIsNone(m['cpm'])
        self.assertIsNone(m['cart_cost'])
        self.assertIsNone(m['click_conversion'])


if __name__ == '__main__':
    unittest.main()

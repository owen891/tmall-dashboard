"""利润结构（profit_structure_service）单元测试。

口径：BI 派米恒等公式 利润 = 净销 − 销售费用 − 自定义费用 − 货本 − 发货 − 其他；
费用 NULL 不 COALESCE 成 0；profit=0 且费用全空 = 未回填哨兵。
"""
import os
import sys
import sqlite3
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.profit_structure_service import profit_structure

SCHEMA = '''
CREATE TABLE products (
    product_id TEXT PRIMARY KEY, title TEXT, category TEXT,
    shop_label TEXT, tier TEXT, status TEXT DEFAULT 'active'
);
CREATE TABLE daily_data (
    shop_id TEXT NOT NULL DEFAULT 'default',
    product_id TEXT, date TEXT, payment_amount REAL, net_sales REAL,
    sales_cost REAL, custom_cost REAL, product_cost REAL,
    logistics_cost REAL, other_cost REAL, platform_fee REAL,
    gift_cost REAL, ad_spend REAL, operating_profit REAL
);
'''


def _insert(conn, rows):
    # shop_id 走 DEFAULT，与请求 scope（get_shop_id() 默认 'default'）一致。
    conn.executemany(
        '''INSERT INTO daily_data (product_id, date, payment_amount, net_sales,
               sales_cost, custom_cost, product_cost, logistics_cost, other_cost,
               platform_fee, gift_cost, ad_spend, operating_profit)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        rows,
    )


class ProfitStructureTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute("INSERT INTO products (product_id, title) VALUES ('A', '商品A')")

    def tearDown(self):
        self.conn.close()

    def test_identity_holds_on_complete_rows(self):
        """费用齐全时恒等成立：净销−Σ费用 = 利润。"""
        _insert(self.conn, [
            # 净销 900 − (100+200+300+50+50) = 200 = profit
            ('A', '2026-08-01', 1000, 900, 100, 200, 300, 50, 50, 80, 10, 150, 200),
            ('A', '2026-08-02', 500, 450, 50, 100, 150, 25, 25, 40, 5, 75, 100),
        ])
        result = profit_structure(self.conn, '2026-08-01', '2026-08-31')
        self.assertTrue(result['available'])
        self.assertTrue(result['identity']['ok'])
        self.assertAlmostEqual(result['identity']['gap'], 0, places=2)
        profit_row = next(r for r in result['rows'] if r['key'] == 'operating_profit')
        self.assertAlmostEqual(profit_row_value(profit_row), 300.0)
        # 自定义费用占比：300/1350（两天 custom 200+100）
        custom = next(r for r in result['rows'] if r['key'] == 'custom_cost')
        self.assertAlmostEqual(custom['share_of_net'], 300 / 1350, places=4)

    def test_sentinel_rows_excluded_and_flagged(self):
        """补采哨兵：profit=0 且费用全 NULL 的行计入 sentinel_rows，不参与恒等。"""
        _insert(self.conn, [
            ('A', '2026-09-01', 1000, 900, 100, 200, 300, 50, 50, 80, 10, 150, 400),
            # 哨兵行：payment!=0、profit=0、费用全 NULL
            ('A', '2026-09-18', 2000, 1800, None, None, None, None, None, None, None, None, 0),
        ])
        result = profit_structure(self.conn, '2026-09-01', '2026-09-30')
        self.assertEqual(result['sentinel_rows'], 1)
        # 恒等只对费用齐全行成立（哨兵行 net_sales 仍进 SUM → identity fail，但 gap 有说明）
        self.assertFalse(result['identity']['ok'])
        self.assertIn('未回填', result['identity']['note'])

    def test_null_cost_not_coerced_to_zero(self):
        """单桶费用 NULL → 该桶 value=None（缺失），其他桶正常。"""
        _insert(self.conn, [
            ('A', '2026-08-01', 1000, 900, 100, None, 300, 50, 50, 80, 10, 150, 450),
        ])
        result = profit_structure(self.conn, '2026-08-01', '2026-08-31')
        custom = next(r for r in result['rows'] if r['key'] == 'custom_cost')
        self.assertIsNone(custom['value'])
        self.assertIsNone(custom['share_of_net'])
        other = next(r for r in result['rows'] if r['key'] == 'other_cost')
        self.assertEqual(other['value'], 50)

    def test_compare_period_change_rate(self):
        """对比期环比：费用率逐桶 change_rate（第 4/5 参数是 compare_start/end）。"""
        _insert(self.conn, [
            ('A', '2026-08-01', 1000, 900, 100, 200, 300, 50, 50, 80, 10, 150, 200),
            ('A', '2026-07-01', 500, 450, 50, 100, 150, 25, 25, 40, 5, 75, 100),
        ])
        result = profit_structure(self.conn, '2026-08-01', '2026-08-31',
                                  None, '2026-07-01', '2026-07-31')
        self.assertTrue(result['compare'])
        sales_row = next(r for r in result['rows'] if r['key'] == 'sales_cost')
        self.assertEqual(sales_row['prev_value'], 50.0)  # 7月窗口只有 07-01 一行
        self.assertAlmostEqual(sales_row['change_rate'], 1.0, places=3)  # 100/50 - 1

    def test_empty_window_reports_missing(self):
        result = profit_structure(self.conn, '2027-01-01', '2027-01-31')
        self.assertFalse(result['available'])
        self.assertIn('daily_data', result['missing_inputs'])


def profit_row_value(row):
    return row['value']


if __name__ == '__main__':
    unittest.main()

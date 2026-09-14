import unittest

from scripts.import_paimi_bi_daily import date_from_file, observation_from_payload
from pathlib import Path


class PaimiBiDailyImportTests(unittest.TestCase):
    def test_filename_date_is_used_as_the_daily_fact_date(self):
        self.assertEqual(
            date_from_file(Path('商品总览_天猫_Primeet派米旗舰店_2026-08-21.xlsx')),
            '2026-08-21',
        )

    def test_standard_daily_observation_uses_bi_columns(self):
        row = observation_from_payload('1001', '2026-08-21', {
            '支付金额(支付)': '1,234.50',
            '普通单退款金额': 12.5,
            '净销售额(支付)': 1222,
            '销售件数(支付)': 15,
            '访客数': 100,
            '浏览量': 200,
            '支付转化率': '12.5%',
            '加购率': '20%',
            '支付人数': 13,
            '真实客单价': 94.96,
            '推广花费(账单)': 50,
            '推广ROI(账单)': 24.69,
        })
        self.assertEqual(row['product_id'], '1001')
        self.assertEqual(row['date'], '2026-08-21')
        self.assertEqual(row['payment_amount'], 1234.5)
        self.assertEqual(row['successful_refund_amount'], 12.5)
        self.assertEqual(row['net_sales'], 1222.0)
        self.assertEqual(row['product_visitors'], 100.0)
        self.assertEqual(row['payment_conversion'], 0.125)
        self.assertEqual(row['favorite_cart_rate'], 0.2)
        self.assertEqual(row['ad_roi'], 24.69)


if __name__ == '__main__':
    unittest.main()

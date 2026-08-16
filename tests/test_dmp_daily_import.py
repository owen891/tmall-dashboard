import os
import sqlite3
import tempfile
import unittest

import pandas as pd


class DmpDailyImportTests(unittest.TestCase):
    def test_daily_dmp_fields_are_imported_and_exposed(self):
        from app import create_app
        from db import init_db
        from scripts.import_data import import_dmp_daily

        with tempfile.TemporaryDirectory(prefix='tmall-dmp-') as root:
            database = os.path.join(root, 'dashboard.db')
            init_db(database)
            connection = sqlite3.connect(database)
            frame = pd.DataFrame([
                {
                    '宝贝ID': 'dmp-001', '宝贝名称': 'DMP 商品', '日期': 20260401,
                    '货品成长阶段': '成长期', '支付金额': '1,234.50', 'IPV': 100,
                    '营销推广IPV': 20, '营销推广消耗': 50, '营销推广ROI': 24.69,
                    '收藏率': '5%', '支付转化率': '2%', '复购率': '1%',
                    '预售支付金额': 10, '预售销量': 2, '非推广IPV': 80,
                    '搜索IPV': 30, '推荐IPV': 40, '免费搜索点击率': '6%',
                    '笔单价': 123.45, '连带购买量': 3, '连带购买率': '3%',
                    '连带购买叶子类目宽度': 2, '复购用户数': 1,
                },
            ])
            import_dmp_daily(connection, frame)
            connection.commit()
            connection.close()

            client = create_app({'TESTING': True, 'DATABASE_PATH': database}).test_client()
            response = client.get('/api/products?dim=daily&start=2026-04-01&end=2026-04-01&status=all&limit=1')
            self.assertEqual(response.status_code, 200)
            row = response.get_json()['data']['rows'][0]
            self.assertEqual(row['product_id'], 'dmp-001')
            self.assertEqual(row['paid_ipv'], 20)
            self.assertEqual(row['organic_ipv'], 80)
            self.assertEqual(row['search_ipv'], 30)
            self.assertEqual(row['presale_qty'], 2)
            self.assertEqual(row['category_width'], 2)
            self.assertAlmostEqual(row['search_click_rate'], 0.06)


if __name__ == '__main__':
    unittest.main()

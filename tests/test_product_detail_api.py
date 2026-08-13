import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class ProductDetailApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-dashboard-product-detail-tests-')
        from app import create_app
        from db import get_db
        self.path = os.path.join(self.temp.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()
        with get_db(self.path) as conn:
            conn.execute("INSERT INTO products (product_id,title) VALUES ('detail-a','详情商品')")
            conn.execute("INSERT INTO daily_data (product_id,date,payment_amount,refund_amount,ipv,buyers,ad_spend) VALUES ('detail-a','2026-04-01',100,10,20,2,5)")
            conn.commit()

    def tearDown(self): self.temp.cleanup()

    def test_detail_returns_product_trend_lifecycle_and_actions(self):
        response = self.client.get('/api/products/detail-a/detail')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']; response.close()
        self.assertEqual(data['product']['title'], '详情商品')
        self.assertEqual(data['daily_trend'][0]['net_sales'], 90.0)
        self.assertIn('lifecycle', data)


if __name__ == '__main__': unittest.main(verbosity=2)

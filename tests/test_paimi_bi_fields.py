import os
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class PaimiBiFieldsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-paimi-bi-tests-')
        from app import create_app
        self.db = os.path.join(self.temp_dir.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.db})
        self.client = self.app.test_client()
        from db import get_db
        with get_db(self.db) as connection:
            connection.execute("INSERT INTO products (product_id, title, status) VALUES ('p-1', '测试商品', 'active')")
            connection.execute("""INSERT INTO monthly_data
                (product_id, month, payment_amount, refund_amount, net_sales, visitors, buyers)
                VALUES ('p-1', '2026-07', 100, 10, 90, 20, 2)""")
            connection.execute("""INSERT INTO monthly_source_payload
                (product_id, month, source_filename, source_hash, payload_json)
                VALUES ('p-1', '2026-07', 'source.xlsx', 'hash', '{\"链接库存数量\":12,\"利润率(账单)\":0.35}')""")
            connection.execute("""INSERT INTO source_field_catalog
                (field_key, source_column, label, group_name, data_type, format, source_type, available_months_json, nonempty_count)
                VALUES ('bi_stock', '链接库存数量', '链接库存数量', 'BI 数据源字段', 'number', 'number', 'bi_monthly_overview', '[\"2026-07\"]', 1)""")
            connection.execute("""INSERT INTO source_field_catalog
                (field_key, source_column, label, group_name, data_type, format, source_type, available_months_json, nonempty_count)
                VALUES ('bi_margin', '利润率(账单)', '利润率(账单)', 'BI 数据源字段', 'number', 'percent', 'bi_monthly_overview', '[\"2026-07\"]', 1)""")
            connection.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_settings_exposes_imported_bi_field_catalog(self):
        response = self.client.get('/api/settings')
        self.assertEqual(response.status_code, 200)
        fields = response.get_json()['data']['field_catalog']['products']
        stock = next(field for field in fields if field['key'] == 'bi_stock')
        self.assertEqual(stock['label'], '链接库存数量')
        self.assertEqual(stock['format'], 'number')
        self.assertEqual(stock['available_months'], ['2026-07'])

    def test_monthly_products_response_resolves_bi_payload_fields(self):
        response = self.client.get('/api/products?dim=monthly&period=2026-07&status=all&product_id=p-1')
        self.assertEqual(response.status_code, 200)
        item = response.get_json()['data']['rows'][0]
        self.assertEqual(item['bi_stock'], 12)
        self.assertEqual(item['bi_margin'], 0.35)
        self.assertNotIn('bi_payload_json', item)

    def test_product_template_can_reference_catalogued_bi_field(self):
        response = self.client.put('/api/settings', json={
            'view_templates': {
                'operate': {'label': '基础运营', 'columns': ['product_id', 'title', 'bi_stock']},
            },
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('bi_stock', response.get_json()['data']['view_templates']['operate']['columns'])


if __name__ == '__main__':
    unittest.main()

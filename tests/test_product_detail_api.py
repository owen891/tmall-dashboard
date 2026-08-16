import os
import sys
import tempfile
import unittest
from unittest.mock import patch

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
        self.assertEqual(data['summary']['payment_amount'], 100.0)
        self.assertEqual(data['summary']['net_sales'], 90.0)
        self.assertEqual(data['summary']['payment_conversion_rate'], .1)
        self.assertEqual(data['summary']['expense_ratio'], .05)
        self.assertEqual(data['summary']['average_order_value'], 50.0)
        self.assertEqual(data['summary']['refund_rate'], .1)
        self.assertEqual(data['summary']['metric_availability']['refund_rate'], 'available')

    def test_detail_does_not_calculate_lifecycle_for_the_entire_catalog(self):
        with patch('api.product_detail_api.lifecycle_service.list', side_effect=AssertionError('full catalog scan')):
            response = self.client.get('/api/products/detail-a/detail')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['lifecycle']['product_id'], 'detail-a')
        response.close()

    def test_detail_respects_selected_date_range(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute("INSERT INTO daily_data (product_id,date,payment_amount,refund_amount,ipv,buyers,ad_spend) VALUES ('detail-a','2026-04-02',200,20,40,4,10)")
            conn.commit()

        response = self.client.get('/api/products/detail-a/detail?start=2026-04-02&end=2026-04-02')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']; response.close()
        self.assertEqual([row['date'] for row in data['daily_trend']], ['2026-04-02'])
        self.assertEqual(data['summary']['payment_amount'], 200.0)
        self.assertEqual(data['summary']['data_cutoff_date'], '2026-04-02')

    def test_detail_marks_missing_key_inputs_unavailable(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute("INSERT INTO products (product_id,title) VALUES ('detail-missing','缺字段商品')")
            conn.execute("INSERT INTO daily_data (product_id,date,payment_amount,refund_amount,ipv,buyers,ad_spend) VALUES ('detail-missing','2026-04-01',100,NULL,20,2,NULL)")
            conn.commit()

        response = self.client.get('/api/products/detail-missing/detail')
        payload = response.get_json()
        response.close()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['availability'], 'missing-fields')
        self.assertIn('successful_refund_amount', payload['missing_inputs'])
        self.assertIsNone(payload['data']['summary']['net_sales'])

    def test_detail_includes_history_period_analysis_and_evidence(self):
        response = self.client.get('/api/products/detail-a/detail')
        payload = response.get_json(); response.close()
        data = payload['data']
        self.assertIn('lifecycle_history', data)
        self.assertIn('period_comparison', data)
        self.assertIn('contribution_analysis', data)
        self.assertIn('evidence_summary', data)
        self.assertEqual(data['evidence_summary']['coverage']['days'], 1)

    def test_detail_rejects_invalid_date_range_and_exports_csv(self):
        response = self.client.get('/api/products/detail-a/detail?start=bad')
        self.assertEqual(response.status_code, 422)
        response.close()
        export = self.client.get('/api/products/detail-a/detail/export')
        self.assertEqual(export.status_code, 200)
        self.assertIn('attachment;', export.headers.get('Content-Disposition', ''))
        self.assertIn('payment_amount', export.get_data(as_text=True))
        export.close()

    def test_detail_monthly_analysis_and_export_respect_selected_range(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.executemany(
                "INSERT INTO daily_data (product_id,date,payment_amount,refund_amount,ipv,buyers,ad_spend) VALUES (?,?,?,?,?,?,?)",
                [
                    ('detail-a', '2026-05-01', 300, 0, 30, 3, 15),
                    ('detail-a', '2026-06-01', 400, 0, 40, 4, 20),
                ],
            )
            conn.commit()
        response = self.client.get('/api/products/detail-a/detail?start=2026-05-01&end=2026-05-31')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']; response.close()
        self.assertEqual([item['month'] for item in data['monthly_analysis']], ['2026-05'])
        self.assertEqual([item['month'] for item in data['period_comparison']], ['2026-05'])
        self.assertTrue(data['evidence_summary']['unknowns'])

        export = self.client.get('/api/products/detail-a/detail/export?start=2026-05-01&end=2026-05-31')
        self.assertEqual(export.status_code, 200)
        csv_text = export.get_data(as_text=True)
        self.assertIn('2026-05-01', csv_text)
        self.assertNotIn('2026-06-01', csv_text)
        export.close()

    def test_export_rejects_invalid_date_range(self):
        response = self.client.get('/api/products/detail-a/detail/export?start=2026-05-02&end=2026-05-01')
        self.assertEqual(response.status_code, 422)
        response.close()

    def test_export_rejects_wrong_capability(self):
        response = self.client.get('/api/products/detail-a/detail/export?capability_key=settings.configure_templates')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['code'], 'FORBIDDEN')
        response.close()


if __name__ == '__main__': unittest.main(verbosity=2)

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
        self.assertEqual(data['summary']['expense_ratio'], 0.055556)
        self.assertEqual(data['summary']['average_order_value'], 50.0)
        self.assertEqual(data['summary']['refund_rate'], .1)
        self.assertEqual(data['summary']['metric_availability']['refund_rate'], 'available')
        self.assertEqual(data['summary']['payment_qty'], 0)
        self.assertIn('search_visitors', data['summary'])
        self.assertIn('paid_ipv', data['summary'])
        self.assertIn('detail_metrics', data)
        self.assertIn('presale_amount', {item['key'] for item in data['detail_metrics']})
        self.assertIn('data_source', {item['key'] for item in data['detail_metrics']})
        self.assertIn('search_visitors', data['daily_trend'][0])

    def test_product_promotion_workbench_returns_current_range_summary(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute(
                """INSERT INTO promotion_campaign_items
                   (shop_id, campaign_id, product_id, campaign_name, channel)
                   VALUES ('default', 'detail-campaign', 'detail-a', '详情计划', '搜索推广')"""
            )
            conn.execute(
                """INSERT INTO promotion_daily_facts
                   (shop_id, date, channel, campaign_id, product_id, grain,
                    campaign_name, ad_spend, attributed_payment_amount,
                    impressions, clicks, payment_buyers)
                   VALUES ('default', '2026-04-01', '搜索推广', 'detail-campaign',
                           'detail-a', 'campaign', '详情计划', 20, 80, 1000, 40, 4)"""
            )
            conn.commit()

        response = self.client.get('/api/products/detail-a/promotion?start=2026-04-01&end=2026-04-01')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        self.assertEqual(payload['availability'], 'available')
        self.assertEqual(payload['data']['product_id'], 'detail-a')
        self.assertEqual(payload['data']['summary']['ad_spend'], 20.0)
        self.assertAlmostEqual(payload['data']['summary']['roi'], 4.0, places=6)
        self.assertEqual(payload['data']['campaigns'][0]['campaign_id'], 'detail-campaign')

    def test_product_promotion_workbench_exposes_no_data_state(self):
        response = self.client.get('/api/products/detail-a/promotion?start=2026-04-01&end=2026-04-01')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        self.assertEqual(payload['availability'], 'no-data')
        self.assertIn('promotion_daily', payload['missing_inputs'])
        self.assertFalse(payload['capabilities']['can_drill_campaign'])

    def test_product_trade_workbench_returns_transaction_and_refund_theme(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute(
                """INSERT INTO daily_data
                   (product_id, date, payment_amount, refund_amount, payment_qty,
                    buyers, order_amount, order_buyers, cart_qty, cart_users, fav_users)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ('detail-a', '2026-04-02', 200, 20, 4, 3, 220, 3, 8, 6, 2),
            )
            conn.commit()

        response = self.client.get('/api/products/detail-a/trade?start=2026-04-01&end=2026-04-02')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        self.assertEqual(payload['availability'], 'available')
        self.assertEqual(payload['data']['summary']['payment_amount'], 300.0)
        self.assertEqual(payload['data']['summary']['refund_amount'], 30.0)
        self.assertEqual(payload['data']['summary']['net_sales'], 270.0)
        self.assertEqual(payload['data']['summary']['refund_rate'], 0.1)
        self.assertEqual(payload['data']['trend'][1]['net_sales'], 180.0)

    def test_product_trade_workbench_preserves_no_data_state(self):
        response = self.client.get('/api/products/detail-a/trade?start=2026-05-01&end=2026-05-01')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        self.assertEqual(payload['availability'], 'no-data')
        self.assertIn('daily_data', payload['missing_inputs'])
        self.assertFalse(payload['capabilities']['can_drill'])

    def test_granular_capabilities_report_missing_fact_tables_without_inference(self):
        response = self.client.get('/api/products/detail-a/granular-capabilities?start=2026-04-01&end=2026-04-01')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        self.assertEqual(payload['availability'], 'source-unavailable')
        self.assertFalse(payload['capabilities']['can_view_sku'])
        self.assertFalse(payload['capabilities']['can_view_region'])
        self.assertFalse(payload['capabilities']['can_view_hour'])
        themes = {item['key']: item for item in payload['data']['themes']}
        self.assertEqual(themes['sku']['source_table'], 'product_sku_daily')
        self.assertEqual(themes['region']['source_table'], 'product_region_daily')
        self.assertEqual(themes['hour']['source_table'], 'product_hourly')
        for theme in themes.values():
            self.assertEqual(theme['coverage']['row_count'], 0)
            self.assertEqual(theme['capabilities'], [])
            self.assertIn(theme['source_table'], payload['missing_inputs'])

    def test_granular_capabilities_reports_coverage_and_capability_field_readiness(self):
        from db import get_db

        with get_db(self.path) as conn:
            conn.execute('''
                CREATE TABLE product_sku_daily (
                    product_id TEXT,
                    sku_id TEXT,
                    date TEXT,
                    payment_amount REAL,
                    updated_at TEXT
                )
            ''')
            conn.execute(
                'INSERT INTO product_sku_daily VALUES (?, ?, ?, ?, ?)',
                ('detail-a', 'sku-1', '2026-04-01', 100, '2026-04-02 08:00:00'),
            )
            conn.commit()

        response = self.client.get('/api/products/detail-a/granular-capabilities?start=2026-04-01&end=2026-04-01')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        sku = next(item for item in payload['data']['themes'] if item['key'] == 'sku')
        self.assertEqual(sku['availability'], 'partial')
        self.assertEqual(sku['coverage']['row_count'], 1)
        self.assertEqual(sku['coverage']['dimension_count'], 1)
        self.assertEqual(sku['coverage']['latest_update'], '2026-04-02 08:00:00')
        self.assertIn('payment_quantity', sku['missing_inputs'])
        readiness = {item['key']: item for item in sku['capability_readiness']}
        self.assertFalse(readiness['sku_ranking']['available'])
        self.assertTrue(readiness['export']['available'])
        self.assertEqual(sku['capabilities'], ['export'])

    def test_granular_theme_returns_real_grouped_rows_only_for_requested_theme(self):
        from db import get_db

        with get_db(self.path) as conn:
            conn.execute('''
                CREATE TABLE product_region_daily (
                    product_id TEXT,
                    region_code TEXT,
                    region_name TEXT,
                    date TEXT,
                    visitors REAL,
                    buyers REAL,
                    payment_amount REAL
                )
            ''')
            conn.executemany(
                'INSERT INTO product_region_daily VALUES (?, ?, ?, ?, ?, ?, ?)',
                [
                    ('detail-a', 'CN-ZJ', '浙江', '2026-04-01', 100, 5, 500),
                    ('detail-a', 'CN-ZJ', '浙江', '2026-04-02', 50, 5, 300),
                    ('detail-a', 'CN-JS', '江苏', '2026-04-01', 80, 2, 120),
                ],
            )
            conn.commit()

        response = self.client.get('/api/products/detail-a/granular-capabilities?theme=region&start=2026-04-01&end=2026-04-02&limit=10')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        analysis = payload['data']['analysis']
        self.assertEqual(analysis['key'], 'region')
        self.assertEqual(analysis['row_count'], 2)
        self.assertEqual(analysis['rows'][0]['dimension_value'], 'CN-ZJ')
        self.assertEqual(analysis['rows'][0]['payment_amount'], 800.0)
        self.assertEqual(analysis['rows'][0]['conversion_rate'], 10 / 150)
        sku = next(item for item in payload['data']['themes'] if item['key'] == 'sku')
        self.assertNotIn('rows', sku)

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

    def test_detail_degrades_for_promotion_only_product(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute(
                """INSERT INTO promotion_daily_facts
                   (shop_id, date, channel, product_id, grain, ad_spend,
                    attributed_payment_amount, impressions, clicks)
                   VALUES ('default', '2026-04-01', 'search', 'promotion-only',
                           'product', 10, 20, 100, 5)"""
            )
            conn.execute(
                """INSERT INTO promotion_campaign_items
                   (shop_id, campaign_id, product_id, product_name, image_url)
                   VALUES ('default', 'campaign-1', 'promotion-only', 'Promotion Product',
                           'https://cdn.example.com/promotion-only.jpg')"""
            )
            conn.commit()

        response = self.client.get('/api/products/promotion-only/detail')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        data = payload['data']
        self.assertEqual(payload['availability'], 'partial')
        self.assertEqual(data['product']['title'], 'Promotion Product')
        self.assertEqual(data['product']['catalog_status'], 'missing')
        self.assertEqual(data['product']['source_status'], 'promotion_fact_only')
        self.assertEqual(data['product']['promotion_fact_count'], 1)
        self.assertFalse(payload['capabilities']['can_create_action'])
        self.assertFalse(payload['capabilities']['can_export'])
        self.assertTrue(any('商品主档缺失' in item for item in payload['limitations']))

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
        self.assertIn('search_visitors', export.get_data(as_text=True))
        self.assertIn('presale_amount', export.get_data(as_text=True))
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

    def test_detail_returns_problem_context_for_source_rule(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute(
                "INSERT INTO daily_data (product_id,date,payment_amount,refund_amount,ipv,buyers,ad_spend) VALUES (?,?,?,?,?,?,?)",
                ('detail-a', '2026-04-02', 1000, 300, 100, 40, 500),
            )
            conn.commit()
        response = self.client.get('/api/products/detail-a/detail?rule_key=high_paid_high_refund&period=2026-04&category_mode=all')
        self.assertEqual(response.status_code, 200)
        context = response.get_json()['data']['problem_context']
        response.close()
        self.assertEqual(context['status'], 'matched')
        self.assertEqual(context['rule_key'], 'high_paid_high_refund')
        self.assertEqual({item['key'] for item in context['matched_fields']}, {'expense_ratio', 'refund_rate'})
        self.assertEqual(context['period'], '2026-04')

    def test_detail_problem_context_preserves_missing_inputs(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute("INSERT INTO products (product_id,title) VALUES ('detail-rule-missing','缺字段商品')")
            conn.execute(
                "INSERT INTO daily_data (product_id,date,payment_amount,refund_amount,ipv,buyers,ad_spend) VALUES (?,?,?,?,?,?,?)",
                ('detail-rule-missing', '2026-04-01', 100, None, 100, 2, None),
            )
            conn.commit()
        response = self.client.get('/api/products/detail-rule-missing/detail?rule_key=high_paid_high_refund')
        self.assertEqual(response.status_code, 200)
        context = response.get_json()['data']['problem_context']
        response.close()
        self.assertEqual(context['status'], 'not-computable')
        self.assertIn('refund_amount', context['missing_fields'])
        self.assertIn('ad_spend', context['missing_fields'])

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

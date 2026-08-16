import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class PromotionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-promotion-tests-')
        from app import create_app
        from db import get_db
        self.path = os.path.join(self.temp_dir.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()
        with get_db(self.path) as conn:
            conn.execute("INSERT INTO products (product_id, title) VALUES ('p1', '演示凉感四件套')")
            conn.execute("INSERT INTO daily_data (product_id,date,payment_amount,refund_amount,net_sales) VALUES ('p1','2026-04-01',200,20,180)")
            conn.execute("INSERT INTO promotion_daily_facts (date,channel,campaign_id,unit_id,product_id,ad_spend,attributed_payment_amount,impressions,clicks) VALUES ('2026-04-01','search','c1','u1','p1',10,50,100,10)")
            conn.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_drilldown_returns_weighted_metrics_at_imported_grain(self):
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=campaign&channel=search')
        self.assertEqual(response.status_code, 200)
        item = response.get_json()['data']['rows'][0]
        response.close()
        self.assertEqual(item['campaign_id'], 'c1')
        self.assertEqual(item['roi'], 5.0)
        self.assertEqual(item['ctr'], .1)

    def test_product_grain_includes_catalog_title(self):
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=product')
        item = response.get_json()['data']['rows'][0]
        response.close()
        self.assertEqual(item['title'], '演示凉感四件套')

    def test_product_grain_includes_paid_detail_costs_and_image(self):
        with __import__('db').get_db(self.path) as conn:
            conn.execute("UPDATE products SET image_url = 'https://cdn.example.com/p1.jpg' WHERE product_id = 'p1'")
            conn.execute("""INSERT INTO paid_detail (
                product_id, date_range, total_orders, cart_adds, cart_cost, new_buyers,
                favs, direct_cart_adds, indirect_cart_adds
            ) VALUES ('p1', '2026-04', 3, 4, 2.5, 2, 5, 3, 1)""")
            conn.commit()
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=product')
        item = response.get_json()['data']['rows'][0]
        response.close()
        self.assertEqual(item['image_url'], 'https://cdn.example.com/p1.jpg')
        self.assertEqual(item['link_gsv'], 200.0)
        self.assertEqual(item['link_net_sales'], 180.0)
        self.assertEqual(item['expense_ratio'], .05)
        self.assertEqual(item['cart_adds'], 4)
        self.assertEqual(item['cart_cost'], 2.5)
        self.assertEqual(item['new_buyers'], 2)
        self.assertEqual(item['new_customer_cost'], 5.0)
        self.assertEqual(item['direct_cart_adds'], 3)

    def test_product_grain_aggregates_each_product_once_across_channels(self):
        with __import__('db').get_db(self.path) as conn:
            conn.execute("INSERT INTO promotion_daily_facts (date,channel,campaign_id,unit_id,product_id,ad_spend,attributed_payment_amount,impressions,clicks) VALUES ('2026-04-01','display','c2','u2','p1',20,70,200,20)")
            conn.commit()
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=product')
        rows = response.get_json()['data']['rows']
        response.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['product_id'], 'p1')
        self.assertEqual(rows[0]['ad_spend'], 30.0)
        self.assertEqual(rows[0]['attributed_payment_amount'], 120.0)

    def test_domain_response_exposes_real_monthly_breakdowns_by_product(self):
        with __import__('db').get_db(self.path) as conn:
            conn.execute("""INSERT INTO monthly_data (
                product_id, month, keyword_spend, keyword_sales, keyword_roi, keyword_visitors, keyword_ppc,
                crowd_spend, crowd_sales, crowd_roi, crowd_visitors, crowd_ppc,
                site_spend, site_sales, site_roi, site_visitors, site_ppc
            ) VALUES ('p1','2026-04',12,36,3,24,0.5,8,32,4,16,0.5,6,30,5,12,0.5)""")
            conn.commit()
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-30&group_by=product')
        breakdowns = response.get_json()['data']['breakdowns']
        response.close()
        self.assertEqual(breakdowns['keywords']['availability'], 'available')
        self.assertEqual(breakdowns['keywords']['rows'][0]['title'], '演示凉感四件套')
        self.assertEqual(breakdowns['keywords']['rows'][0]['spend'], 12.0)
        self.assertEqual(breakdowns['keywords']['rows'][0]['sales'], 36.0)
        self.assertEqual(breakdowns['crowd']['rows'][0]['roi'], 4.0)
        self.assertEqual(breakdowns['site']['rows'][0]['visitors'], 12)

    def test_monthly_breakdowns_are_not_limited_to_daily_fact_products(self):
        with __import__('db').get_db(self.path) as conn:
            conn.execute("INSERT INTO products (product_id, title) VALUES ('p2', '历史投放商品')")
            conn.execute("INSERT INTO monthly_data (product_id, month, keyword_spend, keyword_sales, keyword_visitors, keyword_ppc) VALUES ('p2','2026-04',20,80,40,0.5)")
            conn.commit()
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-30&group_by=product')
        keyword_rows = response.get_json()['data']['breakdowns']['keywords']['rows']
        response.close()
        self.assertEqual([row['product_id'] for row in keyword_rows], ['p2'])
        self.assertEqual(keyword_rows[0]['title'], '历史投放商品')

    def test_monthly_breakdowns_return_no_data_instead_of_fabricated_zero_summary(self):
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-30&group_by=product')
        breakdowns = response.get_json()['data']['breakdowns']
        response.close()
        for key in ('keywords', 'crowd', 'site'):
            self.assertEqual(breakdowns[key], {'availability': 'no-data', 'rows': []})

    def test_drilldown_exposes_conversion_direct_indirect_and_paid_share_from_facts(self):
        with __import__('db').get_db(self.path) as conn:
            conn.execute("UPDATE promotion_daily_facts SET payment_buyers = 2, direct_payment_amount = 30, indirect_payment_amount = 20 WHERE campaign_id = 'c1'")
            conn.execute("INSERT INTO store_daily_facts (date, payment_amount) VALUES ('2026-04-01', 100)")
            conn.commit()
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=product')
        item = response.get_json()['data']['rows'][0]; response.close()
        self.assertEqual(item['cvr'], .2)
        self.assertEqual(item['direct_payment_amount'], 30.0)
        self.assertEqual(item['indirect_payment_amount'], 20.0)
        self.assertEqual(item['paid_share'], .5)

    def test_unavailable_grain_does_not_return_fabricated_rows(self):
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=unit&channel=other')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json(); response.close()
        self.assertEqual(payload['availability'], 'no-data')
        self.assertEqual(payload['data']['rows'], [])

    def test_global_promotion_channel_alias_filters_results(self):
        with __import__('db').get_db(self.path) as conn:
            conn.execute("INSERT INTO promotion_daily_facts (date,channel,campaign_id,unit_id,product_id,ad_spend,attributed_payment_amount) VALUES ('2026-04-01','display','c2','u2','p2',10,20)")
            conn.commit()
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=channel&promotionChannel=display')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['channel'] for row in response.get_json()['data']['rows']], ['display'])

    def test_domain_response_includes_trend_alerts_and_available_grains(self):
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=channel')
        payload = response.get_json(); response.close()
        data = payload['data']
        self.assertEqual(data['available_grains'], ['channel', 'campaign', 'unit', 'product'])
        self.assertEqual(data['trend'][0]['date'], '2026-04-01')
        self.assertEqual(data['trend'][0]['roi'], 5.0)
        self.assertIsInstance(data['alerts'], list)
        self.assertTrue(payload['capabilities']['can_export'])
        self.assertTrue(payload['capabilities']['can_drilldown'])

    def test_no_rows_disable_promotion_drilldown(self):
        response = self.client.get(
            '/api/promotion?start=2026-04-01&end=2026-04-01&group_by=channel&channel=other'
        )
        payload = response.get_json()
        response.close()

        self.assertEqual(payload['availability'], 'no-data')
        self.assertFalse(payload['capabilities']['can_drilldown'])
        self.assertFalse(payload['capabilities']['can_export'])

    def test_missing_unit_dimension_disables_unit_grouping(self):
        with __import__('db').get_db(self.path) as connection:
            connection.execute("UPDATE promotion_daily_facts SET unit_id = '' WHERE campaign_id = 'c1'")
            connection.commit()

        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=channel')
        payload = response.get_json()
        response.close()

        self.assertFalse(payload['capabilities']['can_group_by_unit'])

    def test_saved_promotion_rule_changes_live_alerts(self):
        created = self.client.post('/api/alert-rules', json={
            'name': 'ROI 低于 6', 'scope': 'promotion_product', 'metric': 'roi',
            'operator': 'lt', 'threshold': 6, 'level': 'warning', 'enabled': True,
        })
        self.assertEqual(created.status_code, 201)
        rule_id = created.get_json()['data']['id']

        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=product')
        alerts = response.get_json()['data']['alerts']
        response.close()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['rule_id'], rule_id)
        self.assertEqual(alerts[0]['threshold'], 6.0)

        updated = self.client.put(f'/api/alert-rules/{rule_id}', json={'threshold': 4})
        self.assertEqual(updated.status_code, 200)
        response = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-01&group_by=product')
        self.assertEqual(response.get_json()['data']['alerts'], [])
        response.close()

    def test_alert_rule_api_rejects_invalid_configuration(self):
        invalid_payloads = [
            {'name': 'bad', 'scope': 'unknown', 'metric': 'roi', 'operator': 'lt', 'threshold': 3, 'level': 'warning'},
            {'name': 'bad', 'scope': 'promotion_product', 'metric': 'refund_rate', 'operator': 'lt', 'threshold': 3, 'level': 'warning'},
            {'name': 'bad', 'scope': 'promotion_product', 'metric': 'roi', 'operator': 'eq', 'threshold': 3, 'level': 'warning'},
            {'name': 'bad', 'scope': 'promotion_product', 'metric': 'roi', 'operator': 'lt', 'threshold': 3, 'level': 'critical'},
            {'name': 'bad', 'scope': 'promotion_product', 'metric': 'roi', 'operator': 'lt', 'level': 'warning'},
        ]
        for payload in invalid_payloads:
            response = self.client.post('/api/alert-rules', json=payload)
            self.assertEqual(response.status_code, 422, payload)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_invalid_or_reversed_dates_return_structured_validation_error(self):
        for query in (
            'start=2026-04-01&end=bad',
            'start=2026-04-02&end=2026-04-01',
        ):
            response = self.client.get(f'/api/promotion?{query}')
            payload = response.get_json()
            response.close()
            self.assertEqual(response.status_code, 422)
            self.assertEqual(payload['code'], 'VALIDATION_ERROR')


if __name__ == '__main__':
    unittest.main(verbosity=2)

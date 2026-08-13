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


if __name__ == '__main__':
    unittest.main(verbosity=2)

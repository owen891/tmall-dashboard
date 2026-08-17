import os
import sys
import tempfile
import unittest
import io

from openpyxl import Workbook

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class ShopScopeApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-shop-scope-')
        from app import create_app
        from db import get_db

        self.path = os.path.join(self.temp_dir.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()
        with get_db(self.path) as conn:
            conn.executemany(
                "INSERT INTO products (product_id, title) VALUES (?, ?)",
                [('scope-product', 'Scoped product')],
            )
            conn.executemany(
                """INSERT INTO daily_data
                   (shop_id, product_id, date, payment_amount, refund_amount, net_sales, ipv, buyers, ad_spend)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    ('shop-a', 'scope-product', '2026-04-01', 100, 10, 90, 10, 2, 5),
                    ('shop-a', 'scope-product', '2026-04-02', 120, 12, 108, 12, 3, 6),
                    ('shop-b', 'scope-product', '2026-04-01', 900, 90, 810, 90, 20, 45),
                    ('shop-b', 'scope-product', '2026-04-02', 920, 92, 828, 92, 21, 46),
                ],
            )
            conn.executemany(
                """INSERT INTO promotion_daily_facts
                   (shop_id, date, channel, campaign_id, unit_id, product_id,
                    ad_spend, attributed_payment_amount, impressions, clicks, payment_buyers)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    ('shop-a', '2026-04-01', 'search', 'a-campaign', 'a-unit', 'scope-product', 5, 25, 100, 10, 2),
                    ('shop-b', '2026-04-01', 'search', 'b-campaign', 'b-unit', 'scope-product', 50, 250, 1000, 100, 20),
                ],
            )
            conn.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_daily_compare_is_scoped_to_requested_shop(self):
        response = self.client.get(
            '/api/compare?dim=daily&period_a=2026-04-01&period_b=2026-04-02&shop_id=shop-a'
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        response.close()
        self.assertEqual(payload['kpi_compare']['gmv']['period_a'], 100.0)
        self.assertEqual(payload['kpi_compare']['gmv']['period_b'], 120.0)
        self.assertEqual(payload['product_changes'][0]['amount_a'], 100.0)

    def test_kpi_trend_products_and_overview_are_scoped_to_requested_shop(self):
        kpi = self.client.get('/api/kpi?dim=daily&period=2026-04-01&shop_id=shop-a').get_json()
        self.assertEqual(kpi['current']['gmv'], 100.0)
        self.assertEqual(kpi['current']['aov'], 50.0)

        trend = self.client.get('/api/trend?dim=daily&start=2026-04-01&end=2026-04-01&shop_id=shop-a').get_json()
        self.assertEqual(trend[0]['gmv'], 100.0)

        products = self.client.get(
            '/api/products?dim=daily&period=2026-04-01&status=all&limit=10&shop_id=shop-a'
        ).get_json()['data']['rows']
        scoped = next(row for row in products if row['product_id'] == 'scope-product')
        self.assertEqual(scoped['payment_amount'], 100.0)

        overview = self.client.get(
            '/api/overview?start=2026-04-01&end=2026-04-02&shop_id=shop-a'
        ).get_json()['data']
        self.assertEqual(overview['payment_amount'], 220.0)

    def test_promotion_trend_and_grains_are_scoped_to_requested_shop(self):
        response = self.client.get(
            '/api/promotion?start=2026-04-01&end=2026-04-01&group_by=campaign&shop_id=shop-a'
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        response.close()
        self.assertEqual([row['campaign_id'] for row in payload['data']['rows']], ['a-campaign'])
        self.assertEqual(payload['data']['trend'][0]['ad_spend'], 5.0)
        self.assertEqual(payload['data']['available_grains'], ['channel', 'campaign', 'unit', 'product'])
        self.assertEqual(payload['data']['source_batches'], [])

    def test_non_default_promotion_product_scope_hides_single_shop_legacy_metrics(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute(
                """INSERT INTO paid_detail (product_id, date_range, total_orders, cart_adds, cart_cost)
                   VALUES ('scope-product', '2026-04', 9, 8, 2)"""
            )
            conn.execute(
                """INSERT INTO monthly_data (product_id, month, keyword_spend, keyword_sales, keyword_visitors, keyword_ppc)
                   VALUES ('scope-product', '2026-04', 10, 40, 20, .5)"""
            )
            conn.commit()
        response = self.client.get(
            '/api/promotion?start=2026-04-01&end=2026-04-30&group_by=product&shop_id=shop-a'
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        response.close()
        item = payload['data']['rows'][0]
        self.assertIsNone(item['total_orders'])
        self.assertEqual(payload['data']['breakdowns']['keywords']['availability'], 'no-data')
        self.assertTrue(payload['limitations'])

    def test_non_default_product_list_and_export_hide_paid_detail_legacy_rows(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.execute(
                """INSERT INTO paid_detail (product_id, date_range, impressions, clicks, cost, total_orders)
                   VALUES ('scope-product', '2026-04', 99, 9, 8, 7)"""
            )
            conn.commit()
        products = self.client.get(
            '/api/products?dim=daily&period=2026-04-01&status=all&limit=10&shop_id=shop-a'
        )
        self.assertEqual(products.status_code, 200)
        row = next(item for item in products.get_json()['data']['rows'] if item['product_id'] == 'scope-product')
        self.assertEqual(row['impressions'], 0)
        self.assertEqual(row['total_orders'], 0)
        products.close()

        export = self.client.post(
            '/api/export',
            json={'type': 'products', 'dim': 'daily', 'period': '2026-04-01', 'status': 'all', 'shop_id': 'shop-a'},
        )
        self.assertEqual(export.status_code, 200)
        export.close()

    def test_non_default_legacy_domain_endpoints_fail_closed(self):
        urls = (
            '/api/lifecycle?shop_id=shop-a',
            '/api/lifecycle/assessments?shop_id=shop-a',
            '/api/actions?shop_id=shop-a',
            '/api/products/scope-product/detail?shop_id=shop-a',
            '/api/alerts?period=2026-04&shop_id=shop-a',
            '/api/goals/2026?shop_id=shop-a',
            '/api/product_target_progress?period=2026-04&shop_id=shop-a',
            '/api/overview?start=2026-04-01&end=2026-04-02&lifecycle_stage=growth&shop_id=shop-a',
            '/api/overview/daily-matrix?start=2026-04-01&end=2026-04-02&lifecycle_stage=growth&shop_id=shop-a',
            '/api/health?period=2026-04&shop_id=shop-a',
            '/api/reviews/summary?shop_id=shop-a',
            '/api/ad_performance?dim=monthly&period=2026-04&shop_id=shop-a',
            '/api/legacy/actions?shop_id=shop-a',
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'UNSUPPORTED_SCOPE')
                response.close()

    def test_product_diagnose_tool_fails_closed_for_non_default_shop(self):
        response = self.client.post(
            '/api/tools/execute?shop_id=shop-a',
            json={'tool_id': 'product_diagnose', 'params': {'product_id': 'scope-product'}},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'UNSUPPORTED_SCOPE')
        response.close()

    def test_import_writes_daily_fact_to_requested_shop(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['date', 'product_id', 'payment_amount', 'successful_refund_amount', 'product_visitors', 'payment_buyers', 'ad_spend'])
        sheet.append(['2026-04-03', 'imported-product', 300, 30, 30, 6, 15])
        content = io.BytesIO()
        workbook.save(content)
        content.seek(0)

        preview_response = self.client.post(
            '/api/imports/preview?shop_id=shop-a',
            data={'file': (content, 'shop-a-daily.xlsx')},
            content_type='multipart/form-data',
        )
        self.assertEqual(preview_response.status_code, 200)
        preview = preview_response.get_json()['data']
        preview_response.close()

        confirm_response = self.client.post(
            '/api/imports?shop_id=shop-a',
            json={'preview_id': preview['id'], 'mapping': preview['mapping']},
        )
        self.assertEqual(confirm_response.status_code, 201)
        confirm_response.close()

        from db import get_db
        with get_db(self.path) as conn:
            rows = conn.execute(
                "SELECT shop_id, payment_amount FROM daily_data WHERE product_id = 'imported-product'"
            ).fetchall()
        self.assertEqual([(row['shop_id'], row['payment_amount']) for row in rows], [('shop-a', 300.0)])

    def test_legacy_week_month_and_target_endpoints_reject_explicit_shop_scope(self):
        for url in (
            '/api/kpi?dim=monthly&period=2026-04&shop_id=shop-a',
            '/api/trend?dim=weekly&start=2026-04-01&end=2026-04-07&shop_id=shop-a',
            '/api/compare?dim=monthly&period_a=2026-04&period_b=2026-05&shop_id=shop-a',
            '/api/products?dim=monthly&period=2026-04&shop_id=shop-a',
            '/api/target_progress?dim=monthly&period=2026-04&shop_id=shop-a',
            '/api/product_target_progress?period=2026-04&shop_id=shop-a',
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'UNSUPPORTED_SCOPE')
                response.close()

    def test_non_default_monthly_import_preview_fails_closed_before_legacy_lookup(self):
        from db import get_db

        with get_db(self.path) as conn:
            conn.execute(
                "INSERT INTO monthly_data (product_id, month, payment_amount) VALUES (?, ?, ?)",
                ('scope-product', '2026-04', 999.0),
            )
            conn.commit()

        workbook = Workbook()
        sheet = workbook.active
        sheet.append([
            'date', 'product_id', 'payment_amount', 'successful_refund_amount',
            'product_visitors', 'payment_buyers',
        ])
        sheet.append(['2026-04-01', 'scope-product', 100.0, 10.0, 20, 2])
        content = io.BytesIO()
        workbook.save(content)
        content.seek(0)

        response = self.client.post(
            '/api/imports/preview?shop_id=shop-a&source_type=product_month',
            data={'file': (content, 'shop-a-monthly.xlsx')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['code'], 'UNSUPPORTED_SCOPE')
        response.close()

    def test_import_batches_and_revert_are_scoped_to_current_shop(self):
        from db import get_db
        with get_db(self.path) as conn:
            conn.executemany(
                """INSERT INTO import_batches
                   (id, shop_id, source_type, source_filename, source_hash, status, quality_summary)
                   VALUES (?, ?, ?, ?, ?, 'completed', '{}')""",
                [
                    ('batch-shop-a', 'shop-a', 'product_day', 'a.xlsx', 'hash-a'),
                    ('batch-shop-b', 'shop-b', 'product_day', 'b.xlsx', 'hash-b'),
                ],
            )
            conn.commit()

        listed = self.client.get('/api/imports?shop_id=shop-a')
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row['id'] for row in listed.get_json()['data']], ['batch-shop-a'])
        listed.close()

        audit = self.client.get('/api/imports/batch-shop-b/audit?shop_id=shop-a')
        self.assertEqual(audit.status_code, 422)
        self.assertEqual(audit.get_json()['code'], 'UNSUPPORTED_SCOPE')
        audit.close()

        reverted = self.client.post('/api/imports/batch-shop-b/revert?shop_id=shop-a')
        self.assertEqual(reverted.status_code, 422)
        self.assertEqual(reverted.get_json()['code'], 'UNSUPPORTED_SCOPE')
        reverted.close()


if __name__ == '__main__':
    unittest.main()

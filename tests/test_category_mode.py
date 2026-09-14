# -*- coding: utf-8 -*-
"""Category mode (品类模式) contract tests.

The dashboard supports scoping to a BI product label (标品袜子 etc.) via the
`category_mode` request parameter:
  - absent / all -> no filtering (backward compatible)
  - sock        -> alias for 标品袜子
  - <label>     -> exact BI label value (multi-label values supported)
The frontend defaults to sock; the service-side default stays all.
"""
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class CategoryModeContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-category-tests-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from app import create_app
        from db import get_db

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        self.client = self.app.test_client()
        with get_db(self.database_path) as connection:
            connection.executemany(
                'INSERT INTO products (product_id, title, status, shop_label) VALUES (?, ?, ?, ?)',
                [
                    ('sock-a', '标品袜A', 'active', '标品袜子'),
                    ('sock-b', '标品袜B', 'active', '标品袜子,平销商品'),
                    ('other-a', '内裤A', 'active', '内裤'),
                    ('unlabeled-a', '未打标A', 'active', ''),
                ],
            )
            connection.executemany(
                '''
                INSERT INTO daily_data (
                    product_id, date, payment_amount, refund_amount,
                    ipv, buyers, ad_spend
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    ('sock-a', '2026-04-01', 100, 10, 10, 2, 20),
                    ('sock-b', '2026-04-02', 200, 20, 20, 4, 30),
                    ('other-a', '2026-04-03', 300, 30, 30, 6, 40),
                    ('unlabeled-a', '2026-04-04', 400, 40, 40, 8, 50),
                ],
            )
            connection.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _overview(self, query):
        resp = self.client.get(f'/api/overview?start=2026-04-01&end=2026-04-30{query}')
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        return resp.get_json()

    def test_overview_without_param_returns_all(self):
        payload = self._overview('')
        self.assertEqual(payload['data']['payment_amount'], 1000)

    def test_overview_all_mode_returns_all(self):
        payload = self._overview('&category_mode=all')
        self.assertEqual(payload['data']['payment_amount'], 1000)

    def test_overview_sock_filters_to_standard_socks(self):
        payload = self._overview('&category_mode=sock')
        # sock-a + sock-b (multi-label matches too) = 300; other/unlabeled excluded
        self.assertEqual(payload['data']['payment_amount'], 300)

    def test_overview_exact_label_filters(self):
        payload = self._overview('&category_mode=内裤')
        self.assertEqual(payload['data']['payment_amount'], 300)

    def test_products_sock_filters(self):
        resp = self.client.get(
            '/api/products?dim=daily&start=2026-04-01&end=2026-04-30&category_mode=sock'
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        payload = resp.get_json()
        self.assertEqual(payload['data']['total'], 2)
        ids = {row['product_id'] for row in payload['data']['rows']}
        self.assertEqual(ids, {'sock-a', 'sock-b'})

    def test_products_all_mode_returns_all(self):
        resp = self.client.get(
            '/api/products?dim=daily&start=2026-04-01&end=2026-04-30&category_mode=all'
        )
        payload = resp.get_json()
        self.assertEqual(payload['data']['total'], 4)

    def test_overview_monthly_fallback_applies_category_filter(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.executemany(
                '''
                INSERT INTO monthly_data (
                    month, product_id, payment_amount, refund_amount, visitors, ad_spend
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''',
                [
                    ('2026-05', 'sock-a', 1000, 100, 100, 200),
                    ('2026-05', 'sock-b', 2000, 200, 200, 300),
                    ('2026-05', 'other-a', 3000, 300, 300, 400),
                    ('2026-05', 'unlabeled-a', 4000, 400, 400, 500),
                ],
            )
            connection.commit()
        resp_all = self.client.get('/api/overview?start=2026-05-01&end=2026-05-31')
        self.assertEqual(resp_all.status_code, 200)
        self.assertEqual(resp_all.get_json()['data']['payment_amount'], 10000)
        resp_sock = self.client.get('/api/overview?start=2026-05-01&end=2026-05-31&category_mode=sock')
        self.assertEqual(resp_sock.status_code, 200)
        self.assertEqual(resp_sock.get_json()['data']['payment_amount'], 3000)

    def test_settings_returns_category_modes(self):
        resp = self.client.get('/api/settings')
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        payload = resp.get_json()
        modes = payload['data']['category_modes']
        values = [m['value'] for m in modes]
        self.assertIn('all', values)
        self.assertIn('sock', values)
        self.assertIn('内裤', values)
        self.assertEqual(payload['data']['category_mode_default'], 'sock')

    def test_promotion_accepts_category_mode(self):
        resp = self.client.get('/api/promotion?start=2026-04-01&end=2026-04-30&category_mode=sock')
        # promotion_facts are absent in this fixture; the point is the param is accepted (422 only on missing dates)
        self.assertIn(resp.status_code, (200, 404))
        if resp.status_code == 200:
            self.assertIsNotNone(resp.get_json()['ok'])

    def test_frontend_contract(self):
        api_js = open(os.path.join(PROJECT_ROOT, 'frontend/ui_demo/assets/api.js'), encoding='utf-8').read()
        shell_js = open(os.path.join(PROJECT_ROOT, 'frontend/ui_demo/assets/shell.js'), encoding='utf-8').read()
        shell_css = open(os.path.join(PROJECT_ROOT, 'frontend/ui_demo/assets/shell.css'), encoding='utf-8').read()
        self.assertIn('dashboard.categoryMode', api_js)
        self.assertIn('category_mode', api_js)
        self.assertIn("DEFAULT_CATEGORY_MODE = 'sock'", api_js)
        self.assertIn('data-category-mode', shell_js)
        self.assertIn('标品袜子', shell_js)
        self.assertIn('demo-category__select', shell_css)


if __name__ == '__main__':
    unittest.main()

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

    def test_lifecycle_list_sock_filters(self):
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
        resp_all = self.client.get('/api/lifecycle?limit=100')
        self.assertEqual(resp_all.status_code, 200)
        self.assertEqual(len(resp_all.get_json()), 4)
        resp_sock = self.client.get('/api/lifecycle?limit=100&category_mode=sock')
        self.assertEqual(resp_sock.status_code, 200)
        ids = {row['product_id'] for row in resp_sock.get_json()}
        self.assertEqual(ids, {'sock-a', 'sock-b'})

    def test_compare_sock_filters(self):
        resp_all = self.client.get('/api/compare?dim=daily&period_a=2026-04-01&period_b=2026-04-03')
        self.assertEqual(resp_all.status_code, 200)
        kpi_all = resp_all.get_json()['kpi_compare']['gmv']
        self.assertEqual(kpi_all['period_a'], 100)
        self.assertEqual(kpi_all['period_b'], 300)
        resp_sock = self.client.get('/api/compare?dim=daily&period_a=2026-04-01&period_b=2026-04-03&category_mode=sock')
        self.assertEqual(resp_sock.status_code, 200)
        kpi_sock = resp_sock.get_json()['kpi_compare']
        # 04-03 has no sock-labeled rows, so no KPI pair exists (filtered out).
        self.assertNotIn('gmv', kpi_sock)

    def test_trend_sock_filters(self):
        resp_all = self.client.get('/api/trend?dim=daily&start=2026-04-01&end=2026-04-30')
        self.assertEqual(resp_all.status_code, 200)
        rows_all = resp_all.get_json()
        self.assertEqual(len(rows_all), 4)
        self.assertEqual(sum(r['gmv'] for r in rows_all), 1000)
        resp_sock = self.client.get('/api/trend?dim=daily&start=2026-04-01&end=2026-04-30&category_mode=sock')
        self.assertEqual(resp_sock.status_code, 200)
        rows_sock = resp_sock.get_json()
        self.assertEqual(len(rows_sock), 2)
        self.assertEqual(sum(r['gmv'] for r in rows_sock), 300)

    def test_anomalies_sock_filters(self):
        resp_all = self.client.get('/api/anomalies?dim=daily&period=2026-04-04&prev_period=2026-04-02')
        self.assertEqual(resp_all.status_code, 200)
        resp_sock = self.client.get('/api/anomalies?dim=daily&period=2026-04-04&prev_period=2026-04-02&category_mode=sock')
        self.assertEqual(resp_sock.status_code, 200)
        # 04-04 has no sock-labeled rows -> no anomalies reported for the period.
        self.assertEqual(resp_sock.get_json()['anomalies'], [])

    def test_kpi_sock_filters(self):
        resp_all = self.client.get('/api/kpi?dim=daily&period=2026-04-04&prev_period=2026-04-02')
        self.assertEqual(resp_all.status_code, 200)
        self.assertEqual(resp_all.get_json()['current']['gmv'], 400)
        resp_sock = self.client.get('/api/kpi?dim=daily&period=2026-04-04&prev_period=2026-04-02&category_mode=sock')
        self.assertEqual(resp_sock.status_code, 200)
        # 04-04 has no sock-labeled rows -> current period has no facts.
        self.assertIsNone(resp_sock.get_json()['current'])

    def test_export_sock_filters(self):
        payload = {'type': 'products', 'dim': 'daily', 'start': '2026-04-01', 'end': '2026-04-30'}
        resp_all = self.client.post('/api/export', json=payload)
        self.assertEqual(resp_all.status_code, 200)
        size_all = len(resp_all.data)
        resp_sock = self.client.post('/api/export?category_mode=sock', json=payload)
        self.assertEqual(resp_sock.status_code, 200)
        size_sock = len(resp_sock.data)
        self.assertLess(size_sock, size_all)

    def test_frontend_hides_category_on_data_center(self):
        shell_js = open(os.path.join(PROJECT_ROOT, 'frontend/ui_demo/assets/shell.js'), encoding='utf-8').read()
        self.assertIn("hideCategoryPages", shell_js)
        self.assertIn("'data-center'", shell_js)

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

    def test_target_progress_sock_filters(self):
        resp_all = self.client.get('/api/target_progress?dim=daily&period=2026-04-04')
        self.assertEqual(resp_all.status_code, 200)
        self.assertEqual(resp_all.get_json()['actual']['gsv'], 400)
        resp_sock = self.client.get('/api/target_progress?dim=daily&period=2026-04-04&category_mode=sock')
        self.assertEqual(resp_sock.status_code, 200)
        # 04-04 has no sock rows -> category-scoped actual has no facts.
        self.assertIsNone(resp_sock.get_json()['actual'])

    def test_actions_sock_filters(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.executemany(
                '''INSERT INTO product_actions (
                       product_id, purpose_type, purpose_note, action_type, action_detail, target_metric,
                   status, planned_at, observer_window_days, version
                   ) VALUES (?, 'promotion', '提价', 'adjust_bid', '提价测试', 'gmv',
                   'pending_execution', ?, 7, 1)''',
                [('sock-a', '2026-04-10'), ('other-a', '2026-04-11')],
            )
            connection.commit()
        resp_all = self.client.get('/api/actions')
        self.assertEqual(resp_all.status_code, 200)
        self.assertEqual(len(resp_all.get_json()['data']), 2)
        resp_sock = self.client.get('/api/actions?category_mode=sock')
        self.assertEqual(resp_sock.status_code, 200)
        ids = [r['product_id'] for r in resp_sock.get_json()['data']]
        self.assertEqual(ids, ['sock-a'])

    def test_calendar_actions_sock_filters(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.executemany(
                '''INSERT INTO product_actions (
                       product_id, purpose_type, purpose_note, action_type, action_detail, target_metric,
                   status, planned_at, observer_window_days, version
                   ) VALUES (?, 'promotion', '提价', 'adjust_bid', '提价测试', 'gmv',
                   'pending_execution', ?, 7, 1)''',
                [('sock-a', '2026-04-10'), ('other-a', '2026-04-11')],
            )
            connection.commit()
        resp_all = self.client.get('/api/actions/calendar?start=2026-04-01&end=2026-04-30')
        self.assertEqual(resp_all.status_code, 200)
        self.assertEqual(len(resp_all.get_json()['data']), 2)
        resp_sock = self.client.get('/api/actions/calendar?start=2026-04-01&end=2026-04-30&category_mode=sock')
        self.assertEqual(resp_sock.status_code, 200)
        ids = [r['product_id'] for r in resp_sock.get_json()['data']]
        self.assertEqual(ids, ['sock-a'])

    def test_import_field_aliases_label_to_shop_label(self):
        import services.import_service as isvc
        self.assertIn('shop_label', isvc.PRODUCT_DAY_OPTIONAL_FIELDS)
        self.assertIn('商品标签', isvc.FIELD_ALIASES['product_tags'])
        self.assertIn('品类标签', isvc.FIELD_ALIASES['shop_label'])

    def test_confirm_extracts_shop_label_from_bi_label_column(self):
        import io as _io
        import pandas as pd
        from db import get_db
        from services.import_service import import_service as svc
        df = pd.DataFrame({
            '日期': ['2026-04-05'],
            '商品ID': ['new-sock-2'],
            '商品标签': ['标品袜子'],
            '支付金额': [100],
            '访客数': [10],
        })
        bio = _io.BytesIO()
        df.to_excel(bio, index=False)
        with self.app.app_context():
            preview = svc.preview('bi2.xlsx', bio.getvalue(), 'product_day')
            svc.confirm(preview['id'], {
                'date': '日期', 'product_id': '商品ID', 'payment_amount': '支付金额',
                'product_visitors': '访客数',
            })
        with get_db(self.database_path) as connection:
            label = connection.execute(
                'SELECT shop_label FROM products WHERE product_id = ?', ('new-sock-2',)
            ).fetchone()['shop_label']
        self.assertEqual(label, '标品袜子')

    def test_import_batch_writes_shop_label(self):
        from uuid import uuid4
        from db import get_db
        from repos.import_repo import ImportRepo

        def run(rows):
            batch = {
                'id': uuid4().hex, 'shop_id': 'default', 'source_type': 'product_day',
                'source_filename': 'bi.xlsx', 'source_hash': 'h', 'total_rows': 1, 'valid_rows': 1,
                'invalid_rows': 0, 'quality_summary': '{}',
            }
            # Repo resolves the DB via Flask app config; keep it on the fixture database.
            with self.app.app_context():
                ImportRepo.complete_product_daily_batch(batch, rows)

        run([{
            'shop_id': 'default', 'product_id': 'new-sock', 'date': '2026-04-05',
            'payment_amount': 100, 'product_visitors': 10, 'product_name': '新品袜',
            'shop_label': '标品袜子',
        }])
        with get_db(self.database_path) as connection:
            label = connection.execute(
                'SELECT shop_label FROM products WHERE product_id = ?', ('new-sock',)
            ).fetchone()['shop_label']
        self.assertEqual(label, '标品袜子')
        # 空标签导入不得覆盖已有标签
        run([{
            'shop_id': 'default', 'product_id': 'new-sock', 'date': '2026-04-06',
            'payment_amount': 200, 'product_visitors': 20, 'product_name': '新品袜',
            'shop_label': '',
        }])
        with get_db(self.database_path) as connection:
            label = connection.execute(
                'SELECT shop_label FROM products WHERE product_id = ?', ('new-sock',)
            ).fetchone()['shop_label']
        self.assertEqual(label, '标品袜子')


if __name__ == '__main__':
    unittest.main()

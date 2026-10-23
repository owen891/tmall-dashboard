import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import io

from openpyxl import Workbook

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class ShopScopeApiTests(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict('os.environ', {'TMALL_LEGACY_SHOP_ID': 'legacy-shop'})
        self._env.start()
        self.addCleanup(self._env.stop)
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

    def test_client_shop_id_does_not_change_server_scope(self):
        from flask import request
        from db import get_shop_id

        with self.app.test_request_context('/api/status?shop_id=shop-b'):
            self.assertEqual(get_shop_id(), 'default')

        response = self.client.get(
            '/api/compare?dim=daily&period_a=2026-04-01&period_b=2026-04-02&shop_id=shop-a'
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        response.close()
        self.assertEqual(payload['kpi_compare']['gmv']['period_a'], 100.0)
        self.assertEqual(payload['kpi_compare']['gmv']['period_b'], 120.0)
        self.assertEqual(payload['product_changes'][0]['amount_a'], 100.0)

    def test_trend_products_and_overview_are_scoped_to_requested_shop(self):
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
        # 非 default 店铺不联 paid_detail（join 条件 1=0），这些单店旧指标应当“不可得”，
        # 返回 NULL（前端渲染 `--`），而不是伪造一个真实的 0。
        self.assertIsNone(row['impressions'])
        self.assertIsNone(row['total_orders'])
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
            '/api/overview?start=2026-04-01&end=2026-04-02&lifecycle_stage=growth&shop_id=shop-a',
            '/api/overview/daily-matrix?start=2026-04-01&end=2026-04-02&lifecycle_stage=growth&shop_id=shop-a',
            '/api/health?period=2026-04&shop_id=shop-a',
            '/api/reviews/summary?shop_id=shop-a',
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'UNSUPPORTED_SCOPE')
                response.close()

    def test_non_default_legacy_catalog_writes_fail_closed(self):
        requests = (
            ('PUT', '/api/products/scope-product/field?shop_id=shop-a', {'field': 'tier', 'value': 'A'}),
        )
        for method, url, payload in requests:
            with self.subTest(method=method, url=url):
                response = self.client.open(url, method=method, json=payload)
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

    def test_category_analysis_surfaces_isolate_named_shops_via_daily_data(self):
        """SEC-01：只读 daily_data 的接口必须「按店过滤」，而不是 fail closed。

        2026-10-11 实测：
          services/category_analysis_service.py  source_tables 只有 daily_data
            （:238 与 :295），_aggregate 的 clauses 首项是 'd.shop_id = ?'（:67）
          services/leaf_weekly_service.py        source_tables 是
            ['daily_data', 'products']（:252），每条 SQL 都带 d.shop_id = ?（:99、:141）
        daily_data 是多店表（唯一键含 shop_id），所以命名店铺能被正确隔离，
        返回 200 是正确行为。这里锁定该契约：非默认店铺请求不得返回默认店铺的
        整店数据，也不能被误改成 422（那会让多店部署直接不可用）。
        """
        urls = (
            '/api/category-analysis/compare?start=2026-04-01&end=2026-04-30&shop_id=shop-a',
            '/api/category-analysis/matrix?years=2026&metric=net_sales&shop_id=shop-a',
            '/api/category-analysis/leaf-weekly-board?shop_id=shop-a',
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertIn('data', payload)
                response.close()

    def test_monthly_data_backed_surfaces_fail_closed_for_non_default_shop(self):
        """SEC-04：真正读 monthly_data（无 shop_id 列）的接口必须 fail closed。

        2026-10-11 实测：monthly_data 在 db_migrations.py 建表时就没有 shop_id
        列，所以任何以它为唯一/主要数据源的读接口都无法隔离命名店铺，必须 422。
        这里锁定 product-overview 的 rule-results：api/product_overview_api.py:55
        调用 _reject_named_shop_read()，而该接口在 :86 用
        INNER JOIN monthly_data 取数，属于无法隔离的接口。
        """
        urls = (
            '/api/product-overview/rule-results?shop_id=shop-a',
            '/api/lifecycle/assessments?shop_id=shop-a',
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'UNSUPPORTED_SCOPE')
                response.close()

    def test_product_overview_rules_metadata_is_shop_independent(self):
        """纯元数据接口不读表，因此不该被 scope guard 拦成 422。

        api/product_overview_api.py:44 的 /rules 只调用 list_rules()，而
        services/product_rules_service.py:221 的 list_rules() 返回内存表
        PRODUCT_RULES 的拷贝，完全不碰 monthly_data。给这样的接口加 fail-closed
        会让非默认店铺看不到规则说明，属于过度加锁。

        注意 success() 会把业务载荷包在 data 键下，rules 不在顶层。
        """
        response = self.client.get('/api/product-overview/rules?shop_id=shop-a')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('data', payload)
        self.assertIn('rules', payload['data'])
        self.assertTrue(payload['data']['rules'])
        response.close()

    def test_legacy_shop_scope_guard_is_shared_not_reimplemented(self):
        """每个 legacy 单店接口都必须走同一个 guard，不能各自散落判断。

        历史上 product_overview_api 自己写了一个 _reject_named_shop_read()，
        与 services/shop_scope_service.py 的 reject_legacy_shop_scope() 并存，
        两处的默认店铺白名单必须一致，否则改一处会留下一个能越权的入口。
        """
        from services.shop_scope_service import reject_legacy_shop_scope
        from api import product_overview_api

        with self.app.test_request_context('/api/product-overview/rule-results?shop_id=shop-a'):
            denied = product_overview_api._reject_named_shop_read()
            self.assertIsNotNone(denied)
            self.assertEqual(denied[0].get_json()['code'], 'UNSUPPORTED_SCOPE')

        with self.app.test_request_context('/api/product-overview/rule-results?shop_id=default'):
            self.assertIsNone(product_overview_api._reject_named_shop_read())

        with self.app.test_request_context('/api/x?shop_id=legacy-shop'):
            self.assertIsNone(reject_legacy_shop_scope('probe'))

    def test_no_gbk_mojibake_literals_in_scope_sources(self):
        """api/ services/ repos/ 不得残留 GBK 往返造成的乱码字面量。

        2026-10-11 实测出两处真实坏数据：
          api/product_detail_api.py:804  reject_legacy_shop_scope('鍟嗗搧浜ゆ槗鍒嗘瀽')
          api/product_detail_api.py:826  failure('NOT_FOUND', '鍟嗗搧涓嶅瓨鍦?')
        两者都是 UTF-8 字节被按 GBK 解码再编码（「商品」「交易」「不存在」被
        写成 鍟嗗搧 / 浜ゆ槗 / 涓嶅瓨鍦?）。文件本身仍是合法 UTF-8，所以普通
        读写不会报错，只有字面量本身是坏的——必须靠字符级扫描才抓得住。

        注意：不能用 PowerShell 控制台判断这个问题。中文 Windows 控制台是
        GBK 代码页，会把正确的 UTF-8 输出显示成乱码，从而产生假阳性。
        """
        # 这些是 GBK 往返后出现的特征字符，正常中文源码里不会出现
        mojibake_markers = ('\u935f', '\u6dde\u69d9', '\u6d93\u5b85', '\u93a8')
        offenders = []
        for folder in ('api', 'services', 'repos'):
            directory = os.path.join(PROJECT_ROOT, folder)
            if not os.path.isdir(directory):
                continue
            for name in sorted(os.listdir(directory)):
                if not name.endswith('.py'):
                    continue
                path = os.path.join(directory, name)
                with io.open(path, encoding='utf-8') as handle:
                    text = handle.read()
                for marker in mojibake_markers:
                    if marker in text:
                        offenders.append(f'{folder}/{name}: {marker!r}')
        self.assertEqual(offenders, [], f'发现 GBK 乱码字面量：{offenders}')

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
            '/api/trend?dim=weekly&start=2026-04-01&end=2026-04-07&shop_id=shop-a',
            '/api/compare?dim=monthly&period_a=2026-04&period_b=2026-05&shop_id=shop-a',
            '/api/products?dim=monthly&period=2026-04&shop_id=shop-a',
            '/api/target_progress?dim=monthly&period=2026-04&shop_id=shop-a',
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


def test_primary_shop_legacy_period_endpoints_share_scope_guard(tmp_path, monkeypatch):
    from app import create_app
    from scripts.gate_fixture import seed_database, SHOP_ID
    from unittest.mock import patch
    from services.shop_scope_service import reject_legacy_shop_scope
    database = tmp_path / 'scope-contract.db'
    monkeypatch.setenv('TMALL_LEGACY_SHOP_ID', SHOP_ID)
    app = create_app({'TESTING': True, 'DATABASE_PATH': str(database),
                      'SHOP_ID': SHOP_ID, 'ASSET_RELEASE_ROOT': str(tmp_path / 'assets'),
                      'IMPORT_SCAN_ALLOWED_ROOTS': []})
    seed_database(database)
    paths = ['/api/products?dim=monthly', '/api/trend?dim=monthly',
             '/api/compare?dim=monthly&period_a=2026-08&period_b=2026-09',
             '/api/target_progress?dim=monthly&period=2026-09',
             '/api/products?dim=weekly', '/api/trend?dim=weekly']
    with app.test_client() as client:
        for path in paths:
            with patch('services.shop_scope_service.reject_legacy_shop_scope',
                       wraps=reject_legacy_shop_scope) as guard:
                with client.get(path) as response:
                    assert response.status_code == 200, (path, response.get_json())
                assert guard.called, path
            for shop in ('shop-a', 'shop-b', 'untrusted'):
                with client.get(path + '&shop_id=' + shop) as response:
                    assert response.status_code == 422, (path, shop, response.get_json())
                    assert response.get_json()['code'] == 'UNSUPPORTED_SCOPE'
        with client.get('/api/products?dim=daily&shop_id=shop-a') as response:
            assert response.status_code == 200

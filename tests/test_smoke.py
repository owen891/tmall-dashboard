"""
冒烟测试 — 验证所有 API 路由可达，重构安全网。

运行方式：
    cd e:\\tm数据表格\\tmall-dashboard
    python -m unittest tests.test_smoke -v

设计原则：
- 路由注册验证：通过 Flask url_map 检查所有路由是否注册
- GET 请求：应返回 200 或 404（无数据时允许 404），不应 500
- POST/PUT/DELETE：应返回非 500（路由存在但资源不存在是正常的）
- 只修改一次性测试数据库，不读取或复制用户数据库
"""

import sys
import atexit
import io
import os
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Deterministic empty-schema fixture: importing tests must never read user data.
_TEST_DATA_DIR = tempfile.TemporaryDirectory(prefix='tmall-dashboard-tests-')
atexit.register(_TEST_DATA_DIR.cleanup)
_TEST_DB_PATH = os.path.join(_TEST_DATA_DIR.name, 'dashboard.db')

from app import create_app
from db import get_db
from scripts.gate_fixture import seed_database
app = create_app({'TESTING': True, 'DATABASE_PATH': _TEST_DB_PATH, 'SHOP_ID': 'default'})

#: 事实行必须写对 shop_id，否则会被按店铺过滤掉。
# daily_data.shop_id 的列默认值是 'default'，而这里 app 用的是真实店铺号，
# 不显式写入就会造出「主档有商品、单日事实查不到」的假象，
# 让 /api/products 的 daily+单日区间查询（走 JOIN 事实表）返回 0 条。
_TEST_SHOP_ID = app.config['SHOP_ID']
seed_database(_TEST_DB_PATH)


def _insert_contract_products():
    prefix = f"contract-{uuid.uuid4().hex[:10]}"
    active_id = f"{prefix}-active"
    inactive_id = f"{prefix}-inactive"
    with get_db(_TEST_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO products (product_id, title, tier, style, status, starred) VALUES (?, ?, ?, ?, ?, ?)",
            (active_id, 'Contract Active Product', 'Contract Tier A', 'Contract Style A', 'active', 0)
        )
        conn.execute(
            "INSERT INTO products (product_id, title, tier, style, status, starred) VALUES (?, ?, ?, ?, ?, ?)",
            (inactive_id, 'Contract Inactive Product', 'Contract Tier B', 'Contract Style B', 'inactive', 1)
        )
        conn.execute(
            "INSERT INTO daily_data (shop_id, product_id, date, payment_amount, refund_amount, net_sales, ipv, pv, payment_conversion, ad_spend, ad_roi, buyers, avg_order_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_TEST_SHOP_ID, active_id, '2026-04-01', 100, 0, 100, 10, 20, 0.1, 20, 5, 2, 50)
        )
        conn.execute(
            "INSERT INTO daily_data (shop_id, product_id, date, payment_amount, refund_amount, net_sales, ipv, pv, payment_conversion, ad_spend, ad_roi, buyers, avg_order_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_TEST_SHOP_ID, inactive_id, '2026-04-01', 50, 0, 50, 5, 10, 0.2, 10, 5, 1, 50)
        )
        conn.execute(
            "INSERT INTO operation_actions (product_id, action_date, action_type, action_detail) VALUES (?, ?, ?, ?)",
            (active_id, '2026-04-02', 'active-action', 'included')
        )
        conn.execute(
            "INSERT INTO operation_actions (product_id, action_date, action_type, action_detail) VALUES (?, ?, ?, ?)",
            (inactive_id, '2026-04-02', 'inactive-action', 'filtered')
        )
        conn.execute(
            "INSERT INTO operation_actions (product_id, action_date, action_type, action_detail) VALUES (?, ?, ?, ?)",
            (active_id, '2026-05-02', 'other-period-action', 'filtered')
        )
        conn.commit()
    return active_id, inactive_id


def _get_first_product_id():
    """获取数据库中第一个 product_id，用于测试"""
    try:
        with get_db(_TEST_DB_PATH) as conn:
            row = conn.execute('SELECT product_id FROM products LIMIT 1').fetchone()
            return row[0] if row else 'nonexistent'
    except Exception:
        return 'nonexistent'


class SmokeTestBase(unittest.TestCase):
    """冒烟测试基类"""

    @classmethod
    def setUpClass(cls):
        """Track streamed/file responses until class cleanup closes them."""
        from flask.testing import FlaskClient
        responses = []

        class ClosingClient(FlaskClient):
            def open(self, *args, **kwargs):
                response = super().open(*args, **kwargs)
                responses.append(response)
                return response

        cls.client = ClosingClient(app, app.response_class)
        cls.addClassCleanup(lambda: [response.close() for response in responses])

    def assertGetNoCrash(self, path, params=None):
        """GET 请求不应返回 500（崩溃），允许 200 或 404"""
        resp = self.client.get(path, query_string=params)
        self.assertNotEqual(resp.status_code, 500,
                            f"GET {path} 返回 500 — 服务器崩溃！\n{resp.data[:500]}")
        return resp

    def assertMutationNoCrash(self, method, path, json=None):
        """POST/PUT/DELETE 不应返回 500（崩溃），允许 400/404"""
        if method == 'POST':
            resp = self.client.post(path, json=json or {})
        elif method == 'PUT':
            resp = self.client.put(path, json=json or {})
        elif method == 'DELETE':
            resp = self.client.delete(path, json=json or {})
        else:
            resp = self.client.get(path)
        self.assertNotEqual(resp.status_code, 500,
                            f"{method} {path} 返回 500 — 服务器崩溃！\n{resp.data[:500]}")
        return resp


class TestPageRender(SmokeTestBase):
    """页面渲染测试"""

    def test_index_page(self):
        """首页应正常渲染"""
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'\xe5\xa4\xa9\xe7\x8c\xab', resp.data)  # "天猫" in UTF-8
        resp.close()


class TestKpiEndpoints(SmokeTestBase):
    """KPI 与概览相关端点"""

    def test_status(self):
        self.assertGetNoCrash('/api/status')

    def test_trend(self):
        self.assertGetNoCrash('/api/trend', params={'dim': 'weekly'})
    def test_anomalies(self):
        self.assertGetNoCrash('/api/anomalies', params={'dim': 'weekly'})

    def test_target_progress(self):
        self.assertGetNoCrash('/api/target_progress', params={'period': ''})

    def test_review_data(self):
        self.assertGetNoCrash('/api/review', params={'dim': 'weekly'})


class TestProductEndpoints(SmokeTestBase):
    """商品管理相关端点"""

    def test_products(self):
        self.assertGetNoCrash('/api/products', params={'dim': 'weekly', 'page': 1})

    def test_products_supports_daily_date_range(self):
        response = self.client.get('/api/products', query_string={
            'dim': 'daily',
            'start': '2026-09-10',
            'end': '2026-09-17',
            'limit': 5,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertGreater(payload['data']['total'], 0)
        self.assertTrue(any(row['payment_amount'] > 0 for row in payload['data']['rows']))

    def test_product_field_update(self):
        self.assertMutationNoCrash('PUT', '/api/products/nonexistent/field',
                                   json={'field': 'tier', 'value': 'test'})

    def test_notes_get(self):
        self.assertGetNoCrash('/api/notes/nonexistent')

    def test_notes_add(self):
        """添加备注路由应存在且不崩溃"""
        pid = _get_first_product_id()
        self.assertMutationNoCrash('POST', '/api/notes',
                                   json={'product_id': pid, 'note': 'smoke test'})

    def test_notes_reject_malformed_payloads(self):
        for payload in ([], {'product_id': [], 'note': {}}, {}):
            response = self.client.post('/api/notes', json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')
        response = self.client.post('/api/notes', data='not-json', content_type='text/plain')
        self.assertEqual(response.status_code, 422)

    def test_notes_delete(self):
        self.assertMutationNoCrash('DELETE', '/api/notes/99999')

    def test_product_tags_get(self):
        self.assertGetNoCrash('/api/product_tags', params={'product_id': 'nonexistent'})

    def test_product_tags_add(self):
        self.assertMutationNoCrash('POST', '/api/product_tags',
                                   json={'product_id': 'nonexistent', 'tag': 'test'})

    def test_product_tags_reject_malformed_payloads(self):
        for payload in ([], {'product_id': [], 'tag': {}}, {}):
            response = self.client.post('/api/product_tags', json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')
        response = self.client.post('/api/product_tags', data='not-json', content_type='text/plain')
        self.assertEqual(response.status_code, 422)

    def test_product_tags_delete(self):
        self.assertMutationNoCrash('DELETE', '/api/product_tags/99999')

    def test_legacy_catalog_writes_reject_malformed_payloads(self):
        cases = (
            ('/api/products/missing/field', {'field': [], 'value': {}}),
        )
        for path, payload in cases:
            with self.subTest(path=path):
                response = self.client.post(path, json=payload) if path != '/api/products/missing/field' else self.client.put(path, json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_products_status_filter_uses_same_where_for_data_and_total(self):
        _, inactive_id = _insert_contract_products()
        response = self.client.get('/api/products', query_string={
            'dim': 'daily',
            'start': '2026-04-01',
            'end': '2026-04-01',
            'status': 'inactive',
            'search': inactive_id,
            'limit': 20,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        ids = [row['product_id'] for row in payload['data']['rows']]
        self.assertEqual(payload['data']['total'], 1)
        self.assertEqual(ids, [inactive_id])
        self.assertTrue(all(row['status'] == 'inactive' for row in payload['data']['rows']))

    def test_products_all_status_includes_active_and_inactive(self):
        active_id, inactive_id = _insert_contract_products()
        prefix = active_id.rsplit('-', 1)[0]
        response = self.client.get('/api/products', query_string={
            'dim': 'daily',
            'start': '2026-04-01',
            'end': '2026-04-01',
            'status': 'all',
            'search': prefix,
            'limit': 20,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['data']['total'], 2)
        self.assertEqual({row['product_id'] for row in payload['data']['rows']}, {active_id, inactive_id})

    def test_products_all_status_without_other_filters_is_valid_sql(self):
        response = self.client.get('/api/products', query_string={
            'dim': 'daily', 'start': '2026-04-01', 'end': '2026-04-19', 'status': 'all',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.get_json())

    def test_products_response_includes_global_facets(self):
        active_id, _ = _insert_contract_products()
        response = self.client.get('/api/products', query_string={
            'dim': 'daily',
            'start': '2026-04-01',
            'end': '2026-04-01',
            'search': active_id,
            'limit': 20,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('facets', payload['data'])
        self.assertIn('Contract Tier A', payload['data']['facets']['tiers'])
        self.assertIn('Contract Tier B', payload['data']['facets']['tiers'])
        self.assertIn('Contract Style A', payload['data']['facets']['styles'])
        self.assertIn('Contract Style B', payload['data']['facets']['styles'])
        self.assertIn('active', payload['data']['facets']['statuses'])
        self.assertIn('inactive', payload['data']['facets']['statuses'])


class TestRefundEndpoints(SmokeTestBase):
    """退款分析相关端点"""

    def test_refund_alert(self):
        self.assertGetNoCrash('/api/refund_alert', params={'dim': 'weekly'})


class TestActionEndpoints(SmokeTestBase):
    """运营动作相关端点"""

    def test_actions_list(self):
        self.assertGetNoCrash('/api/actions', params={'dim': 'weekly'})

    def test_action_create(self):
        self.assertMutationNoCrash('POST', '/api/actions', json={
            'product_id': 'nonexistent', 'action_date': '2026-01-01',
            'action_type': 'test', 'action_detail': 'smoke test'
        })

    def test_action_update(self):
        self.assertMutationNoCrash('PUT', '/api/actions/99999', json={
            'action_type': 'test', 'action_detail': 'updated'
        })

    def test_action_delete(self):
        self.assertMutationNoCrash('DELETE', '/api/actions/99999')

class TestAlertEndpoints(SmokeTestBase):
    """预警系统相关端点"""

    def test_alerts_list(self):
        self.assertGetNoCrash('/api/alerts', params={'period': ''})

    def test_alert_dismiss(self):
        self.assertMutationNoCrash('POST', '/api/alerts/99999/dismiss')

    def test_alert_rules_list(self):
        self.assertGetNoCrash('/api/alert_rules')

    def test_alert_rules_create(self):
        self.assertMutationNoCrash('POST', '/api/alert_rules', json={
            'metric': 'refund_rate', 'operator': 'gt',
            'threshold': 0.2, 'level': 'warning'
        })

    def test_alert_rules_reject_malformed_payloads(self):
        for payload in ([], {'metric': [], 'operator': {}, 'threshold': 'not-a-number'}, {}):
            response = self.client.post('/api/alert_rules', json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')
        response = self.client.post('/api/alert_rules', data='not-json', content_type='text/plain')
        self.assertEqual(response.status_code, 422)

    def test_alert_rules_delete(self):
        self.assertMutationNoCrash('DELETE', '/api/alert_rules/99999')

    def test_alert_checks(self):
        self.assertGetNoCrash('/api/alert_checks', params={'dim': 'weekly'})


class TestHealthEndpoints(SmokeTestBase):
    """健康度相关端点"""

    def test_health(self):
        self.assertGetNoCrash('/api/health', params={'dim': 'weekly'})


class TestReviewEndpoints(SmokeTestBase):
    """评价分析相关端点"""

    def test_reviews_summary(self):
        self.assertGetNoCrash('/api/reviews/summary')

    def test_reviews_list(self):
        self.assertGetNoCrash('/api/reviews/list', params={'page': 1})

    def test_reviewed_products(self):
        self.assertGetNoCrash('/api/reviews/products')

class TestCompareEndpoints(SmokeTestBase):
    """周期对比相关端点"""

    def test_compare(self):
        self.assertGetNoCrash('/api/compare', params={'dim': 'weekly'})

    def test_compare_rejects_unknown_dimension(self):
        response = self.client.get('/api/compare', query_string={
            'dim': 'not-real', 'period_a': '2026-07', 'period_b': '2026-08',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_lifecycle(self):
        self.assertGetNoCrash('/api/lifecycle')

    def test_lifecycle_clamps_negative_limit(self):
        response = self.client.get('/api/lifecycle', query_string={'limit': -1})
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.get_json()), 1)


class TestImportEndpoints(SmokeTestBase):
    """数据导入相关端点"""

class TestSystemEndpoints(SmokeTestBase):
    """系统/日志/备份/导出相关端点"""

    def test_periods(self):
        self.assertGetNoCrash('/api/periods', params={'dim': 'weekly'})

    def test_export(self):
        self.assertMutationNoCrash('POST', '/api/export', json={
            'type': 'products', 'dim': 'weekly', 'period': ''
        })

    def test_export_rejects_malformed_payloads(self):
        for payload in ([], {'dim': {'invalid': True}}, {}):
            response = self.client.post('/api/export', json=payload)
            self.assertNotEqual(response.status_code, 500)
            if payload != {}:
                self.assertEqual(response.status_code, 422)
        response = self.client.post('/api/export', data='not-json', content_type='text/plain')
        self.assertEqual(response.status_code, 422)

    def test_logs_get(self):
        self.assertGetNoCrash('/api/logs')

    def test_logs_create(self):
        self.assertMutationNoCrash('POST', '/api/logs', json={
            'action': 'test', 'detail': 'smoke test'
        })

    def test_logs_reject_malformed_payloads(self):
        for payload in ([], {'action': [], 'detail': {}, 'operator': {}}, {}):
            response = self.client.post('/api/logs', json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')
        response = self.client.post('/api/logs', data='not-json', content_type='text/plain')
        self.assertEqual(response.status_code, 422)

class TestChartEventEndpoints(SmokeTestBase):
    """图表事件标注相关端点"""

class TestScheduledTaskEndpoints(SmokeTestBase):
    """定时任务相关端点"""

class TestTaskBoardEndpoints(SmokeTestBase):
    """任务看板相关端点"""

class TestUserKpiEndpoints(SmokeTestBase):
    """用户 KPI 相关端点"""

class TestToolEndpoints(SmokeTestBase):
    """工具箱相关端点"""

    def test_tools_list(self):
        self.assertGetNoCrash('/api/tools/list')

    def test_tools_execute(self):
        self.assertMutationNoCrash('POST', '/api/tools/execute', json={
            'tool_name': 'nonexistent'
        })

    def test_tools_reject_malformed_payloads(self):
        for payload in ([], {'tool_id': 'review_reply', 'params': []}, {'tool_id': 'main_image_suggest', 'params': {'limit': 'bad'}}):
            response = self.client.post('/api/tools/execute', json=payload)
            self.assertNotEqual(response.status_code, 500)
            if payload != []:
                self.assertEqual(response.status_code, 422)
        response = self.client.post('/api/tools/execute', data='not-json', content_type='text/plain')
        self.assertEqual(response.status_code, 422)

    def test_tools_return_structured_errors_for_invalid_execution(self):
        missing = self.client.post('/api/tools/execute', json={
            'tool_id': 'review_reply', 'params': {},
        })
        self.assertEqual(missing.status_code, 422)
        self.assertFalse(missing.get_json()['ok'])
        self.assertEqual(missing.get_json()['code'], 'VALIDATION_ERROR')

        unavailable = self.client.post('/api/tools/execute', json={
            'tool_id': 'main_image_gen', 'params': {},
        })
        self.assertEqual(unavailable.status_code, 409)
        self.assertFalse(unavailable.get_json()['ok'])
        self.assertEqual(unavailable.get_json()['code'], 'TOOL_NOT_AVAILABLE')

        unknown_product = self.client.post('/api/tools/execute', json={
            'tool_id': 'product_diagnose', 'params': {'product_id': '__missing__'},
        })
        self.assertEqual(unknown_product.status_code, 404)
        self.assertFalse(unknown_product.get_json()['ok'])
        self.assertEqual(unknown_product.get_json()['code'], 'NOT_FOUND')

    def test_tools_tasks(self):
        self.assertGetNoCrash('/api/tools/tasks')


class TestRouteRegistry(unittest.TestCase):
    """路由注册验证 — 确保重构后路由不丢失"""

    # 所有期望注册的路由（rule, method）
    # 只列出关键路由，同一 rule 的多个 method 分别列出
    EXPECTED_ROUTES = [
        # 页面
        ('/', 'GET'),
        # KPI 与概览
        ('/api/status', 'GET'),
        ('/api/trend', 'GET'),
        ('/api/anomalies', 'GET'),
        ('/api/target_progress', 'GET'),
        ('/api/review', 'GET'),
        # 商品
        ('/api/products', 'GET'),
        ('/api/products/<product_id>/field', 'PUT'),
        ('/api/notes/<product_id>', 'GET'),
        ('/api/notes', 'POST'),
        ('/api/notes/<int:note_id>', 'DELETE'),
        ('/api/product_tags', 'GET'),
        ('/api/product_tags', 'POST'),
        ('/api/product_tags/<int:tag_id>', 'DELETE'),
        # 推广与退款
        ('/api/refund_alert', 'GET'),
        # 运营动作
        ('/api/actions', 'GET'),
        ('/api/actions', 'POST'),
        ('/api/actions/<int:action_id>', 'PUT'),
        ('/api/actions/<int:action_id>', 'DELETE'),
        # 预警
        ('/api/alerts', 'GET'),
        ('/api/alerts/<int:alert_id>/dismiss', 'POST'),
        ('/api/alert_rules', 'GET'),
        ('/api/alert_rules', 'POST'),
        ('/api/alert_rules/<int:rule_id>', 'DELETE'),
        ('/api/alert_checks', 'GET'),
        # 健康度
        ('/api/health', 'GET'),
        # 评价
        ('/api/reviews/summary', 'GET'),
        ('/api/reviews/list', 'GET'),
        ('/api/reviews/products', 'GET'),
        # 对比与生命周期
        ('/api/compare', 'GET'),
        ('/api/lifecycle', 'GET'),
        # 导入
        # 系统
        ('/api/periods', 'GET'),
        ('/api/export', 'POST'),
        ('/api/logs', 'GET'),
        ('/api/logs', 'POST'),
        # 图表事件
        # 定时任务
        # 任务看板
        # 用户KPI
        # 工具箱
        ('/api/tools/list', 'GET'),
        ('/api/tools/execute', 'POST'),
        ('/api/tools/tasks', 'GET'),
    ]

    def test_all_routes_registered(self):
        """验证所有期望路由都已注册"""
        registered = set()
        for rule in app.url_map.iter_rules():
            for method in rule.methods:
                if method in ('GET', 'POST', 'PUT', 'DELETE'):
                    registered.add((rule.rule, method))

        missing = []
        for rule, method in self.EXPECTED_ROUTES:
            if (rule, method) not in registered:
                missing.append(f"{method} {rule}")

        self.assertEqual(missing, [],
                         f"以下路由未注册（重构后可能丢失）：\n" +
                         "\n".join(f"  - {m}" for m in missing))

    def test_route_count_not_decreased(self):
        """路由+方法组合总数不应减少"""
        registered = set()
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith('/static'):
                continue
            for method in rule.methods:
                if method in ('GET', 'POST', 'PUT', 'DELETE'):
                    registered.add((rule.rule, method))

        # 当前基线：84 个路由+方法组合
        self.assertGreaterEqual(len(registered), len(self.EXPECTED_ROUTES),
                                f"路由+方法组合数 {len(registered)} < 期望 {len(self.EXPECTED_ROUTES)}")


if __name__ == '__main__':
    unittest.main(verbosity=2)

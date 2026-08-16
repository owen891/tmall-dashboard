"""
冒烟测试 — 验证所有 API 路由可达，重构安全网。

运行方式：
    cd e:\\tm数据表格\\tmall-dashboard
    python -m unittest tests.test_smoke -v

设计原则：
- 路由注册验证：通过 Flask url_map 检查所有路由是否注册
- GET 请求：应返回 200 或 404（无数据时允许 404），不应 500
- POST/PUT/DELETE：应返回非 500（路由存在但资源不存在是正常的）
- 不修改任何数据，只读测试
"""

import sys
import os
import shutil
import tempfile
import unittest
import uuid

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mutation smoke tests run against a disposable copy so the checked-in demo
# database remains stable across local and CI test runs.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix='tmall-dashboard-tests-')
_TEST_DB_PATH = os.path.join(_TEST_DATA_DIR, 'dashboard.db')
_SOURCE_DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'dashboard.db')
if os.path.exists(_SOURCE_DB_PATH):
    shutil.copy2(_SOURCE_DB_PATH, _TEST_DB_PATH)
os.environ['TMALL_DB_PATH'] = _TEST_DB_PATH

from app import app
from db import get_db


def _insert_contract_products():
    prefix = f"contract-{uuid.uuid4().hex[:10]}"
    active_id = f"{prefix}-active"
    inactive_id = f"{prefix}-inactive"
    with get_db() as conn:
        conn.execute(
            "INSERT INTO products (product_id, title, tier, style, status, starred) VALUES (?, ?, ?, ?, ?, ?)",
            (active_id, 'Contract Active Product', 'Contract Tier A', 'Contract Style A', 'active', 0)
        )
        conn.execute(
            "INSERT INTO products (product_id, title, tier, style, status, starred) VALUES (?, ?, ?, ?, ?, ?)",
            (inactive_id, 'Contract Inactive Product', 'Contract Tier B', 'Contract Style B', 'inactive', 1)
        )
        conn.execute(
            "INSERT INTO daily_data (product_id, date, payment_amount, refund_amount, net_sales, ipv, pv, payment_conversion, ad_spend, ad_roi, buyers, avg_order_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (active_id, '2026-04-01', 100, 0, 100, 10, 20, 0.1, 20, 5, 2, 50)
        )
        conn.execute(
            "INSERT INTO daily_data (product_id, date, payment_amount, refund_amount, net_sales, ipv, pv, payment_conversion, ad_spend, ad_roi, buyers, avg_order_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (inactive_id, '2026-04-01', 50, 0, 50, 5, 10, 0.2, 10, 5, 1, 50)
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
        with get_db() as conn:
            row = conn.execute('SELECT product_id FROM products LIMIT 1').fetchone()
            return row[0] if row else 'nonexistent'
    except Exception:
        return 'nonexistent'


class SmokeTestBase(unittest.TestCase):
    """冒烟测试基类"""

    @classmethod
    def setUpClass(cls):
        """创建测试客户端，复用现有数据库"""
        app.config['TESTING'] = True
        cls.client = app.test_client()

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

    def test_kpi(self):
        self.assertGetNoCrash('/api/kpi', params={'dim': 'weekly', 'period': ''})

    def test_trend(self):
        self.assertGetNoCrash('/api/trend', params={'dim': 'weekly'})

    def test_multi_trend(self):
        self.assertGetNoCrash('/api/multi_trend', params={'dim': 'weekly', 'periods': ''})

    def test_anomalies(self):
        self.assertGetNoCrash('/api/anomalies', params={'dim': 'weekly'})

    def test_target_progress(self):
        self.assertGetNoCrash('/api/target_progress', params={'period': ''})

    def test_product_target_progress(self):
        self.assertGetNoCrash('/api/product_target_progress', params={'period': ''})

    def test_customer_analysis(self):
        self.assertGetNoCrash('/api/customer_analysis', params={'dim': 'weekly'})

    def test_funnel(self):
        self.assertGetNoCrash('/api/funnel', params={'dim': 'weekly'})

    def test_industry_benchmark(self):
        self.assertGetNoCrash('/api/industry_benchmark', params={'dim': 'weekly'})

    def test_report(self):
        self.assertGetNoCrash('/api/report', params={'dim': 'weekly'})

    def test_review_data(self):
        self.assertGetNoCrash('/api/review', params={'dim': 'weekly'})


class TestProductEndpoints(SmokeTestBase):
    """商品管理相关端点"""

    def test_products(self):
        self.assertGetNoCrash('/api/products', params={'dim': 'weekly', 'page': 1})

    def test_products_supports_daily_date_range(self):
        response = self.client.get('/api/products', query_string={
            'dim': 'daily',
            'start': '2026-04-01',
            'end': '2026-04-19',
            'limit': 5,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertGreater(payload['data']['total'], 0)
        self.assertTrue(any(row['payment_amount'] > 0 for row in payload['data']['rows']))

    def test_star_route(self):
        self.assertMutationNoCrash('POST', '/api/star', json={'product_id': 'nonexistent'})

    def test_product_field_update(self):
        self.assertMutationNoCrash('PUT', '/api/products/nonexistent/field',
                                   json={'field': 'tier', 'value': 'test'})

    def test_batch_update(self):
        self.assertMutationNoCrash('POST', '/api/batch_update',
                                   json={'product_ids': [], 'field': 'tier', 'value': ''})

    def test_notes_get(self):
        self.assertGetNoCrash('/api/notes/nonexistent')

    def test_notes_add(self):
        """添加备注路由应存在且不崩溃"""
        pid = _get_first_product_id()
        self.assertMutationNoCrash('POST', '/api/notes',
                                   json={'product_id': pid, 'note': 'smoke test'})

    def test_notes_delete(self):
        self.assertMutationNoCrash('DELETE', '/api/notes/99999')

    def test_product_tags_get(self):
        self.assertGetNoCrash('/api/product_tags', params={'product_id': 'nonexistent'})

    def test_product_tags_add(self):
        self.assertMutationNoCrash('POST', '/api/product_tags',
                                   json={'product_id': 'nonexistent', 'tag': 'test'})

    def test_product_tags_delete(self):
        self.assertMutationNoCrash('DELETE', '/api/product_tags/99999')

    def test_batch_tags_add(self):
        self.assertMutationNoCrash('POST', '/api/batch_tags',
                                   json={'product_ids': [], 'tags': []})

    def test_batch_tags_delete(self):
        self.assertMutationNoCrash('DELETE', '/api/batch_tags',
                                   json={'product_ids': [], 'tags': []})

    def test_star_explicit_set_is_idempotent(self):
        active_id, _ = _insert_contract_products()
        first = self.client.post('/api/star', json={'product_id': active_id, 'starred': 1})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()['starred'], 1)

        second = self.client.post('/api/star', json={'product_id': active_id, 'starred': 1})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json()['starred'], 1)

        with get_db() as conn:
            row = conn.execute('SELECT starred FROM products WHERE product_id = ?', (active_id,)).fetchone()
        self.assertEqual(row[0], 1)

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


class TestAdEndpoints(SmokeTestBase):
    """推广分析相关端点"""

    def test_ad_performance(self):
        self.assertGetNoCrash('/api/ad_performance', params={'dim': 'weekly'})

    def test_ad_alerts(self):
        self.assertGetNoCrash('/api/ad_alerts', params={'dim': 'weekly'})

    def test_ad_trend(self):
        self.assertGetNoCrash('/api/ad_trend', params={'dim': 'weekly'})

    def test_ad_trend_monthly_with_active_product_join(self):
        response = self.client.get('/api/ad_trend', query_string={'dim': 'monthly', 'period': '2026-03'})
        self.assertEqual(response.status_code, 200)


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

    def test_action_stats(self):
        self.assertGetNoCrash('/api/action_stats', params={'dim': 'weekly'})

    def test_actions_list_filters_product_id_with_period(self):
        active_id, _ = _insert_contract_products()
        response = self.client.get('/api/legacy/actions', query_string={
            'period': '2026-04',
            'product_id': active_id,
            'limit': 20,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([row['product_id'] for row in payload], [active_id])
        self.assertEqual([row['action_type'] for row in payload], ['active-action'])

    def test_actions_list_clamps_negative_limit(self):
        response = self.client.get('/api/legacy/actions', query_string={'limit': -1})
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.get_json()), 1)


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

    def test_review_upload(self):
        self.assertMutationNoCrash('POST', '/api/upload/reviews')


class TestMarketEndpoints(SmokeTestBase):
    """市场分析相关端点"""

    def test_market_summary(self):
        self.assertGetNoCrash('/api/market/summary')

    def test_market_keywords(self):
        self.assertGetNoCrash('/api/market/keywords')

    def test_market_need_stats(self):
        self.assertGetNoCrash('/api/market/need_stats')

    def test_market_rankings(self):
        self.assertGetNoCrash('/api/market/rankings')

    def test_market_histograms(self):
        self.assertGetNoCrash('/api/market/histograms')

    def test_market_opportunities(self):
        self.assertGetNoCrash('/api/market/opportunities')

    def test_market_reports(self):
        self.assertGetNoCrash('/api/market/reports')

    def test_market_upload(self):
        self.assertMutationNoCrash('POST', '/api/upload/market')


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

    def test_upload_data(self):
        self.assertMutationNoCrash('POST', '/api/upload/data')

    def test_import_progress(self):
        self.assertGetNoCrash('/api/import_progress/nonexistent')

    def test_upload_keywords(self):
        self.assertMutationNoCrash('POST', '/api/upload/keywords')


class TestSystemEndpoints(SmokeTestBase):
    """系统/日志/备份/导出相关端点"""

    def test_periods(self):
        self.assertGetNoCrash('/api/periods', params={'dim': 'weekly'})

    def test_backup(self):
        response = self.assertMutationNoCrash('POST', '/api/backup')
        self.assertEqual(response.get_json(), {'success': True, 'skipped': 'testing'})

    def test_export(self):
        self.assertMutationNoCrash('POST', '/api/export', json={
            'type': 'products', 'dim': 'weekly', 'period': ''
        })

    def test_logs_get(self):
        self.assertGetNoCrash('/api/logs')

    def test_logs_create(self):
        self.assertMutationNoCrash('POST', '/api/logs', json={
            'action': 'test', 'detail': 'smoke test'
        })

    def test_traffic_structure(self):
        self.assertGetNoCrash('/api/traffic_structure', params={'dim': 'weekly'})

    def test_shop_target(self):
        self.assertMutationNoCrash('POST', '/api/targets/shop', json={
            'period': '2026-08', 'target_gsv': 100000
        })


class TestChartEventEndpoints(SmokeTestBase):
    """图表事件标注相关端点"""

    def test_chart_events_get(self):
        self.assertGetNoCrash('/api/chart_events')

    def test_chart_events_create(self):
        self.assertMutationNoCrash('POST', '/api/chart_events', json={
            'event_date': '2026-01-01', 'title': 'smoke test'
        })

    def test_chart_events_delete(self):
        self.assertMutationNoCrash('DELETE', '/api/chart_events/99999')


class TestScheduledTaskEndpoints(SmokeTestBase):
    """定时任务相关端点"""

    def test_scheduled_tasks_list(self):
        self.assertGetNoCrash('/api/scheduled_tasks')

    def test_scheduled_tasks_create(self):
        self.assertMutationNoCrash('POST', '/api/scheduled_tasks', json={
            'task_name': 'smoke test', 'cron_expr': '0 8 * * *'
        })

    def test_scheduled_tasks_update(self):
        self.assertMutationNoCrash('PUT', '/api/scheduled_tasks/99999', json={
            'task_name': 'updated'
        })

    def test_scheduled_tasks_delete(self):
        self.assertMutationNoCrash('DELETE', '/api/scheduled_tasks/99999')

    def test_scheduled_tasks_run(self):
        self.assertMutationNoCrash('POST', '/api/scheduled_tasks/99999/run')


class TestTaskBoardEndpoints(SmokeTestBase):
    """任务看板相关端点"""

    def test_tasks_list(self):
        self.assertGetNoCrash('/api/tasks')

    def test_tasks_create(self):
        self.assertMutationNoCrash('POST', '/api/tasks', json={
            'title': 'smoke test task'
        })

    def test_tasks_update(self):
        response = self.assertMutationNoCrash('PUT', '/api/tasks/99999', json={
            'title': 'updated'
        })
        self.assertEqual(response.status_code, 404)

    def test_tasks_delete(self):
        response = self.assertMutationNoCrash('DELETE', '/api/tasks/99999')
        self.assertEqual(response.status_code, 404)


class TestUserKpiEndpoints(SmokeTestBase):
    """用户 KPI 相关端点"""

    def test_user_kpis_list(self):
        self.assertGetNoCrash('/api/user_kpis')

    def test_user_kpis_create(self):
        self.assertMutationNoCrash('POST', '/api/user_kpis', json={
            'user_name': 'test', 'period': '2026-08'
        })

    def test_user_kpis_update(self):
        response = self.assertMutationNoCrash('PUT', '/api/user_kpis/99999', json={
            'user_name': 'updated'
        })
        self.assertEqual(response.status_code, 404)

    def test_user_kpis_delete(self):
        response = self.assertMutationNoCrash('DELETE', '/api/user_kpis/99999')
        self.assertEqual(response.status_code, 404)


class TestKeywordsEndpoints(SmokeTestBase):
    """搜索关键词相关端点"""

    def test_keywords_list(self):
        self.assertGetNoCrash('/api/keywords')


class TestToolEndpoints(SmokeTestBase):
    """工具箱相关端点"""

    def test_tools_list(self):
        self.assertGetNoCrash('/api/tools/list')

    def test_tools_execute(self):
        self.assertMutationNoCrash('POST', '/api/tools/execute', json={
            'tool_name': 'nonexistent'
        })

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
        ('/api/kpi', 'GET'),
        ('/api/trend', 'GET'),
        ('/api/multi_trend', 'GET'),
        ('/api/anomalies', 'GET'),
        ('/api/target_progress', 'GET'),
        ('/api/product_target_progress', 'GET'),
        ('/api/customer_analysis', 'GET'),
        ('/api/funnel', 'GET'),
        ('/api/industry_benchmark', 'GET'),
        ('/api/report', 'GET'),
        ('/api/review', 'GET'),
        # 商品
        ('/api/products', 'GET'),
        ('/api/star', 'POST'),
        ('/api/products/<product_id>/field', 'PUT'),
        ('/api/batch_update', 'POST'),
        ('/api/notes/<product_id>', 'GET'),
        ('/api/notes', 'POST'),
        ('/api/notes/<int:note_id>', 'DELETE'),
        ('/api/product_tags', 'GET'),
        ('/api/product_tags', 'POST'),
        ('/api/product_tags/<int:tag_id>', 'DELETE'),
        ('/api/batch_tags', 'POST'),
        ('/api/batch_tags', 'DELETE'),
        # 推广与退款
        ('/api/ad_performance', 'GET'),
        ('/api/ad_alerts', 'GET'),
        ('/api/ad_trend', 'GET'),
        ('/api/refund_alert', 'GET'),
        # 运营动作
        ('/api/actions', 'GET'),
        ('/api/actions', 'POST'),
        ('/api/actions/<int:action_id>', 'PUT'),
        ('/api/actions/<int:action_id>', 'DELETE'),
        ('/api/action_stats', 'GET'),
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
        ('/api/upload/reviews', 'POST'),
        ('/api/reviews/summary', 'GET'),
        ('/api/reviews/list', 'GET'),
        ('/api/reviews/products', 'GET'),
        # 市场
        ('/api/upload/market', 'POST'),
        ('/api/market/summary', 'GET'),
        ('/api/market/keywords', 'GET'),
        ('/api/market/need_stats', 'GET'),
        ('/api/market/rankings', 'GET'),
        ('/api/market/histograms', 'GET'),
        ('/api/market/opportunities', 'GET'),
        ('/api/market/reports', 'GET'),
        # 对比与生命周期
        ('/api/compare', 'GET'),
        ('/api/lifecycle', 'GET'),
        # 导入
        ('/api/upload/data', 'POST'),
        ('/api/import_progress/<task_id>', 'GET'),
        ('/api/upload/keywords', 'POST'),
        # 系统
        ('/api/periods', 'GET'),
        ('/api/backup', 'POST'),
        ('/api/export', 'POST'),
        ('/api/logs', 'GET'),
        ('/api/logs', 'POST'),
        ('/api/traffic_structure', 'GET'),
        ('/api/targets/shop', 'POST'),
        # 图表事件
        ('/api/chart_events', 'GET'),
        ('/api/chart_events', 'POST'),
        ('/api/chart_events/<int:event_id>', 'DELETE'),
        # 定时任务
        ('/api/scheduled_tasks', 'GET'),
        ('/api/scheduled_tasks', 'POST'),
        ('/api/scheduled_tasks/<int:task_id>', 'PUT'),
        ('/api/scheduled_tasks/<int:task_id>', 'DELETE'),
        ('/api/scheduled_tasks/<int:task_id>/run', 'POST'),
        # 任务看板
        ('/api/tasks', 'GET'),
        ('/api/tasks', 'POST'),
        ('/api/tasks/<int:task_id>', 'PUT'),
        ('/api/tasks/<int:task_id>', 'DELETE'),
        # 用户KPI
        ('/api/user_kpis', 'GET'),
        ('/api/user_kpis', 'POST'),
        ('/api/user_kpis/<int:kpi_id>', 'PUT'),
        ('/api/user_kpis/<int:kpi_id>', 'DELETE'),
        # 关键词
        ('/api/keywords', 'GET'),
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

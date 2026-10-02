"""辅助目标（净利润/推广费/净费比）链路测试：goals API 预置 → 复盘目标表回退。

对齐 XMind「下月规划-目标规划」：销售额走年度守恒分配，其余指标按月独立预置，
复盘页在未手填时自动读取（来源标记 goals_page）。
"""
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class GoalsMetricTargetsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-goals-metric-tests-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from app import create_app

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        self.client = self.app.test_client()
        # 创建年度目标，goal_versions 才有行。
        status, _ = self.request('POST', '/api/goals', json={'year': 2026, 'annual_target': 36500})
        assert status == 201, status

    def tearDown(self):
        self.temp_dir.cleanup()

    def request(self, method, path, **kwargs):
        response = self.client.open(path, method=method, **kwargs)
        payload = response.get_json()
        status = response.status_code
        response.close()
        return status, payload

    def test_set_and_read_metric_targets(self):
        status, payload = self.request('POST', '/api/goals/2026/metric-targets', json={
            'period_type': 'month', 'period_key': '2026-10',
            'targets': {'profit': 20000, 'ad_spend': 130000, 'net_expense_ratio': 23.7},
        })

        self.assertEqual(status, 201)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['targets']['profit'], 20000)

        status, periods = self.request('GET', '/api/goals/2026/periods')
        self.assertEqual(status, 200)
        targets = periods['data']['metric_targets'].get('2026-10', {})
        self.assertEqual(targets['profit'], 20000)
        self.assertEqual(targets['ad_spend'], 130000)
        self.assertEqual(targets['net_expense_ratio'], 23.7)

    def test_upsert_overwrites_and_null_clears(self):
        self.request('POST', '/api/goals/2026/metric-targets', json={
            'period_type': 'month', 'period_key': '2026-10',
            'targets': {'profit': 10000, 'ad_spend': 100000},
        })
        # 覆盖 profit、清除 ad_spend。
        status, payload = self.request('POST', '/api/goals/2026/metric-targets', json={
            'period_type': 'month', 'period_key': '2026-10',
            'targets': {'profit': 20000, 'ad_spend': None},
        })

        self.assertEqual(status, 201)
        status, periods = self.request('GET', '/api/goals/2026/periods')
        targets = periods['data']['metric_targets'].get('2026-10', {})
        self.assertEqual(targets.get('profit'), 20000)
        self.assertNotIn('ad_spend', targets)

    def test_invalid_metric_and_negative_value_rejected(self):
        status, _ = self.request('POST', '/api/goals/2026/metric-targets', json={
            'period_type': 'month', 'period_key': '2026-10',
            'targets': {'unknown_metric': 1},
        })
        self.assertEqual(status, 422)

        status, _ = self.request('POST', '/api/goals/2026/metric-targets', json={
            'period_type': 'month', 'period_key': '2026-10',
            'targets': {'profit': -5},
        })
        self.assertEqual(status, 422)

    def test_bad_period_key_rejected(self):
        status, _ = self.request('POST', '/api/goals/2026/metric-targets', json={
            'period_type': 'month', 'period_key': '2026-13',
            'targets': {'profit': 1},
        })
        self.assertEqual(status, 422)


class TargetRowsPresetFallbackTests(unittest.TestCase):
    def _rows(self, current, saved, preset):
        from services.period_context import _target_rows
        return {row['key']: row for row in _target_rows(current, saved, preset_targets=preset)}

    def test_review_value_wins_and_preset_fills_gap(self):
        rows = self._rows(
            {'net_sales': 70000, 'profit': -16000, 'ad_spend': 146000, 'net_expense_ratio': 0.203},
            {'target_amount': 80000},  # 复盘手填了销售额目标
            {'profit': 20000, 'ad_spend': 130000},
        )
        self.assertEqual(rows['net_sales']['target'], 80000)
        self.assertEqual(rows['net_sales']['target_source'], 'review')
        self.assertEqual(rows['profit']['target'], 20000)
        self.assertEqual(rows['profit']['target_source'], 'goals_page')
        self.assertEqual(rows['ad_spend']['target'], 130000)
        self.assertEqual(rows['ad_spend']['target_source'], 'goals_page')
        self.assertIsNone(rows['net_expense_ratio']['target'])
        self.assertIsNone(rows['net_expense_ratio']['target_source'])
        # 净费比达成率仍是倒数口径（目标÷实际）。
        self.assertIsNone(rows['net_expense_ratio']['achieved_rate'])
        self.assertAlmostEqual(rows['profit']['achieved_rate'], -16000 / 20000, places=6)

    def test_no_targets_stay_none_not_zero(self):
        rows = self._rows({'net_sales': 70000, 'profit': 0, 'ad_spend': 0, 'net_expense_ratio': 0},
                          None, None)
        for key in ('net_sales', 'profit', 'ad_spend', 'net_expense_ratio'):
            self.assertIsNone(rows[key]['target'])
            self.assertIsNone(rows[key]['achieved_rate'])


if __name__ == '__main__':
    unittest.main()

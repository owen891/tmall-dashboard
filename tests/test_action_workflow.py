import os
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class ActionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-dashboard-actions-tests-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from app import create_app
        from db import get_db

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        self.client = self.app.test_client()
        self.get_db = get_db
        with self.get_db(self.database_path) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('action-a', '动作商品')")
            connection.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def request(self, method, path, **kwargs):
        response = self.client.open(path, method=method, **kwargs)
        payload = response.get_json()
        status = response.status_code
        response.close()
        return status, payload

    def create_action(self, window=2):
        status, payload = self.request('POST', '/api/actions', json={
            'product_id': 'action-a', 'purpose_type': 'increase_sales',
            'purpose_note': '验证图片优化', 'action_type': 'image_change',
            'action_detail': '更换主图', 'target_metric': 'payment_amount',
            'expected_change': 0.1, 'planned_at': '2026-04-03',
            'observer_window_days': window, 'assigned_to': 'operator',
        })
        self.assertEqual(status, 201)
        return payload['data']['id']

    def transition(self, action_id, target, **extra):
        status, current = self.request('GET', f'/api/actions?product_id=action-a')
        self.assertEqual(status, 200)
        action = next(item for item in current['data'] if item['id'] == action_id)
        return self.request('POST', f'/api/actions/{action_id}/transition', json={'status': target, 'version': action['version'], **extra})

    def test_transition_requires_review_before_completion_and_block_reason(self):
        action_id = self.create_action()
        for target in ('pending_execution', 'executing', 'observing', 'pending_review'):
            status, _ = self.transition(action_id, target)
            self.assertEqual(status, 200)

        status, rejected = self.transition(action_id, 'completed')
        self.assertEqual(status, 422)
        self.assertEqual(rejected['code'], 'VALIDATION_ERROR')

        status, blocked = self.transition(action_id, 'blocked')
        self.assertEqual(status, 422)
        self.assertEqual(blocked['code'], 'VALIDATION_ERROR')

        status, blocked = self.transition(
            action_id, 'blocked', blocked_reason='等待素材', expected_recovery_at='2026-04-10',
        )
        self.assertEqual(status, 200)
        self.assertEqual(blocked['data']['status'], 'blocked')

    def test_invalid_action_dates_and_windows_return_validation_error(self):
        base = {
            'product_id': 'action-a', 'purpose_type': 'increase_sales', 'purpose_note': '测试',
            'action_type': 'image_change', 'action_detail': '测试', 'target_metric': 'payment_amount',
            'planned_at': '2026-04-03', 'observer_window_days': 2,
        }
        for field, value in (('planned_at', '2026/04/03'), ('observer_window_days', 'abc'), ('observer_window_days', 366)):
            response = self.client.post('/api/actions', json={**base, field: value})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.get_json()['code'], 'VALIDATION_ERROR')

    def test_review_false_string_is_not_treated_as_true(self):
        action_id = self.create_action(window=1)
        for target in ('pending_execution', 'executing', 'observing'):
            self.transition(action_id, target)
        with self.get_db(self.database_path) as connection:
            connection.executemany(
                '''INSERT INTO daily_data (product_id, date, payment_amount)
                   VALUES (?, ?, ?)''',
                [('action-a', '2026-04-02', 10), ('action-a', '2026-04-04', 20)],
            )
            connection.commit()
        status, recalculated = self.request('POST', '/api/actions/recalculate')
        self.assertEqual(status, 200)
        current = recalculated['data']['actions'][0]
        status, reviewed = self.request('POST', f'/api/actions/{action_id}/review', json={
            'version': current['version'], 'effective': 'false', 'reason': '无效',
            'conclusion': '无效', 'next_action': '停止', 'reviewer': 'operator',
        })
        self.assertEqual(status, 200)
        self.assertEqual(reviewed['data']['review_effective'], 0)

    def test_action_list_uses_standard_envelope(self):
        self.create_action()
        status, payload = self.request('GET', '/api/actions?product_id=action-a')
        self.assertEqual(status, 200)
        self.assertTrue(payload['ok'])
        self.assertIsInstance(payload['data'], list)

    def test_action_list_supports_pending_review_filter_and_includes_history(self):
        action_id = self.create_action()
        status, listed = self.request('GET', '/api/actions?status=pending_review')
        self.assertEqual(status, 200)
        self.assertEqual(listed['data'], [])
        for target in ('pending_execution', 'executing', 'observing'):
            self.transition(action_id, target)
        status, listed = self.request('GET', '/api/actions?status=observing')
        self.assertEqual(status, 200)
        self.assertTrue(listed['data'][0]['action_detail'])
        self.assertGreaterEqual(len(listed['data'][0]['history']), 2)

    def test_unfiltered_action_list_preserves_legacy_all_status_contract(self):
        action_id = self.create_action()
        status, listed = self.request('GET', '/api/actions')
        self.assertEqual(status, 200)
        self.assertEqual([item['id'] for item in listed['data']], [action_id])

    def test_legacy_action_mutations_are_read_only(self):
        for method, path in (
            ('POST', '/api/legacy/actions'),
            ('PUT', '/api/legacy/actions/1'),
            ('DELETE', '/api/legacy/actions/1'),
        ):
            status, payload = self.request(method, path, json={})
            self.assertEqual(status, 409)
            self.assertEqual(payload['code'], 'LEGACY_READ_ONLY')

        response = self.client.get('/api/legacy/actions')
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_new_action_writes_only_product_actions(self):
        action_id = self.create_action()
        with self.get_db(self.database_path) as connection:
            product_count = connection.execute('SELECT COUNT(*) FROM product_actions WHERE id = ?', (action_id,)).fetchone()[0]
            legacy_count = connection.execute('SELECT COUNT(*) FROM operation_actions').fetchone()[0]
        self.assertEqual(product_count, 1)
        self.assertEqual(legacy_count, 0)

    def test_formal_action_boundary_rejects_unknown_product_and_capability(self):
        payload = {
            'product_id': 'missing-product', 'purpose_type': 'increase_sales', 'purpose_note': 'x',
            'action_type': 'image_change', 'action_detail': 'x', 'target_metric': 'payment_amount',
            'planned_at': '2026-04-03', 'observer_window_days': 7,
        }
        status, result = self.request('POST', '/api/actions', json=payload)
        self.assertEqual(status, 404)
        self.assertEqual(result['code'], 'NOT_FOUND')
        payload['product_id'] = 'action-a'; payload['capability_key'] = 'settings.configure_templates'
        status, result = self.request('POST', '/api/actions', json=payload)
        self.assertEqual(status, 403)
        self.assertEqual(result['code'], 'FORBIDDEN')

    def test_workflow_mutations_reject_wrong_capability(self):
        action_id = self.create_action()
        status, result = self.request('POST', f'/api/actions/{action_id}/transition', json={
            'status': 'pending_execution', 'version': 1, 'capability_key': 'settings.configure_templates',
        })
        self.assertEqual(status, 403)
        self.assertEqual(result['code'], 'FORBIDDEN')
        status, result = self.request('POST', '/api/actions/recalculate', json={
            'capability_key': 'settings.configure_templates',
        })
        self.assertEqual(status, 403)
        self.assertEqual(result['code'], 'FORBIDDEN')
        self.transition(action_id, 'pending_execution')
        self.transition(action_id, 'executing')
        self.transition(action_id, 'observing')
        self.transition(action_id, 'pending_review')
        status, result = self.request('POST', f'/api/actions/{action_id}/review', json={
            'version': 5, 'effective': True, 'reason': 'x', 'conclusion': 'x', 'next_action': 'x', 'reviewer': 'x',
            'capability_key': 'settings.configure_templates',
        })
        self.assertEqual(status, 403)
        self.assertEqual(result['code'], 'FORBIDDEN')

    def test_batch_creation_shares_group_and_history_tracks_transitions(self):
        status, created = self.request('POST', '/api/actions/batch', json={
            'product_ids': ['action-a'], 'purpose_type': 'increase_sales', 'purpose_note': '批量验证',
            'action_type': 'price_change', 'action_detail': '调整价格', 'target_metric': 'payment_amount',
            'planned_at': '2026-04-03', 'observer_window_days': 2,
        })
        self.assertEqual(status, 201)
        action = created['data']['actions'][0]
        self.assertTrue(action['action_group_id'])
        status, _ = self.transition(action['id'], 'pending_execution')
        self.assertEqual(status, 200)
        status, history = self.request('GET', f"/api/actions/{action['id']}/history")
        self.assertEqual(status, 200)
        self.assertEqual(history['data'][-1]['to_status'], 'pending_execution')

    def test_recalculation_waits_for_full_windows_then_enables_review(self):
        action_id = self.create_action(window=2)
        for target in ('pending_execution', 'executing', 'observing'):
            status, _ = self.transition(action_id, target)
            self.assertEqual(status, 200)

        status, incomplete = self.request('POST', '/api/actions/recalculate')
        self.assertEqual(status, 200)
        self.assertEqual(incomplete['data']['updated_count'], 0)
        status, observing = self.request('GET', '/api/actions?product_id=action-a')
        self.assertIn('数据不完整', observing['data'][0]['calculation_note'])

        with self.get_db(self.database_path) as connection:
            connection.executemany(
                '''INSERT INTO daily_data (product_id, date, payment_amount)
                   VALUES (?, ?, ?)''',
                [
                    ('action-a', '2026-04-01', 100), ('action-a', '2026-04-02', 200),
                    ('action-a', '2026-04-04', 150), ('action-a', '2026-04-05', 210),
                ],
            )
            connection.commit()

        status, calculated = self.request('POST', '/api/actions/recalculate')
        self.assertEqual(status, 200)
        self.assertEqual(calculated['data']['updated_count'], 1)
        self.assertEqual(calculated['data']['actions'][0]['status'], 'pending_review')
        self.assertEqual(calculated['data']['actions'][0]['before_metric_value'], 150.0)
        self.assertEqual(calculated['data']['actions'][0]['after_metric_value'], 180.0)

        status, reviewed = self.request('POST', f'/api/actions/{action_id}/review', json={
            'version': calculated['data']['actions'][0]['version'], 'effective': True, 'reason': '支付金额提升', 'conclusion': '主图保留',
            'next_action': '继续观察', 'reviewer': 'operator',
        })
        self.assertEqual(status, 200)
        self.assertEqual(reviewed['data']['status'], 'completed')

        status, reopened = self.transition(action_id, 'pending_review')
        self.assertEqual(status, 200)
        self.assertEqual(reopened['data']['status'], 'pending_review')


if __name__ == '__main__':
    unittest.main(verbosity=2)

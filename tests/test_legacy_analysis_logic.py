import os
import tempfile
import unittest


class LegacyAnalysisLogicTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-analysis-logic-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from app import create_app

        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        self.client = self.app.test_client()

        from db import get_db
        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO monthly_data (
                    product_id, month, visitors, buyers, new_buyers,
                    page_views, cart_qty, fav_users, payment_qty
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                ('monthly-a', '2026-08', 100, 20, 8, 300, 40, 10, 15),
            )
            connection.execute(
                '''INSERT INTO daily_data (
                    product_id, date, ipv, pv, buyers,
                    new_payment_buyers, returning_payment_buyers,
                    cart_qty, fav_users, payment_qty
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                ('daily-a', '2026-08-20', 100, 300, 20, 3, 17, 40, 10, 15),
            )
            connection.execute(
                '''INSERT INTO weekly_data (
                    product_id, week_start, ipv, pv
                ) VALUES (?, ?, ?, ?)''',
                ('weekly-a', '2026-08-17', 100, 300),
            )
            connection.execute(
                '''INSERT INTO weekly_data (
                    product_id, week_start, ipv, pv
                ) VALUES (?, ?, ?, ?)''',
                ('weekly-b', '2026-08-24', 100, 300),
            )
            connection.execute(
                '''INSERT INTO store_daily_facts (
                    shop_id, date, product_visitors, payment_buyers,
                    returning_payment_buyers
                ) VALUES (?, ?, ?, ?, ?)''',
                ('default', '2026-08-20', 100, 20, 12),
            )
            connection.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_customer_analysis_uses_buyer_denominator_and_real_daily_split(self):
        monthly = self.client.get(
            '/api/customer_analysis?dim=monthly&period=2026-08'
        ).get_json()
        self.assertEqual(monthly['new_buyers'], 8)
        self.assertEqual(monthly['returning_buyers'], 12)
        self.assertEqual(monthly['new_ratio'], 0.4)
        self.assertEqual(monthly['returning_ratio'], 0.6)
        self.assertEqual(monthly['availability'], 'partial')
        self.assertTrue(any('跨日去重' in item for item in monthly['limitations']))
        self.assertIsNone(monthly['prev_new_ratio'])
        self.assertIsNone(monthly['prev_returning_ratio'])

        daily = self.client.get(
            '/api/customer_analysis?dim=daily&period=2026-08-20'
        ).get_json()
        self.assertEqual(daily['new_buyers'], 8)
        self.assertEqual(daily['returning_buyers'], 12)
        self.assertEqual(daily['new_ratio'], 0.4)
        self.assertEqual(daily['returning_ratio'], 0.6)

    def test_customer_analysis_does_not_invent_weekly_customer_split(self):
        payload = self.client.get(
            '/api/customer_analysis?dim=weekly&period=2026-08-24'
        ).get_json()
        self.assertEqual(payload['availability'], 'missing-fields')
        self.assertIsNone(payload['new_buyers'])
        self.assertIsNone(payload['returning_buyers'])
        self.assertIsNone(payload['new_ratio'])
        self.assertIsNone(payload['returning_ratio'])
        self.assertIsNone(payload['total_visitors'])
        self.assertIn('store_daily_facts.payment_buyers', payload['missing_fields'])

    def test_customer_analysis_respects_store_scope(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.execute(
                '''INSERT INTO store_daily_facts (
                    shop_id, date, product_visitors, payment_buyers,
                    returning_payment_buyers
                ) VALUES (?, ?, ?, ?, ?)''',
                ('shop-a', '2026-08-20', 200, 30, 9),
            )
            connection.commit()
        response = self.client.get(
            '/api/customer_analysis?dim=daily&period=2026-08-20&shop_id=shop-a'
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['new_buyers'], 21)
        self.assertEqual(payload['returning_buyers'], 9)
        self.assertEqual(payload['source'], 'store_daily_facts')

    def test_funnel_reads_daily_fields_instead_of_hardcoded_zero(self):
        payload = self.client.get(
            '/api/funnel?dim=daily&period=2026-08-20'
        ).get_json()
        values = [step['value'] for step in payload['steps']]
        self.assertEqual(values, [100, 300, 40, 10, 15])

    def test_funnel_marks_weekly_missing_steps_without_zero_filling(self):
        payload = self.client.get(
            '/api/funnel?dim=weekly&period=2026-08-17'
        ).get_json()
        self.assertEqual(payload['availability'], 'missing-fields')
        self.assertEqual(payload['steps'][0]['value'], 100)
        self.assertEqual(payload['steps'][1]['value'], 300)
        self.assertIsNone(payload['steps'][2]['value'])
        self.assertIsNone(payload['steps'][3]['value'])
        self.assertIsNone(payload['steps'][4]['value'])
        self.assertIn('cart_qty', payload['missing_fields'])

    def test_legacy_batch_tags_does_not_claim_missing_or_duplicate_products(self):
        from db import get_db
        with get_db(self.database_path) as connection:
            connection.execute(
                "INSERT INTO products (product_id, title) VALUES ('tagged-product', 'Tagged')"
            )
            connection.commit()

        first = self.client.post('/api/batch_tags', json={
            'product_ids': ['tagged-product', 'missing-product'], 'tag': '重点'
        }).get_json()
        self.assertEqual(first['added'], 1)
        self.assertEqual(first['missing'], 1)

        second = self.client.post('/api/batch_tags', json={
            'product_ids': ['tagged-product'], 'tag': '重点'
        }).get_json()
        self.assertEqual(second['added'], 0)
        self.assertEqual(second['duplicates'], 1)

    def test_legacy_management_mutations_use_validation_and_audit(self):
        invalid_task = self.client.post('/api/tasks', json={
            'title': 'invalid', 'status': 'unknown'
        })
        self.assertEqual(invalid_task.status_code, 422)

        task = self.client.post('/api/tasks', json={
            'title': 'legacy task', 'operator': 'tester', 'reason': 'compatibility'
        })
        self.assertEqual(task.status_code, 200)
        task_id = task.get_json()['data']['id']
        updated = self.client.put(f'/api/tasks/{task_id}', json={
            'status': 'doing', 'operator': 'tester', 'reason': 'compatibility update'
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()['data']['status'], 'doing')
        cancelled = self.client.put(f'/api/tasks/{task_id}', json={'status': 'cancelled'})
        self.assertEqual(cancelled.status_code, 200)

        invalid_kpi = self.client.post('/api/user_kpis', json={
            'user_name': 'tester', 'period': '2026-08', 'achievement_rate': 1.1
        })
        self.assertEqual(invalid_kpi.status_code, 422)
        kpi = self.client.post('/api/user_kpis', json={
            'user_name': 'tester', 'period': '2026-08', 'achievement_rate': 0.8,
            'operator': 'tester', 'reason': 'compatibility'
        })
        self.assertEqual(kpi.status_code, 200)

        from db import get_db
        with get_db(self.database_path) as connection:
            audit_count = connection.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE operator = 'tester'"
            ).fetchone()[0]
        self.assertEqual(audit_count, 3)


if __name__ == '__main__':
    unittest.main()

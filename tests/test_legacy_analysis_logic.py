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

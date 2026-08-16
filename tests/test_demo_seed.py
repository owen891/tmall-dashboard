import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch


class DemoSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-demo-seed-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_requires_explicit_demo_target(self):
        from scripts import seed_demo_data

        fake_root = Path(self.temp_dir.name) / 'repo'
        (fake_root / 'data').mkdir(parents=True)
        with patch.object(seed_demo_data, 'ROOT', str(fake_root)), patch('sys.argv', ['seed_demo_data.py']):
            with self.assertRaises(SystemExit) as raised:
                seed_demo_data.main()

        self.assertEqual(raised.exception.code, 2)

    def test_cli_refuses_repository_database_without_explicit_override(self):
        from scripts import seed_demo_data

        fake_root = Path(self.temp_dir.name) / 'repo'
        (fake_root / 'data').mkdir(parents=True)
        production_database = fake_root / 'data' / 'dashboard.db'
        production_database.write_bytes(b'production-placeholder')
        with patch.object(seed_demo_data, 'ROOT', str(fake_root)), patch('sys.argv', [
            'seed_demo_data.py', '--database', str(production_database),
        ]):
            with self.assertRaises(SystemExit) as raised:
                seed_demo_data.main()

        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(production_database.read_bytes(), b'production-placeholder')

    def test_seed_is_idempotent_and_covers_all_ga_domains(self):
        from scripts.seed_demo_data import seed_demo_data

        first = seed_demo_data(self.database_path)
        second = seed_demo_data(self.database_path)
        self.assertEqual(first, second)

        with closing(sqlite3.connect(self.database_path)) as connection:
            counts = {
                table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                for table in (
                    'products', 'daily_data', 'store_daily_facts', 'promotion_daily_facts',
                    'product_actions', 'product_action_history', 'lifecycle_profiles',
                    'period_reviews', 'goal_versions', 'daily_goals', 'import_batches',
                    'weekly_data', 'monthly_data', 'paid_detail', 'product_health', 'reviews',
                )
            }
            date_range = connection.execute(
                "SELECT MIN(date), MAX(date) FROM store_daily_facts WHERE source_batch_id = 'demo-store-batch'"
            ).fetchone()
            grains = connection.execute(
                "SELECT COUNT(DISTINCT channel), COUNT(DISTINCT campaign_id), COUNT(DISTINCT unit_id), COUNT(DISTINCT product_id) FROM promotion_daily_facts WHERE source_batch_id = 'demo-promotion-batch'"
            ).fetchone()

        self.assertGreaterEqual(counts['products'], 8)
        self.assertGreaterEqual(counts['daily_data'], 8 * 365)
        self.assertGreaterEqual(counts['store_daily_facts'], 365)
        self.assertGreaterEqual(counts['promotion_daily_facts'], 365)
        self.assertGreaterEqual(counts['product_actions'], 6)
        self.assertGreaterEqual(counts['product_action_history'], 6)
        self.assertGreaterEqual(counts['lifecycle_profiles'], 8)
        self.assertGreaterEqual(counts['period_reviews'], 3)
        self.assertEqual(counts['goal_versions'], 1)
        self.assertEqual(counts['daily_goals'], 365)
        self.assertGreaterEqual(counts['import_batches'], 3)
        self.assertGreaterEqual(counts['weekly_data'], 8 * 80)
        self.assertGreaterEqual(counts['monthly_data'], 8 * 20)
        self.assertEqual(counts['paid_detail'], 8)
        self.assertEqual(counts['product_health'], 8)
        self.assertEqual(counts['reviews'], 32)
        self.assertEqual(date_range, ('2025-01-01', '2026-08-12'))
        self.assertTrue(all(value >= 4 for value in grains))

    def test_seeded_metrics_are_business_consistent_and_drive_real_apis(self):
        from scripts.seed_demo_data import seed_demo_data
        from app import create_app

        seed_demo_data(self.database_path)
        app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        client = app.test_client()

        overview = client.get('/api/overview?start=2026-07-14&end=2026-08-12').get_json()
        promotion = client.get('/api/promotion?start=2026-07-14&end=2026-08-12&group_by=channel').get_json()
        products = client.get('/api/products?dim=daily&start=2026-07-14&end=2026-08-12&product_id=DEMO-001&status=all').get_json()
        actions = client.get('/api/actions').get_json()
        lifecycle = client.get('/api/lifecycle/assessments?productId=DEMO-001').get_json()
        goals = client.get('/api/goals/2026/periods').get_json()

        self.assertEqual(overview['availability'], 'available')
        self.assertGreater(overview['data']['payment_amount'], overview['data']['net_sales'])
        self.assertAlmostEqual(
            overview['data']['net_sales'],
            overview['data']['payment_amount'] - overview['data']['successful_refund_amount'],
            places=2,
        )
        self.assertGreater(overview['data']['returning_buyer_ratio'], 0.2)
        self.assertLess(overview['data']['returning_buyer_ratio'], 0.5)

        self.assertEqual(len(promotion['data']['rows']), 4)
        for row in promotion['data']['rows']:
            self.assertAlmostEqual(row['roi'], row['attributed_payment_amount'] / row['ad_spend'], places=5)
            self.assertAlmostEqual(row['ctr'], row['clicks'] / row['impressions'], places=5)
            self.assertAlmostEqual(row['cvr'], row['payment_buyers'] / row['clicks'], places=5)

        product = products['data']['rows'][0]
        self.assertEqual(product['product_id'], 'DEMO-001')
        self.assertGreater(product['payment_amount'], product['refund_amount'])
        self.assertGreater(product['roi'], 1)
        self.assertEqual(actions['data'][0]['status'], 'pending_review')
        self.assertEqual(lifecycle['data'][0]['stage'], 'mature')
        self.assertEqual(len(goals['data']['levels']['date']), 365)

    def test_reseed_repairs_all_demo_product_metrics(self):
        from scripts.seed_demo_data import seed_demo_data

        seed_demo_data(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """UPDATE daily_data
                   SET search_ipv = 1, recommend_ipv = 1, paid_ipv = 1, organic_ipv = 1,
                       payment_conversion = 0, cart_rate = 0, fav_rate = 0, bounce_rate = 0,
                       avg_stay_duration = 0, ad_roi = 0, avg_order_value = 0, uv_value = 0,
                       cart_qty = 0, fav_users = 0, search_conversion = 0,
                       search_visitors = 0, cart_users = 0
                   WHERE product_id = 'DEMO-001' AND date = '2026-08-12'"""
            )
            connection.commit()

        seed_demo_data(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                """SELECT search_ipv, recommend_ipv, paid_ipv, organic_ipv,
                          payment_conversion, cart_rate, fav_rate, bounce_rate,
                          avg_stay_duration, ad_roi, avg_order_value, uv_value,
                          cart_qty, fav_users, search_conversion, search_visitors, cart_users
                   FROM daily_data
                   WHERE product_id = 'DEMO-001' AND date = '2026-08-12'"""
            ).fetchone()

        self.assertTrue(all(value > 0 for value in row))

    def test_seed_preserves_existing_goals_and_reviews(self):
        from db import init_db
        from scripts.seed_demo_data import seed_demo_data

        init_db(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "INSERT INTO goal_versions (year, version, annual_target) VALUES (2026, 7, 1234567)"
            )
            connection.execute(
                """INSERT INTO daily_goals
                   (year, goal_date, target_amount, source, reason, version)
                   VALUES (2026, '2026-08-12', 7654.32, 'manual', '真实经营目标', 7)"""
            )
            connection.execute(
                """INSERT INTO period_reviews
                   (period_type, period_key, summary, conclusions, next_actions, reviewer)
                   VALUES ('day', '2026-08-12', '真实复盘', '真实结论', '真实动作', '店长')"""
            )
            connection.commit()

        seed_demo_data(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            version = connection.execute(
                "SELECT version, annual_target FROM goal_versions WHERE year = 2026"
            ).fetchone()
            goal = connection.execute(
                """SELECT target_amount, source, reason, version FROM daily_goals
                   WHERE year = 2026 AND goal_date = '2026-08-12'"""
            ).fetchone()
            review = connection.execute(
                """SELECT summary, conclusions, next_actions, reviewer FROM period_reviews
                   WHERE period_type = 'day' AND period_key = '2026-08-12'"""
            ).fetchone()

        self.assertEqual(version, (7, 1234567.0))
        self.assertEqual(goal, (7654.32, 'manual', '真实经营目标', 7))
        self.assertEqual(review, ('真实复盘', '真实结论', '真实动作', '店长'))

    def test_seed_populates_operating_workspace_context(self):
        from scripts.seed_demo_data import seed_demo_data

        seed_demo_data(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table} WHERE " + clause).fetchone()[0]
                for table, clause in {
                    'shop_targets': "period LIKE '2026-%'",
                    'product_targets': "period LIKE '2026-%' AND product_id LIKE 'DEMO-%'",
                    'alerts': "period LIKE '2026-%' AND title LIKE '演示%'",
                    'task_items': "title LIKE '演示%'",
                    'user_kpis': "period LIKE '2026-%' AND user_name LIKE '演示%'",
                    'product_notes': "product_id LIKE 'DEMO-%' AND note LIKE '演示%'",
                    'product_tags': "product_id LIKE 'DEMO-%' AND tag LIKE '演示%'",
                    'review_summary': "product_id LIKE 'DEMO-%'",
                    'operation_actions': "product_id LIKE 'DEMO-%' AND action_type LIKE '演示%'",
                }.items()
            }
        self.assertGreaterEqual(counts['shop_targets'], 3)
        self.assertGreaterEqual(counts['product_targets'], 8)
        self.assertGreaterEqual(counts['alerts'], 2)
        self.assertGreaterEqual(counts['task_items'], 3)
        self.assertGreaterEqual(counts['user_kpis'], 3)
        self.assertGreaterEqual(counts['product_notes'], 4)
        self.assertGreaterEqual(counts['product_tags'], 8)
        self.assertEqual(counts['review_summary'], 8)
        self.assertGreaterEqual(counts['operation_actions'], 3)

    def test_seed_populates_real_demo_workflow_history(self):
        from scripts.seed_demo_data import seed_demo_data

        seed_demo_data(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            lifecycle_history = connection.execute(
                "SELECT COUNT(*) FROM lifecycle_history WHERE product_id LIKE 'DEMO-%'"
            ).fetchone()[0]
            goal_adjustments = connection.execute(
                "SELECT COUNT(*) FROM goal_adjustments WHERE year = 2026 AND reason LIKE '演示%'"
            ).fetchone()[0]
            goal_locks = connection.execute(
                "SELECT COUNT(*) FROM goal_locks WHERE year = 2026"
            ).fetchone()[0]
            import_changes = connection.execute(
                "SELECT COUNT(*) FROM import_batch_changes WHERE batch_id = 'demo-product-batch' AND reverted_at IS NULL"
            ).fetchone()[0]

        self.assertGreaterEqual(lifecycle_history, 8)
        self.assertGreaterEqual(goal_adjustments, 1)
        self.assertGreaterEqual(goal_locks, 1)
        self.assertEqual(import_changes, 8 * 589)

    def test_demo_product_batch_is_really_revertible(self):
        from scripts.seed_demo_data import seed_demo_data
        from app import create_app

        seed_demo_data(self.database_path)
        app = create_app({'TESTING': True, 'DATABASE_PATH': self.database_path})
        response = app.test_client().post('/api/imports/demo-product-batch/revert')

        self.assertEqual(response.status_code, 200)
        with closing(sqlite3.connect(self.database_path)) as connection:
            remaining = connection.execute(
                "SELECT COUNT(*) FROM daily_data WHERE product_id LIKE 'DEMO-%'"
            ).fetchone()[0]
            status = connection.execute(
                "SELECT status FROM import_batches WHERE id = 'demo-product-batch'"
            ).fetchone()[0]
        self.assertEqual(remaining, 0)
        self.assertEqual(status, 'reverted')

    def test_seed_does_not_overwrite_non_demo_business_facts(self):
        from db import init_db
        from scripts.seed_demo_data import seed_demo_data

        init_db(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "INSERT INTO products (product_id, title, status) VALUES ('REAL-001', '真实商品', 'active')"
            )
            connection.execute(
                """INSERT INTO daily_data
                   (product_id, date, payment_amount, refund_amount, net_sales, data_source)
                   VALUES ('REAL-001', '2026-08-12', 9999, 99, 9900, 'real.xlsx')"""
            )
            connection.execute(
                """INSERT INTO store_daily_facts
                   (shop_id, date, payment_amount, successful_refund_amount, source_batch_id)
                   VALUES ('default', '2026-08-12', 8888, 88, 'real-store-batch')"""
            )
            connection.commit()

        seed_demo_data(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            product = connection.execute(
                "SELECT title FROM products WHERE product_id = 'REAL-001'"
            ).fetchone()
            daily = connection.execute(
                "SELECT payment_amount, data_source FROM daily_data WHERE product_id = 'REAL-001' AND date = '2026-08-12'"
            ).fetchone()
            store = connection.execute(
                "SELECT payment_amount, source_batch_id FROM store_daily_facts WHERE shop_id = 'default' AND date = '2026-08-12'"
            ).fetchone()

        self.assertEqual(product, ('真实商品',))
        self.assertEqual(daily, (9999.0, 'real.xlsx'))
        self.assertEqual(store, (8888.0, 'real-store-batch'))


if __name__ == '__main__':
    unittest.main()

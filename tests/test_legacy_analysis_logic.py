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

if __name__ == '__main__':
    unittest.main()

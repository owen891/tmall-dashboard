import sqlite3
import unittest

from scripts.data_quality_check import check_duplicates


class DataQualityCheckTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.executescript(
            '''
            CREATE TABLE daily_data (
                shop_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                date TEXT NOT NULL,
                payment_amount REAL DEFAULT 0
            );
            CREATE TABLE monthly_data (
                product_id TEXT NOT NULL,
                month TEXT NOT NULL,
                payment_amount REAL DEFAULT 0
            );
            '''
        )

    def tearDown(self):
        self.connection.close()

    def test_daily_duplicates_are_scoped_by_shop(self):
        self.connection.executemany(
            'INSERT INTO daily_data (shop_id, product_id, date) VALUES (?, ?, ?)',
            [
                ('shop-a', 'p1', '2026-04-01'),
                ('shop-b', 'p1', '2026-04-01'),
            ],
        )
        issues = check_duplicates(self.connection)
        self.assertFalse([issue for issue in issues if issue['table'] == 'daily_data'])

    def test_daily_duplicate_within_shop_is_reported(self):
        self.connection.executemany(
            'INSERT INTO daily_data (shop_id, product_id, date) VALUES (?, ?, ?)',
            [
                ('shop-a', 'p1', '2026-04-01'),
                ('shop-a', 'p1', '2026-04-01'),
            ],
        )
        issues = check_duplicates(self.connection)
        daily_issues = [issue for issue in issues if issue['table'] == 'daily_data']
        self.assertEqual(len(daily_issues), 1)
        self.assertIn('(shop_id, product_id, date)', daily_issues[0]['message'])

    def test_monthly_legacy_schema_uses_its_supported_key(self):
        self.connection.executemany(
            'INSERT INTO monthly_data (product_id, month) VALUES (?, ?)',
            [('p1', '2026-04'), ('p1', '2026-04')],
        )
        issues = check_duplicates(self.connection)
        monthly_issues = [issue for issue in issues if issue['table'] == 'monthly_data']
        self.assertEqual(len(monthly_issues), 1)
        self.assertIn('(product_id, month)', monthly_issues[0]['message'])


if __name__ == '__main__':
    unittest.main()

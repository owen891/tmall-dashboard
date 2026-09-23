import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.aggregate_store_daily import main


class AggregateStoreDailyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-store-aggregate-')
        self.database = Path(self.temp_dir.name) / 'dashboard.db'
        connection = sqlite3.connect(self.database)
        connection.executescript(
            '''
            CREATE TABLE daily_data (
                shop_id TEXT, date TEXT, payment_amount REAL, refund_amount REAL,
                ipv INTEGER, buyers INTEGER, returning_payment_buyers INTEGER, ad_spend REAL
            );
            CREATE TABLE store_daily_facts (
                shop_id TEXT, date TEXT, payment_amount REAL,
                successful_refund_amount REAL, product_visitors INTEGER,
                payment_buyers INTEGER, returning_payment_buyers INTEGER, ad_spend REAL,
                UNIQUE(shop_id, date)
            );
            INSERT INTO daily_data VALUES
                ('shop-a', '2026-09-20', 100, 3, 20, 4, 1, 5),
                ('shop-a', '2026-09-20', 50, 2, 10, 2, 0, 1);
            INSERT INTO store_daily_facts VALUES
                ('shop-a', '2026-09-20', 1, 1, 1, 1, 1, 1);
            '''
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _row(self, database):
        connection = sqlite3.connect(database)
        try:
            return connection.execute(
                'SELECT payment_amount, successful_refund_amount, product_visitors, payment_buyers, ad_spend FROM store_daily_facts'
            ).fetchone()
        finally:
            connection.close()

    def test_preview_is_read_only(self):
        before = self._row(self.database)
        self.assertEqual(main(['--db', str(self.database), '--lookback-days', '30']), 0)
        self.assertEqual(self._row(self.database), before)

    def test_apply_requires_backup_and_preserves_before_state(self):
        with self.assertRaises(SystemExit):
            main(['--db', str(self.database), '--apply'])

        backup = Path(self.temp_dir.name) / 'before-aggregate.db'
        self.assertEqual(main([
            '--db', str(self.database), '--lookback-days', '30',
            '--apply', '--backup-destination', str(backup),
        ]), 0)
        self.assertEqual(self._row(self.database), (150.0, 5.0, 30, 6, 6.0))
        self.assertEqual(self._row(backup), (1.0, 1.0, 1, 1, 1.0))


if __name__ == '__main__':
    unittest.main()

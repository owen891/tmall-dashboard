import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backfill_store_daily_facts import main


class BackfillStoreDailyFactsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-store-backfill-')
        self.database = Path(self.temp_dir.name) / 'dashboard.db'
        connection = sqlite3.connect(self.database)
        connection.executescript(
            '''
            CREATE TABLE daily_data (
                shop_id TEXT, date TEXT, payment_amount REAL, refund_amount REAL,
                ipv INTEGER, buyers INTEGER, returning_payment_buyers INTEGER, ad_spend REAL
            );
            CREATE TABLE store_daily_facts (
                shop_id TEXT NOT NULL, date TEXT NOT NULL, payment_amount REAL,
                successful_refund_amount REAL, product_visitors INTEGER,
                payment_buyers INTEGER, returning_payment_buyers INTEGER, ad_spend REAL,
                source_batch_id TEXT, PRIMARY KEY(shop_id, date)
            );
            INSERT INTO daily_data VALUES
                ('shop-a', '2026-09-20', 100, 3, 20, 4, 1, 5),
                ('shop-a', '2026-09-20', 50, 2, 10, 2, 0, 1),
                ('shop-a', '2026-09-19', 25, 1, 5, 1, 0, 2);
            INSERT INTO store_daily_facts VALUES
                ('shop-a', '2026-09-20', 1, 1, 1, 1, 1, 1, 'old-batch');
            '''
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _rows(self, database):
        connection = sqlite3.connect(database)
        try:
            return connection.execute(
                '''SELECT shop_id, date, payment_amount, successful_refund_amount,
                          product_visitors, payment_buyers, returning_payment_buyers,
                          ad_spend, source_batch_id
                   FROM store_daily_facts ORDER BY date'''
            ).fetchall()
        finally:
            connection.close()

    def test_preview_is_read_only(self):
        before = self._rows(self.database)
        self.assertEqual(main([
            '--db', str(self.database), '--shop-id', 'shop-a', '--lookback-days', '30'
        ]), 0)
        self.assertEqual(self._rows(self.database), before)

    def test_apply_requires_backup(self):
        with self.assertRaises(SystemExit):
            main(['--db', str(self.database), '--shop-id', 'shop-a', '--apply'])

    def test_apply_aggregates_and_preserves_backup(self):
        backup = Path(self.temp_dir.name) / 'before-backfill.db'
        self.assertEqual(main([
            '--db', str(self.database), '--shop-id', 'shop-a', '--lookback-days', '30',
            '--apply', '--backup-destination', str(backup),
        ]), 0)
        self.assertEqual(self._rows(self.database), [
            ('shop-a', '2026-09-19', 25.0, 1.0, 5, 1, 0, 2.0, 'aggregated_from_daily_data'),
            ('shop-a', '2026-09-20', 150.0, 5.0, 30, 6, 1, 6.0, 'aggregated_from_daily_data'),
        ])
        self.assertEqual(self._rows(backup), [
            ('shop-a', '2026-09-20', 1.0, 1.0, 1, 1, 1, 1.0, 'old-batch'),
        ])


if __name__ == '__main__':
    unittest.main()

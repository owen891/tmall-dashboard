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

    def test_skip_if_current_applies_when_stale(self):
        """已过期时 --skip-if-current 不能误跳过：仍要备份并写入。"""
        backup = Path(self.temp_dir.name) / 'stale.db'
        self.assertEqual(main([
            '--db', str(self.database), '--lookback-days', '30',
            '--apply', '--backup-destination', str(backup), '--skip-if-current',
        ]), 0)
        self.assertTrue(backup.exists())
        self.assertEqual(self._row(self.database), (150.0, 5.0, 30, 6, 6.0))

    def test_skip_if_current_skips_second_run(self):
        """已一致时跳过：不产生备份文件、不改动数据。这是两个调度入口
        每天各跑一次时避免重复全量备份的关键。"""
        first = Path(self.temp_dir.name) / 'first.db'
        self.assertEqual(main([
            '--db', str(self.database), '--lookback-days', '30',
            '--apply', '--backup-destination', str(first),
        ]), 0)
        self.assertTrue(first.exists())

        second = Path(self.temp_dir.name) / 'second.db'
        before = self._row(self.database)
        self.assertEqual(main([
            '--db', str(self.database), '--lookback-days', '30',
            '--apply', '--backup-destination', str(second), '--skip-if-current',
        ]), 0)
        self.assertFalse(second.exists(), '跳过时不应生成备份')
        self.assertEqual(self._row(self.database), before)

    def test_is_current_detects_value_drift(self):
        """行数相同但值不同（例如上游补采改了金额）也必须判为不一致。"""
        import sqlite3 as _sqlite3

        from scripts.aggregate_store_daily import is_current

        connection = _sqlite3.connect(self.database)
        connection.row_factory = _sqlite3.Row
        try:
            self.assertFalse(is_current(connection, 30))
            connection.execute(
                "UPDATE store_daily_facts SET payment_amount=150, successful_refund_amount=5, "
                "product_visitors=30, payment_buyers=6, returning_payment_buyers=1, ad_spend=6 "
                "WHERE shop_id='shop-a' AND date='2026-09-20'"
            )
            self.assertTrue(is_current(connection, 30))
            connection.execute(
                "UPDATE store_daily_facts SET payment_amount=151 WHERE shop_id='shop-a'"
            )
            self.assertFalse(is_current(connection, 30))
        finally:
            connection.close()


if __name__ == '__main__':
    unittest.main()

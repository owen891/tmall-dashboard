import json
import sqlite3
import unittest


from scripts.backfill_provenance import plan_backfill


class BackfillProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript('''
            CREATE TABLE import_batches (
                id TEXT PRIMARY KEY,
                shop_id TEXT,
                source_filename TEXT,
                source_hash TEXT,
                source_type TEXT,
                status TEXT,
                valid_rows INTEGER,
                quality_summary TEXT,
                created_at TEXT
            );
            CREATE TABLE daily_data (
                id INTEGER PRIMARY KEY,
                shop_id TEXT,
                product_id TEXT,
                date TEXT,
                data_source TEXT
            );
            CREATE TABLE daily_data_observations (
                shop_id TEXT,
                product_id TEXT,
                date TEXT
            );
        ''')

    def tearDown(self):
        self.connection.close()

    def _add_batch(self, batch_id, source_hash):
        self.connection.execute(
            '''INSERT INTO import_batches
               (id, shop_id, source_filename, source_hash, source_type, status,
                valid_rows, quality_summary, created_at)
               VALUES (?, 'default', 'legacy.xlsx', ?, 'product_day', 'completed',
                       1, ?, ?)''',
            (
                batch_id,
                source_hash,
                json.dumps({'date_range': {'start': '2026-04-19', 'end': '2026-04-19'}}),
                batch_id,
            ),
        )

    def test_same_filename_with_different_hashes_is_ambiguous(self):
        self._add_batch('batch-a', 'hash-a')
        self._add_batch('batch-b', 'hash-b')
        self.connection.execute(
            "INSERT INTO daily_data VALUES (1, 'default', 'product-a', '2026-04-19', 'legacy.xlsx')"
        )

        eligible, skipped = plan_backfill(self.connection)

        self.assertEqual(eligible, [])
        self.assertEqual(skipped[0]['reason'], 'ambiguous_batch')
        self.assertEqual(skipped[0]['batch_count'], 2)

    def test_single_exact_batch_is_eligible(self):
        self._add_batch('batch-a', 'hash-a')
        self.connection.execute(
            "INSERT INTO daily_data VALUES (1, 'default', 'product-a', '2026-04-19', 'legacy.xlsx')"
        )

        eligible, skipped = plan_backfill(self.connection)

        self.assertEqual(skipped, [])
        self.assertEqual(len(eligible), 1)
        self.assertEqual(len(eligible[0]['rows']), 1)


if __name__ == '__main__':
    unittest.main()

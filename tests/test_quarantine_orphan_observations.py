import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.quarantine_orphan_observations import main, plan, apply_plan


class QuarantineOrphanObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-quarantine-observations-')
        self.database = Path(self.temp_dir.name) / 'dashboard.db'
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE daily_data (shop_id TEXT, product_id TEXT, date TEXT);
            CREATE TABLE import_batches (id TEXT PRIMARY KEY);
            CREATE TABLE daily_data_observations (
                id INTEGER PRIMARY KEY, shop_id TEXT, product_id TEXT, date TEXT,
                source_system TEXT, source_type TEXT, source_batch_id TEXT,
                source_filename TEXT, payload_json TEXT, field_presence_json TEXT,
                quality_status TEXT, observed_at TEXT
            );
            INSERT INTO daily_data_observations VALUES
                (1, 'shop', 'orphan', '2026-04-05', 'bi', 'product_day', 'test-batch', 'x.xlsx', '{}', '{}', 'passed', 'now'),
                (2, 'shop', 'has-fact', '2026-04-05', 'bi', 'product_day', 'test-batch', 'x.xlsx', '{}', '{}', 'passed', 'now');
            INSERT INTO daily_data VALUES ('shop', 'has-fact', '2026-04-05');
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_plan_blocks_rows_with_daily_fact(self):
        report = plan(self.database, source_batch_ids=['test-batch'])
        self.assertEqual(report['selected_count'], 2)
        self.assertEqual(report['eligible_count'], 1)
        self.assertEqual(len(report['blocked']), 1)

    def test_apply_archives_and_removes_only_eligible_rows(self):
        report = plan(self.database, observation_ids=[1])
        result = apply_plan(self.database, report, reason='test residual')
        self.assertEqual(result, {'archived_count': 1, 'deleted_count': 1})
        connection = sqlite3.connect(self.database)
        self.assertEqual(connection.execute('SELECT COUNT(*) FROM daily_data_observations').fetchone()[0], 1)
        self.assertEqual(connection.execute('SELECT COUNT(*) FROM daily_data_observations_quarantine').fetchone()[0], 1)
        connection.close()

    def test_cli_requires_explicit_selector(self):
        output = self.database.parent / 'report.json'
        with self.assertRaises(ValueError):
            main(['--database', str(self.database), '--output', str(output)])


if __name__ == '__main__':
    unittest.main()

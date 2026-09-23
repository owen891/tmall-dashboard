import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backfill_item_flow_collect_item_count import main


class BackfillItemFlowCollectItemCountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-item-flow-count-')
        self.database = Path(self.temp.name) / 'dashboard.db'
        self.backup = Path(self.temp.name) / 'before.db'
        self.output = Path(self.temp.name) / 'report.json'
        connection = sqlite3.connect(self.database)
        connection.execute('''CREATE TABLE sycm_item_flow_source_daily (
            id INTEGER PRIMARY KEY, stat_date TEXT, collect_item_count INTEGER, collect_count INTEGER
        )''')
        connection.executemany(
            'INSERT INTO sycm_item_flow_source_daily VALUES (?, ?, ?, ?)',
            [(1, '2026-09-20', None, 3), (2, '2026-09-20', 4, 5)],
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_dry_run_does_not_mutate(self):
        self.assertEqual(main([
            '--database', str(self.database), '--output', str(self.output),
        ]), 0)
        report = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertTrue(report['dry_run'])
        self.assertEqual(report['before']['eligible_rows'], 1)
        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(connection.execute(
                'SELECT collect_item_count FROM sycm_item_flow_source_daily WHERE id=1'
            ).fetchone()[0], None)
        finally:
            connection.close()

    def test_apply_requires_backup_and_backfills_only_missing_values(self):
        self.assertEqual(main([
            '--database', str(self.database), '--backup-destination', str(self.backup),
            '--apply', '--output', str(self.output),
        ]), 0)
        report = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertTrue(report['backup']['ok'])
        self.assertEqual(report['changed_rows'], 1)
        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(connection.execute(
                'SELECT collect_item_count FROM sycm_item_flow_source_daily WHERE id=1'
            ).fetchone()[0], 3)
            self.assertEqual(connection.execute(
                'SELECT collect_item_count FROM sycm_item_flow_source_daily WHERE id=2'
            ).fetchone()[0], 4)
        finally:
            connection.close()


if __name__ == '__main__':
    unittest.main()

import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


class ReleaseAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-release-audit-')
        self.database_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        connection = sqlite3.connect(self.database_path)
        connection.executescript(
            '''
            CREATE TABLE import_batches (
                id TEXT PRIMARY KEY,
                source_type TEXT,
                source_filename TEXT,
                status TEXT
            );
            INSERT INTO import_batches VALUES
                ('demo-product-batch', 'product_day', 'demo_product_day.xlsx', 'completed'),
                ('real-product-batch', 'product_day', 'shop_export.xls', 'completed');
            '''
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_report_surfaces_dirty_worktree_and_mixed_batches(self):
        from scripts.release_audit import build_report

        with patch('scripts.release_audit._git_status', return_value=[' M app.py', '?? scratch.txt']), patch(
            'scripts.release_audit._tracked_sensitive_artifacts', return_value=[]
        ):
            report = build_report(self.temp_dir.name, self.database_path)

        self.assertEqual(report['worktree'], {'changed': 1, 'untracked': 1, 'deleted': 0})
        self.assertEqual(report['database']['integrity'], 'ok')
        self.assertEqual(report['database']['import_batches'], {'demo': 1, 'real': 1})
        self.assertIn('dirty_worktree', report['blockers'])
        self.assertIn('mixed_demo_and_real_batches', report['warnings'])

    def test_report_blocks_daily_facts_without_observation_and_lineage(self):
        from scripts.release_audit import build_report

        connection = sqlite3.connect(self.database_path)
        connection.executescript(
            '''
            CREATE TABLE daily_data (
                shop_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                date TEXT NOT NULL
            );
            CREATE TABLE daily_data_observations (
                shop_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                date TEXT NOT NULL
            );
            CREATE TABLE fact_field_lineage (
                shop_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                date TEXT NOT NULL
            );
            INSERT INTO daily_data VALUES ('default', 'p-1', '2026-08-01');
            '''
        )
        connection.commit()
        connection.close()

        with patch('scripts.release_audit._git_status', return_value=[]), patch(
            'scripts.release_audit._tracked_sensitive_artifacts', return_value=[]
        ):
            report = build_report(self.temp_dir.name, self.database_path)

        self.assertEqual(report['database']['provenance'], {
            'daily_rows': 1,
            'without_observations': 1,
            'without_lineage': 1,
        })
        self.assertIn('untraceable_daily_facts', report['blockers'])

    def test_report_blocks_tracked_runtime_and_source_data(self):
        from scripts.release_audit import build_report

        tracked = [
            'data/dashboard.db',
            'data/import_log.json',
            'data/raw/shop-export.xlsx',
            'backend/data/db/dashboard.db',
            'legacy/data/import_log.json',
            'archive/backup.sqlite3',
            'source.xlsx',
            'template.xlsx',
        ]
        with patch('scripts.release_audit._git_status', return_value=[]), patch(
            'scripts.release_audit._tracked_sensitive_artifacts', return_value=tracked
        ):
            report = build_report(self.temp_dir.name, self.database_path)

        self.assertEqual(report['repository']['tracked_sensitive_artifacts'], tracked)
        self.assertIn('tracked_sensitive_artifacts', report['blockers'])

    def test_main_strict_returns_nonzero_without_mutating_database(self):
        from scripts.release_audit import main

        before = Path(self.database_path).read_bytes()
        with patch('scripts.release_audit._git_status', return_value=[]), patch(
            'scripts.release_audit._tracked_sensitive_artifacts', return_value=[]
        ), patch('sys.argv', [
            'release_audit.py', '--database', self.database_path, '--strict',
        ]):
            with self.assertRaises(SystemExit) as raised:
                main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(Path(self.database_path).read_bytes(), before)

    def test_main_non_strict_emits_json_and_succeeds(self):
        from scripts.release_audit import main

        with patch('scripts.release_audit._git_status', return_value=[]), patch(
            'scripts.release_audit._tracked_sensitive_artifacts', return_value=[]
        ), patch('sys.argv', [
            'release_audit.py', '--database', self.database_path,
        ]), patch('builtins.print') as printed:
            with self.assertRaises(SystemExit) as raised:
                main()

        self.assertEqual(raised.exception.code, 0)
        payload = json.loads(printed.call_args.args[0])
        self.assertEqual(payload['database']['integrity'], 'ok')


if __name__ == '__main__':
    unittest.main()

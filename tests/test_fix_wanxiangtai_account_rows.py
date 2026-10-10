import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class FixWanxiangtaiAccountRowsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-wxt-account-fix-')
        self.database = Path(self.temp_dir.name) / 'dashboard.db'
        connection = sqlite3.connect(self.database)
        connection.execute(
            '''CREATE TABLE promotion_daily_facts (
                date TEXT,
                ad_spend REAL,
                attributed_payment_amount REAL,
                impressions INTEGER,
                source_batch_id TEXT,
                grain TEXT
            )'''
        )
        connection.execute(
            '''INSERT INTO promotion_daily_facts
               VALUES ('2026-09-20', 10, 20, 100, 'batch-1', 'account')'''
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run(self, *arguments):
        root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment['TMALL_DB_PATH'] = str(self.database)
        # Use the interpreter running the tests instead of a hard-coded venv
        # path: on this machine the venv launcher is sandbox-degraded to Low
        # Integrity Level and cannot create SQLite files under the system TEMP
        # directory, which made the subprocess backup step fail. The script
        # under test is interpreter-agnostic.
        return subprocess.run(
            [sys.executable,
             str(root / 'scripts' / 'fix_wanxiangtai_account_rows.py'),
             *arguments],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
        )

    def _count(self, database):
        connection = sqlite3.connect(database)
        try:
            return connection.execute(
                "SELECT COUNT(*) FROM promotion_daily_facts WHERE grain='account'"
            ).fetchone()[0]
        finally:
            connection.close()

    def test_default_mode_is_read_only(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._count(self.database), 1)

    def test_apply_requires_backup_destination(self):
        result = self._run('--apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._count(self.database), 1)

    def test_apply_deletes_only_after_online_backup(self):
        backup = Path(self.temp_dir.name) / 'before-account-fix.db'
        result = self._run('--apply', '--backup-destination', str(backup))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._count(self.database), 0)
        self.assertEqual(self._count(backup), 1)
        connection = sqlite3.connect(backup)
        try:
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        finally:
            connection.close()


if __name__ == '__main__':
    unittest.main()

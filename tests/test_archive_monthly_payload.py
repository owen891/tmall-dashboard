import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.archive_monthly_payload import apply_archive, inspect


class ArchiveMonthlyPayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-monthly-archive-')
        self.db = Path(self.temp_dir.name) / 'dashboard.db'
        conn = sqlite3.connect(self.db)
        conn.executescript('''
            CREATE TABLE monthly_source_payload (
              product_id TEXT NOT NULL, month TEXT NOT NULL,
              source_filename TEXT NOT NULL, source_hash TEXT NOT NULL,
              payload_json TEXT NOT NULL, imported_at TEXT,
              PRIMARY KEY(product_id, month)
            );
            CREATE TABLE archive_catalog (
              archive_key TEXT PRIMARY KEY, source_kind TEXT, source_table TEXT,
              archive_path TEXT, source_sha256 TEXT, row_count INTEGER,
              min_value TEXT, max_value TEXT, status TEXT, metadata_json TEXT
            );
            INSERT INTO monthly_source_payload VALUES
              ('p1','2025-01','a.xlsx','h1','{}','2025-01-01'),
              ('p2','2026-09','b.xlsx','h2','{}','2026-09-01');
        ''')
        conn.commit(); conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_apply_requires_backup_and_records_catalog(self):
        self.assertEqual(inspect(self.db, '2026-01')['row_count'], 1)
        backup = Path(self.temp_dir.name) / 'backup.db'
        result = apply_archive(
            self.db, '2026-01', Path(self.temp_dir.name) / 'archive', backup
        )
        self.assertEqual(result['deleted'], 1)
        self.assertTrue(backup.exists())
        conn = sqlite3.connect(self.db)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM monthly_source_payload').fetchone()[0], 1)
        row = conn.execute('SELECT source_table, row_count, status FROM archive_catalog').fetchone()
        conn.close()
        self.assertEqual(row, ('monthly_source_payload', 1, 'verified'))


if __name__ == '__main__':
    unittest.main()

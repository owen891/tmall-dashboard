import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.enforce_retention import enforce


def _days_ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


SCHEMA = '''
CREATE TABLE retention_policies (
  policy_key TEXT PRIMARY KEY, source_kind TEXT NOT NULL, source_table TEXT NOT NULL,
  retention_days INTEGER NOT NULL, mode TEXT NOT NULL DEFAULT 'archive',
  protected INTEGER NOT NULL DEFAULT 0, updated_at TEXT
);
CREATE TABLE archive_catalog (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  archive_key TEXT NOT NULL UNIQUE, source_kind TEXT, source_table TEXT,
  archive_path TEXT NOT NULL, source_sha256 TEXT NOT NULL,
  row_count INTEGER NOT NULL DEFAULT 0, min_value TEXT, max_value TEXT,
  archived_at TEXT, status TEXT NOT NULL DEFAULT 'verified', metadata_json TEXT
);
CREATE TABLE collector_data_staging (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_key TEXT, batch_id TEXT,
  unit_type TEXT, unit_key TEXT, payload_json TEXT, status TEXT,
  quality_message TEXT, created_at TEXT, published_at TEXT
);
CREATE TABLE monthly_source_payload (
  product_id TEXT NOT NULL, month TEXT NOT NULL, source_filename TEXT,
  source_hash TEXT, payload_json TEXT, imported_at TEXT,
  PRIMARY KEY(product_id, month)
);
CREATE TABLE audit_table (id INTEGER PRIMARY KEY, payload TEXT);
'''


class EnforceRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-enforce-retention-')
        self.db = Path(self.temp_dir.name) / 'dashboard.db'
        conn = sqlite3.connect(self.db)
        conn.executescript(SCHEMA)
        old_date, new_date = _days_ago(60), _days_ago(1)
        conn.executemany(
            'INSERT INTO collector_data_staging '
            '(payload_json, status, created_at, published_at) VALUES (?,?,?,?)',
            [('{"a":1}', 'published', old_date, old_date),
             ('{"b":2}', 'published', new_date, new_date),
             ('{"c":3}', 'staged', old_date, None)])
        old_month = f'{(date.today().year - 1):04d}-{date.today().month:02d}'
        conn.execute(
            'INSERT INTO monthly_source_payload VALUES (?,?,?,?,?,?)',
            ('p1', old_month, 'a.xlsx', 'h1', '{}', old_date))
        conn.execute(
            'INSERT INTO monthly_source_payload VALUES (?,?,?,?,?,?)',
            ('p2', f'{date.today().year:04d}-{date.today().month:02d}',
             'b.xlsx', 'h2', '{}', new_date))
        conn.execute("INSERT INTO audit_table VALUES (1, 'keep-me')")
        conn.executemany(
            'INSERT INTO retention_policies '
            '(policy_key, source_kind, source_table, retention_days, mode, protected) '
            'VALUES (?,?,?,?,?,0)',
            [('staging', 'runtime', 'collector_data_staging', 14, 'purge_after_archive'),
             ('monthly', 'raw_payload', 'monthly_source_payload', 180, 'archive'),
             ('audit', 'audit', 'audit_table', 1, 'retain')])
        conn.execute(
            "INSERT INTO retention_policies "
            "(policy_key, source_kind, source_table, retention_days, mode, protected) "
            "VALUES ('protected_audit', 'audit', 'audit_table', 1, 'archive', 1)")
        conn.commit()
        conn.close()
        self.archive_dir = Path(self.temp_dir.name) / 'archives'

    def tearDown(self):
        for conn in getattr(self, '_conns', []):
            try:
                conn.close()
            except sqlite3.Error:
                pass
        self.temp_dir.cleanup()

    def _connect(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        self._conns = getattr(self, '_conns', [])
        self._conns.append(conn)
        return conn

    def test_dry_run_mutates_nothing(self):
        report = enforce(self.db, apply_changes=False, archive_dir=self.archive_dir)
        self.assertFalse(report['apply'])
        conn = self._connect()
        self.assertEqual(conn.execute(
            'SELECT COUNT(*) FROM collector_data_staging').fetchone()[0], 3)
        self.assertEqual(conn.execute(
            'SELECT COUNT(*) FROM archive_catalog').fetchone()[0], 0)

    def test_purge_deletes_only_old_published(self):
        report = enforce(self.db, apply_changes=True, archive_dir=self.archive_dir)
        self.assertTrue(report['policy']['delete_performed'])
        conn = self._connect()
        rows = conn.execute(
            'SELECT status, published_at FROM collector_data_staging').fetchall()
        # old published purged; new published and old staged (no published_at) remain
        self.assertEqual(len(rows), 2)
        self.assertNotIn(('published', _days_ago(60)), [(r[0], r[1]) for r in rows])
        staging = next(p for p in report['policies']
                       if p['source_table'] == 'collector_data_staging')
        self.assertEqual(staging['action'], 'purged')

    def test_archive_exports_and_catalogs(self):
        report = enforce(self.db, apply_changes=True, archive_dir=self.archive_dir)
        conn = self._connect()
        remaining = [r[0] for r in conn.execute(
            'SELECT month FROM monthly_source_payload').fetchall()]
        self.assertEqual(remaining, [f'{date.today().year:04d}-{date.today().month:02d}'])
        catalog = conn.execute(
            'SELECT source_table, row_count, status, archive_path '
            'FROM archive_catalog').fetchone()
        self.assertEqual(catalog['source_table'], 'monthly_source_payload')
        self.assertEqual(catalog['row_count'], 1)
        self.assertEqual(catalog['status'], 'verified')
        self.assertTrue(Path(catalog['archive_path']).exists())
        monthly = next(p for p in report['policies']
                        if p['source_table'] == 'monthly_source_payload')
        self.assertEqual(monthly['action'], 'archived')

    def test_protected_and_retain_tables_untouched(self):
        enforce(self.db, apply_changes=True, archive_dir=self.archive_dir)
        conn = self._connect()
        self.assertEqual(conn.execute(
            'SELECT COUNT(*) FROM audit_table').fetchone()[0], 1)

    def test_missing_policies_table_reports_error(self):
        other = Path(self.temp_dir.name) / 'other.db'
        sqlite3.connect(other).close()
        report = enforce(other)
        self.assertIn('error', report)

    def test_row_count_change_during_export_aborts(self):
        # simulate a concurrent insert racing the export by wrapping export_rows
        from scripts import enforce_retention as mod
        original = mod.export_rows

        def racing(conn, table, column, cutoff, extra_where, target):
            count, sha = original(conn, table, column, cutoff, extra_where, target)
            if table == 'monthly_source_payload' and count:
                conn.execute(
                    "INSERT INTO monthly_source_payload VALUES ('racer', '2000-01', "
                    "'r.xlsx', 'h9', '{}', '2000-01-01')")
            return count, sha

        mod.export_rows = racing
        try:
            with self.assertRaises(RuntimeError):
                enforce(self.db, apply_changes=True, archive_dir=self.archive_dir)
        finally:
            mod.export_rows = original
        conn = self._connect()
        # nothing deleted and nothing cataloged: the racer insert rolled back
        # with the aborted transaction, so both original rows remain
        self.assertEqual(conn.execute(
            'SELECT COUNT(*) FROM monthly_source_payload').fetchone()[0], 2)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM monthly_source_payload WHERE product_id='p1'"
        ).fetchone()[0], 1)
        self.assertEqual(conn.execute(
            'SELECT COUNT(*) FROM archive_catalog').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()

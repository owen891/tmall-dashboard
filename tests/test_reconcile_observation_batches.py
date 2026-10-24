import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.reconcile_observation_batches import apply_plan, plan, run
from services.snapshot_source_types import SNAPSHOT_SOURCE_TYPES
SNAPSHOT_TYPE = next(iter(SNAPSHOT_SOURCE_TYPES))
SNAPSHOT_OVERVIEW_TYPE = f'{SNAPSHOT_TYPE.rsplit("_", 2)[0]}_overview'


class ReconcileObservationBatchesTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            '''
            CREATE TABLE import_batches (
                id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                status TEXT NOT NULL,
                valid_rows INTEGER,
                quality_summary TEXT,
                created_at TEXT
            );
            CREATE TABLE daily_data_observations (
                id INTEGER PRIMARY KEY,
                shop_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                date TEXT NOT NULL,
                source_system TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_batch_id TEXT,
                source_filename TEXT
            );
            '''
        )

    def tearDown(self):
        self.connection.close()

    def test_unique_match_is_planned_and_applied(self):
        self.connection.execute(
            '''INSERT INTO import_batches
               VALUES ('batch-1', 'shop-a', ?,
                       'C:/imports/bi-2026-08-21.xlsx', 'completed', 2, ?, '2026-08-22')''',
            (SNAPSHOT_TYPE, json.dumps({'date': '2026-08-21'})),
        )
        self.connection.executemany(
            '''INSERT INTO daily_data_observations
               (id,shop_id,product_id,date,source_system,source_type,source_batch_id,source_filename)
               VALUES (?,?,?,?,?,?,?,?)''',
            [
                (1, 'shop-a', 'p1', '2026-08-21', 'business_advisor', SNAPSHOT_TYPE, 'bi-2026-08-21.xlsx', 'bi-2026-08-21.xlsx'),
                (2, 'shop-a', 'p2', '2026-08-21', 'business_advisor', SNAPSHOT_TYPE, 'bi-2026-08-21.xlsx', 'bi-2026-08-21.xlsx'),
            ],
        )
        report = plan(self.connection)
        self.assertEqual(report['summary']['unique_row_count'], 2)
        self.assertEqual(report['groups'][0]['classification'], 'unique')
        written = apply_plan(self.connection, report)
        self.assertEqual(written['updated_rows'], 2)
        self.assertEqual(
            self.connection.execute(
                'SELECT COUNT(*) FROM daily_data_observations WHERE source_batch_id = "batch-1"'
            ).fetchone()[0],
            2,
        )

    def test_multiple_candidates_are_never_applied(self):
        for batch_id in ('batch-a', 'batch-b'):
            self.connection.execute(
                '''INSERT INTO import_batches
                   VALUES (?, 'shop-a', 'product_day', 'bi.xlsx', 'completed', 1, ?, ?)''',
                (batch_id, json.dumps({'date': '2026-08-21'}), batch_id),
            )
        self.connection.execute(
            '''INSERT INTO daily_data_observations
               (id,shop_id,product_id,date,source_system,source_type,source_batch_id,source_filename)
               VALUES (1,'shop-a','p1','2026-08-21','business_advisor','product_day','bi.xlsx','bi.xlsx')'''
        )
        report = plan(self.connection)
        self.assertEqual(report['summary']['ambiguous_group_count'], 1)
        self.assertEqual(apply_plan(self.connection, report)['updated_rows'], 0)
        self.assertEqual(
            self.connection.execute(
                'SELECT source_batch_id FROM daily_data_observations'
            ).fetchone()[0],
            'bi.xlsx',
        )

    def test_run_requires_explicit_backup_before_apply(self):
        with tempfile.TemporaryDirectory(prefix='tmall-reconcile-') as directory:
            database = Path(directory) / 'dashboard.db'
            connection = sqlite3.connect(database)
            connection.executescript(
                '''
                CREATE TABLE import_batches (
                    id TEXT PRIMARY KEY, shop_id TEXT NOT NULL, source_type TEXT NOT NULL,
                    source_filename TEXT NOT NULL, status TEXT NOT NULL, valid_rows INTEGER,
                    quality_summary TEXT, created_at TEXT
                );
                CREATE TABLE daily_data_observations (
                    id INTEGER PRIMARY KEY, shop_id TEXT NOT NULL, product_id TEXT NOT NULL,
                    date TEXT NOT NULL, source_system TEXT NOT NULL, source_type TEXT NOT NULL,
                    source_batch_id TEXT, source_filename TEXT
                );
                '''
            )
            connection.commit()
            connection.close()

            with self.assertRaises(ValueError):
                run(database, apply=True)

    def test_run_uses_online_backup_for_wal_database(self):
        with tempfile.TemporaryDirectory(prefix='tmall-reconcile-') as directory:
            database = Path(directory) / 'dashboard.db'
            backup = Path(directory) / 'before-reconcile.db'
            connection = sqlite3.connect(database)
            connection.execute('PRAGMA journal_mode=WAL')
            connection.executescript(
                '''
                CREATE TABLE import_batches (
                    id TEXT PRIMARY KEY, shop_id TEXT NOT NULL, source_type TEXT NOT NULL,
                    source_filename TEXT NOT NULL, status TEXT NOT NULL, valid_rows INTEGER,
                    quality_summary TEXT, created_at TEXT
                );
                CREATE TABLE daily_data_observations (
                    id INTEGER PRIMARY KEY, shop_id TEXT NOT NULL, product_id TEXT NOT NULL,
                    date TEXT NOT NULL, source_system TEXT NOT NULL, source_type TEXT NOT NULL,
                    source_batch_id TEXT, source_filename TEXT
                );
                INSERT INTO import_batches VALUES
                    ('batch-1', 'shop-a', 'product_day', 'bi.xlsx', 'completed', 1,
                     '{"date":"2026-08-21"}', '2026-08-22');
                INSERT INTO daily_data_observations VALUES
                    (1, 'shop-a', 'p1', '2026-08-21', 'business_advisor', 'product_day',
                     'bi.xlsx', 'bi.xlsx');
                '''
            )
            connection.commit()
            connection.close()

            report = run(database, apply=True, backup_destination=backup)

            self.assertTrue(report['backup']['ok'])
            self.assertEqual(report['written']['updated_rows'], 1)
            self.assertTrue(backup.is_file())
            backup_connection = sqlite3.connect(backup)
            try:
                self.assertEqual(
                    backup_connection.execute(
                        'SELECT source_batch_id FROM daily_data_observations'
                    ).fetchone()[0],
                    'bi.xlsx',
                )
                self.assertEqual(
                    backup_connection.execute('PRAGMA integrity_check').fetchone()[0],
                    'ok',
                )
            finally:
                backup_connection.close()


if __name__ == '__main__':
    unittest.main()

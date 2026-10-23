import io
import os
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from openpyxl import Workbook


def workbook_bytes(rows):
    book = Workbook()
    sheet = book.active
    sheet.append(['date', 'product_id', 'payment_amount', 'product_visitors'])
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


class ImportScanServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tmall-import-scan-')
        self.db_path = os.path.join(self.tmp.name, 'scan.db')
        self.inbox = os.path.join(self.tmp.name, 'inbox')
        os.makedirs(self.inbox)
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': self.db_path,
            'IMPORT_SCAN_ALLOWED_ROOTS': [self.inbox],
        })
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()
        self.tmp.cleanup()

    def test_job_rejects_path_outside_allowed_root(self):
        from services.import_scan_service import ImportScanValidationError, ImportScanService
        with self.assertRaises(ImportScanValidationError):
            ImportScanService.create_job({
                'task_name': 'bad',
                'folder_path': self.tmp.name,
                'source_type': 'product_day',
                'cron_expr': '* * * * *',
            })

    def test_windows_style_traversal_and_unc_paths_are_rejected(self):
        from services.import_scan_service import ImportScanValidationError, ImportScanService

        for folder, code in (
            (self.inbox + r'\..\outside', 'SCAN_FOLDER_TRAVERSAL'),
            (self.inbox + r'/nested\..\outside', 'SCAN_FOLDER_TRAVERSAL'),
            (r'\\server\share\imports', 'SCAN_FOLDER_LOCAL_ONLY'),
            (r'\\?\C:\imports', 'SCAN_FOLDER_LOCAL_ONLY'),
        ):
            with self.subTest(folder=folder):
                with self.assertRaises(ImportScanValidationError) as raised:
                    ImportScanService.create_job({
                        'task_name': 'invalid-path', 'folder_path': folder,
                        'source_type': 'auto', 'cron_expr': '* * * * *',
                    })
                self.assertEqual(raised.exception.code, code)

    def test_desktop_mode_accepts_existing_local_folder_outside_allowlist(self):
        from services.import_scan_service import ImportScanService

        selected_folder = os.path.join(self.tmp.name, 'desktop-selected')
        os.makedirs(selected_folder)

        with mock.patch.dict(os.environ, {'TMALL_DESKTOP_MODE': '1'}):
            job = ImportScanService.create_job({
                'task_name': 'desktop-folder',
                'folder_path': selected_folder,
                'source_type': 'auto',
                'cron_expr': '0 8 * * *',
            })

        self.assertEqual(job['folder_path'], os.path.realpath(selected_folder))

    def test_desktop_mode_config_accepts_existing_local_folder_without_process_env(self):
        from services.import_scan_service import ImportScanService

        selected_folder = os.path.join(self.tmp.name, 'desktop-config-selected')
        os.makedirs(selected_folder)
        self.app.config['TMALL_DESKTOP_MODE'] = '1'

        with mock.patch.dict(os.environ, {'TMALL_DESKTOP_MODE': ''}):
            job = ImportScanService.create_job({
                'task_name': 'desktop-config-folder',
                'folder_path': selected_folder,
                'source_type': 'auto',
                'cron_expr': '0 8 * * *',
            })

        self.assertEqual(job['folder_path'], os.path.realpath(selected_folder))

    def test_combined_patterns_match_supported_import_formats(self):
        from services.import_scan_service import DEFAULT_FILE_PATTERN, _matches_pattern

        self.assertEqual(DEFAULT_FILE_PATTERN, '*.xlsx;*.xls;*.csv;*.zip')
        for filename in ('daily.xlsx', 'legacy.xls', 'promotion.csv', 'reports.zip'):
            self.assertTrue(_matches_pattern(filename, DEFAULT_FILE_PATTERN))
        self.assertFalse(_matches_pattern('notes.pdf', DEFAULT_FILE_PATTERN))

    def test_running_lease_has_actionable_conflict_and_expired_lease_is_reclaimed(self):
        from services.import_scan_service import ImportScanConflictError, ImportScanService

        job = ImportScanService.create_job({
            'task_name': 'lease', 'folder_path': self.inbox,
            'source_type': 'auto', 'cron_expr': '* * * * *',
        })
        token = ImportScanService._acquire_lease(job['id'])
        with self.assertRaises(ImportScanConflictError) as raised:
            ImportScanService._acquire_lease(job['id'])
        self.assertEqual(raised.exception.code, 'SCAN_RUNNING')

        with self.app.app_context():
            from db import get_db
            with get_db() as conn:
                conn.execute(
                    "UPDATE import_scan_jobs SET lease_until=?, status='running' WHERE id=?",
                    ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), job['id']),
                )
                conn.commit()
        reclaimed = ImportScanService._acquire_lease(job['id'])
        self.assertNotEqual(reclaimed, token)
        self.assertEqual(ImportScanService.get_job(job['id'])['status'], 'running')

    def test_disabled_job_has_distinct_conflict_code(self):
        from services.import_scan_service import ImportScanConflictError, ImportScanService

        job = ImportScanService.create_job({
            'task_name': 'disabled', 'folder_path': self.inbox,
            'source_type': 'auto', 'cron_expr': '* * * * *', 'enabled': False,
        })
        with self.assertRaises(ImportScanConflictError) as raised:
            ImportScanService._acquire_lease(job['id'])
        self.assertEqual(raised.exception.code, 'SCAN_DISABLED')

    def test_run_once_imports_stable_file_and_is_idempotent(self):
        from services.import_scan_service import ImportScanService
        path = os.path.join(self.inbox, 'daily.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'p-1', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'daily',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        first = ImportScanService.run_job_once(job['id'])
        self.assertEqual(first['imported_count'], 0)
        second = ImportScanService.run_job_once(job['id'])
        self.assertEqual(second['imported_count'], 1)
        third = ImportScanService.run_job_once(job['id'])
        self.assertEqual(third['imported_count'], 0)
        files = ImportScanService.list_files(job['id'])
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['status'], 'imported')
        self.assertIsNotNone(files[0]['batch_id'])

    def test_read_stable_file_rejects_changes_after_discovery(self):
        from services.import_scan_service import ImportScanConflictError, ImportScanService

        path = os.path.join(self.inbox, 'changed.xlsx')
        with open(path, 'wb') as handle:
            handle.write(b'original')
        stat = os.stat(path)
        item = (path, 'changed.xlsx', stat.st_size, stat.st_mtime_ns, ImportScanService._file_hash(path))

        with open(path, 'wb') as handle:
            handle.write(b'replaced')

        with self.assertRaises(ImportScanConflictError) as raised:
            ImportScanService._read_stable_file(item)
        self.assertEqual(raised.exception.code, 'FILE_UNSTABLE')

    def test_manual_scan_force_imports_a_new_file_without_stability_wait(self):
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'manual.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'manual', 100, 10]]))
        job = ImportScanService.create_job({
            'task_name': 'manual',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })

        result = ImportScanService.run_job_once(job['id'], force=True)

        self.assertEqual(result['discovered_count'], 1)
        self.assertEqual(result['imported_count'], 1)
        self.assertEqual(ImportScanService.list_files(job['id'])[0]['status'], 'imported')

    def test_invalid_preview_is_blocked_without_business_write(self):
        from services.import_scan_service import ImportScanService
        path = os.path.join(self.inbox, 'invalid.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', '', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'invalid',
            'folder_path': self.inbox,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        result = ImportScanService.run_job_once(job['id'])
        self.assertEqual(result['blocked_count'], 1)
        self.assertEqual(ImportScanService.list_files(job['id'])[0]['status'], 'blocked')

    def test_scan_uses_cron_expression_when_scheduling_next_run(self):
        from services.import_scan_service import ImportScanService

        fixed_now = datetime(2026, 8, 16, 9, 15, tzinfo=timezone.utc)
        with patch('services.import_scan_service._utc_now', return_value=fixed_now):
            job = ImportScanService.create_job({
                'task_name': 'morning',
                'folder_path': self.inbox,
                'source_type': 'product_day',
                'cron_expr': '0 8 * * *',
            })
            self.assertEqual(job['next_run'], '2026-08-17T00:00:00+00:00')
            self.assertEqual(ImportScanService.run_due_jobs(now=fixed_now + timedelta(hours=1)), [])
            ImportScanService.run_job_once(job['id'])

        scheduled = ImportScanService.get_job(job['id'])['next_run']
        self.assertEqual(scheduled, '2026-08-17T00:00:00+00:00')

    def test_update_uses_cron_expression_when_scheduling_next_run(self):
        from services.import_scan_service import ImportScanService

        fixed_now = datetime(2026, 8, 16, 9, 15, tzinfo=timezone.utc)
        with patch('services.import_scan_service._utc_now', return_value=fixed_now):
            job = ImportScanService.create_job({
                'task_name': 'morning',
                'folder_path': self.inbox,
                'source_type': 'product_day',
                'cron_expr': '* * * * *',
            })
            updated = ImportScanService.update_job(job['id'], {'cron_expr': '30 9 * * *'})

        self.assertEqual(updated['next_run'], '2026-08-17T01:30:00+00:00')

    def test_run_due_jobs_reports_failure_and_continues_after_invalid_directory(self):
        from services.import_scan_service import ImportScanService

        broken_folder = os.path.join(self.inbox, 'broken')
        healthy_folder = os.path.join(self.inbox, 'healthy')
        os.makedirs(broken_folder)
        os.makedirs(healthy_folder)
        broken = ImportScanService.create_job({
            'task_name': 'broken',
            'folder_path': broken_folder,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        healthy = ImportScanService.create_job({
            'task_name': 'healthy',
            'folder_path': healthy_folder,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        os.rmdir(broken_folder)

        results = ImportScanService.run_due_jobs(now=datetime.now(timezone.utc) + timedelta(minutes=1))

        self.assertEqual([result['job_id'] for result in results], [broken['id'], healthy['id']])
        self.assertEqual(results[0]['status'], 'failed')
        self.assertIn('folder_path', results[0]['error'])
        broken_after_failure = ImportScanService.get_job(broken['id'])
        self.assertEqual(broken_after_failure['status'], 'error')
        self.assertEqual(broken_after_failure['enabled'], False)
        self.assertGreater(
            datetime.fromisoformat(broken_after_failure['next_run']),
            datetime.now(timezone.utc),
        )
        follow_up = ImportScanService.run_due_jobs(now=datetime.now(timezone.utc) + timedelta(minutes=2))
        self.assertEqual([result['job_id'] for result in follow_up], [healthy['id']])
        # Re-enabling after the folder is restored returns the job to the
        # schedulable state instead of requiring a database repair.
        os.makedirs(broken_folder)
        restored = ImportScanService.update_job(broken['id'], {'enabled': True})
        self.assertEqual(restored['status'], 'active')

    def test_repeated_scan_of_same_file_version_does_not_create_second_batch(self):
        from db import get_db
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'same-version.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'same-version', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'same-version',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        ImportScanService.run_job_once(job['id'])

        with get_db(self.db_path) as connection:
            batch_count = connection.execute(
                'SELECT COUNT(*) FROM import_batches WHERE source_filename = ?',
                ('same-version.xlsx',),
            ).fetchone()[0]
            connection.execute(
                "UPDATE import_scan_files SET status='discovered' WHERE job_id=?",
                (job['id'],),
            )
            connection.commit()

        ImportScanService.run_job_once(job['id'])

        with get_db(self.db_path) as connection:
            self.assertEqual(
                connection.execute(
                    'SELECT COUNT(*) FROM import_batches WHERE source_filename = ?',
                    ('same-version.xlsx',),
                ).fetchone()[0],
                batch_count,
            )

    def test_recent_importing_file_is_skipped_by_overlapping_worker(self):
        from db import get_db
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'in-progress.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'in-progress', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'in-progress',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        source_hash = ImportScanService._file_hash(path)
        with get_db(self.db_path) as connection:
            connection.execute(
                "UPDATE import_scan_files SET source_hash=?, status='importing' WHERE job_id=?",
                (source_hash, job['id']),
            )
            connection.commit()

        result = ImportScanService.run_job_once(job['id'])

        self.assertEqual(result['imported_count'], 0)
        self.assertEqual(result['discovered_count'], 0)
        self.assertEqual(ImportScanService.list_files(job['id'])[0]['status'], 'importing')

    def test_stale_importing_file_is_recovered_after_lease_expiry(self):
        from db import get_db
        from services.import_scan_service import ImportScanService, LEASE_SECONDS

        path = os.path.join(self.inbox, 'stale-import.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'stale-import', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'stale-import',
            'folder_path': self.inbox,
            'file_pattern': '*.xlsx',
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        source_hash = ImportScanService._file_hash(path)
        stale_at = (datetime.now(timezone.utc) - timedelta(seconds=LEASE_SECONDS + 1)).replace(microsecond=0).isoformat()
        with get_db(self.db_path) as connection:
            connection.execute(
                "UPDATE import_scan_files SET source_hash=?, status='importing', updated_at=? WHERE job_id=?",
                (source_hash, stale_at, job['id']),
            )
            connection.commit()

        result = ImportScanService.run_job_once(job['id'])

        self.assertEqual(result['imported_count'], 1)
        self.assertEqual(ImportScanService.list_files(job['id'])[0]['status'], 'imported')

    def test_touch_lease_renews_until_and_only_for_the_holder(self):
        """JOB-01: a run longer than LEASE_SECONDS must be able to hold its lease."""
        from db import get_db
        from services.import_scan_service import ImportScanService, LEASE_SECONDS

        job = ImportScanService.create_job({
            'task_name': 'heartbeat',
            'folder_path': self.inbox,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        token = ImportScanService._acquire_lease(job['id'])
        with get_db(self.db_path) as connection:
            before = connection.execute(
                'SELECT lease_until FROM import_scan_jobs WHERE id=?', (job['id'],)
            ).fetchone()['lease_until']

        # Drag the deadline back so a renewal is observable rather than a no-op.
        expired = (datetime.now(timezone.utc) - timedelta(seconds=LEASE_SECONDS)).replace(
            microsecond=0
        ).isoformat()
        with get_db(self.db_path) as connection:
            connection.execute(
                'UPDATE import_scan_jobs SET lease_until=? WHERE id=?', (expired, job['id'])
            )
            connection.commit()

        # T06: expiry is now a hard boundary; the old token must not resurrect.
        self.assertFalse(ImportScanService._touch_lease(job['id'], token))
        with get_db(self.db_path) as connection:
            connection.execute('UPDATE import_scan_jobs SET lease_until=? WHERE id=?',
                               ((datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat(), job['id']))
            connection.commit()
        self.assertTrue(ImportScanService._touch_lease(job['id'], token))
        with get_db(self.db_path) as connection:
            after = connection.execute(
                'SELECT lease_until, lease_token FROM import_scan_jobs WHERE id=?', (job['id'],)
            ).fetchone()
        self.assertGreater(after['lease_until'], expired)
        self.assertEqual(after['lease_token'], token)

        # A stale token (the lease was stolen) must not be able to renew.
        self.assertFalse(ImportScanService._touch_lease(job['id'], 'stolen-token'))
        with get_db(self.db_path) as connection:
            unchanged = connection.execute(
                'SELECT lease_until FROM import_scan_jobs WHERE id=?', (job['id'],)
            ).fetchone()['lease_until']
        self.assertEqual(unchanged, after['lease_until'])
        self.assertGreaterEqual(before, '')  # anchor: the original deadline was readable

    def test_stolen_lease_cannot_claim_or_update_the_same_file(self):
        """JOB-01: file rows are fenced, otherwise a stolen lease imports twice."""
        from db import get_db
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'fenced.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'p-fenced', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'fenced',
            'folder_path': self.inbox,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'])
        file_id = ImportScanService.list_files(job['id'])[0]['id']

        # Reset to a claimable state, but hand ownership to a *different* token.
        with get_db(self.db_path) as connection:
            connection.execute(
                """UPDATE import_scan_files
                   SET status='discovered', batch_id=NULL, preview_id=NULL, lease_token='owner-a'
                   WHERE id=?""",
                (file_id,),
            )
            connection.commit()

        self.assertFalse(ImportScanService._claim_discovered_file(file_id, 'owner-b'))
        ImportScanService._update_file(file_id, 'owner-b', status='failed', error_code='SHOULD_NOT_STICK')
        with get_db(self.db_path) as connection:
            row = connection.execute(
                'SELECT status, lease_token, error_code FROM import_scan_files WHERE id=?', (file_id,)
            ).fetchone()
        self.assertEqual(row['lease_token'], 'owner-a')
        self.assertNotEqual(row['status'], 'failed')

        # The real owner can still claim and write.
        with get_db(self.db_path) as connection:
            connection.execute('UPDATE import_scan_jobs SET lease_token=?, lease_until=? WHERE id=?',
                               ('owner-a', (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(), job['id']))
            connection.commit()
        self.assertTrue(ImportScanService._claim_discovered_file(file_id, 'owner-a'))
        ImportScanService._update_file(file_id, 'owner-a', status='failed', error_code='OWNER_WRITE')
        with get_db(self.db_path) as connection:
            row = connection.execute(
                'SELECT status, error_code FROM import_scan_files WHERE id=?', (file_id,)
            ).fetchone()
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['error_code'], 'OWNER_WRITE')

    def test_unowned_and_stale_files_stay_reclaimable_after_fencing(self):
        """JOB-01: fencing must not strand rows the heartbeat was meant to protect."""
        from db import get_db
        from services.import_scan_service import ImportScanService, LEASE_SECONDS

        path = os.path.join(self.inbox, 'unowned.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'p-unowned', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'unowned',
            'folder_path': self.inbox,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'], force=True)
        file_id = ImportScanService.list_files(job['id'])[0]['id']

        # A never-owned row (lease_token NULL) is claimable by a token holder.
        with get_db(self.db_path) as connection:
            connection.execute(
                "UPDATE import_scan_files SET status='discovered', batch_id=NULL, lease_token=NULL WHERE id=?",
                (file_id,),
            )
            connection.commit()
        with get_db(self.db_path) as connection:
            connection.execute('UPDATE import_scan_jobs SET lease_token=?, lease_until=? WHERE id=?',
                               ('owner-c', (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(), job['id']))
            connection.commit()
        self.assertTrue(ImportScanService._claim_discovered_file(file_id, 'owner-c'))

        # A crashed holder's row is reclaimable only once it goes stale.
        fresh = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with get_db(self.db_path) as connection:
            connection.execute(
                "UPDATE import_scan_files SET status='importing', lease_token='dead-owner', updated_at=? WHERE id=?",
                (fresh, file_id),
            )
            connection.commit()
        self.assertFalse(ImportScanService._claim_discovered_file(file_id, 'owner-d'))

        # Leave generous headroom: _iso() truncates to whole seconds, so a
        # boundary-exact timestamp would flake against the freshly sampled now.
        stale = (datetime.now(timezone.utc) - timedelta(seconds=LEASE_SECONDS * 3)).replace(
            microsecond=0
        ).isoformat()
        with get_db(self.db_path) as connection:
            connection.execute(
                "UPDATE import_scan_files SET updated_at=? WHERE id=?", (stale, file_id)
            )
            connection.commit()
        with get_db(self.db_path) as connection:
            connection.execute('UPDATE import_scan_jobs SET lease_token=?, lease_until=? WHERE id=?',
                               ('owner-d', (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat(), job['id']))
            connection.commit()
        self.assertTrue(ImportScanService._claim_discovered_file(file_id, 'owner-d'))

    def test_lost_lease_stops_the_run_before_further_imports(self):
        """JOB-01: once the lease is stolen the run must abort, not keep importing."""
        from services.import_scan_service import (
            ImportScanConflictError, ImportScanService, LEASE_SECONDS,
        )

        path = os.path.join(self.inbox, 'abort.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'p-abort', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'abort',
            'folder_path': self.inbox,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })

        def steal(job_id, token, shop_id=None):
            # Simulate a competing runner taking the lease mid-run.
            return False

        # force=True bypasses the two-phase stability gate: a first sighting has no
        # previous row, so without it the discovery loop yields no candidate and the
        # heartbeat would never be exercised.
        with patch.object(ImportScanService, '_touch_lease', side_effect=steal):
            with self.assertRaises(ImportScanConflictError) as raised:
                ImportScanService.run_job_once(job['id'], force=True)

        self.assertEqual(raised.exception.code, 'SCAN_LEASE_LOST')
        self.assertEqual(ImportScanService.list_files(job['id']), [])
        self.assertGreater(LEASE_SECONDS, 0)

    def test_release_clears_file_ownership_without_touching_terminal_rows(self):
        """JOB-01: a finished run must not leave stale *unfinished* file ownership.

        Terminal rows (``imported``/``blocked``/``failed``) deliberately keep the
        token of the run that produced them: they are never re-claimable -- see
        ``_upsert_discovered``, which short-circuits on those statuses -- and the
        token is the only record of which process wrote the evidence.  What must
        not survive is ownership of a row that is still in flight, because a
        crashed holder's ``importing`` row would otherwise never be reclaimable.
        """
        from db import get_db
        from services.import_scan_service import ImportScanService

        path = os.path.join(self.inbox, 'release.xlsx')
        with open(path, 'wb') as handle:
            handle.write(workbook_bytes([['2026-08-01', 'p-release', 100, 10]]))
        old = (datetime.now(timezone.utc) - timedelta(minutes=2)).timestamp()
        os.utime(path, (old, old))
        job = ImportScanService.create_job({
            'task_name': 'release',
            'folder_path': self.inbox,
            'source_type': 'product_day',
            'cron_expr': '* * * * *',
        })
        ImportScanService.run_job_once(job['id'], force=True)
        with get_db(self.db_path) as connection:
            row = connection.execute(
                'SELECT status, lease_token FROM import_scan_files WHERE job_id=?', (job['id'],)
            ).fetchone()
        self.assertEqual(row['status'], 'imported')

        # Release must not strand the rows this run owns: an in-flight file left
        # behind by the finishing holder has to become reclaimable again, but a
        # row a successor stole must keep the successor's token.
        token = ImportScanService._acquire_lease(job['id'])
        with get_db(self.db_path) as connection:
            connection.execute(
                "UPDATE import_scan_files SET status='importing', lease_token=? WHERE id IN "
                "(SELECT id FROM import_scan_files WHERE job_id=?)",
                (token, job['id']),
            )
            connection.commit()
        ImportScanService._release_lease(job['id'], token)
        with get_db(self.db_path) as connection:
            in_flight = connection.execute(
                'SELECT lease_token FROM import_scan_files WHERE job_id=?', (job['id'],)
            ).fetchone()
        self.assertIsNone(in_flight['lease_token'])

    def test_run_due_jobs_returns_failure_evidence_and_continues(self):
        from services.import_scan_service import ImportScanService

        broken_folder = os.path.join(self.inbox, 'broken-evidence')
        healthy_folder = os.path.join(self.inbox, 'healthy-evidence')
        os.makedirs(broken_folder)
        os.makedirs(healthy_folder)
        broken = ImportScanService.create_job({
            'task_name': 'broken-evidence', 'folder_path': broken_folder,
            'source_type': 'product_day', 'cron_expr': '* * * * *',
        })
        healthy = ImportScanService.create_job({
            'task_name': 'healthy-evidence', 'folder_path': healthy_folder,
            'source_type': 'product_day', 'cron_expr': '* * * * *',
        })
        os.rmdir(broken_folder)

        results = ImportScanService.run_due_jobs(now=datetime.now(timezone.utc) + timedelta(minutes=1))

        self.assertEqual([item['job_id'] for item in results], [broken['id'], healthy['id']])
        self.assertEqual(results[0]['status'], 'failed')
        self.assertIn('folder_path', results[0]['error'])

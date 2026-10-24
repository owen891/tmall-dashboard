"""JOB-01: real SQLite commits, controlled UTC clock, no production scans."""
import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from db import get_db
from services.import_scan_service import ImportScanService as Scan, ImportScanConflictError, import_service
from services.import_scan_lease import LeaseKeeper, ScanClaim, ScanLeaseLost


class InjectedCrash(BaseException):
    pass


class ImportScanLeaseContractTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp = tempfile.TemporaryDirectory(prefix='job01-contract-')
        self.root = Path(self.tmp.name)
        self.inbox = self.root / 'inbox'
        self.inbox.mkdir()
        self.path = self.inbox / 'one.csv'
        self.content = 'date,product_id,payment_amount,product_visitors\n2026-08-01,lease-product,100,10\n'
        self.path.write_text(self.content, encoding='utf-8')
        self.db_path = str(self.root / 'fixture.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.db_path,
                               'IMPORT_SCAN_ALLOWED_ROOTS': [str(self.inbox)]})
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.clock_patch = patch('services.import_scan_service._utc_now', side_effect=lambda: self.now)
        self.clock_patch.start()
        self.job = Scan.create_job({'task_name': 'contract', 'folder_path': str(self.inbox),
                                   'source_type': 'product_day', 'file_pattern': '*.csv', 'cron_expr': '* * * * *'})

    def tearDown(self):
        self.clock_patch.stop()
        self.ctx.pop()
        self.tmp.cleanup()

    def advance(self, seconds=121):
        self.now += timedelta(seconds=seconds)

    def counts(self):
        with get_db() as conn:
            return tuple(conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                         for t in ('daily_data', 'import_batches', 'import_staging_rows', 'import_batch_changes'))

    def run_once(self):
        return Scan.run_job_once(self.job['id'], force=True)

    def assert_successor_once(self):
        self.assertEqual(self.run_once()['imported_count'], 1)
        self.assertEqual(self.run_once()['imported_count'], 0)
        self.assertEqual(self.counts()[:2], (1, 1))

    def test_single_file_over_120_seconds_renews_from_real_heartbeat_thread(self):
        original = import_service.preview
        original_touch = Scan._touch_lease
        original_start = LeaseKeeper.start
        renewed = threading.Event()
        keepers = []

        def start(keeper):
            keeper.interval = .01  # accelerate scheduling, not the 120s lease
            keepers.append(keeper)
            return original_start(keeper)

        def touch(*args, **kwargs):
            result = original_touch(*args, **kwargs)
            if threading.current_thread().name == 'import-scan-lease':
                renewed.set()
            return result

        def slow_preview(*args, **kwargs):
            result = original(*args, **kwargs)
            for _ in range(3):
                renewed.clear()
                self.advance(50)
                self.assertTrue(renewed.wait(5), 'real heartbeat did not commit renewal')
                with get_db() as conn:
                    until = conn.execute('SELECT lease_until FROM import_scan_jobs WHERE id=?', (self.job['id'],)).fetchone()[0]
                self.assertGreater(until, self.now.isoformat())
                with self.assertRaises(ImportScanConflictError):
                    Scan._acquire_lease(self.job['id'])
            return result

        with patch.object(LeaseKeeper, 'start', start), patch.object(Scan, '_touch_lease', side_effect=touch), patch.object(import_service, 'preview', side_effect=slow_preview):
            self.assertEqual(self.run_once()['imported_count'], 1)
        self.assertFalse(keepers[0].thread.is_alive())
        self.assertEqual(self.counts()[:2], (1, 1))
        self.assertEqual(self.run_once()['imported_count'], 0)

    def test_discovery_expiry_cannot_resurrect_token(self):
        original = Scan._discover

        def slow_discover(*args, **kwargs):
            result = original(*args, **kwargs)
            self.advance()
            return result

        with patch.object(Scan, '_discover', side_effect=slow_discover), patch.object(LeaseKeeper, 'start', lambda k: k):
            with self.assertRaises(ImportScanConflictError) as raised:
                self.run_once()
        self.assertEqual(raised.exception.code, 'SCAN_LEASE_LOST')
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        self.assertEqual(Scan.list_files(self.job['id']), [])
        self.assert_successor_once()

    def test_preview_takeover_fences_old_worker_business_writes(self):
        original = import_service.preview
        successor = []

        def preview(*args, **kwargs):
            result = original(*args, **kwargs)
            self.advance()
            successor.append(Scan._acquire_lease(self.job['id']))
            return result

        with patch.object(import_service, 'preview', side_effect=preview), patch.object(LeaseKeeper, 'start', lambda k: k):
            with self.assertRaises(ImportScanConflictError) as raised:
                self.run_once()
        self.assertEqual(raised.exception.code, 'SCAN_LEASE_LOST')
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        with get_db() as conn:
            self.assertEqual(conn.execute('SELECT lease_token FROM import_scan_jobs').fetchone()[0], successor[0])
            run = conn.execute('SELECT status,error_message FROM import_scan_runs').fetchone()
        self.assertEqual(run['status'], 'failed')
        self.assertIn('SCAN_LEASE_LOST', run['error_message'])
        Scan._release_lease(self.job['id'], successor[0])
        self.assert_successor_once()

    def test_check_to_commit_competitor_is_locked_and_expiry_rolls_back_everything(self):
        import repos.import_repo as repo
        original = repo.record_daily_observation
        blocked = []

        def contend(*args, **kwargs):
            result = original(*args, **kwargs)
            other = sqlite3.connect(self.db_path, timeout=0)
            try:
                with self.assertRaises(sqlite3.OperationalError) as raised:
                    other.execute('BEGIN IMMEDIATE')
                blocked.append(str(raised.exception))
            finally:
                other.close()
            self.advance()  # validation already ran, now expiry before commit
            return result

        with patch.object(repo, 'record_daily_observation', side_effect=contend), patch.object(LeaseKeeper, 'start', lambda k: k):
            with self.assertRaises(ImportScanConflictError):
                self.run_once()
        self.assertIn('locked', blocked[0])
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        with get_db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)
            self.assertIsNone(conn.execute('SELECT batch_id FROM import_scan_files').fetchone()[0])
        self.assert_successor_once()

    def test_real_crashed_owner_token_is_recovered_and_active_owner_not_reclaimed(self):
        old = Scan._acquire_lease(self.job['id'])
        item = Scan._discover(Scan.get_job(self.job['id']), force=True)[0]
        row, _ = Scan._upsert_discovered(self.job['id'], item, old)
        self.assertTrue(Scan._claim_discovered_file(row['id'], old))
        with get_db() as conn:
            conn.execute('UPDATE import_scan_files SET updated_at=?', ((self.now-timedelta(seconds=360)).isoformat(),))
            conn.commit()
        same, process = Scan._upsert_discovered(self.job['id'], item, old)
        self.assertFalse(process)
        self.assertEqual(same['lease_token'], old)
        self.assertFalse(Scan._claim_discovered_file(row['id'], 'rogue'))
        self.advance()
        with get_db() as conn:
            self.assertEqual(conn.execute('SELECT lease_token FROM import_scan_files').fetchone()[0], old)
        self.assert_successor_once()

    def test_crash_after_business_commit_has_atomic_file_terminal_marker(self):
        with patch.object(import_service, '_report', side_effect=InjectedCrash('post-commit crash')):
            with self.assertRaises(InjectedCrash):
                self.run_once()
        with get_db() as conn:
            row = conn.execute('SELECT status,batch_id FROM import_scan_files').fetchone()
            batch = conn.execute('SELECT id,status FROM import_batches').fetchone()
        self.assertEqual((row['status'], row['batch_id']), ('imported', batch['id']))
        self.assertEqual(batch['status'], 'completed')
        self.advance()
        self.assertEqual(self.run_once()['imported_count'], 0)
        self.assertEqual(self.counts()[:2], (1, 1))

    def test_renewal_database_busy_exposes_failure_and_writes_no_business(self):
        original = import_service.preview
        keepers = []

        def start(keeper):
            keepers.append(keeper)
            return keeper  # deterministic pulse while a real second writer holds DB

        def busy_preview(*args, **kwargs):
            result = original(*args, **kwargs)
            other = sqlite3.connect(self.db_path, timeout=0)
            try:
                other.execute('BEGIN IMMEDIATE')
                with self.assertRaises(ScanLeaseLost):
                    keepers[0].pulse()
            finally:
                other.rollback()
                other.close()
            return result

        with patch.object(LeaseKeeper, 'start', start), patch.object(import_service, 'preview', side_effect=busy_preview), self.assertLogs('services.import_scan_lease', level='WARNING') as logs:
            with self.assertRaises(ImportScanConflictError):
                self.run_once()
        self.assertIn('locked', '\n'.join(logs.output))
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        self.advance()
        self.assert_successor_once()

    def test_same_path_changed_content_is_new_version_but_repeat_is_idempotent(self):
        self.assert_successor_once()
        self.path.write_text(self.content.replace(',100,', ',200,'), encoding='utf-8')
        self.assertEqual(self.run_once()['imported_count'], 1)
        self.assertEqual(self.run_once()['imported_count'], 0)
        self.assertEqual(self.counts()[:2], (1, 2))
        with get_db() as conn:
            self.assertEqual(conn.execute('SELECT payment_amount FROM daily_data').fetchone()[0], 200)

    def test_generic_promotion_branch_rejects_expired_claim(self):
        with get_db() as conn:
            conn.execute("UPDATE import_scan_jobs SET source_type='promotion_channel_day' WHERE id=?", (self.job['id'],))
            conn.commit()
        self.path.write_text('date,channel,ad_spend,attributed_payment_amount\n2026-08-01,search,10,100\n', encoding='utf-8')
        original = import_service.preview

        def slow(*args, **kwargs):
            result = original(*args, **kwargs)
            self.advance()
            return result

        with patch.object(import_service, 'preview', side_effect=slow), patch.object(LeaseKeeper, 'start', lambda k: k):
            with self.assertRaises(ImportScanConflictError):
                self.run_once()
        with get_db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM promotion_daily_facts').fetchone()[0], 0)
        self.assertEqual(self.counts()[:2], (0, 0))
        self.assertEqual(self.run_once()['imported_count'], 1)
        self.assertEqual(self.run_once()['imported_count'], 0)

    def test_manual_confirm_original_signature_and_preview_idempotency(self):
        from services.import_service import ImportValidationError
        preview = import_service.preview('manual.csv', self.content.encode(), 'product_day')
        result = import_service.confirm(preview['id'], preview['mapping'])
        with self.assertRaises(ImportValidationError):
            import_service.confirm(preview['id'], preview['mapping'])
        with get_db() as conn:
            batch = conn.execute('SELECT id,status FROM import_batches').fetchone()
        self.assertEqual((result['id'], batch['status']), (batch['id'], 'completed'))
        self.assertEqual(self.counts()[:2], (1, 1))

    def test_due_scheduler_recovers_expired_running_job_but_not_active_holder(self):
        token = Scan._acquire_lease(self.job['id'])
        # A real claim survives process death (no finally/release executed).
        old = (self.now-timedelta(seconds=300)).timestamp()
        os.utime(self.path, (old, old))
        item = Scan._discover(Scan.get_job(self.job['id']), force=True)[0]
        row, _ = Scan._upsert_discovered(self.job['id'], item, token)
        self.assertTrue(Scan._claim_discovered_file(row['id'], token))
        self.assertEqual(Scan.run_due_jobs(now=self.now), [])
        self.advance(180)
        first = Scan.run_due_jobs(now=self.now)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]['imported_count'], 1)
        self.assertEqual(self.counts()[:2], (1, 1))

    def test_claim_content_or_shop_mismatch_rejected_in_business_transaction(self):
        original = import_service.confirm
        for replacement in ({'source_hash': 'not-the-file-hash'}, {'shop_id': 'wrong-shop'}):
            with self.subTest(replacement=replacement):
                def wrong_claim(*args, **kwargs):
                    from dataclasses import replace
                    kwargs['scan_claim'] = replace(kwargs['scan_claim'], **replacement)
                    return original(*args, **kwargs)

                with patch.object(import_service, 'confirm', side_effect=wrong_claim):
                    with self.assertRaises(ImportScanConflictError):
                        self.run_once()
                self.assertEqual(self.counts(), (0, 0, 0, 0))
                self.advance()

    def test_generic_final_fence_rolls_back_already_staged_facts_and_batch(self):
        with get_db() as conn:
            conn.execute("UPDATE import_scan_jobs SET source_type='promotion_channel_day' WHERE id=?", (self.job['id'],))
            conn.commit()
        self.path.write_text('date,channel,ad_spend,attributed_payment_amount\n2026-08-01,search,10,100\n', encoding='utf-8')
        original = ScanClaim.finish

        def expire_at_finish(claim, connection, batch):
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM promotion_daily_facts').fetchone()[0], 1)
            self.advance()
            return original(claim, connection, batch)

        with patch.object(ScanClaim, 'finish', expire_at_finish):
            with self.assertRaises(ImportScanConflictError):
                self.run_once()
        with get_db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM promotion_daily_facts').fetchone()[0], 0)
            self.assertIsNone(conn.execute('SELECT batch_id FROM import_scan_files').fetchone()[0])
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        self.assertEqual(self.run_once()['imported_count'], 1)
        self.assertEqual(self.run_once()['imported_count'], 0)

    def test_takeover_between_discovery_and_file_claim_is_failed_not_completed(self):
        original = Scan._claim_discovered_file
        successor = []

        def takeover(file_id, token):
            self.advance()
            successor.append(Scan._acquire_lease(self.job['id']))
            with get_db() as conn:
                conn.execute("UPDATE import_scan_jobs SET last_error='successor-sentinel' WHERE id=?", (self.job['id'],))
                conn.commit()
            return original(file_id, token)

        with patch.object(Scan, '_claim_discovered_file', side_effect=takeover), patch.object(LeaseKeeper, 'start', lambda k: k):
            with self.assertRaises(ImportScanConflictError) as raised:
                self.run_once()
        self.assertEqual(raised.exception.code, 'SCAN_LEASE_LOST')
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        with get_db() as conn:
            run = conn.execute('SELECT status,error_message FROM import_scan_runs').fetchone()
            job = conn.execute('SELECT status,lease_token,last_error FROM import_scan_jobs').fetchone()
        self.assertEqual(run['status'], 'failed')
        self.assertIn('SCAN_LEASE_LOST', run['error_message'])
        self.assertEqual(tuple(job), ('running', successor[0], 'successor-sentinel'))
        Scan._release_lease(self.job['id'], successor[0])
        self.assert_successor_once()

    def test_takeover_after_last_legal_skip_cannot_commit_completed_run(self):
        self.assert_successor_once()
        original = Scan._upsert_discovered
        successor = []

        def takeover(*args, **kwargs):
            result = original(*args, **kwargs)
            self.assertFalse(result[1])  # already committed file, normal skip
            self.advance()
            successor.append(Scan._acquire_lease(self.job['id']))
            return result

        with patch.object(Scan, '_upsert_discovered', side_effect=takeover), patch.object(LeaseKeeper, 'start', lambda k: k):
            with self.assertRaises(ImportScanConflictError):
                self.run_once()
        with get_db() as conn:
            run = conn.execute('SELECT status,error_message FROM import_scan_runs ORDER BY rowid DESC LIMIT 1').fetchone()
            self.assertEqual(conn.execute('SELECT lease_token FROM import_scan_jobs').fetchone()[0], successor[0])
        self.assertEqual(run['status'], 'failed')
        self.assertIn('SCAN_LEASE_LOST', run['error_message'])
        self.assertEqual(self.counts()[:2], (1, 1))

    def test_live_job_can_skip_file_committed_since_discovery_snapshot(self):
        self.assert_successor_once()
        original = Scan._upsert_discovered

        def stale_discovery(*args, **kwargs):
            row, _ = original(*args, **kwargs)
            return row, True  # stale observation, authoritative claim sees batch_id

        with patch.object(Scan, '_upsert_discovered', side_effect=stale_discovery):
            result = self.run_once()
        self.assertEqual((result['status'], result['imported_count']), ('completed', 0))
        self.assertEqual(self.counts()[:2], (1, 1))

import json
import os
import tempfile
import unittest


class CollectorRunServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-collector-run-')
        self.db_path = os.path.join(self.temp_dir.name, 'dashboard.db')
        from db import init_db
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_lifecycle_is_persisted(self):
        from services.collector_run_service import create_run, get_run, update_run

        run_id = create_run(
            'sycm_flow', 'shop-a', db_path=self.db_path,
            window_start='2026-09-17', window_end='2026-09-17',
        )
        queued = get_run(run_id, db_path=self.db_path)
        self.assertEqual(queued['status'], 'queued')
        self.assertEqual(queued['source_key'], 'sycm_flow')
        self.assertEqual(queued['shop_id'], 'shop-a')

        update_run(run_id, status='running', attempt=1, db_path=self.db_path)
        running = get_run(run_id, db_path=self.db_path)
        self.assertEqual(running['status'], 'running')
        self.assertEqual(running['attempt'], 1)
        self.assertIsNotNone(running['started_at'])

        update_run(
            run_id, status='succeeded', db_path=self.db_path,
            stats={'published_rows': 12},
        )
        completed = get_run(run_id, db_path=self.db_path)
        self.assertEqual(completed['status'], 'succeeded')
        self.assertEqual(json.loads(completed['stats_json'])['published_rows'], 12)
        self.assertIsNotNone(completed['finished_at'])

    def test_failed_run_keeps_structured_error(self):
        from services.collector_run_service import create_run, get_run, update_run

        run_id = create_run('wanxiangtai', 'default', db_path=self.db_path)
        update_run(
            run_id, status='failed', db_path=self.db_path,
            error_code='AUTH_REQUIRED', error_message='session expired',
        )
        failed = get_run(run_id, db_path=self.db_path)
        self.assertEqual(failed['error_code'], 'AUTH_REQUIRED')
        self.assertEqual(failed['error_message'], 'session expired')
        self.assertIsNotNone(failed['finished_at'])

    def test_quality_gate_is_persisted_and_blocks_on_error(self):
        from services.collector_run_service import (
            create_run, quality_gate, record_quality_result,
        )
        run_id = create_run('bi_daily', 'default', db_path=self.db_path)
        self.assertEqual(quality_gate(run_id, db_path=self.db_path)['status'], 'not-evaluated')
        record_quality_result(
            run_id, 'row_count_nonzero', db_path=self.db_path,
            expected_value='>0', actual_value=0, status='failed',
            message='采集没有产生任何行',
        )
        gate = quality_gate(run_id, db_path=self.db_path)
        self.assertEqual(gate['status'], 'failed')
        self.assertEqual(gate['failed_rules'], 1)

    def test_legacy_source_snapshot_is_audited_in_staging(self):
        from db import get_db
        from services.collector_run_service import stage_source_snapshot, list_data_staging
        with get_db(self.db_path) as conn:
            conn.execute('''CREATE TABLE sycm_flow_source_daily (
                id INTEGER PRIMARY KEY, stat_date TEXT, channel_name TEXT)''')
            conn.execute("INSERT INTO sycm_flow_source_daily VALUES (1, '2026-09-18', '搜索')")
            conn.commit()
        result = stage_source_snapshot(
            'run-snapshot', 'sycm_flow', 'sycm_flow_source_daily', 'stat_date',
            db_path=self.db_path,
        )
        self.assertEqual(result['status'], 'published')
        self.assertEqual(result['row_count'], 1)
        self.assertEqual(list_data_staging('run-snapshot', db_path=self.db_path)[0]['status'], 'published')

    def test_raw_artifact_is_compressed_and_hash_indexed(self):
        from services.collector_run_service import create_run, list_artifacts, persist_artifact, read_artifact
        run_id = create_run('bi_daily', 'default', db_path=self.db_path)
        artifact = persist_artifact(run_id, 'process_output', 'raw output', db_path=self.db_path)
        self.assertTrue(artifact['path'].endswith('.json.gz'))
        self.assertEqual(len(artifact['sha256']), 64)
        rows = list_artifacts(run_id, db_path=self.db_path)
        self.assertEqual(rows[0]['sha256'], artifact['sha256'])
        replayed = read_artifact(rows[0]['id'], run_id, db_path=self.db_path)
        self.assertEqual(replayed['content'], 'raw output')

    def test_collector_support_tables_are_created(self):
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        try:
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            conn.close()
        self.assertTrue({
            'collector_runs', 'collector_leases', 'collector_checkpoints', 'collector_quality_results',
            'collector_artifacts', 'collector_data_staging', 'collector_health_alerts',
            'collector_schema_snapshots',
        }.issubset(tables))

    def test_health_alerts_are_upserted_and_resolved(self):
        from services.collector_run_service import (
            list_health_alerts, record_health_alert, resolve_health_alert,
        )
        record_health_alert('sycm_flow', 'data_delay', '延迟 4 天', db_path=self.db_path)
        record_health_alert('sycm_flow', 'data_delay', '延迟 5 天', db_path=self.db_path)
        alerts = list_health_alerts(source_key='sycm_flow', db_path=self.db_path)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['message'], '延迟 5 天')
        resolve_health_alert('sycm_flow', 'data_delay', alerts[0]['fingerprint'], db_path=self.db_path)
        self.assertEqual(list_health_alerts(source_key='sycm_flow', db_path=self.db_path), [])

    def test_schema_snapshot_detects_catalog_change(self):
        from services.collector_run_service import save_schema_snapshot
        first = save_schema_snapshot('sycm_flow', {'fields': ['a']}, db_path=self.db_path)
        same = save_schema_snapshot('sycm_flow', {'fields': ['a']}, db_path=self.db_path)
        changed = save_schema_snapshot('sycm_flow', {'fields': ['a', 'b']}, db_path=self.db_path)
        self.assertFalse(first['changed'])
        self.assertFalse(same['changed'])
        self.assertTrue(changed['changed'])

    def test_collector_manifest_hashes_scripts(self):
        from pathlib import Path
        from scripts.collector_manifest import build_manifest
        manifest = build_manifest(Path(__file__).resolve().parents[1] / 'scripts')
        names = {item['name'] for item in manifest['scripts']}
        self.assertIn('collector_healthcheck.py', names)
        self.assertTrue(all(len(item['sha256']) == 64 for item in manifest['scripts']))

    def test_production_audit_is_read_only_and_reports_database(self):
        from scripts.collector_production_audit import build_audit
        report = build_audit(self.db_path, self.temp_dir.name)
        self.assertTrue(report['database']['exists'])
        self.assertEqual(report['database']['integrity'], 'ok')
        self.assertIn('scheduled_tasks', report)

    def test_artifact_archive_dry_run_and_apply_preserve_hash(self):
        from datetime import datetime, timedelta, timezone
        from pathlib import Path
        from services.collector_run_service import create_run, persist_artifact
        from scripts.archive_collector_artifacts import plan_archive, apply_archive
        run_id = create_run('bi_daily', 'default', db_path=self.db_path)
        artifact = persist_artifact(run_id, 'process_output', 'archive me', db_path=self.db_path)
        conn = __import__('sqlite3').connect(self.db_path)
        try:
            conn.execute("UPDATE collector_artifacts SET created_at=?", ((datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),))
            conn.commit()
        finally:
            conn.close()
        archive_dir = Path(self.temp_dir.name) / 'archive'
        plan = plan_archive(self.db_path, archive_dir, 30)
        self.assertEqual(len(plan), 1)
        self.assertEqual(apply_archive(self.db_path, plan), 1)
        self.assertFalse(Path(artifact['path']).exists())
        self.assertTrue(Path(plan[0]['target']).exists())

    def test_lineage_archive_exports_and_deletes_exact_date_range(self):
        import sqlite3
        from pathlib import Path
        from scripts.archive_lineage_raw import apply_archive, inspect
        conn = sqlite3.connect(self.db_path)
        conn.execute('''CREATE TABLE bi_product_daily_raw (
            shop_id TEXT, product_id TEXT, date TEXT, raw_data TEXT)''')
        conn.execute("INSERT INTO bi_product_daily_raw (shop_id, product_id, date, raw_data) VALUES ('default','p1','2025-01-01','{}')")
        conn.execute("INSERT INTO daily_data_observations (product_id, date, source_system, source_type, payload_json) VALUES ('p1','2025-01-01','test','test','{}')")
        conn.execute("INSERT INTO fact_field_lineage (product_id, date, field_key, effective_source_system, effective_source_type, source_role) VALUES ('p1','2025-01-01','gmv','test','test','primary')")
        conn.execute("INSERT INTO bi_product_daily_raw (shop_id, product_id, date, raw_data) VALUES ('default','p2','2026-09-17','{}')")
        conn.commit(); conn.close()
        report = inspect(self.db_path, '2026-01-01')
        self.assertEqual(report['tables']['fact_field_lineage']['row_count'], 1)
        result = apply_archive(self.db_path, '2026-01-01', Path(self.temp_dir.name) / 'lineage')
        self.assertEqual(len(result['tables']), 3)
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM fact_field_lineage").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM bi_product_daily_raw").fetchone()[0], 1)
        conn.close()

    def test_database_lease_blocks_duplicate_source_and_releases(self):
        from services.collector_run_service import (
            acquire_lease, create_run, release_lease,
        )
        first = create_run('bi_daily', 'shop-a', db_path=self.db_path)
        second = create_run('bi_daily', 'shop-a', db_path=self.db_path)
        self.assertTrue(acquire_lease('bi_daily', 'shop-a', first, db_path=self.db_path))
        self.assertFalse(acquire_lease('bi_daily', 'shop-a', second, db_path=self.db_path))
        release_lease('bi_daily', 'shop-a', first, db_path=self.db_path)
        self.assertTrue(acquire_lease('bi_daily', 'shop-a', second, db_path=self.db_path))

    def test_terminal_run_lease_is_reclaimed_before_ttl(self):
        from services.collector_run_service import acquire_lease, create_run, update_run

        first = create_run('sycm_item_flow', 'shop-a', db_path=self.db_path)
        second = create_run('sycm_item_flow', 'shop-a', db_path=self.db_path)
        self.assertTrue(acquire_lease('sycm_item_flow', 'shop-a', first, db_path=self.db_path))
        update_run(first, status='failed', db_path=self.db_path, error_code='PROCESS_FAILED')
        self.assertTrue(acquire_lease('sycm_item_flow', 'shop-a', second, db_path=self.db_path))

    def test_checkpoint_is_idempotent_and_resumable(self):
        from services.collector_run_service import (
            create_run, get_run, list_checkpoints, upsert_checkpoint,
        )

        run_id = create_run('sycm_item_flow', 'default', db_path=self.db_path)
        upsert_checkpoint(
            run_id, 'product', '1001', db_path=self.db_path,
            page_no=1, status='succeeded', row_count=25, source_hash='a1',
        )
        upsert_checkpoint(
            run_id, 'product', '1001', db_path=self.db_path,
            page_no=1, status='failed', row_count=0, source_hash='a2',
            error_code='HTTP_429', error_message='rate limited',
        )
        checkpoints = list_checkpoints(run_id, db_path=self.db_path)
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]['status'], 'failed')
        self.assertEqual(checkpoints[0]['error_code'] if 'error_code' in checkpoints[0] else checkpoints[0]['last_error_code'], 'HTTP_429')
        self.assertEqual(get_run(run_id, db_path=self.db_path)['status'], 'queued')

    def test_retry_plan_contains_only_failed_business_units(self):
        from services.collector_retry_service import build_retry_plan
        from services.collector_run_service import create_run, upsert_checkpoint

        run_id = create_run('sycm_item_flow', 'default', db_path=self.db_path)
        upsert_checkpoint(run_id, 'product', 'ok', db_path=self.db_path, status='succeeded')
        upsert_checkpoint(run_id, 'product', 'bad', db_path=self.db_path, status='failed',
                          error_code='HTTP_429')
        plan = build_retry_plan(run_id, db_path=self.db_path)
        self.assertEqual(plan['unit_count'], 1)
        self.assertEqual(plan['units'][0]['unit_key'], 'bad')
        self.assertTrue(plan['executable'])

    def test_retry_diff_reports_recovered_and_unresolved_units(self):
        from services.collector_retry_service import retry_diff
        from services.collector_run_service import create_run, upsert_checkpoint, update_run
        parent = create_run('sycm_item_flow', 'default', db_path=self.db_path)
        upsert_checkpoint(parent, 'product', 'a', db_path=self.db_path, status='failed')
        upsert_checkpoint(parent, 'product', 'b', db_path=self.db_path, status='failed')
        child = create_run('sycm_item_flow', 'default', db_path=self.db_path,
                           mode='retry', requested_by=f'retry:{parent}')
        upsert_checkpoint(child, 'product', 'a', db_path=self.db_path, status='succeeded')
        diff = retry_diff(parent, child, db_path=self.db_path)
        self.assertEqual(diff['planned'], 2)
        self.assertEqual(diff['recovered'], 1)
        self.assertEqual(diff['unresolved'], 1)
        self.assertEqual(diff['completion_rate'], 0.5)


if __name__ == '__main__':
    unittest.main()

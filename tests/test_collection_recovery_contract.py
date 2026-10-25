"""Collection recovery checks use temporary fixtures, never the business DB/browser."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class RecoveryPolicyTests(unittest.TestCase):
    def test_failure_categories_and_retry_after_budget(self):
        from services.collector_run_service import classify_collection_failure as classify, retry_decision
        for message, category in [('MANUAL_LOGIN_REQUIRED', 'auth'), ('PermissionError: denied', 'permission'),
                ('HTTP 429 Retry-After: 120', 'rate_limit'), ('connection reset', 'transport'),
                ('cancelled', 'cancelled'), ('schema_changed', 'schema'), ('unspecified failure', 'unknown')]:
            with self.subTest(category=category):
                failure = classify([message], 1)
                self.assertEqual(failure['category'], category)
                decision = retry_decision(failure, attempt=1, elapsed_seconds=0)
                self.assertEqual(decision['retry'], category in ('transport', 'rate_limit'))
        limited = classify(['HTTP 429', 'Retry-After: 120'])
        self.assertEqual(retry_decision(limited, attempt=1, elapsed_seconds=0)['delay_seconds'], 120)
        self.assertFalse(retry_decision(limited, attempt=1, elapsed_seconds=800)['retry'])
        self.assertFalse(retry_decision(limited, attempt=3, elapsed_seconds=0)['retry'])
        self.assertFalse(retry_decision(classify(['HTTP 429']), attempt=1, elapsed_seconds=0)['retry'])

    def test_retry_after_http_date_and_unknown_stay_conservative(self):
        from datetime import datetime, timezone
        from services.collector_run_service import classify_collection_failure as classify
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        self.assertEqual(classify(['HTTP 429', 'Retry-After: Sat, 17 Oct 2026 00:02:00 GMT'], now=now)['retry_after_seconds'], 120)
        self.assertFalse(classify(['HTTP 429', 'Retry-After: nonsense'])['retryable'])


class RecoveryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='recovery-contract-')
        self.addCleanup(self.temp.cleanup)
        self.db_path = str(Path(self.temp.name) / 'fixture.db')
        from db import init_db
        init_db(self.db_path)
        # This entire class is database/files-only; any real network or child process is a test failure.
        self.addCleanup(patch.stopall)
        patch('socket.socket.connect', side_effect=AssertionError('network forbidden')).start()
        patch('subprocess.Popen', side_effect=AssertionError('process forbidden')).start()

    def test_fault_dedup_recovery_and_delivery_are_distinct(self):
        from services.collector_run_service import record_health_alert, resolve_health_alert, pending_health_events
        from scripts.collector_healthcheck import deliver_events
        fp = record_health_alert('fixture', 'failure', 'fixture', db_path=self.db_path)
        record_health_alert('fixture', 'failure', 'fixture', db_path=self.db_path)
        self.assertEqual(len(pending_health_events(db_path=self.db_path)), 1)
        self.assertEqual(deliver_events(db_path=self.db_path)[0]['status'], 'unconfigured')
        self.assertEqual(deliver_events(db_path=self.db_path, dry_run=True)[0]['status'], 'dry_run')
        self.assertEqual(deliver_events(db_path=self.db_path, webhook='fixture:', sender=lambda *_: 503)[0]['status'], 'failed')
        self.assertEqual(deliver_events(db_path=self.db_path, webhook='fixture:', sender=lambda *_: 204)[0]['status'], 'delivered')
        self.assertEqual(deliver_events(db_path=self.db_path, webhook='fixture:', sender=lambda *_: self.fail('duplicate delivery')), [])
        self.assertTrue(resolve_health_alert('fixture', 'failure', fp, db_path=self.db_path))
        self.assertFalse(resolve_health_alert('fixture', 'failure', fp, db_path=self.db_path))
        pending = pending_health_events(db_path=self.db_path)
        self.assertEqual([x['kind'] for x in pending], ['recovery'])
        self.assertEqual(pending[0]['external_delivery'], 'unconfigured')

    def test_gap_only_closes_on_fact_and_field_acceptance(self):
        from services.collector_run_service import (reconcile_date_gaps, verify_fact_dates,
            create_run, update_run)
        from db import get_db
        day = '2026-10-15'
        reconcile_date_gaps('fixture', [day], db_path=self.db_path)
        run = create_run('fixture', 'default', db_path=self.db_path)
        update_run(run, status='succeeded', db_path=self.db_path)
        self.assertEqual(reconcile_date_gaps('fixture', [], db_path=self.db_path)['open_dates'], [day])
        with get_db(self.db_path) as conn:
            conn.execute('CREATE TABLE fixture_facts (date TEXT, metric REAL)')
            conn.execute('INSERT INTO fixture_facts VALUES (?, NULL)', (day,))
            rejected = verify_fact_dates(conn, 'fixture_facts', 'date', ['date', 'metric'], [day])
            self.assertEqual(rejected['verified_dates'], [])
            conn.execute('UPDATE fixture_facts SET metric=0')
            accepted = verify_fact_dates(conn, 'fixture_facts', 'date', ['date', 'metric'], [day])
            self.assertEqual(accepted['verified_dates'], [day])
            self.assertEqual(verify_fact_dates(conn, 'fixture_facts', 'date', ['missing'], [day])['status'], 'unknown')
            conn.commit()
        closed = reconcile_date_gaps('fixture', [], verified_dates=accepted['verified_dates'], db_path=self.db_path)
        self.assertEqual(closed, {'open_dates': [], 'closed': [day]})

    def test_independent_heartbeat_absent_stale_and_whole_host_uncovered(self):
        from datetime import datetime, timedelta, timezone
        from services.collector_run_service import healthcheck_coverage
        from scripts.collector_healthcheck import write_heartbeat
        path = Path(self.temp.name) / 'heartbeat.json'
        self.assertEqual(healthcheck_coverage(path)['status'], 'missing')
        write_heartbeat(path, 'degraded')
        self.assertEqual(healthcheck_coverage(path)['status'], 'active')
        result = healthcheck_coverage(path, now=datetime.now(timezone.utc) + timedelta(days=2))
        self.assertEqual(result['status'], 'stale')
        self.assertEqual(result['host_or_api_down'], 'uncovered')
        self.assertFalse(result['autonomous_detection'])

    def test_endpoint_failure_has_local_event_and_recovery(self):
        from scripts.collector_healthcheck import persist_alerts
        from services.collector_run_service import pending_health_events
        persist_alerts({'ok': False, 'error_type': 'fixture'}, self.db_path)
        persist_alerts({'ok': False, 'error_type': 'fixture'}, self.db_path)
        self.assertEqual(len(pending_health_events(db_path=self.db_path)), 1)
        persist_alerts({'ok': True, 'data': {'sources': []}}, self.db_path)
        self.assertEqual([e['kind'] for e in pending_health_events(db_path=self.db_path)], ['fault', 'recovery'])

    def test_retry_owner_blocked_never_spawns_and_releases_lease(self):
        from services.collector_retry_service import _run_retry
        from services.collector_run_service import create_run, get_run, acquire_lease
        from scripts.browser_runtime import BrowserConfigurationError
        run = create_run('bi_daily', 'default', db_path=self.db_path, window_start='2026-10-01', window_end='2026-10-01')
        plan = {'source_key': 'bi_daily', 'shop_id': 'default', 'window_start':'2026-10-01', 'window_end':'2026-10-01', 'units': []}
        with patch('services.collector_retry_service.require_browser_identity', side_effect=BrowserConfigurationError('owner mismatch')), \
                patch('services.collector_retry_service.subprocess.run') as spawn:
            _run_retry(run, plan, collectors_dir=self.temp.name, python_executable=sys.executable,
                       script_name='fixture.py', db_path=self.db_path, browser_config={'fixture': True})
        spawn.assert_not_called()
        state = get_run(run, db_path=self.db_path)
        self.assertEqual(state['status'], 'blocked')
        self.assertEqual(state['error_code'], 'BROWSER_NOT_READY')
        successor = create_run('bi_daily', 'default', db_path=self.db_path)
        self.assertTrue(acquire_lease('bi_daily', 'default', successor, db_path=self.db_path))

    def test_retry_uses_selected_runtime_browser_and_preserves_proxy(self):
        from types import SimpleNamespace
        from services.collector_retry_service import _run_retry
        from services.collector_run_service import create_run, get_run
        run = create_run('bi_daily', 'default', db_path=self.db_path, window_start='2026-10-01', window_end='2026-10-01')
        plan = {'source_key': 'bi_daily', 'shop_id': 'default', 'window_start':'2026-10-01', 'window_end':'2026-10-01', 'units': [
            {'unit_type': 'product', 'unit_key': 'fixture', 'page_no': None, 'row_count': 1}]}
        output = 'CHECKPOINT_JSON ' + json.dumps({'event': 'checkpoint', 'unit_type': 'product',
            'unit_key': 'fixture', 'status': 'succeeded', 'row_count': 1})
        from db import get_db
        with get_db(self.db_path) as conn:
            conn.execute("INSERT INTO daily_data(shop_id,product_id,date,payment_amount) VALUES('default','fixture','2026-10-01',0)")
            conn.commit()
        output += '\nRESULT_JSON ' + json.dumps({'event':'result','schema_version':1,'source_key':'bi_daily',
            'run_id':run,'window_start':'2026-10-01','window_end':'2026-10-01','status':'succeeded',
            'return_code':0,'row_count':1,'quality_gate':'passed',
            'coverage':{'expected_units':1,'succeeded_units':1,'failed_units':0,'complete':True}})
        browser = {'executable': 'fixture.exe', 'user_data_dir': 'fixture-profile',
                   'host': '127.0.0.1', 'port': 41999, 'reuse_only': True}
        with patch('services.collector_retry_service.require_browser_identity') as identity, \
                patch('services.collector_retry_service.resolve_python', return_value='selected-python'), \
                patch.dict(os.environ, {'HTTPS_PROXY': 'fixture-remote-proxy'}), \
                patch('services.collector_retry_service.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=output, stderr='')) as spawn:
            _run_retry(run, plan, collectors_dir=self.temp.name, python_executable=sys.executable,
                       script_name='fixture.py', db_path=self.db_path, browser_config=browser)
        identity.assert_called_once_with(browser)
        self.assertEqual(spawn.call_args.args[0][0], 'selected-python')
        self.assertEqual(spawn.call_args.kwargs['env']['TMALL_CDP_PORT'], '41999')
        self.assertEqual(spawn.call_args.kwargs['env']['HTTPS_PROXY'], 'fixture-remote-proxy')
        self.assertEqual(get_run(run, db_path=self.db_path)['status'], 'succeeded')

    def test_api_independently_exposes_missing_monitor_and_date_acceptance(self):
        from app import create_app
        app = create_app({'TESTING': True, 'DATABASE_PATH': self.db_path,
                          'COLLECTOR_HEARTBEAT_PATH': str(Path(self.temp.name) / 'absent.json')})
        data = app.test_client().get('/api/collect/health').get_json()['data']
        self.assertEqual(data['monitoring']['status'], 'missing')
        self.assertEqual(data['monitoring']['host_or_api_down'], 'uncovered')
        source = next(x for x in data['sources'] if x['source_key'] == 'bi_daily')
        self.assertEqual(source['coverage_scope'], 'date_presence_and_required_fields')
        self.assertIn('coverage_acceptance', source)

    def test_api_failure_policy_controls_actual_mock_process_attempts(self):
        from app import create_app
        from api import collect_api
        from unittest.mock import Mock
        from db import get_db
        class InlineThread:
            def __init__(self, target, **_):
                self.target = target
            def start(self):
                self.target()
        app = create_app({'TESTING': True, 'DATABASE_PATH': self.db_path})
        script = Path(self.temp.name) / collect_api.DATA_SOURCES['bi_daily']['script']
        script.write_text('# never executed', encoding='utf-8')
        for text, attempts, expected in [('MANUAL_LOGIN_REQUIRED', 1, 'auth_required'),
                ('PermissionError: denied', 1, 'blocked'), ('unknown failure', 1, 'failed'),
                ('HTTP 429\nRetry-After: 9999', 1, 'blocked'), ('connection reset', 3, 'failed')]:
            with self.subTest(text=text), \
                    patch.object(collect_api, 'COLLECTORS_DIR', self.temp.name), \
                    patch.object(collect_api, 'check_collect_env', return_value=None), \
                    patch.object(collect_api, '_browser_for_sources', return_value=None), \
                    patch.object(collect_api, 'save_collect_state'), \
                    patch.object(collect_api.threading, 'Thread', InlineThread), \
                    patch('time.sleep'), \
                    patch('subprocess.Popen', return_value=Mock(returncode=1, communicate=Mock(return_value=(text, None)))) as spawn:
                response = app.test_client().post('/api/collect/trigger', json={'source': 'bi_daily'})
                self.assertIn(response.status_code, (200, 202))
                self.assertEqual(spawn.call_count, attempts)
                with get_db(self.db_path) as conn:
                    row = conn.execute('SELECT status FROM collector_runs ORDER BY created_at DESC LIMIT 1').fetchone()
                self.assertEqual(row['status'], expected)

    def test_duplicate_retry_cannot_spawn_or_publish(self):
        from services.collector_run_service import create_run, acquire_lease, get_run
        from services.collector_retry_service import _run_retry
        owner = create_run('bi_daily', 'default', db_path=self.db_path)
        self.assertTrue(acquire_lease('bi_daily', 'default', owner, db_path=self.db_path))
        duplicate = create_run('bi_daily', 'default', db_path=self.db_path)
        with patch('services.collector_retry_service.subprocess.run') as spawn:
            _run_retry(duplicate, {'source_key': 'bi_daily', 'shop_id': 'default', 'units': []},
                       collectors_dir=self.temp.name, python_executable=sys.executable,
                       script_name='fixture.py', db_path=self.db_path)
        spawn.assert_not_called()
        self.assertEqual(get_run(duplicate, db_path=self.db_path)['error_code'], 'ALREADY_RUNNING')

    def test_healthcheck_main_records_fetch_failure_without_sending(self):
        from scripts import collector_healthcheck as health
        import io
        output = Path(self.temp.name) / 'report.json'
        heartbeat = Path(self.temp.name) / 'heartbeat.json'
        with patch.object(sys, 'argv', ['health', '--output', str(output), '--heartbeat', str(heartbeat)]), \
                patch.object(health, 'fetch_health', side_effect=OSError('fixture refused')), \
                patch.object(health, 'notify_webhook') as send, \
                patch.dict(os.environ, {'TMALL_DB_PATH': self.db_path, 'TMALL_HEALTH_WEBHOOK': ''}), \
                patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(health.main(), 1)
        send.assert_not_called()
        report = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(report['notifications'][0]['status'], 'unconfigured')
        self.assertEqual(json.loads(heartbeat.read_text(encoding='utf-8'))['status'], 'error')

    def test_api_fact_acceptance_drives_real_gap_recovery_not_run_success(self):
        from datetime import datetime, timedelta
        from app import create_app
        from api import collect_api
        from db import get_db
        from scripts.collector_healthcheck import persist_alerts
        from services.collector_run_service import create_run, update_run, list_health_alerts
        dates = [(datetime.now().date() - timedelta(days=n)).isoformat() for n in range(1, 8)]
        with get_db(self.db_path) as conn:
            conn.execute("CREATE TABLE fixture_facts(date TEXT, metric REAL, shop_id TEXT DEFAULT 'default')")
            conn.executemany('INSERT INTO fixture_facts(date,metric) VALUES (?, 0)', [(d,) for d in dates])
            conn.execute('UPDATE fixture_facts SET metric=NULL WHERE date=?', (dates[0],))
            conn.commit()
        run = create_run('fixture', 'default', db_path=self.db_path)
        update_run(run, status='succeeded', db_path=self.db_path)
        app = create_app({'TESTING': True, 'DATABASE_PATH': self.db_path, 'SHOP_ID':'default'})
        with patch.dict(collect_api.DATA_SOURCES, {'fixture': {'name': 'fixture', 'table': 'fixture_facts', 'date_col': 'date'}}, clear=True), \
                patch.dict(collect_api.COLLECTOR_CATALOG, {'fixture': {'fields': ['date', 'metric']}}, clear=True):
            before = app.test_client().get('/api/collect/health').get_json()
            self.assertEqual(before['data']['sources'][0]['coverage_acceptance']['status'], 'partial')
            persist_alerts(before, self.db_path)
            self.assertTrue(any(x['alert_type'] == 'date_gap' for x in list_health_alerts(db_path=self.db_path)))
            with get_db(self.db_path) as conn:
                conn.execute('UPDATE fixture_facts SET metric=0')
                conn.commit()
            after = app.test_client().get('/api/collect/health').get_json()
            self.assertEqual(after['data']['sources'][0]['coverage_acceptance']['status'], 'verified')
            persist_alerts(after, self.db_path)
            self.assertFalse(any(x['alert_type'] == 'date_gap' for x in list_health_alerts(db_path=self.db_path)))

    def test_zero_exit_requires_bound_complete_receipt_and_requested_facts(self):
        from app import create_app
        from api import collect_api as api
        from db import get_db
        from unittest.mock import Mock
        from services.collector_run_service import get_run
        class InlineThread:
            def __init__(self, target, **_): self.target = target
            def start(self): self.target()
        app = create_app({'TESTING': True, 'DATABASE_PATH': self.db_path})
        (Path(self.temp.name) / api.DATA_SOURCES['bi_daily']['script']).write_text('# fixture')
        with get_db(self.db_path) as conn:
            conn.execute("INSERT INTO products(product_id,title) VALUES('p','fixture')")
            conn.execute("INSERT INTO daily_data(shop_id,product_id,date,payment_amount) VALUES('default','p','2020-01-01',1)")
            conn.commit()
        for case, expected in [('auth', 'auth_required'), ('unit_failed', 'failed'), ('legacy', 'blocked'),
                               ('old_facts', 'failed'), ('partial_5_of_1873', 'blocked'),
                               ('wrong_run', 'blocked'), ('zero_metric', 'succeeded')]:
            def spawn(*_, **kwargs):
                env = kwargs['env']
                receipt = {'event': 'result', 'schema_version': 1, 'source_key': 'bi_daily',
                    'run_id': env['TMALL_COLLECT_RUN_ID'], 'window_start': '2026-10-16', 'window_end': '2026-10-16',
                    'status': 'succeeded', 'return_code': 0, 'quality_gate': 'passed', 'row_count': 1,
                    'coverage': {'expected_units': 1, 'succeeded_units': 1, 'failed_units': 0, 'complete': True}}
                output = 'RESULT_JSON ' + json.dumps(receipt)
                if case == 'auth': output = 'MANUAL_LOGIN_REQUIRED'
                if case == 'legacy': output = 'completed'
                if case == 'unit_failed': output = 'CHECKPOINT_JSON ' + json.dumps({'event': 'checkpoint', 'unit_type': 'product', 'unit_key': 'p', 'status': 'failed'})
                if case == 'wrong_run':
                    receipt['run_id'] = 'another-run'; output = 'RESULT_JSON ' + json.dumps(receipt)
                if case == 'partial_5_of_1873':
                    receipt.update(row_count=5, coverage={'expected_units': 1873, 'succeeded_units': 5, 'failed_units': 0, 'complete': True})
                    output = 'RESULT_JSON ' + json.dumps(receipt)
                if case == 'zero_metric':
                    with get_db(self.db_path) as conn:
                        conn.execute("INSERT INTO daily_data(shop_id,product_id,date,payment_amount) VALUES('default','p','2026-10-16',0)")
                        conn.commit()
                return Mock(returncode=0, communicate=Mock(return_value=(output, None)))
            with self.subTest(case=case), patch.object(api, 'COLLECTORS_DIR', self.temp.name), \
                    patch.object(api, 'check_collect_env', return_value=None), \
                    patch.object(api, '_browser_for_sources', return_value=None), patch.object(api, 'save_collect_state'), \
                    patch.object(api.threading, 'Thread', InlineThread), patch('subprocess.Popen', side_effect=spawn):
                response = app.test_client().post('/api/collect/trigger', json={'source': 'bi_daily', 'date': '2026-10-16'})
                run_id = response.get_json()['data']['run_id']
                self.assertEqual(get_run(run_id, db_path=self.db_path)['status'], expected)
                with get_db(self.db_path) as conn:
                    count = conn.execute("SELECT COUNT(*) FROM collector_data_staging WHERE batch_id=? AND status='published'", (run_id,)).fetchone()[0]
                self.assertEqual(count, 1 if case == 'zero_metric' else 0)

    def test_sequential_retry_and_stale_queued_plan_do_not_republish(self):
        from services import collector_retry_service as retry
        from services.collector_run_service import create_run, update_run, upsert_checkpoint, get_run
        from types import SimpleNamespace
        from db import get_db
        class InlineThread:
            def __init__(self, target, args=(), kwargs=None, **_): self.target,self.args,self.kwargs=target,args,kwargs or {}
            def start(self): self.target(*self.args, **self.kwargs)
        parent = create_run('bi_daily', 'default', db_path=self.db_path, window_start='2026-10-01', window_end='2026-10-01')
        update_run(parent, status='failed', db_path=self.db_path)
        upsert_checkpoint(parent, 'product', 'p', status='failed', db_path=self.db_path)
        stale_plan = retry.build_retry_plan(parent, db_path=self.db_path)
        output = 'CHECKPOINT_JSON '+json.dumps({'event':'checkpoint','unit_type':'product','unit_key':'p','status':'succeeded','row_count':1})
        with get_db(self.db_path) as conn:
            conn.execute("INSERT INTO daily_data(shop_id,product_id,date,payment_amount) VALUES('default','p','2026-10-01',0)")
            conn.commit()
        def process(*args, **kwargs):
            env = kwargs['env']
            self.assertEqual(env['TMALL_WINDOW_START'], '2026-10-01')
            self.assertEqual(env['TMALL_WINDOW_END'], '2026-10-01')
            self.assertEqual(env['TMALL_SHOP_ID'], 'default')
            receipt = {'event':'result','schema_version':1,'source_key':'bi_daily','run_id':env['TMALL_COLLECT_RUN_ID'],
                'window_start':env['TMALL_WINDOW_START'],'window_end':env['TMALL_WINDOW_END'],
                'status':'succeeded','return_code':0,'row_count':1,'quality_gate':'passed',
                'coverage':{'expected_units':1,'succeeded_units':1,'failed_units':0,'complete':True}}
            return SimpleNamespace(returncode=0, stdout=output+'\nRESULT_JSON '+json.dumps(receipt), stderr='')
        with patch('api.collect_api._browser_for_sources', return_value=None), \
                patch.object(retry, 'resolve_python', return_value='fixture-python'), \
                patch.object(retry.threading, 'Thread', InlineThread), \
                patch.object(retry.subprocess, 'run', side_effect=process) as spawn:
            first = retry.start_retry(parent, collectors_dir=self.temp.name, python_executable=sys.executable,
                script_name='fixture.py', db_path=self.db_path, execute=True)
            second = retry.start_retry(parent, collectors_dir=self.temp.name, python_executable=sys.executable,
                script_name='fixture.py', db_path=self.db_path, execute=True)
            queued = create_run('bi_daily', 'default', db_path=self.db_path, requested_by=f'retry:{parent}')
            retry._run_retry(queued, stale_plan, collectors_dir=self.temp.name, python_executable=sys.executable,
                script_name='fixture.py', db_path=self.db_path)
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(first['child_run_id'], second['child_run_id'])
        self.assertFalse(second['started'])
        self.assertFalse(retry.build_retry_plan(parent, db_path=self.db_path)['executable'])
        self.assertEqual(get_run(queued, db_path=self.db_path)['error_code'], 'RETRY_ALREADY_RECOVERED')
        with get_db(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM collector_checkpoints WHERE run_id=? AND status='failed'", (parent,)).fetchone()[0], 1)


    def test_snapshot_and_date_acceptance_are_shop_bound(self):
        from db import get_db
        from services.collector_run_service import create_run, stage_source_snapshot, verify_fact_dates, list_data_staging
        run = create_run('bi_daily', 'default', db_path=self.db_path)
        with get_db(self.db_path) as conn:
            conn.execute("INSERT INTO daily_data(shop_id,product_id,date,payment_amount) VALUES('other-shop','p','2026-10-01',0)")
            conn.commit()
            acceptance = verify_fact_dates(conn, 'daily_data', 'date', ['payment_amount'], ['2026-10-01'], shop_id='default')
            self.assertEqual(acceptance['verified_dates'], [])
        args = dict(db_path=self.db_path, window_start='2026-10-01', window_end='2026-10-01', expected_rows=1, required_fields=['product_id','date','payment_amount'])
        self.assertEqual(stage_source_snapshot(run, 'bi_daily', 'daily_data', 'date', **args)['status'], 'rejected')
        self.assertEqual(list_data_staging(run, db_path=self.db_path), [])
        with get_db(self.db_path) as conn:
            conn.execute("INSERT INTO daily_data(shop_id,product_id,date,payment_amount) VALUES('default','p','2026-10-01',0)")
            conn.commit()
        self.assertEqual(stage_source_snapshot(run, 'bi_daily', 'daily_data', 'date', **args)['row_count'], 1)
        self.assertEqual({json.loads(row['payload_json'])['shop_id'] for row in list_data_staging(run, db_path=self.db_path)}, {'default'})

    def test_retry_receipt_failure_cannot_close_success_checkpoint(self):
        from services import collector_retry_service as retry
        from services.collector_run_service import create_run, upsert_checkpoint, get_run
        from types import SimpleNamespace
        from db import get_db
        with get_db(self.db_path) as conn:
            for day in ('2026-10-01','2026-10-02','2026-10-03'):
                conn.execute("INSERT INTO daily_data(shop_id,product_id,date,payment_amount) VALUES('default','p',?,0)", (day,))
            conn.commit()
        for case in ('missing','failed_then_success','partial','wrong_run','wrong_shop_facts','complete'):
            with self.subTest(case=case):
                parent = create_run('bi_daily', 'default', db_path=self.db_path, window_start='2026-10-01', window_end='2026-10-03')
                upsert_checkpoint(parent, 'product', 'p', status='failed', db_path=self.db_path)
                plan = retry.build_retry_plan(parent, db_path=self.db_path)
                child = create_run('bi_daily', 'default', db_path=self.db_path, requested_by=f'retry:{parent}', window_start=plan['window_start'], window_end=plan['window_end'])
                def process(*args, **kwargs):
                    env=kwargs['env']
                    self.assertEqual((env['TMALL_WINDOW_START'],env['TMALL_WINDOW_END'],env['TMALL_SHOP_ID']), ('2026-10-01','2026-10-03','default'))
                    receipt={'event':'result','schema_version':1,'source_key':'bi_daily','run_id':child,
                        'window_start':env['TMALL_WINDOW_START'],'window_end':env['TMALL_WINDOW_END'],
                        'status':'succeeded','return_code':0,'row_count':3,'quality_gate':'passed',
                        'coverage':{'expected_units':3,'succeeded_units':3,'failed_units':0,'complete':True}}
                    lines=['CHECKPOINT_JSON '+json.dumps({'event':'checkpoint','unit_type':'product','unit_key':'p','status':'succeeded','row_count':3})]
                    if case=='failed_then_success':
                        lines.append('RESULT_JSON '+json.dumps({**receipt,'status':'failed','quality_gate':'failed','error_code':'QUALITY_GATE_FAILED'}))
                    if case=='partial':receipt['coverage'].update(expected_units=1873)
                    if case=='wrong_run':receipt['run_id']='old-run'
                    if case=='wrong_shop_facts':
                        with get_db(self.db_path) as conn:
                            conn.execute("UPDATE daily_data SET shop_id='other-shop'");conn.commit()
                    if case!='missing':lines.append('RESULT_JSON '+json.dumps(receipt))
                    return SimpleNamespace(returncode=0,stdout='\n'.join(lines),stderr='')
                with patch('api.collect_api._browser_for_sources',return_value=None), patch.object(retry,'resolve_python',return_value='fixture-python'), patch.object(retry.subprocess,'run',side_effect=process):
                    retry._run_retry(child,plan,collectors_dir=self.temp.name,python_executable='fixture',script_name='none',db_path=self.db_path)
                self.assertEqual(get_run(child,db_path=self.db_path)['status']=='succeeded',case=='complete')
                self.assertEqual(retry.build_retry_plan(parent,db_path=self.db_path)['unit_count'],0 if case=='complete' else 1)
                self.assertEqual(retry.retry_diff(parent,child,db_path=self.db_path)['recovered'],1 if case=='complete' else 0)
                with get_db(self.db_path) as conn:
                    conn.execute("UPDATE daily_data SET shop_id='default'");conn.commit()


class LauncherOrderingTests(unittest.TestCase):
    def test_runtime_preflight_precedes_lock_and_credentials(self):
        script = (ROOT / 'scripts/auto-collect.ps1').read_text(encoding='utf-8-sig')
        self.assertIn("Invoke-CollectorPreflight 'runtime'", script)
        runtime = script.index("Invoke-CollectorPreflight 'runtime'")
        self.assertLess(runtime, script.index('if (Test-CollectLockBusy)'))
        self.assertLess(runtime, script.index('$BIUsername ='))
        self.assertLess(script.index("Invoke-CollectorPreflight 'ready'"),
                        script.index('$cookieExportScript ='))


class RuntimeResolverTests(unittest.TestCase):
    def test_priority_invalid_config_and_fallback(self):
        from scripts.runtime_paths import resolve_python, RuntimeConfigurationError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            self.assertEqual(resolve_python(root, environ={}, fallback=sys.executable), sys.executable)
            record = root / 'data/runtime.json'
            record.write_text('{bad', encoding='utf-8')
            with self.assertRaises(RuntimeConfigurationError):
                resolve_python(root, environ={}, fallback=sys.executable)
            self.assertEqual(resolve_python(root, environ={'TMALL_COLLECT_PYTHON': sys.executable}), sys.executable)
            record.write_text(json.dumps({'schema_version': 1, 'python': sys.executable,
                                         'runtime_root': str(Path(sys.executable).parent)}), encoding='utf-8')
            self.assertEqual(resolve_python(root, environ={}), sys.executable)
            for value in ('relative.exe', str(root / 'missing.exe'), ''):
                with self.assertRaises(RuntimeConfigurationError):
                    resolve_python(root, environ={'TMALL_COLLECT_PYTHON': value})

    @unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'Windows resolver')
    def test_powershell_reads_same_record_and_rejects_bad_config(self):
        from scripts.runtime_paths import resolve_python
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            record = root / 'data/runtime.json'
            record.write_text(json.dumps({'schema_version': 1, 'python': sys.executable,
                                         'runtime_root': str(Path(sys.executable).parent)}), encoding='utf-8')
            env = dict(os.environ)
            env.pop('TMALL_COLLECT_PYTHON', None)
            # PowerShell writes its console encoding (GBK on a Chinese Windows), while
            # Python decodes pipes as UTF-8 under PYTHONUTF8=1 — the reader thread then
            # dies on the error text of the bad-config case. Pin PS output to UTF-8.
            prelude = "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
            command = prelude + f". '{ROOT / 'scripts/resolve_runtime.ps1'}'; Resolve-CollectorPython -ProjectRoot '{root}'"
            # Process-local policy matches the existing scheduled action; no machine policy change.
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), resolve_python(root, environ={}))
            record.write_text('{bad', encoding='utf-8')
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
            self.assertNotEqual(result.returncode, 0)


class PreflightTests(unittest.TestCase):
    def run_check(self, root, **kwargs):
        from scripts.collector_preflight import preflight
        return preflight(root=root, sources=['bi_daily'], phase='ready',
                         directories={'cookies': root, 'logs': root, 'checkpoints': root},
                         runtime_probe=lambda: None,
                         browser_probe=lambda: None,
                         fetch_json=lambda url: {'ok': True, 'data': {'service': 'tmall-dashboard', 'database': 'ok'}, 'webSocketDebuggerUrl': 'ws://127.0.0.1:9223/devtools/browser/x'},
                         **kwargs)

    def test_unknown_login_not_success_but_runtime_can_be_checked_without_login(self):
        from scripts.collector_preflight import preflight
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_check(root, login_probe=lambda source: None)
            self.assertFalse(result['ok'])
            self.assertEqual(result['checks'][-1]['status'], 'unknown')
            self.assertEqual(result['checks'][-1]['code'], 'LOGIN_UNKNOWN')
            runtime = preflight(root=root, sources=['bi_daily'], phase='runtime',
                                directories={'logs': root}, runtime_probe=lambda: None,
                                login_probe=lambda source: self.fail('runtime must not read login'))
            self.assertTrue(runtime['ok'])
            self.assertFalse(runtime['collection_ready'])

    def test_healthy_runtime_and_verified_login(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_check(root, login_probe=lambda source: True)
            self.assertTrue(result['ok'])
            self.assertTrue(result['collection_ready'])
            self.assertEqual(list(root.iterdir()), [])

    def test_denied_write_stops_before_network_or_login(self):
        from scripts.collector_preflight import preflight
        with tempfile.TemporaryDirectory() as tmp:
            with patch('scripts.collector_preflight.probe_directory', side_effect=PermissionError('denied')):
                result = preflight(root=Path(tmp), sources=['bi_daily'], phase='ready',
                                   directories={'cookies': Path(tmp)}, runtime_probe=lambda: None,
                                   fetch_json=lambda url: self.fail('network before writable runtime'),
                                   login_probe=lambda source: self.fail('login before writable runtime'))
            self.assertFalse(result['ok'])
            self.assertIn('DIRECTORY_PERMISSION_DENIED', [row['code'] for row in result['checks']])

    def test_missing_directory_not_created(self):
        from scripts.collector_preflight import probe_directory
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'missing'
            with self.assertRaises(FileNotFoundError):
                probe_directory(missing)
            self.assertFalse(missing.exists())

    def test_loopback_only_proxy_bypass(self):
        from scripts.collector_preflight import open_json
        with patch('scripts.collector_preflight.urllib.request.build_opener') as build:
            build.return_value.open.return_value.__enter__.return_value.read.return_value = b'{}'
            with patch.dict(os.environ, {'HTTP_PROXY': 'http://proxy.invalid:9999', 'HTTPS_PROXY': 'http://proxy.invalid:9999'}):
                open_json('http://127.0.0.1:9223/json/version')
                self.assertEqual(build.call_args.args[0].proxies, {})
                open_json('https://example.com/status')
                self.assertNotEqual(build.call_args.args[0].proxies, {})

    def test_missing_import_stops_before_file_or_network_access(self):
        from scripts.collector_preflight import preflight
        def missing():
            raise ModuleNotFoundError('fixture')
        with patch('scripts.collector_preflight.probe_directory') as directory:
            result = preflight(root=ROOT, sources=['bi_daily'], runtime_probe=missing)
        self.assertFalse(result['ok'])
        self.assertEqual(result['checks'][0]['code'], 'RUNTIME_IMPORT_FAILED')
        directory.assert_not_called()

    def test_unhealthy_service_does_not_check_login(self):
        from scripts.collector_preflight import preflight
        with tempfile.TemporaryDirectory() as tmp:
            result = preflight(root=Path(tmp), sources=['bi_daily'], phase='ready',
                               directories={'logs': Path(tmp)}, runtime_probe=lambda: None,
                               browser_probe=lambda: None,
                               fetch_json=lambda url: {'ok': False},
                               login_probe=lambda source: self.fail('service not ready'))
        self.assertFalse(result['ok'])
        self.assertIn('SERVICE_UNAVAILABLE', [row['code'] for row in result['checks']])

    def test_auth_required_and_wxt_unknown_are_not_ready(self):
        from scripts.collector_preflight import probe_session
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_check(Path(tmp), login_probe=lambda source: False)
        self.assertFalse(result['ok'])
        self.assertEqual(result['checks'][-1]['code'], 'LOGIN_REQUIRED')
        self.assertIsNone(probe_session('wanxiangtai', 'http://127.0.0.1:9223',
                                       lambda url: self.fail('must not invent WXT login proof')))

    def test_unknown_source_is_rejected_before_any_probe(self):
        from scripts.collector_preflight import preflight
        result = preflight(root=ROOT, sources=['not-a-source'],
                           runtime_probe=lambda: self.fail('invalid source'))
        self.assertFalse(result['ok'])

    def test_cli_classifies_failures_even_when_ready_phase_requested(self):
        from scripts.collector_preflight import main
        for name, code, expected in [('cookies', 'DIRECTORY_PERMISSION_DENIED', 20),
                                     ('service', 'SERVICE_UNAVAILABLE', 21),
                                     ('login:bi_daily', 'LOGIN_UNKNOWN', 22)]:
            with self.subTest(code=code), patch('scripts.collector_preflight.preflight', return_value={
                    'ok': False, 'checks': [{'name': name, 'code': code, 'status': 'unknown'}]}), patch('builtins.print'):
                self.assertEqual(main(['--sources', 'bi_daily', '--phase', 'ready']), expected)


class ApiRuntimeTests(unittest.TestCase):
    def test_monthly_aggregation_is_not_blocked_by_missing_browser(self):
        import api.collect_api as api
        with patch.object(api, 'resolve_browser', side_effect=AssertionError('local aggregation needs no browser')):
            self.assertIsNone(api._browser_for_sources({'bi_monthly'}))
            self.assertEqual(api.prepare_collect_pages(['bi_monthly']), (True, '月度聚合不需要浏览器'))

    def test_browser_identity_failure_blocks_trigger_before_thread(self):
        from flask import Flask
        import api.collect_api as api
        from scripts.browser_runtime import BrowserConfigurationError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / api.DATA_SOURCES['bi_daily']['script']).write_text('# fixture', encoding='utf-8')
            app = Flask('trigger-browser-fixture')
            app.config['DATABASE_PATH'] = str(root / 'unused.db')
            app.register_blueprint(api.collect_bp)
            with patch.object(api, 'COLLECTORS_DIR', str(root)), patch.object(api, 'create_run', return_value='fixture'), \
                    patch.object(api, 'get_shop_id', return_value='default'), patch.object(api, 'update_run') as update, \
                    patch.object(api, 'resolve_python', return_value=sys.executable), \
                    patch.object(api, '_browser_for_sources', side_effect=BrowserConfigurationError('BROWSER_PROFILE_MISMATCH')), \
                    patch.object(api.threading, 'Thread') as thread:
                response = app.test_client().post('/api/collect/trigger', json={'source': 'bi_daily'})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json()['code'], 'BROWSER_NOT_READY')
            self.assertEqual(update.call_args.kwargs['status'], 'blocked')
            thread.assert_not_called()

    def test_invalid_runtime_blocks_trigger_without_spawning_or_taking_lease(self):
        from flask import Flask
        import api.collect_api as api
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / api.DATA_SOURCES['bi_daily']['script']).write_text('# fixture', encoding='utf-8')
            app = Flask('trigger-runtime-fixture')
            app.config['DATABASE_PATH'] = str(root / 'unused.db')
            app.register_blueprint(api.collect_bp)
            with (patch.object(api, 'COLLECTORS_DIR', str(root)),
                  patch.object(api, 'create_run', return_value='fixture-run'),
                  patch.object(api, 'get_shop_id', return_value='default'),
                  patch.object(api, 'update_run') as update,
                  patch.object(api, 'acquire_lease') as lease,
                  patch.object(api.threading, 'Thread') as thread,
                  patch.dict(os.environ, {'TMALL_COLLECT_PYTHON': str(root / 'missing.exe')})):
                response = app.test_client().post('/api/collect/trigger', json={'source': 'bi_daily'})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json()['code'], 'RUNTIME_CONFIG_INVALID')
            self.assertEqual(update.call_args.kwargs['status'], 'blocked')
            lease.assert_not_called()
            thread.assert_not_called()

    def test_prepare_uses_runtime_record_and_preserves_remote_proxy(self):
        from flask import Flask
        import api.collect_api as api
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'scripts').mkdir()
            (root / 'scripts/auto_login_bi.py').write_text('# fixture', encoding='utf-8')
            (root / 'data').mkdir()
            record = root / 'data/runtime.json'
            record.write_text(json.dumps({'schema_version': 1, 'python': sys.executable,
                                         'runtime_root': str(Path(sys.executable).parent)}), encoding='utf-8')
            app = Flask('runtime-fixture')
            app.config['DATABASE_PATH'] = str(root / 'fixture.db')
            browser = {'host': '127.0.0.1', 'port': 41999, 'executable': 'fixture-browser',
                       'user_data_dir': 'fixture-profile', 'reuse_only': True}
            with app.app_context(), patch.object(api, 'PROJECT_ROOT', root), \
                    patch.object(api, '_browser_for_sources', return_value=browser), \
                    patch.dict(os.environ, {'HTTPS_PROXY': 'http://proxy.invalid:8080'}):
                with patch.object(api.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='ready', stderr='')) as run:
                    ok, _ = api.prepare_collect_pages(['bi_daily'])
                self.assertTrue(ok)
                self.assertEqual(run.call_args.args[0][0], sys.executable)
                self.assertEqual(run.call_args.kwargs['env']['HTTPS_PROXY'], 'http://proxy.invalid:8080')
                self.assertIn('127.0.0.1', run.call_args.kwargs['env']['NO_PROXY'])
                self.assertEqual(run.call_args.kwargs['env']['TMALL_CDP_PORT'], '41999')
                self.assertEqual(run.call_args.kwargs['env']['TMALL_CHROME_REUSE_ONLY'], '1')
                with patch.dict(os.environ, {'TMALL_COLLECT_PYTHON': str(root / 'missing.exe')}), patch.object(api.subprocess, 'run') as run:
                    ok, error = api.prepare_collect_pages(['bi_daily'])
                self.assertFalse(ok)
                self.assertIn('RUNTIME_PATH_INVALID', error)
                run.assert_not_called()


class BrowserConfigurationTests(unittest.TestCase):
    def test_captcha_never_kills_or_restarts_browser_even_legacy_login(self):
        import scripts.auto_login_bi as bi
        import scripts.auto_login_wanxiangtai as wxt
        with patch.object(bi, 'get_page_ws', return_value='fixture'), \
                patch.object(bi, 'cdp_evaluate', side_effect=['submitted', '{"captcha":true}', True]), \
                patch.object(bi.time, 'sleep'), patch.object(bi.subprocess, 'run') as run, \
                patch.object(bi.subprocess, 'Popen') as spawn, patch('builtins.print'):
            self.assertFalse(bi.login_taobao_tab('fixture-user', 'fixture-secret'))
            run.assert_not_called()
            spawn.assert_not_called()
        with patch.object(wxt, 'load_credentials'), patch.object(wxt, 'USERNAME', 'fixture-user'), \
                patch.object(wxt, 'PASSWORD', 'fixture-secret'), \
                patch.object(wxt, 'find_tab', return_value={'webSocketDebuggerUrl': 'fixture'}), \
                patch.object(wxt, 'cdp_eval', side_effect=['filled', 'clicked', 'need_slider']), \
                patch.object(wxt.time, 'sleep'), patch.object(wxt.subprocess, 'run') as run, \
                patch.object(wxt.subprocess, 'Popen') as spawn, patch('builtins.print'):
            self.assertFalse(wxt.do_login())
            run.assert_not_called()
            spawn.assert_not_called()

    def fixture_config(self, root):
        executable = root / 'Selected Browser/chrome.exe'
        executable.parent.mkdir()
        executable.write_bytes(b'fixture-not-executable')
        profile = root / 'User Data'
        profile.mkdir()
        return {'schema_version': 1, 'executable': str(executable), 'user_data_dir': str(profile),
                'host': '127.0.0.1', 'port': 9223, 'reuse_only': True}

    def test_explicit_browser_record_and_bad_record_never_fall_back(self):
        from scripts.browser_runtime import resolve_browser, BrowserConfigurationError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.fixture_config(root)
            with self.assertRaises(BrowserConfigurationError):
                resolve_browser(root, environ={})
            (root / 'data').mkdir()
            record = root / 'data/collector-browser.json'
            record.write_text(json.dumps(config), encoding='utf-8')
            self.assertEqual(resolve_browser(root, environ={}), config)
            with self.assertRaises(BrowserConfigurationError):
                resolve_browser(root, environ={'TMALL_CHROME_PATH': str(root / 'missing.exe')})
            record.write_text('{bad', encoding='utf-8')
            with self.assertRaises(BrowserConfigurationError):
                resolve_browser(root, environ={'TMALL_CHROME_PATH': config['executable'],
                                             'TMALL_CHROME_PROFILE': config['user_data_dir']})

    def test_listener_executable_and_profile_must_all_match(self):
        from scripts.browser_runtime import verify_browser_identity
        with tempfile.TemporaryDirectory() as tmp:
            config = self.fixture_config(Path(tmp))
            row = {'address': '127.0.0.1', 'pid': 123, 'executable': config['executable'],
                   'command_line': f'"{config["executable"]}" --user-data-dir="{config["user_data_dir"]}"'}
            self.assertTrue(verify_browser_identity(config, process_probe=lambda _: [row])['ok'])
            for field, value, code in [('address', '::1', 'BROWSER_LISTENER_MISMATCH'),
                                       ('executable', sys.executable, 'BROWSER_EXECUTABLE_MISMATCH'),
                                       ('command_line', '--user-data-dir=wrong', 'BROWSER_PROFILE_MISMATCH')]:
                with self.subTest(field=field):
                    result = verify_browser_identity(config, process_probe=lambda _: [dict(row, **{field: value})])
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['code'], code)
            self.assertEqual(verify_browser_identity(config, process_probe=lambda _: [])['code'], 'BROWSER_NOT_RUNNING')

    def test_bi_reuse_requires_verified_session_without_credentials_or_navigation(self):
        import scripts.auto_login_bi as login
        config = {'host': '127.0.0.1', 'port': 9223, 'reuse_only': True}
        for session, expected in [(None, 22), (False, 22), (True, 0)]:
            with self.subTest(session=session), patch.object(login, 'resolve_browser', return_value=config), \
                    patch.object(login, 'require_browser_identity'), patch.object(login, 'probe_session', return_value=session), \
                    patch.object(login, 'get_page_ws', return_value='fixture-page'), \
                    patch.object(login, 'load_saved_credentials') as credentials, patch.object(login, 'create_target') as navigation, \
                    patch.object(login.subprocess, 'Popen') as spawn, patch.object(sys, 'argv', ['fixture', '--sources', 'bi_daily']), \
                    patch('builtins.print'):
                self.assertEqual(login.main(), expected)
                credentials.assert_not_called()
                navigation.assert_not_called()
                spawn.assert_not_called()

    def test_wxt_unknown_is_not_login_and_does_not_read_credentials(self):
        import scripts.auto_login_wanxiangtai as login
        with patch.object(login, 'resolve_browser', return_value={'port': 9223, 'reuse_only': True}), \
                patch.object(login, 'require_browser_identity'), patch.object(login, 'probe_session', return_value=None), \
                patch.object(login, 'load_credentials') as credentials, patch.object(login, 'create_tab') as navigation, \
                patch.object(login, 'do_login') as do_login, patch('builtins.print'):
            self.assertEqual(login.main(), 22)
            credentials.assert_not_called()
            navigation.assert_not_called()
            do_login.assert_not_called()


if __name__ == '__main__':
    unittest.main()

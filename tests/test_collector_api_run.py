import os
import tempfile
import unittest
from unittest.mock import patch


class CollectorApiRunTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-collector-api-')
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db'),
            'IMPORT_SCAN_ALLOWED_ROOTS': [self.temp_dir.name],
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_run_returns_structured_not_found(self):
        response = self.client.get('/api/collect/runs/not-found')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['code'], 'RUN_NOT_FOUND')

    def test_health_endpoint_reports_sources_and_staging_window(self):
        response = self.client.get('/api/collect/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['source_count'], 9)
        self.assertIn('staging_7d', data)
        self.assertIn('status', data)
        self.assertIn('consecutive_failures', data['sources'][0])

    def test_catalog_endpoint_exposes_source_contract(self):
        response = self.client.get('/api/collect/catalog')
        self.assertEqual(response.status_code, 200)
        sources = response.get_json()['data']['sources']
        self.assertEqual(len(sources), 9)
        sycm = next(item for item in sources if item['source_key'] == 'sycm_flow')
        self.assertEqual(sycm['publish_mode'], 'staging_atomic')
        self.assertIn('channel_name', sycm['fields'])

    def test_health_endpoint_marks_failed_run_as_degraded(self):
        from services.collector_run_service import create_run, update_run
        run_id = create_run('bi_daily', 'default', db_path=self.app.config['DATABASE_PATH'])
        update_run(run_id, status='failed', db_path=self.app.config['DATABASE_PATH'],
                   error_code='TEST_FAILURE', error_message='fixture')
        response = self.client.get('/api/collect/health')
        self.assertEqual(response.get_json()['data']['status'], 'degraded')

    def test_health_endpoint_exposes_fact_age(self):
        response = self.client.get('/api/collect/health')
        source = response.get_json()['data']['sources'][0]
        self.assertIn('age_days', source)

    def test_disabled_source_is_listed_but_excluded_from_unhealthy(self):
        """未启用的源（dts_market / dmp_shop）仍会列出，但不参与 unhealthy 判定。

        它们依赖独立的挖象浏览器（CDP 9224）+ 人工登录/插件，环境未就绪、
        从未被调度，所以没有运行记录。若把它们算进健康度，整体状态会永远是
        degraded，真正的告警就被噪音淹没了。
        """
        data = self.client.get('/api/collect/health').get_json()['data']
        by_key = {source['source_key']: source for source in data['sources']}

        self.assertEqual(data['source_count'], 9)          # 仍然列出，不隐藏
        disabled = {'dts_market', 'dmp_shop', 'dmp_competition'}
        for key in disabled:
            self.assertFalse(by_key[key]['enabled'])
        self.assertTrue(all(source['enabled'] for key, source in by_key.items()
                            if key not in disabled))

        # 夹具里没有任何采集记录：启用的源都算 unhealthy，未启用的那个不算
        enabled = [source for source in data['sources'] if source['enabled']]
        self.assertEqual(data['unhealthy_count'], len(enabled))
        self.assertEqual(data['status'], 'degraded')

    def test_status_uses_durable_run_and_reconciles_stale_state(self):
        from datetime import datetime, timedelta, timezone
        from services.collector_run_service import create_run
        from db import get_db

        run_id = create_run('bi_daily', 'default', db_path=self.app.config['DATABASE_PATH'])
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        with self.app.app_context(), get_db() as conn:
            conn.execute(
                '''UPDATE collector_runs
                   SET status='running', created_at=?, updated_at=?
                   WHERE id=?''',
                (old, old, run_id),
            )
            conn.commit()

        response = self.client.get('/api/collect/status')
        self.assertEqual(response.status_code, 200)
        source = next(
            item for item in response.get_json()['data']['sources']
            if item['key'] == 'bi_daily'
        )
        self.assertEqual(source['status'], 'failed')
        self.assertEqual(source['run_status'], 'failed')
        self.assertEqual(source['run_id'], run_id)

    def test_status_preserves_partial_run_state(self):
        from services.collector_run_service import create_run, update_run
        run_id = create_run('bi_daily', 'default', db_path=self.app.config['DATABASE_PATH'])
        update_run(run_id, status='partial', db_path=self.app.config['DATABASE_PATH'],
                   error_code='PARTIAL_RETRY', error_message='one unit unresolved')
        response = self.client.get('/api/collect/status')
        source = next(item for item in response.get_json()['data']['sources'] if item['key'] == 'bi_daily')
        self.assertEqual(source['status'], 'partial')
        self.assertEqual(source['run_status'], 'partial')

    def test_log_recovers_durable_status_after_process_memory_is_empty(self):
        from services.collector_run_service import create_run, update_run
        import api.collect_api as collect_api

        run_id = create_run('bi_daily', 'default', db_path=self.app.config['DATABASE_PATH'])
        update_run(run_id, status='partial', db_path=self.app.config['DATABASE_PATH'],
                   error_code='PARTIAL_RETRY', error_message='one unit unresolved')
        with collect_api._state_lock:
            collect_api.collect_tasks.pop('bi_daily', None)

        response = self.client.get('/api/collect/log/bi_daily')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['status'], 'partial')
        self.assertEqual(data['run_status'], 'partial')
        self.assertEqual(data['run_id'], run_id)
        self.assertEqual(data['error'], 'one unit unresolved')

    def test_health_marks_partial_run_as_degraded(self):
        from services.collector_run_service import create_run, update_run
        run_id = create_run('bi_daily', 'default', db_path=self.app.config['DATABASE_PATH'])
        update_run(run_id, status='partial', db_path=self.app.config['DATABASE_PATH'],
                   error_code='PARTIAL_RETRY', error_message='one unit unresolved')
        response = self.client.get('/api/collect/health')
        data = response.get_json()['data']
        self.assertEqual(data['status'], 'degraded')
        source = next(item for item in data['sources'] if item['source_key'] == 'bi_daily')
        self.assertEqual(source['failed_runs_7d'], 1)
        self.assertGreaterEqual(source['consecutive_failures'], 1)

    def test_trigger_exposes_run_id_for_existing_script(self):
        import api.collect_api as collect_api

        # Explicit source/browser fixtures; never depend on the external sibling
        # collectors directory or a real CDP listener in an isolated worktree.
        script = os.path.join(self.temp_dir.name, collect_api.DATA_SOURCES['bi_daily']['script'])
        with open(script, 'w', encoding='utf-8') as handle:
            handle.write('# fixture: environment failure blocks execution\n')
        with patch.object(collect_api, 'COLLECTORS_DIR', self.temp_dir.name), \
                patch.object(collect_api, '_browser_for_sources', return_value=None), \
                patch.object(collect_api, 'check_collect_env', return_value='test environment blocked'):
            response = self.client.post('/api/collect/trigger', json={'source': 'bi_daily'})
        body = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(body['code'], 'ENVIRONMENT_ERROR')
        self.assertIsNotNone(body.get('requestId'))

        # The environment check happens after the run is created; retrieve the
        # single durable run directly to verify the failed state is persisted.
        from db import get_db
        with self.app.app_context(), get_db() as conn:
            row = conn.execute('SELECT id, status, error_code FROM collector_runs').fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['error_code'], 'ENVIRONMENT_ERROR')

    def test_structured_checkpoint_log_event_is_persisted(self):
        from api.collect_api import _consume_structured_checkpoint_events
        from db import get_db
        from services.collector_run_service import create_run

        run_id = create_run('sycm_item_flow', 'default', db_path=self.app.config['DATABASE_PATH'])
        count = _consume_structured_checkpoint_events(run_id, [
            'normal log line',
            'CHECKPOINT_JSON {"event":"checkpoint","unit_type":"product",'
            '"unit_key":"1001","page_no":2,"status":"succeeded","row_count":30}',
        ], db_path=self.app.config['DATABASE_PATH'])
        self.assertEqual(count, 1)
        with self.app.app_context(), get_db() as conn:
            row = conn.execute(
                'SELECT unit_type, unit_key, page_no, row_count FROM collector_checkpoints WHERE run_id = ?',
                (run_id,),
            ).fetchone()
        self.assertEqual(dict(row), {
            'unit_type': 'product', 'unit_key': '1001', 'page_no': 2, 'row_count': 30,
        })

    def test_coverage_event_is_normalized(self):
        from api.collect_api import _extract_coverage_event
        coverage = _extract_coverage_event([
            'CHECKPOINT_JSON {"event":"coverage","expected_units":10,'
            '"succeeded_units":8,"failed_units":2,"row_count":40}'
        ])
        self.assertEqual(coverage['expected_units'], 10)
        self.assertEqual(coverage['rate'], 0.8)

    def test_terminal_result_event_has_stable_schema(self):
        from api.collect_api import _build_result_event
        event = _build_result_event(
            'sycm_flow', 'run-1', status='succeeded', return_code=0,
            row_count=12, coverage={'rate': 1.0}, quality_gate='passed',
        )
        self.assertEqual(event['event'], 'result')
        self.assertEqual(event['schema_version'], 1)
        self.assertEqual(event['row_count'], 12)

    def test_process_failure_classifies_cdp_unavailable_and_keeps_log_tail(self):
        from api.collect_api import _classify_process_failure

        code, message = _classify_process_failure([
            'Traceback (most recent call last):',
            'urllib.error.URLError: <urlopen error [WinError 10061] connection refused>',
            'http://127.0.0.1:9223/json',
        ], 1)
        self.assertEqual(code, 'CDP_UNAVAILABLE')
        self.assertIn('CDP', message)
        self.assertIn('9223/json', message)

    def test_process_failure_keeps_generic_return_code_and_tail(self):
        from api.collect_api import _classify_process_failure

        code, message = _classify_process_failure(['collector failed: bad schema'], 2)
        self.assertEqual(code, 'PROCESS_FAILED')
        self.assertIn('返回码 2', message)
        self.assertIn('bad schema', message)

    def test_collector_alerts_endpoint_reads_persisted_alerts(self):
        from services.collector_run_service import record_health_alert
        record_health_alert('sycm_flow', 'data_delay', '延迟',
                            db_path=self.app.config['DATABASE_PATH'])
        response = self.client.get('/api/collect/alerts')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload['data']['alerts']), 1)

    def test_retry_endpoint_defaults_to_auditable_preview(self):
        from services.collector_run_service import create_run, upsert_checkpoint
        db_path = self.app.config['DATABASE_PATH']
        run_id = create_run('sycm_item_flow', 'default', db_path=db_path)
        upsert_checkpoint(run_id, 'product', 'bad', db_path=db_path, status='failed')
        response = self.client.post(f'/api/collect/runs/{run_id}/retry', json={})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body['data']['unit_count'], 1)
        self.assertNotIn('child_run_id', body['data'])

    def test_artifact_endpoint_replays_verified_content(self):
        from services.collector_run_service import create_run, persist_artifact, list_artifacts
        db_path = self.app.config['DATABASE_PATH']
        run_id = create_run('bi_daily', 'default', db_path=db_path)
        persist_artifact(run_id, 'process_output', 'hello artifact', db_path=db_path)
        artifact_id = list_artifacts(run_id, db_path=db_path)[0]['id']
        response = self.client.get(
            f'/api/collect/runs/{run_id}/artifacts/{artifact_id}?include_content=1'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['content'], 'hello artifact')

    def test_retry_diff_endpoint_returns_completion_rate(self):
        from services.collector_run_service import create_run, upsert_checkpoint
        db_path = self.app.config['DATABASE_PATH']
        parent = create_run('sycm_item_flow', 'default', db_path=db_path)
        upsert_checkpoint(parent, 'product', 'bad', db_path=db_path, status='failed')
        child = create_run('sycm_item_flow', 'default', db_path=db_path,
                           mode='retry', requested_by=f'retry:{parent}')
        upsert_checkpoint(child, 'product', 'bad', db_path=db_path, status='succeeded')
        from services.collector_run_service import update_run, record_quality_result
        update_run(child, status='succeeded', db_path=db_path)
        record_quality_result(child, 'retry_publication', status='passed', db_path=db_path)
        response = self.client.get(f'/api/collect/runs/{parent}/retry-diff/{child}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['completion_rate'], 1.0)

    def test_collector_staging_endpoint_lists_publish_status(self):
        from services.collector_run_service import create_run
        from db import get_db
        db_path = self.app.config['DATABASE_PATH']
        run_id = create_run('bi_daily', 'default', db_path=db_path)
        with self.app.app_context(), get_db() as conn:
            conn.execute(
                '''INSERT INTO collector_data_staging
                   (source_key, batch_id, unit_type, unit_key, payload_json, status)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                ('bi_daily', run_id, 'product', 'p1', '{"x":1}', 'published'),
            )
            conn.commit()
        response = self.client.get(f'/api/collect/runs/{run_id}/staging')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['quality']['status'], 'passed')
        self.assertEqual(response.get_json()['data']['rows'][0]['status'], 'published')
        self.assertNotIn('payload_json', response.get_json()['data']['rows'][0])


    def test_foreign_shop_cannot_read_run_detail(self):
        from services.collector_run_service import create_run, upsert_checkpoint
        db_path = self.app.config['DATABASE_PATH']
        run_id = create_run('sycm_item_flow', 'shop-a', db_path=db_path)
        upsert_checkpoint(run_id, 'product', '1001', db_path=db_path, status='succeeded')

        own = self.client.get(f'/api/collect/runs/{run_id}?shop_id=shop-a')
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.get_json()['data']['run']['id'], run_id)

        response = self.client.get(f'/api/collect/runs/{run_id}?shop_id=shop-b')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['code'], 'RUN_NOT_FOUND')

    def test_foreign_shop_cannot_replay_artifact(self):
        from services.collector_run_service import create_run, persist_artifact, list_artifacts
        db_path = self.app.config['DATABASE_PATH']
        run_id = create_run('bi_daily', 'shop-a', db_path=db_path)
        persist_artifact(run_id, 'process_output', 'shop-a secret', db_path=db_path)
        artifact_id = list_artifacts(run_id, db_path=db_path)[0]['id']

        own = self.client.get(
            f'/api/collect/runs/{run_id}/artifacts/{artifact_id}?include_content=1&shop_id=shop-a'
        )
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.get_json()['data']['content'], 'shop-a secret')

        response = self.client.get(
            f'/api/collect/runs/{run_id}/artifacts/{artifact_id}?include_content=1&shop_id=shop-b'
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['code'], 'ARTIFACT_NOT_FOUND')

    def test_foreign_shop_cannot_read_staging(self):
        from db import get_db
        from services.collector_run_service import create_run
        db_path = self.app.config['DATABASE_PATH']
        run_id = create_run('bi_daily', 'shop-a', db_path=db_path)
        with get_db(db_path) as conn:
            conn.execute(
                '''INSERT INTO collector_data_staging
                   (source_key, batch_id, unit_type, unit_key, payload_json, status)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                ('bi_daily', run_id, 'product', 'p1', '{"x":1}', 'published'),
            )
            conn.commit()

        own = self.client.get(f'/api/collect/runs/{run_id}/staging?shop_id=shop-a')
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.get_json()['data']['row_count'], 1)

        response = self.client.get(f'/api/collect/runs/{run_id}/staging?shop_id=shop-b')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['code'], 'RUN_NOT_FOUND')

    def test_foreign_shop_cannot_retry_run(self):
        from services.collector_run_service import create_run, upsert_checkpoint
        db_path = self.app.config['DATABASE_PATH']
        run_id = create_run('sycm_item_flow', 'shop-a', db_path=db_path)
        upsert_checkpoint(run_id, 'product', 'bad', db_path=db_path, status='failed')

        own = self.client.post(f'/api/collect/runs/{run_id}/retry?shop_id=shop-a', json={})
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.get_json()['data']['unit_count'], 1)

        response = self.client.post(f'/api/collect/runs/{run_id}/retry?shop_id=shop-b', json={})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()['code'], 'RUN_NOT_FOUND')


if __name__ == '__main__':
    unittest.main()

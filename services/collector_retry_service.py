"""Build and execute checkpoint-scoped collector retries."""

import json
import os
import subprocess
import threading
from pathlib import Path
from scripts.runtime_paths import resolve_python, loopback_proxy_env, RuntimeConfigurationError
from scripts.browser_runtime import require_browser_identity, BrowserConfigurationError

from services.collector_run_service import (
    acquire_lease,
    create_run,
    record_quality_result,
    persist_artifact,
    release_lease,
    update_run,
    upsert_checkpoint,
    list_checkpoints,
    collection_completion_evidence,
    stage_source_snapshot,
    _run_owner_clause,
)


def failed_checkpoints(run_id, *, db_path=None, shop_id=None):
    from db import get_db
    params = [run_id]
    sql = ('''SELECT unit_type, unit_key, page_no, cursor, row_count,
                     last_error_code, last_error_message
              FROM collector_checkpoints
              WHERE run_id = ? AND status IN ('failed', 'blocked')
                AND unit_type <> 'process' ''')
    sql += _run_owner_clause('collector_checkpoints', shop_id, params)
    sql += ' ORDER BY unit_type, unit_key, page_no'
    with get_db(db_path) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def build_retry_plan(run_id, *, db_path=None, shop_id=None):
    from services.collector_run_service import get_run
    parent = get_run(run_id, db_path=db_path, shop_id=shop_id)
    if not parent:
        return None
    units = failed_checkpoints(run_id, db_path=db_path, shop_id=shop_id)
    # Preserve original failure evidence, but never execute a unit that an accepted
    # child already recovered. This survives sequential requests and process restarts.
    from db import get_db
    with get_db(db_path) as conn:
        recovered = conn.execute(
            '''SELECT DISTINCT c.unit_type,c.unit_key,c.page_no FROM collector_checkpoints c
               JOIN collector_runs r ON r.id=c.run_id
               WHERE r.requested_by=? AND r.shop_id=? AND r.source_key=?
                 AND r.status='succeeded' AND c.status='succeeded'
                 AND EXISTS (SELECT 1 FROM collector_quality_results q
                     WHERE q.run_id=r.id AND q.rule_key='retry_publication' AND q.status='passed') ''',
            (f'retry:{run_id}', parent['shop_id'], parent['source_key']),
        ).fetchall()
    closed = {(row['unit_type'], row['unit_key'], row['page_no']) for row in recovered}
    units = [row for row in units if (row['unit_type'], row['unit_key'], row['page_no']) not in closed]
    return {
        'parent_run_id': run_id,
        'source_key': parent['source_key'],
        'shop_id': parent['shop_id'],
        'window_start': parent['window_start'],
        'window_end': parent['window_end'],
        'unit_count': len(units),
        'units': units,
        'executable': bool(units),
    }


def retry_diff(parent_run_id, child_run_id, *, db_path=None, shop_id=None):
    """Compare the failed-unit set of a parent run with a retry run."""
    from services.collector_run_service import get_run, list_checkpoints
    parent = get_run(parent_run_id, db_path=db_path, shop_id=shop_id)
    child = get_run(child_run_id, db_path=db_path, shop_id=shop_id)
    if not parent or not child:
        return None
    if child.get('requested_by') != f'retry:{parent_run_id}':
        raise ValueError('retry 子任务与父运行记录不匹配')
    parent_failed = {
        (row['unit_type'], row['unit_key'], row.get('page_no'))
        for row in failed_checkpoints(parent_run_id, db_path=db_path, shop_id=shop_id)
    }
    child_rows = list_checkpoints(child_run_id, db_path=db_path, shop_id=shop_id)
    from services.collector_run_service import list_quality_results
    accepted = child['status'] == 'succeeded' and any(
        row['rule_key'] == 'retry_publication' and row['status'] == 'passed'
        for row in list_quality_results(child_run_id, db_path=db_path, shop_id=shop_id))
    child_succeeded = {
        (row['unit_type'], row['unit_key'], row.get('page_no'))
        for row in child_rows if accepted and row['status'] == 'succeeded'
    }
    recovered = parent_failed & child_succeeded
    unresolved = parent_failed - child_succeeded
    return {
        'parent_run_id': parent_run_id,
        'child_run_id': child_run_id,
        'planned': len(parent_failed),
        'recovered': len(recovered),
        'unresolved': len(unresolved),
        'completion_rate': round(len(recovered) / len(parent_failed), 4) if parent_failed else 1.0,
        'recovered_units': [_unit_dict(item) for item in sorted(recovered, key=str)],
        'unresolved_units': [_unit_dict(item) for item in sorted(unresolved, key=str)],
    }


def _unit_dict(item):
    unit_type, unit_key, page_no = item
    return {'unit_type': unit_type, 'unit_key': unit_key, 'page_no': page_no}


def start_retry(run_id, *, collectors_dir, python_executable, script_name,
                db_path=None, execute=False, shop_id=None):
    plan = build_retry_plan(run_id, db_path=db_path, shop_id=shop_id)
    if plan is None:
        raise ValueError('采集运行记录不存在')
    if not execute:
        return plan
    if not plan['units']:
        from db import get_db
        with get_db(db_path) as conn:
            prior = conn.execute(
                "SELECT id FROM collector_runs WHERE requested_by=? AND status IN ('succeeded','partial') ORDER BY created_at DESC LIMIT 1",
                (f'retry:{run_id}',),
            ).fetchone()
        if prior:
            return {**plan, 'started': False, 'already_recovered': True, 'child_run_id': prior['id']}
        raise ValueError('没有可重试的失败 unit')
    from api.collect_api import _browser_for_sources
    python_executable = resolve_python(Path(__file__).resolve().parents[1], fallback=python_executable)
    browser_config = _browser_for_sources([plan['source_key']])
    child_id = create_run(
        plan['source_key'], plan['shop_id'], db_path=db_path, mode='retry',
        window_start=plan['window_start'], window_end=plan['window_end'],
        requested_by=f'retry:{run_id}',
    )
    thread = threading.Thread(
        target=_run_retry, args=(child_id, plan),
        kwargs={
            'collectors_dir': collectors_dir,
            'python_executable': python_executable,
            'script_name': script_name,
            'db_path': db_path,
            'browser_config': browser_config,
        }, daemon=True,
    )
    thread.start()
    return {**plan, 'child_run_id': child_id, 'started': True}


def _run_retry(run_id, plan, *, collectors_dir, python_executable, script_name, db_path,
               browser_config=None):
    # Deliberately unscoped: this daemon thread has no request context, and its
    # run was already authorized by the HTTP caller before the thread started.
    source_key = plan['source_key']
    shop_id = plan['shop_id']
    if not acquire_lease(source_key, shop_id, run_id, db_path=db_path, ttl_seconds=960):
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='ALREADY_RUNNING', error_message='该来源已有运行任务')
        return
    try:
        if plan.get('parent_run_id'):
            refreshed = build_retry_plan(plan['parent_run_id'], db_path=db_path, shop_id=shop_id)
            if not refreshed or not refreshed['units']:
                update_run(run_id, status='cancelled', db_path=db_path,
                           error_code='RETRY_ALREADY_RECOVERED', error_message='失败单元已被先前补数恢复，不再执行')
                return
            plan = refreshed
        update_run(run_id, status='running', db_path=db_path, worker_id='retry-worker', attempt=1)
        for unit in plan['units']:
            upsert_checkpoint(
                run_id, unit['unit_type'], unit['unit_key'], db_path=db_path,
                page_no=unit['page_no'], status='queued', row_count=unit['row_count'],
            )
        from api.collect_api import _browser_for_sources, _apply_browser_env
        if browser_config is None:
            browser_config = _browser_for_sources([source_key])
        if browser_config is not None:
            require_browser_identity(browser_config)
        python_executable = resolve_python(Path(__file__).resolve().parents[1], fallback=python_executable)
        env = loopback_proxy_env()
        _apply_browser_env(env, browser_config)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['TMALL_DB_PATH'] = db_path
        env['TMALL_COLLECT_RUN_ID'] = run_id
        env['TMALL_SHOP_ID'] = shop_id
        for field, key in (('window_start', 'TMALL_WINDOW_START'), ('window_end', 'TMALL_WINDOW_END')):
            if plan.get(field):
                env[key] = plan[field]
            else:
                env.pop(key, None)
        env['TMALL_RETRY_UNITS_JSON'] = json.dumps(plan['units'], ensure_ascii=False)
        path = str(Path(collectors_dir) / script_name)
        proc = subprocess.run(
            [python_executable, '-u', path], cwd=collectors_dir, env=env,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900,
        )
        output = (proc.stdout or '') + (proc.stderr or '')
        persist_artifact(run_id, 'retry_output', output, db_path=db_path)
        # Reuse the same event parser as the regular collector API so retry
        # results are compared at business-unit granularity.
        from api.collect_api import _consume_structured_checkpoint_events
        _consume_structured_checkpoint_events(run_id, output.splitlines(), db_path=db_path)
        child_checkpoints = list_checkpoints(run_id, db_path=db_path)
        target_keys = {(u['unit_type'], u['unit_key'], u.get('page_no')) for u in plan['units']}
        succeeded_keys = {
            (u['unit_type'], u['unit_key'], u.get('page_no'))
            for u in child_checkpoints if u['status'] == 'succeeded'
        }
        failed_keys = target_keys - succeeded_keys
        retry_summary = {
            'planned': len(target_keys),
            'succeeded': len(target_keys & succeeded_keys),
            'failed_or_missing': len(failed_keys),
            'failed_units': [
                {'unit_type': t, 'unit_key': k, 'page_no': p}
                for t, k, p in sorted(failed_keys, key=lambda item: str(item))
            ],
        }
        retry_stats = {
            'retry_units': len(plan['units']),
            'output_lines': len(output.splitlines()),
            'retry_summary': retry_summary,
        }
        from services.collector_run_service import classify_collection_failure
        explicit_failure = classify_collection_failure(output.splitlines(), proc.returncode)
        no_explicit_failure = explicit_failure['category'] == 'unknown'
        evidence = collection_completion_evidence(output.splitlines(), run_id=run_id,
            source_key=source_key, window_start=plan.get('window_start'),
            window_end=plan.get('window_end'), db_path=db_path)
        retry_stats['completion_evidence'] = evidence
        # Checkpoints describe progress only; they never override a failed receipt.
        if proc.returncode == 0 and not evidence['ok']:
            partial_progress = bool(failed_keys and succeeded_keys and evidence['code'] in {
                'CHECKPOINT_INCOMPLETE', 'COMPLETION_UNVERIFIED'})
            update_run(run_id, status='partial' if partial_progress else evidence['status'], db_path=db_path,
                       error_code='PARTIAL_RETRY' if partial_progress else evidence['code'], stats=retry_stats)
            record_quality_result(run_id, 'retry_completion', db_path=db_path,
                                  expected_value=0, actual_value=len(failed_keys), status='failed',
                                  message=evidence['code'])
            record_quality_result(run_id, 'retry_publication', db_path=db_path, status='failed',
                                  message='未通过统一完成证据，成功 checkpoint 不关闭待恢复单元')
            return
        if proc.returncode == 0 and evidence['ok']:
            from api.collect_api import DATA_SOURCES, COLLECTOR_CATALOG
            config = DATA_SOURCES.get(source_key, {})
            if not plan.get('window_start') or not plan.get('window_end'):
                snapshot = {'status': 'rejected', 'reason': 'requested_window_missing'}
            else:
                snapshot = stage_source_snapshot(run_id, source_key, config.get('table'), config.get('date_col'),
                    db_path=db_path, window_start=plan['window_start'], window_end=plan['window_end'],
                    expected_rows=evidence['receipt']['row_count'],
                    required_fields=COLLECTOR_CATALOG.get(source_key, {}).get('fields', []))
            retry_stats['staging_snapshot'] = snapshot
            accepted = snapshot.get('status') == 'published'
            record_quality_result(run_id, 'retry_publication', db_path=db_path,
                                  status='passed' if accepted else 'failed', message=snapshot.get('reason'))
            if not accepted:
                update_run(run_id, status='failed', db_path=db_path, error_code='QUALITY_GATE_FAILED', stats=retry_stats)
                record_quality_result(run_id, 'retry_completion', db_path=db_path, status='failed',
                                      message='目标店铺日期事实未通过验收')
                return
        if proc.returncode == 0 and not failed_keys and target_keys and no_explicit_failure:
            update_run(run_id, status='succeeded', db_path=db_path, stats=retry_stats)
            record_quality_result(run_id, 'retry_process_exit', db_path=db_path,
                                  expected_value=0, actual_value=proc.returncode, status='passed')
            record_quality_result(run_id, 'retry_completion', db_path=db_path,
                                  expected_value=0, actual_value=0, status='passed')
        elif proc.returncode == 0 and no_explicit_failure:
            completion_status = 'partial' if succeeded_keys else 'failed'
            update_run(run_id, status=completion_status, db_path=db_path,
                       error_code='PARTIAL_RETRY' if completion_status == 'partial' else 'RETRY_UNRESOLVED',
                       error_message=f'重试仍有 {len(failed_keys)} 个 unit 未恢复',
                       stats=retry_stats)
            record_quality_result(run_id, 'retry_process_exit', db_path=db_path,
                                  expected_value=0, actual_value=proc.returncode, status='passed')
            record_quality_result(run_id, 'retry_completion', db_path=db_path,
                                  expected_value=0, actual_value=len(failed_keys), status='failed',
                                  message=f'重试仍有 {len(failed_keys)} 个 unit 未恢复')
        else:
            failure = explicit_failure
            update_run(run_id, status=failure['status'], db_path=db_path,
                       error_code=failure['code'], error_message=output[-2000:],
                       stats=retry_stats)
            record_quality_result(run_id, 'retry_process_exit', db_path=db_path,
                                  expected_value=0, actual_value=proc.returncode,
                                  status='failed', message=output[-2000:])
            record_quality_result(run_id, 'retry_completion', db_path=db_path,
                                  expected_value=0, actual_value=len(failed_keys), status='failed',
                                  message='重试进程未正常完成')
    except subprocess.TimeoutExpired:
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='TIMEOUT', error_message='局部重试超过 900 秒')
    except (RuntimeConfigurationError, BrowserConfigurationError) as exc:
        update_run(run_id, status='blocked', db_path=db_path,
                   error_code='BROWSER_NOT_READY' if isinstance(exc, BrowserConfigurationError)
                   else 'RUNTIME_CONFIG_INVALID', error_message=str(exc))
    except Exception as exc:
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='COLLECTOR_EXCEPTION', error_message=str(exc))
    finally:
        release_lease(source_key, shop_id, run_id, db_path=db_path)

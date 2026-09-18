"""Build and execute checkpoint-scoped collector retries."""

import json
import os
import subprocess
import threading
from pathlib import Path

from services.collector_run_service import (
    acquire_lease,
    create_run,
    record_quality_result,
    persist_artifact,
    release_lease,
    update_run,
    upsert_checkpoint,
    list_checkpoints,
)


def failed_checkpoints(run_id, *, db_path=None):
    from db import get_db
    with get_db(db_path) as conn:
        rows = conn.execute(
            '''SELECT unit_type, unit_key, page_no, cursor, row_count,
                      last_error_code, last_error_message
               FROM collector_checkpoints
               WHERE run_id = ? AND status IN ('failed', 'blocked')
                 AND unit_type <> 'process'
               ORDER BY unit_type, unit_key, page_no''',
            (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def build_retry_plan(run_id, *, db_path=None):
    from services.collector_run_service import get_run
    parent = get_run(run_id, db_path=db_path)
    if not parent:
        return None
    units = failed_checkpoints(run_id, db_path=db_path)
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


def retry_diff(parent_run_id, child_run_id, *, db_path=None):
    """Compare the failed-unit set of a parent run with a retry run."""
    from services.collector_run_service import get_run, list_checkpoints
    parent = get_run(parent_run_id, db_path=db_path)
    child = get_run(child_run_id, db_path=db_path)
    if not parent or not child:
        return None
    if child.get('requested_by') != f'retry:{parent_run_id}':
        raise ValueError('retry 子任务与父运行记录不匹配')
    parent_failed = {
        (row['unit_type'], row['unit_key'], row.get('page_no'))
        for row in failed_checkpoints(parent_run_id, db_path=db_path)
    }
    child_rows = list_checkpoints(child_run_id, db_path=db_path)
    child_succeeded = {
        (row['unit_type'], row['unit_key'], row.get('page_no'))
        for row in child_rows if row['status'] == 'succeeded'
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
                db_path=None, execute=False):
    plan = build_retry_plan(run_id, db_path=db_path)
    if plan is None:
        raise ValueError('采集运行记录不存在')
    if not plan['units']:
        raise ValueError('没有可重试的失败 unit')
    if not execute:
        return plan
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
        }, daemon=True,
    )
    thread.start()
    return {**plan, 'child_run_id': child_id, 'started': True}


def _run_retry(run_id, plan, *, collectors_dir, python_executable, script_name, db_path):
    source_key = plan['source_key']
    shop_id = plan['shop_id']
    if not acquire_lease(source_key, shop_id, run_id, db_path=db_path):
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='ALREADY_RUNNING', error_message='该来源已有运行任务')
        return
    try:
        update_run(run_id, status='running', db_path=db_path, worker_id='retry-worker', attempt=1)
        for unit in plan['units']:
            upsert_checkpoint(
                run_id, unit['unit_type'], unit['unit_key'], db_path=db_path,
                page_no=unit['page_no'], status='queued', row_count=unit['row_count'],
            )
        env = os.environ.copy()
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
        if proc.returncode == 0:
            update_run(run_id, status='succeeded', db_path=db_path,
                       stats={'retry_units': len(plan['units']), 'output_lines': len(output.splitlines()),
                              'retry_summary': retry_summary})
            record_quality_result(run_id, 'retry_process_exit', db_path=db_path,
                                  expected_value=0, actual_value=proc.returncode, status='passed')
        else:
            update_run(run_id, status='failed', db_path=db_path,
                       error_code='PROCESS_FAILED', error_message=output[-2000:],
                       stats={'retry_units': len(plan['units']), 'retry_summary': retry_summary})
            record_quality_result(run_id, 'retry_process_exit', db_path=db_path,
                                  expected_value=0, actual_value=proc.returncode,
                                  status='failed', message=output[-2000:])
    except subprocess.TimeoutExpired:
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='TIMEOUT', error_message='局部重试超过 900 秒')
    except Exception as exc:
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='COLLECTOR_EXCEPTION', error_message=str(exc))
    finally:
        release_lease(source_key, shop_id, run_id, db_path=db_path)

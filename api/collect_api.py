"""
数据采集状态API
提供各数据源的采集状态查询和手动触发功能
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from flask import Blueprint, current_app, request

from api.api_response import success, failure
from db import get_db
from db import get_shop_id
from config import APP_VERSION
from services.collector_run_service import (
    create_run,
    get_run,
    acquire_lease,
    list_checkpoints,
    list_quality_results,
    list_artifacts,
    list_data_staging,
    summarize_data_staging,
    stage_source_snapshot,
    persist_artifact,
    read_artifact,
    quality_gate,
    release_lease,
    record_quality_result,
    list_health_alerts,
    upsert_checkpoint,
    update_run,
)
from services.collector_retry_service import retry_diff, start_retry

collect_bp = Blueprint('collect', __name__)

# 采集状态持久化文件。允许部署环境通过配置覆盖，默认跟随仓库根目录。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = os.environ.get('TMALL_COLLECT_STATE_FILE', str(PROJECT_ROOT / 'data' / 'collect_state.json'))

def load_collect_state():
    """从文件加载采集状态"""
    global collect_tasks
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                collect_tasks = json.load(f)
            # 清除运行中的状态（服务重启后不可能还在运行）
            for key in collect_tasks:
                if collect_tasks[key].get('status') == 'running':
                    collect_tasks[key]['status'] = 'failed'
                    collect_tasks[key]['error'] = '服务重启，采集中断'
            print(f"[collect_api] 已加载采集状态: {len(collect_tasks)} 个数据源")
    except Exception as e:
        print(f"[collect_api] 加载采集状态失败: {e}")
        collect_tasks = {}

_state_lock = threading.RLock()


def save_collect_state():
    """保存采集状态到文件，使用原子替换避免并发写出半个 JSON。"""
    try:
        state_path = Path(STATE_FILE)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        # 保存关键状态和最近日志（output已在采集流程中截断为最多200行，不会过大）。
        with _state_lock:
            state_to_save = {
                key: {
                    'status': task.get('status', 'idle'),
                    'last_run': task.get('last_run'),
                    'error': task.get('error'),
                    'return_code': task.get('return_code'),
                    'attempts': task.get('attempts'),
                    'run_id': task.get('run_id'),
                    'output': task.get('output', [])[-200:],
                }
                for key, task in collect_tasks.items()
            }
        fd, temp_name = tempfile.mkstemp(prefix=f'{state_path.name}.', suffix='.tmp', dir=state_path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(state_to_save, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, state_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    except Exception as e:
        print(f"[collect_api] 保存采集状态失败: {e}")


def _consume_structured_checkpoint_events(run_id, lines, db_path=None):
    """Parse optional JSON checkpoint events emitted by external collectors.

    Accepted formats are a JSON line or ``CHECKPOINT_JSON {json}`` with
    ``event=checkpoint``, ``unit_type`` and ``unit_key`` fields. Plain logs are
    ignored for backwards compatibility.
    """
    consumed = 0
    for line in lines or []:
        candidate = str(line).strip()
        if candidate.startswith('CHECKPOINT_JSON '):
            candidate = candidate[len('CHECKPOINT_JSON '):].strip()
        if not candidate.startswith('{'):
            continue
        try:
            event = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if event.get('event') not in {'checkpoint', 'collector_checkpoint'}:
            continue
        unit_type = event.get('unit_type')
        unit_key = event.get('unit_key')
        if not unit_type or not unit_key:
            continue
        upsert_checkpoint(
            run_id, str(unit_type), str(unit_key), db_path=db_path,
            page_no=event.get('page_no'), cursor=event.get('cursor'),
            status=event.get('status', 'succeeded'),
            row_count=int(event.get('row_count') or 0),
            source_hash=event.get('source_hash'),
            error_code=event.get('error_code'),
            error_message=event.get('error_message'),
        )
        consumed += 1
    return consumed


def _extract_coverage_event(lines):
    """Read the last machine-readable coverage event from collector output."""
    coverage = None
    for line in lines or []:
        candidate = str(line).strip()
        if candidate.startswith('CHECKPOINT_JSON '):
            candidate = candidate[len('CHECKPOINT_JSON '):].strip()
        if not candidate.startswith('{'):
            continue
        try:
            event = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if event.get('event') == 'coverage':
            coverage = {
                'expected_units': int(event.get('expected_units') or 0),
                'succeeded_units': int(event.get('succeeded_units') or 0),
                'failed_units': int(event.get('failed_units') or 0),
                'row_count': int(event.get('row_count') or 0),
            }
            expected = coverage['expected_units']
            coverage['rate'] = round(
                coverage['succeeded_units'] / expected, 4) if expected else None
    return coverage


def _build_result_event(source_key, run_id, *, status, return_code=None,
                        row_count=0, coverage=None, quality_gate=None,
                        error_code=None):
    """Create the stable terminal event consumed by logs and replay tooling."""
    return {
        'event': 'result',
        'schema_version': 1,
        'source_key': source_key,
        'run_id': run_id,
        'status': status,
        'return_code': return_code,
        'row_count': int(row_count or 0),
        'coverage': coverage,
        'quality_gate': quality_gate,
        'error_code': error_code,
    }

# 采集脚本路径：允许部署环境覆盖，保留旧路径作为兼容 fallback。
COLLECTORS_DIR = os.environ.get('TMALL_COLLECTORS_DIR', r'E:\www\BI采集\collectors')
VENV_PYTHON = os.environ.get('TMALL_COLLECT_PYTHON', sys.executable)
CDP_PORT = int(os.environ.get('TMALL_CDP_PORT', '9223'))

# 数据源配置
DATA_SOURCES = {
    'bi_daily': {
        'name': 'BI商品日度',
        'table': 'daily_data',
        'date_col': 'date',
        # 用全量采集器：先取 BI 表格的全部 676 列、分批写入列模板再取数合并。
        # 旧的 collect_overview_daily.py 只拿默认列模板的 59 个字段，
        # 浏览量/退款金额/加购件数/收藏人数等十余个指标会全部落 0。
        'script': 'collect_overview_full.py',
        'description': 'BI商品总览日度全量采集（676字段）',
    },
    'bi_monthly': {
        'name': 'BI商品月度',
        'table': 'monthly_data',
        'date_col': 'month',
        'script': 'aggregate_monthly.py',
        'description': 'BI商品月度数据聚合',
    },
    'sycm_flow': {
        'name': '生意参谋-店铺流量',
        'table': 'sycm_flow_source_daily',
        'date_col': 'stat_date',
        'script': 'collect_sycm_flow.py',
        'description': '生意参谋店铺流量来源采集',
    },
    'sycm_item_flow': {
        'name': '生意参谋-单品流量',
        'table': 'sycm_item_flow_source_daily',
        'date_col': 'stat_date',
        'script': 'collect_sycm_item_flow_v6.py',
        'description': '生意参谋单品流量来源采集',
    },
    'sycm_market': {
        'name': '生意参谋-市场数据',
        'table': 'sycm_market_item_rank',
        'date_col': 'stat_date',
        'script': 'collect_sycm_market.py',
        'description': '生意参谋市场排行采集',
    },
    'wanxiangtai': {
        'name': '万相台推广',
        'table': 'promotion_daily_facts',
        'date_col': 'date',
        'script': 'collect_wanxiangtai_auto.py',
        'description': '万相台推广数据采集',
    },
}

COLLECTOR_CATALOG = {
    'bi_daily': {'unit_type': 'product', 'publish_mode': 'staging_atomic', 'fields': ['product_id', 'date', 'payment_amount']},
    'bi_monthly': {'unit_type': 'product', 'publish_mode': 'aggregate', 'fields': ['product_id', 'month', 'payment_amount']},
    'sycm_flow': {'unit_type': 'channel', 'publish_mode': 'staging_atomic', 'fields': ['stat_date', 'channel_name', 'uv', 'pay_amount']},
    'sycm_item_flow': {'unit_type': 'product_channel', 'publish_mode': 'staging_atomic', 'fields': ['stat_date', 'item_id', 'channel_name', 'uv']},
    'sycm_market': {'unit_type': 'category_rank', 'publish_mode': 'staging_atomic', 'fields': ['stat_date', 'cate_id', 'item_id', 'rank']},
    'wanxiangtai': {'unit_type': 'promotion_unit', 'publish_mode': 'staging_atomic', 'fields': ['date', 'channel', 'ad_spend', 'clicks']},
}

# 采集任务状态
collect_tasks = {}

# 模块加载时从文件恢复状态
load_collect_state()
_collect_locks = {key: threading.Lock() for key in DATA_SOURCES}


@collect_bp.route('/api/collect/status', methods=['GET'])
def get_collect_status():
    """获取各数据源的采集状态"""
    with get_db() as conn:
        c = conn.cursor()
        sources = []
        for key, config in DATA_SOURCES.items():
            try:
                c.execute(f'SELECT MAX({config["date_col"]}), COUNT(*) FROM {config["table"]}')
                latest, count = c.fetchone()

                # 计算数据新鲜度
                freshness = 'unknown'
                if latest:
                    try:
                        latest_date = datetime.strptime(str(latest)[:10], '%Y-%m-%d').date()
                        today = datetime.now().date()
                        days_diff = (today - latest_date).days
                        if days_diff == 0:
                            freshness = 'today'
                        elif days_diff == 1:
                            freshness = 'yesterday'
                        elif days_diff <= 3:
                            freshness = 'recent'
                        else:
                            freshness = 'stale'
                    except Exception:
                        # 日期解析失败时保持 freshness='unknown'，不影响状态展示
                        pass

                sources.append({
                    'key': key,
                    'name': config['name'],
                    'description': config['description'],
                    'latest_date': str(latest) if latest else None,
                    'record_count': count,
                    'freshness': freshness,
                    'script': config['script'],
                    'status': collect_tasks.get(key, {}).get('status', 'idle'),
                    'last_run': collect_tasks.get(key, {}).get('last_run'),
                })
            except Exception as e:
                sources.append({
                    'key': key,
                    'name': config['name'],
                    'description': config['description'],
                    'error': str(e),
                    'status': 'error',
                })

    return success({'sources': sources})


@collect_bp.route('/api/collect/catalog', methods=['GET'])
def get_collect_catalog():
    """Return the machine-readable source/table/unit contract."""
    return success({
        'sources': [
            {'source_key': key, **config, **COLLECTOR_CATALOG.get(key, {})}
            for key, config in DATA_SOURCES.items()
        ],
        'version': '1',
    }, evidence=[{'source': 'DATA_SOURCES', 'count': len(DATA_SOURCES)}])


@collect_bp.route('/api/collect/health', methods=['GET'])
def get_collect_health():
    """Read-only operational health summary for collectors."""
    db_path = current_app.config.get('DATABASE_PATH')
    with get_db(db_path) as conn:
        source_rows = []
        for key, config in DATA_SOURCES.items():
            table_error = None
            try:
                latest = conn.execute(
                    f'SELECT MAX({config["date_col"]}) AS latest, COUNT(*) AS row_count FROM {config["table"]}'
                ).fetchone()
            except Exception as exc:
                latest = {'latest': None, 'row_count': 0}
                table_error = str(exc)
            run = conn.execute(
                '''SELECT id, status, error_code, finished_at, updated_at
                   FROM collector_runs WHERE source_key = ?
                   ORDER BY created_at DESC LIMIT 1''', (key,)
            ).fetchone()
            failed = conn.execute(
                '''SELECT COUNT(*) AS count FROM collector_runs
                   WHERE source_key = ? AND status IN ('failed', 'auth_required', 'blocked')
                     AND created_at >= datetime('now', '-7 days')''', (key,)
            ).fetchone()['count']
            recent_runs = conn.execute(
                '''SELECT status FROM collector_runs
                   WHERE source_key = ? ORDER BY created_at DESC LIMIT 30''',
                (key,),
            ).fetchall()
            consecutive_failures = 0
            for recent in recent_runs:
                if recent['status'] in {'failed', 'auth_required', 'blocked'}:
                    consecutive_failures += 1
                else:
                    break
            source_rows.append({
                'source_key': key,
                'name': config['name'],
                'latest_fact_date': latest['latest'],
                'fact_row_count': latest['row_count'] or 0,
                'last_run': dict(run) if run else None,
                'failed_runs_7d': failed,
                'consecutive_failures': consecutive_failures,
                'table_error': table_error,
            })
            latest_value = latest['latest']
            source_rows[-1]['age_days'] = None
            if latest_value:
                try:
                    parsed = datetime.strptime(str(latest_value)[:10], '%Y-%m-%d').date()
                    source_rows[-1]['age_days'] = max(0, (datetime.now().date() - parsed).days)
                except ValueError:
                    source_rows[-1]['age_days'] = None
        staging = conn.execute(
            '''SELECT status, COUNT(*) AS count FROM collector_data_staging
               WHERE created_at >= datetime('now', '-7 days') GROUP BY status'''
        ).fetchall()
    unhealthy = [row for row in source_rows
                  if row['table_error'] or not row['last_run'] or row['age_days'] is None
                  or row['age_days'] > 3
                  or row['last_run']['status'] in {'failed', 'auth_required', 'blocked'}]
    return success({
        'sources': source_rows,
        'staging_7d': {row['status']: row['count'] for row in staging},
        'source_count': len(source_rows),
        'unhealthy_count': len(unhealthy),
        'status': 'degraded' if unhealthy else 'healthy',
    }, availability='available', evidence=[
        {'source': 'collector_runs', 'window': '7d'},
        {'source': 'collector_data_staging', 'window': '7d'},
    ])


@collect_bp.route('/api/collect/alerts', methods=['GET'])
def get_collect_alerts():
    """Return persisted collector health alerts for operations screens."""
    db_path = current_app.config.get('DATABASE_PATH')
    source_key = request.args.get('source_key') or None
    status = request.args.get('status', 'open')
    if status not in {'open', 'resolved'}:
        return failure('VALIDATION_ERROR', 'status 必须是 open 或 resolved', status=422)
    return success({'alerts': list_health_alerts(
        source_key=source_key, status=status, db_path=db_path,
    )})



_prepare_lock = threading.Lock()


def check_collect_env(source_key):
    """Every trigger must pass browser preparation, including direct API calls."""
    ok, output = prepare_collect_pages([source_key])
    return None if ok else output



def prepare_collect_pages(source_keys):
    """Start the shared CDP pages and verify the BI login before collection."""
    requested = set(source_keys or DATA_SOURCES)
    if requested == {'bi_monthly'}:
        return True, '月度聚合不需要浏览器'
    needs_bi = bool(requested & {'bi_daily'})
    script = PROJECT_ROOT / 'scripts' / 'auto_login_bi.py'
    if not script.exists():
        return False, f'页面准备脚本不存在: {script}'
    args = [VENV_PYTHON, '-u', str(script), '--sources', ','.join(sorted(requested))]
    if not needs_bi:
        args.append('--skip-bi-login')
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['TMALL_CDP_PORT'] = str(CDP_PORT)
    env['TMALL_DB_PATH'] = current_app.config['DATABASE_PATH']
    try:
        result = subprocess.run(
            args, cwd=str(PROJECT_ROOT), env=env,
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f'页面准备执行失败: {exc}'
    output = (result.stdout or '') + (result.stderr or '')
    if result.returncode != 0:
        tail = '\n'.join(output.splitlines()[-8:])
        return False, f'页面准备失败（返回码 {result.returncode}）:\n{tail}'
    return True, output


@collect_bp.route('/api/collect/prepare', methods=['POST'])
def prepare_collect():
    """Prepare the browser pages required by manual collection."""
    data = request.get_json() or {}
    source_keys = data.get('sources') or list(DATA_SOURCES)
    if isinstance(source_keys, str):
        source_keys = [source_keys]
    invalid = [key for key in source_keys if key not in DATA_SOURCES]
    if invalid:
        return failure('INVALID_SOURCE', f'无效的数据源: {", ".join(invalid)}')
    ok, output = prepare_collect_pages(source_keys)
    if not ok:
        return failure('PREPARE_FAILED', output)
    return success({'sources': source_keys, 'output': output[-4000:]})


@collect_bp.route('/api/collect/trigger', methods=['POST'])
def trigger_collect():
    """手动触发采集"""
    data = request.get_json() or {}
    source_key = data.get('source')

    if not source_key or source_key not in DATA_SOURCES:
        return failure('INVALID_SOURCE', '无效的数据源')

    config = DATA_SOURCES[source_key]
    script_path = os.path.join(COLLECTORS_DIR, config['script'])

    db_path = current_app.config.get('DATABASE_PATH')
    shop_id = get_shop_id()
    run_id = create_run(source_key, shop_id, db_path=db_path, mode='manual')

    if not os.path.exists(script_path):
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='SCRIPT_NOT_FOUND', error_message=f'采集脚本不存在: {script_path}')
        return failure('SCRIPT_NOT_FOUND', f'采集脚本不存在: {script_path}')

    # 在启动线程前占用数据源锁，避免并发请求同时启动同一采集器。
    source_lock = _collect_locks[source_key]
    if not source_lock.acquire(blocking=False):
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='ALREADY_RUNNING', error_message='该数据源正在采集中，请稍候')
        return failure('ALREADY_RUNNING', '该数据源正在采集中，请稍候')
    if not acquire_lease(source_key, shop_id, run_id, db_path=db_path):
        source_lock.release()
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='ALREADY_RUNNING', error_message='该数据源在其他进程中正在采集中')
        return failure('ALREADY_RUNNING', '该数据源在其他进程中正在采集中，请稍候')
    with _state_lock:
        if collect_tasks.get(source_key, {}).get('status') == 'running':
            source_lock.release()
            update_run(run_id, status='failed', db_path=db_path,
                       error_code='ALREADY_RUNNING', error_message='该数据源正在采集中，请稍候')
            return failure('ALREADY_RUNNING', '该数据源正在采集中，请稍候')
        collect_tasks[source_key] = {
            'status': 'queued',
            'last_run': datetime.now().isoformat(),
            'output': [],
            'attempt': 0,
            'run_id': run_id,
        }
    save_collect_state()
    update_run(run_id, status='queued', db_path=db_path)
    upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                      status='queued')

    # 采集前环境检查
    env_error = check_collect_env(source_key)
    if env_error:
        source_lock.release()
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='ENVIRONMENT_ERROR', error_message=env_error)
        upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                          status='failed', error_code='ENVIRONMENT_ERROR',
                          error_message=env_error)
        record_quality_result(run_id, 'environment_ready', db_path=db_path,
                              status='failed', message=env_error)
        print('RESULT_JSON ' + json.dumps(_build_result_event(
            source_key, run_id, status='failed', quality_gate='failed',
            error_code='ENVIRONMENT_ERROR'), ensure_ascii=False))
        with _state_lock:
            collect_tasks[source_key] = {
                'status': 'failed',
                'last_run': datetime.now().isoformat(),
                'output': [],
                'error': env_error,
                'run_id': run_id,
            }
        save_collect_state()
        return failure('ENVIRONMENT_ERROR', env_error)

    # 后台运行采集脚本（带超时和重试）
    MAX_RETRIES = 2
    RETRY_DELAY = 30  # 秒
    # 全量 BI 采集需要分批设置列模板（676 列 / 每批 23 列 ≈ 30 批），
    # 单轮远超旧的 300 秒上限，放宽到 900 秒。
    COLLECT_TIMEOUT = 900  # 15分钟

    def run_collection():
        all_output = []
        last_error = None
        def process_quality(status, actual, message=None):
            record_quality_result(
                run_id, 'process_exit_code', db_path=db_path,
                expected_value=0, actual_value=actual,
                status=status, message=message,
            )
        try:
            for attempt in range(MAX_RETRIES + 1):
                with _state_lock:
                    collect_tasks[source_key] = {
                        'status': 'running',
                        'last_run': datetime.now().isoformat(),
                        'output': all_output,
                        'attempt': attempt + 1,
                        'run_id': run_id,
                    }
                update_run(run_id, status='running', db_path=db_path, attempt=attempt + 1)
                upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                                  status='running')
                save_collect_state()
                try:
                    process_env = os.environ.copy()
                    process_env['PYTHONIOENCODING'] = 'utf-8'
                    process_env['TMALL_COLLECT_RUN_ID'] = run_id
                    process_env['TMALL_DB_PATH'] = db_path
                    process_env['TMALL_CDP_PORT'] = str(CDP_PORT)
                    process_env['TMALL_COLLECTOR_VERSION'] = APP_VERSION
                    # 单品流量采集的商品数上限。采集器默认已是 200，这里再固化一次，
                    # 避免部署环境未设置时回落到旧的 50 造成覆盖度断崖。
                    process_env.setdefault('TMALL_ITEM_MAX_ITEMS', '200')
                    proc = subprocess.Popen(
                        [VENV_PYTHON, '-u', script_path],
                        cwd=COLLECTORS_DIR,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        bufsize=1,
                        env=process_env,
                    )
                    try:
                        stdout, _ = proc.communicate(timeout=COLLECT_TIMEOUT)
                        output_lines = (stdout or '').splitlines()
                        persist_artifact(run_id, 'process_output', stdout or '', db_path=db_path)
                        structured_checkpoint_count = _consume_structured_checkpoint_events(
                            run_id, output_lines, db_path=db_path,
                        )
                        coverage = _extract_coverage_event(output_lines)
                        all_output.extend(output_lines[-50:])
                        if len(all_output) > 200:
                            all_output = all_output[-200:]
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                        all_output.append(f'[系统] 采集超时（{COLLECT_TIMEOUT}秒），已强制终止')
                        last_error = f'采集超时（{COLLECT_TIMEOUT}秒）'
                        if attempt < MAX_RETRIES:
                            all_output.append(f'[系统] {RETRY_DELAY}秒后进行第{attempt + 2}次重试...')
                            import time as _time
                            _time.sleep(RETRY_DELAY)
                            continue
                        with _state_lock:
                            collect_tasks[source_key] = {
                                'status': 'timed_out',
                                'last_run': datetime.now().isoformat(),
                                'output': all_output,
                                'error': last_error,
                                'attempts': attempt + 1,
                                'run_id': run_id,
                            }
                        update_run(run_id, status='failed', db_path=db_path, attempt=attempt + 1,
                                   error_code='TIMEOUT', error_message=last_error)
                        process_quality('failed', 'timeout', last_error)
                        upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                                          status='failed', error_code='TIMEOUT',
                                          error_message=last_error)
                        all_output.append('RESULT_JSON ' + json.dumps(_build_result_event(
                            source_key, run_id, status='failed', quality_gate='not_evaluated',
                            error_code='TIMEOUT'), ensure_ascii=False))
                        save_collect_state()
                        return

                    if proc.returncode == 0:
                        snapshot = None
                        try:
                            # Legacy collectors write facts directly; capture
                            # the resulting partition for unified audit/quality.
                            snapshot = stage_source_snapshot(
                                run_id, source_key, config['table'], config['date_col'],
                                db_path=db_path,
                            )
                            record_quality_result(
                                run_id, 'staging_snapshot_non_empty',
                                db_path=db_path, expected_value='>0',
                                actual_value=snapshot.get('row_count', 0),
                                status='passed' if snapshot.get('row_count', 0) else 'failed',
                                message=None if snapshot.get('row_count', 0) else '正式表快照为空',
                            )
                        except Exception as exc:
                            snapshot = {'status': 'rejected', 'reason': str(exc)}
                            record_quality_result(
                                run_id, 'staging_snapshot', db_path=db_path,
                                status='failed', message=str(exc), severity='error',
                            )
                        with _state_lock:
                            collect_tasks[source_key] = {
                                'status': 'completed',
                                'last_run': datetime.now().isoformat(),
                                'output': all_output,
                                'return_code': proc.returncode,
                                'attempts': attempt + 1,
                                'run_id': run_id,
                            }
                        has_output = bool(output_lines)
                        snapshot_ok = bool(snapshot and snapshot.get('status') == 'published'
                                           and snapshot.get('row_count', 0) > 0)
                        gate_ok = has_output and snapshot_ok
                        update_run(run_id, status='succeeded' if gate_ok else 'failed', db_path=db_path,
                                   attempt=attempt + 1,
                                   stats={'return_code': proc.returncode, 'output_lines': len(all_output),
                                          'structured_checkpoints': structured_checkpoint_count,
                                          'coverage': coverage,
                                          'staging_snapshot': snapshot,
                                          'quality_gate': 'passed' if gate_ok else 'failed'},
                                   error_code=None if gate_ok else 'QUALITY_GATE_FAILED',
                                   error_message=None if gate_ok else '采集输出或 staging 快照未通过质量门禁')
                        process_quality(
                            'passed' if gate_ok else 'failed',
                            proc.returncode,
                            None if gate_ok else '采集输出或 staging 快照未通过质量门禁',
                        )
                        upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                                          status='succeeded' if gate_ok else 'failed', row_count=len(all_output),
                                          error_code=None if gate_ok else 'QUALITY_GATE_FAILED',
                                          error_message=None if gate_ok else '采集输出或 staging 快照未通过质量门禁')
                        all_output.append('RESULT_JSON ' + json.dumps(_build_result_event(
                            source_key, run_id,
                            status='succeeded' if gate_ok else 'failed',
                            return_code=proc.returncode,
                            row_count=(snapshot or {}).get('row_count', 0),
                            coverage=coverage,
                            quality_gate='passed' if gate_ok else 'failed',
                            error_code=None if gate_ok else 'QUALITY_GATE_FAILED',
                        ), ensure_ascii=False))
                        save_collect_state()
                        return

                    last_error = f'采集失败，返回码 {proc.returncode}'
                    if attempt < MAX_RETRIES:
                        all_output.append(f'[系统] 采集失败（返回码 {proc.returncode}），{RETRY_DELAY}秒后重试...')
                        import time as _time
                        _time.sleep(RETRY_DELAY)
                        continue
                    with _state_lock:
                        collect_tasks[source_key] = {
                            'status': 'failed',
                            'last_run': datetime.now().isoformat(),
                            'output': all_output,
                            'error': last_error,
                            'return_code': proc.returncode,
                            'attempts': attempt + 1,
                            'run_id': run_id,
                        }
                    update_run(run_id, status='failed', db_path=db_path, attempt=attempt + 1,
                               error_code='PROCESS_FAILED', error_message=last_error)
                    process_quality('failed', proc.returncode, last_error)
                    upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                                      status='failed', error_code='PROCESS_FAILED',
                                      error_message=last_error)
                    all_output.append('RESULT_JSON ' + json.dumps(_build_result_event(
                        source_key, run_id, status='failed', return_code=proc.returncode,
                        quality_gate='not_evaluated', error_code='PROCESS_FAILED'), ensure_ascii=False))
                    save_collect_state()
                    return
                except Exception as error:
                    last_error = str(error)
                    if attempt < MAX_RETRIES:
                        all_output.append(f'[系统] 采集异常: {error}，{RETRY_DELAY}秒后重试...')
                        import time as _time
                        _time.sleep(RETRY_DELAY)
                        continue
                    with _state_lock:
                        collect_tasks[source_key] = {
                            'status': 'failed',
                            'last_run': datetime.now().isoformat(),
                            'output': all_output,
                            'error': last_error,
                            'attempts': attempt + 1,
                            'run_id': run_id,
                        }
                    update_run(run_id, status='failed', db_path=db_path, attempt=attempt + 1,
                               error_code='COLLECTOR_EXCEPTION', error_message=last_error)
                    process_quality('failed', 'exception', last_error)
                    upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                                      status='failed', error_code='COLLECTOR_EXCEPTION',
                                      error_message=last_error)
                    all_output.append('RESULT_JSON ' + json.dumps(_build_result_event(
                        source_key, run_id, status='failed', quality_gate='not_evaluated',
                        error_code='COLLECTOR_EXCEPTION'), ensure_ascii=False))
                    save_collect_state()
                    return
        finally:
            release_lease(source_key, shop_id, run_id, db_path=db_path)
            source_lock.release()

    thread = threading.Thread(target=run_collection, daemon=True)
    thread.start()

    return success({'message': f'已触发{config["name"]}采集', 'source': source_key, 'run_id': run_id})


@collect_bp.route('/api/collect/log/<source_key>', methods=['GET'])
def get_collect_log(source_key):
    """获取采集日志"""
    if source_key not in DATA_SOURCES:
        return failure('INVALID_SOURCE', '无效的数据源')

    task = collect_tasks.get(source_key, {})
    return success({
        'source': source_key,
        'status': task.get('status', 'idle'),
        'last_run': task.get('last_run'),
        'run_id': task.get('run_id'),
        'output': task.get('output', []),
        'error': task.get('error'),
    })


@collect_bp.route('/api/collect/runs/<run_id>', methods=['GET'])
def get_collect_run(run_id):
    """Return a durable collector run record by id."""
    run = get_run(run_id, db_path=current_app.config.get('DATABASE_PATH'))
    if not run:
        return failure('RUN_NOT_FOUND', '采集运行记录不存在', status=404)
    db_path = current_app.config.get('DATABASE_PATH')
    return success({
        'run': run,
        'checkpoints': list_checkpoints(run_id, db_path=db_path),
        'quality_results': list_quality_results(run_id, db_path=db_path),
        'artifacts': list_artifacts(run_id, db_path=db_path),
        'quality_gate': quality_gate(run_id, db_path=db_path),
    })


@collect_bp.route('/api/collect/runs/<run_id>/retry', methods=['POST'])
def retry_collect_run(run_id):
    """Preview or execute a retry limited to failed checkpoint units."""
    body = request.get_json(silent=True) or {}
    try:
        parent = get_run(run_id, db_path=current_app.config.get('DATABASE_PATH'))
        if not parent:
            return failure('RUN_NOT_FOUND', '采集运行记录不存在', status=404)
        config = DATA_SOURCES.get(parent['source_key'])
        if not config:
            return failure('INVALID_SOURCE', '运行记录对应的数据源不存在', status=422)
        result = start_retry(
            run_id,
            collectors_dir=COLLECTORS_DIR,
            python_executable=VENV_PYTHON,
            script_name=config['script'],
            db_path=current_app.config.get('DATABASE_PATH'),
            execute=bool(body.get('execute')),
        )
        return success(result, status=202 if result.get('started') else 200)
    except ValueError as exc:
        return failure('RETRY_NOT_AVAILABLE', str(exc), status=422)


@collect_bp.route('/api/collect/runs/<run_id>/artifacts/<int:artifact_id>', methods=['GET'])
def get_collect_artifact(run_id, artifact_id):
    """Replay a stored raw collector artifact after hash verification."""
    try:
        artifact = read_artifact(
            artifact_id, run_id,
            db_path=current_app.config.get('DATABASE_PATH'),
        )
    except ValueError as exc:
        return failure('ARTIFACT_INVALID', str(exc), status=409)
    if not artifact:
        return failure('ARTIFACT_NOT_FOUND', '采集原始 artifact 不存在', status=404)
    if request.args.get('include_content') not in {'1', 'true', 'yes'}:
        artifact.pop('content', None)
    return success(artifact)


@collect_bp.route('/api/collect/runs/<run_id>/staging', methods=['GET'])
def get_collect_staging(run_id):
    run = get_run(run_id, db_path=current_app.config.get('DATABASE_PATH'))
    if not run:
        return failure('RUN_NOT_FOUND', '采集运行记录不存在', status=404)
    rows = list_data_staging(run_id, db_path=current_app.config.get('DATABASE_PATH'))
    quality = summarize_data_staging(rows)
    # Avoid returning all raw payloads by default; callers can request them
    # explicitly when replay/debugging is needed.
    if request.args.get('include_payload') not in {'1', 'true', 'yes'}:
        for row in rows:
            row.pop('payload_json', None)
    return success({
        'batch_id': run_id,
        'row_count': len(rows),
        'quality': quality,
        'rows': rows,
    }, availability='available' if rows else 'no-data',
       evidence_level='full' if rows else 'insufficient',
       evidence=[{'source': 'collector_data_staging', 'batch_id': run_id,
                  'row_count': len(rows)}])


@collect_bp.route('/api/collect/runs/<run_id>/retry-diff/<child_run_id>', methods=['GET'])
def get_collect_retry_diff(run_id, child_run_id):
    try:
        result = retry_diff(
            run_id, child_run_id,
            db_path=current_app.config.get('DATABASE_PATH'),
        )
    except ValueError as exc:
        return failure('RETRY_SCOPE_ERROR', str(exc), status=422)
    if not result:
        return failure('RUN_NOT_FOUND', '父或子采集运行记录不存在', status=404)
    return success(result)

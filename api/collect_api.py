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
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, current_app, request

from api.api_response import success, failure
from db import get_db
from db import get_shop_id
from config import APP_VERSION
from scripts.runtime_paths import resolve_python, RuntimeConfigurationError, loopback_proxy_env
from scripts.browser_runtime import resolve_browser, require_browser_identity, BrowserConfigurationError
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
    latest_runs_by_source,
    reconcile_stale_runs,
    upsert_checkpoint,
    update_run,
    classify_collection_failure, retry_decision, healthcheck_coverage, verify_fact_dates,
    collection_completion_evidence,
)
from services.collector_retry_service import retry_diff, start_retry
from services.shop_scope_service import current_request_shop_id

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
                        error_code=None, window_start=None, window_end=None):
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
        'window_start': window_start,
        'window_end': window_end,
    }


def _classify_process_failure(lines, return_code=None):
    """Keep the useful tail of a collector failure and classify known causes.

    External collectors often fail before they can emit a structured result.
    Persisting only ``PROCESS_FAILED`` hides the actionable cause, especially
    when the shared Chrome/CDP endpoint has disappeared between preparation and
    process launch.
    """
    result = classify_collection_failure(lines, return_code)
    message = result['message']
    if result['code'] == 'CDP_UNAVAILABLE':
        message = 'CDP 浏览器调试端口不可用。\n' + message
    return result['code'], message[:2000]

# 采集脚本路径：允许部署环境覆盖，默认优先使用仓库内 collectors，
# 再兼容项目同级的本地采集器目录。
def _default_collectors_dir():
    candidates = (
        PROJECT_ROOT / 'collectors',
        PROJECT_ROOT.parent / 'BI采集' / 'collectors',
    )
    return str(next((candidate for candidate in candidates if candidate.is_dir()), candidates[0]))


COLLECTORS_DIR = os.environ.get('TMALL_COLLECTORS_DIR') or _default_collectors_dir()
# Resolve per request: a validated runtime switch does not require stale module globals.
VENV_PYTHON = sys.executable  # Backward-compatible fallback, never overrides explicit settings.
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
        # 月度源：按月节奏判新鲜度，日度 3 天阈值对它永远不健康
        'fresh_days': 40,
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
        'script': 'collect_wanxiangtai_dims_v4.py',
        'description': '万相台推广数据采集',
    },
    'dts_market': {
        'name': '店透视-市场榜单',
        # 与其它源不同：店透视趋势分析按 4 周窗口成批导入 market_products，
        # 最新数据日期取 market_analysis_runs.analysis_date（窗口结束日）。
        'table': 'market_analysis_runs',
        'date_col': 'analysis_date',
        'script': 'collect_dts_market.py',
        'description': '店透视市场排行趋势分析（三类目 4 周窗口批量导入）',
        # 周窗口源：一键采集与日度新鲜度判定均按窗口节奏处理，不走日度默认
        'cadence': 'window',
        'fresh_days': 40,
        # 2026-10-02：尚未纳入任何调度。它依赖独立的挖象浏览器（CDP 9224，
        # 与采集 Chrome 的 9223 不同）+ 店透视插件 + 外部解析脚本，环境未就绪。
        # 标记为未启用：health 仍会列出它，但不参与 unhealthy 判定 —— 否则一个
        # 从没跑过的源会让整体状态永远 degraded，把真告警淹没成噪音。
        # 环境就绪后改成 True 并加调度即可。
        'enabled': False,
    },
    'dmp_shop': {
        'name': '达摩盘-全店洞察',
        # 全店洞察按 endDate+period 快照导入 dmp_shop_items，
        # 最新数据日期取行内 end_date（DMP 数据窗口 T-1/T-2 收口）。
        'table': 'dmp_shop_items',
        'date_col': 'end_date',
        'script': 'collect_dmp_shop.py',
        'description': '达摩盘货品洞察-全店洞察（本店+同行同层 overview、单品指标含 peerValue）',
        # 挖象浏览器(CDP 9224) + DMP 人工登录依赖，与 dts_market 同属
        # 环境不保证的源：走 window 节奏人工触发，一键采集不碰它。
        'cadence': 'window',
        'fresh_days': 3,
        # 未启用：health 会列出但不参与 unhealthy 判定/告警，避免挖象没开时
        # 整体状态永远 degraded。验证日常跑稳后可改 True。
        'enabled': False,
    },
    'dmp_competition': {
        'name': '达摩盘-竞争分析',
        # 竞争快照按 endDate 落 dmp_competitor_monitor / _indicators，
        # 最新数据日期取行内 end_date（竞争窗口 T-1 收口）。
        'table': 'dmp_competitor_monitor',
        'date_col': 'end_date',
        'script': 'collect_dmp_competition.py',
        'description': '达摩盘竞争分析（竞对探测、监控列表、每竞对消耗/人群交集/份额分档）',
        # 与 dmp_shop 同一挖象浏览器+人工登录依赖，window 节奏人工触发
        'cadence': 'window',
        'fresh_days': 3,
        'enabled': False,
    },
}

COLLECTOR_CATALOG = {
    'bi_daily': {'unit_type': 'product', 'publish_mode': 'staging_atomic', 'fields': ['product_id', 'date', 'payment_amount']},
    'bi_monthly': {'unit_type': 'product', 'publish_mode': 'aggregate', 'fields': ['product_id', 'month', 'payment_amount']},
    'sycm_flow': {'unit_type': 'channel', 'publish_mode': 'staging_atomic', 'fields': ['stat_date', 'channel_name', 'uv', 'pay_amount']},
    'sycm_item_flow': {'unit_type': 'product_channel', 'publish_mode': 'staging_atomic', 'fields': ['stat_date', 'item_id', 'channel_name', 'uv']},
    'sycm_market': {'unit_type': 'category_rank', 'publish_mode': 'staging_atomic', 'fields': ['stat_date', 'cate_id', 'item_id', 'rank']},
    'wanxiangtai': {'unit_type': 'promotion_unit', 'publish_mode': 'staging_atomic', 'fields': ['date', 'channel', 'ad_spend', 'clicks']},
    'dts_market': {'unit_type': 'market_batch', 'publish_mode': 'batch_import', 'fields': ['analysis_date', 'period_start', 'period_end', 'category', 'rank']},
    'dmp_shop': {'unit_type': 'dmp_shop_batch', 'publish_mode': 'batch_import', 'fields': ['end_date', 'period', 'item_id', 'ind_key', 'value', 'peer_value']},
    'dmp_competition': {'unit_type': 'dmp_competition_batch', 'publish_mode': 'batch_import', 'fields': ['end_date', 'competitor_name', 'day_cost', 'intersection_click_uv']},
}

# 采集任务状态
collect_tasks = {}

# 模块加载时从文件恢复状态
load_collect_state()
_collect_locks = {key: threading.Lock() for key in DATA_SOURCES}


@collect_bp.route('/api/collect/status', methods=['GET'])
def get_collect_status():
    """获取各数据源的采集状态"""
    db_path = current_app.config.get('DATABASE_PATH')
    reconcile_stale_runs(db_path=db_path)
    durable_runs = latest_runs_by_source(db_path=db_path, shop_id=get_shop_id())

    def _display_status(run, fallback):
        if not run:
            return fallback or 'idle'
        if run['status'] in {'queued', 'running'}:
            return run['status']
        if run['status'] in {'succeeded', 'succeeded_with_warnings'}:
            return 'completed'
        if run['status'] == 'partial':
            return 'partial'
        return 'failed'

    def _last_run_value(run, fallback):
        if run:
            return (
                run.get('finished_at') or run.get('updated_at')
                or run.get('started_at') or run.get('created_at')
            )
        return fallback

    with get_db() as conn:
        c = conn.cursor()
        sources = []
        for key, config in DATA_SOURCES.items():
            try:
                if key == 'dts_market':
                    # 周窗口源：最新数据日期=最新批次窗口结束日，记录数=该批次商品行数
                    row = c.execute(
                        "SELECT analysis_date, id FROM market_analysis_runs "
                        "WHERE source='店透视市场排行' ORDER BY id DESC LIMIT 1").fetchone()
                    latest = row[0] if row else None
                    count = c.execute(
                        'SELECT COUNT(*) FROM market_products WHERE run_id=?',
                        (row[1],)).fetchone()[0] if row else 0
                else:
                    c.execute(f'SELECT MAX({config["date_col"]}), COUNT(*) FROM {config["table"]}')
                    latest, count = c.fetchone()

                # 计算数据新鲜度（周窗口源按 fresh_days 阈值，日度源按 1 天）
                freshness = 'unknown'
                fresh_days = config.get('fresh_days')
                if latest:
                    try:
                        latest_date = datetime.strptime(str(latest)[:10], '%Y-%m-%d').date()
                        today = datetime.now().date()
                        days_diff = (today - latest_date).days
                        if fresh_days is not None:
                            # 周窗口源：只有超过窗口阈值才算过期
                            freshness = 'stale' if days_diff > fresh_days else 'recent'
                        elif days_diff == 0:
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

                durable_run = durable_runs.get(key)
                legacy_task = collect_tasks.get(key, {})
                sources.append({
                    'key': key,
                    'name': config['name'],
                    'description': config['description'],
                    'latest_date': str(latest) if latest else None,
                    'record_count': count,
                    'freshness': freshness,
                    'cadence': config.get('cadence', 'daily'),
                    'script': config['script'],
                    'status': _display_status(
                        durable_run, legacy_task.get('status', 'idle')
                    ),
                    'run_status': durable_run.get('status') if durable_run else None,
                    'run_id': durable_run.get('id') if durable_run else legacy_task.get('run_id'),
                    'last_run': _last_run_value(
                        durable_run, legacy_task.get('last_run')
                    ),
                    'last_run_record': durable_run,
                })
            except Exception as e:
                sources.append({
                    'key': key,
                    'name': config['name'],
                    'description': config['description'],
                    'error': str(e),
                    'status': 'error',
                    'run_status': None,
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
    reconcile_stale_runs(db_path=db_path)
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
                   WHERE source_key = ? AND status IN ('failed', 'auth_required', 'blocked', 'partial')
                     AND created_at >= datetime('now', '-7 days')''', (key,)
            ).fetchone()['count']
            recent_runs = conn.execute(
                '''SELECT status FROM collector_runs
                   WHERE source_key = ? ORDER BY created_at DESC LIMIT 30''',
                (key,),
            ).fetchall()
            consecutive_failures = 0
            for recent in recent_runs:
                if recent['status'] in {'failed', 'auth_required', 'blocked', 'partial'}:
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
                'fresh_days': config.get('fresh_days', 3),
                # 未启用的源（如 dts_market，前置环境未就绪）仍会列出，但不参与
                # unhealthy 判定 —— 否则一个从没被调度过的源会让整体状态永远是
                # degraded，把真正的告警淹没成噪音。
                'enabled': config.get('enabled', True),
            })
            latest_value = latest['latest']
            source_rows[-1]['age_days'] = None
            if latest_value:
                try:
                    parsed = datetime.strptime(str(latest_value)[:10], '%Y-%m-%d').date()
                    source_rows[-1]['age_days'] = max(0, (datetime.now().date() - parsed).days)
                except ValueError:
                    # 月度表 date_col='month' 存 'YYYY-MM'，按当月 1 日解析
                    try:
                        parsed = datetime.strptime(str(latest_value)[:7], '%Y-%m').date()
                        source_rows[-1]['age_days'] = max(0, (datetime.now().date() - parsed).days)
                    except ValueError:
                        source_rows[-1]['age_days'] = None
            # 近期断档检查：日度源逐日核对最近 7 天（T-1 采集，今天不计为缺失）。
            # age_days 只能发现"整体滞后"；中间缺一天、但最新日期仍是新的时会被漏掉。
            source_rows[-1]['missing_dates'] = []
            source_rows[-1]['gap_check_status'] = 'not_applicable'
            if not table_error and config.get('fresh_days', 3) <= 3:
                try:
                    present_rows = conn.execute(
                        f'''SELECT DISTINCT {config["date_col"]} AS d FROM {config["table"]}
                            WHERE {config["date_col"]} >= date('now', '-8 days')'''
                    ).fetchall()
                    present = {str(row['d'])[:10] for row in present_rows}
                    source_rows[-1]['gap_check_status'] = 'verified'
                    today = datetime.now().date()
                    source_rows[-1]['missing_dates'] = [
                        (today - timedelta(days=offset)).isoformat()
                        for offset in range(1, 8)
                        if (today - timedelta(days=offset)).isoformat() not in present
                    ]
                except Exception:
                    source_rows[-1]['gap_check_status'] = 'unknown'
            open_gaps = conn.execute(
                "SELECT fingerprint FROM collector_health_alerts WHERE source_key=? AND alert_type='date_gap' AND status='open'",
                (key,),
            ).fetchall()
            candidate_dates = {row['fingerprint'] for row in open_gaps}
            source_rows[-1]['open_gap_dates'] = sorted(candidate_dates)
            if config.get('fresh_days', 3) <= 3 and config.get('cadence') != 'window':
                candidate_dates.update((datetime.now().date() - timedelta(days=offset)).isoformat()
                                       for offset in range(1, 8))
            source_rows[-1]['coverage_scope'] = 'date_presence_and_required_fields'
            source_rows[-1]['coverage_acceptance'] = verify_fact_dates(
                conn, config['table'], config['date_col'],
                COLLECTOR_CATALOG.get(key, {}).get('fields'), candidate_dates,
                shop_id=current_request_shop_id(),
            )
        staging = conn.execute(
            '''SELECT status, COUNT(*) AS count FROM collector_data_staging
               WHERE created_at >= datetime('now', '-7 days') GROUP BY status'''
        ).fetchall()
    # 只对「已启用」的源判定健康度：未启用的源（enabled=False）缺数据是预期行为，
    # 不该把整体状态拖成 degraded。
    unhealthy = [row for row in source_rows
                  if row.get('enabled', True) and (
                      row['table_error'] or not row['last_run'] or row['age_days'] is None
                      or row['age_days'] > row.get('fresh_days', 3)
                      or row.get('missing_dates') or row.get('gap_check_status') == 'unknown'
                      or row.get('open_gap_dates')
                      or row['coverage_acceptance']['status'] in {'unknown', 'partial'}
                      or row['last_run']['status'] in {'failed', 'auth_required', 'blocked', 'partial'})]
    monitor = healthcheck_coverage(current_app.config.get('COLLECTOR_HEARTBEAT_PATH',
        PROJECT_ROOT / 'logs' / 'collector-health-heartbeat.json'))
    return success({
        'monitoring': monitor,
        'sources': source_rows,
        'staging_7d': {row['status']: row['count'] for row in staging},
        'source_count': len(source_rows),
        'unhealthy_count': len(unhealthy),
        'status': 'degraded' if unhealthy or monitor['status'] != 'active' else 'healthy',
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
    """Source-specific hook; runtime/browser ownership is checked before locks.

    The collector still validates its own remote session. This hook must not be
    interpreted as proof of login or permission to open a different browser.
    """
    return None


def _browser_for_sources(source_keys):
    requested = set(source_keys)
    if requested <= {'bi_monthly'}:
        return None  # Local aggregation has no browser dependency.
    if requested - {'bi_monthly', 'bi_daily', 'sycm_flow', 'sycm_item_flow', 'sycm_market', 'wanxiangtai'}:
        # The disabled DTS/DMP sources need a different browser and explicit
        # configuration; never silently send them to the selected BI browser.
        raise BrowserConfigurationError('SOURCE_BROWSER_NOT_CONFIGURED')
    browser = resolve_browser(PROJECT_ROOT)
    require_browser_identity(browser)
    return browser


def _apply_browser_env(env, browser):
    if browser is not None:
        env.update({'TMALL_CDP_PORT': str(browser['port']), 'TMALL_CDP_HOST': browser['host'],
                    'TMALL_CHROME_PATH': browser['executable'], 'TMALL_CHROME_PROFILE': browser['user_data_dir'],
                    'TMALL_CHROME_REUSE_ONLY': '1' if browser['reuse_only'] else '0'})
    return env



def prepare_collect_pages(source_keys):
    """Honor selected-browser reuse policy and verify session/page readiness."""
    requested = set(source_keys or (key for key, item in DATA_SOURCES.items() if item.get('enabled', True)))
    if requested == {'bi_monthly'}:
        return True, '月度聚合不需要浏览器'
    needs_bi = bool(requested & {'bi_daily'})
    script = PROJECT_ROOT / 'scripts' / 'auto_login_bi.py'
    if not script.exists():
        return False, f'页面准备脚本不存在: {script}'
    try:
        python = resolve_python(PROJECT_ROOT, fallback=VENV_PYTHON)
        browser = _browser_for_sources(requested)
    except (RuntimeConfigurationError, BrowserConfigurationError) as exc:
        return False, str(exc)
    args = [python, '-u', str(script), '--sources', ','.join(sorted(requested))]
    if not needs_bi:
        args.append('--skip-bi-login')
    env = loopback_proxy_env()
    env['PYTHONIOENCODING'] = 'utf-8'
    _apply_browser_env(env, browser)
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
    source_keys = data.get('sources') or [key for key, item in DATA_SOURCES.items() if item.get('enabled', True)]
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
    default_day = (datetime.now().date() - timedelta(days=1)).isoformat()
    window_start = data.get('window_start') or data.get('date') or default_day
    window_end = data.get('window_end') or window_start
    try:
        first = datetime.strptime(window_start, '%Y-%m-%d').date()
        last = datetime.strptime(window_end, '%Y-%m-%d').date()
        if last < first or (last - first).days > 31:
            raise ValueError('window must contain 1 to 32 days')
    except (ValueError, TypeError):
        return failure('INVALID_WINDOW', '业务日期窗口必须为 YYYY-MM-DD 且不超过 32 天', status=422)
    run_id = create_run(source_key, shop_id, db_path=db_path, mode='manual',
                        window_start=window_start, window_end=window_end)

    if not os.path.exists(script_path):
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='SCRIPT_NOT_FOUND', error_message=f'采集脚本不存在: {script_path}')
        return failure('SCRIPT_NOT_FOUND', f'采集脚本不存在: {script_path}')

    try:
        collect_python = resolve_python(PROJECT_ROOT, fallback=VENV_PYTHON)
    except RuntimeConfigurationError as exc:
        update_run(run_id, status='blocked', db_path=db_path,
                   error_code='RUNTIME_CONFIG_INVALID', error_message=str(exc))
        return failure('RUNTIME_CONFIG_INVALID', str(exc), status=503)

    try:
        browser_config = _browser_for_sources({source_key})
    except BrowserConfigurationError as exc:
        update_run(run_id, status='blocked', db_path=db_path,
                   error_code='BROWSER_NOT_READY', error_message=str(exc))
        return failure('BROWSER_NOT_READY', str(exc), status=503)

    # 在启动线程前占用数据源锁，避免并发请求同时启动同一采集器。
    source_lock = _collect_locks[source_key]
    if not source_lock.acquire(blocking=False):
        update_run(run_id, status='failed', db_path=db_path,
                   error_code='ALREADY_RUNNING', error_message='该数据源正在采集中，请稍候')
        return failure('ALREADY_RUNNING', '该数据源正在采集中，请稍候')
    if not acquire_lease(source_key, shop_id, run_id, db_path=db_path, ttl_seconds=2700):
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
    # 店透视是浏览器自动化（三类目串行导出 + 防风控停顿），15 分钟不够；
    # 且重试会再次驱动真实浏览器（可能撞 x5sec 风控），失败留给人工判断。
    if source_key in ('dts_market', 'dmp_shop', 'dmp_competition'):
        # 浏览器自动化（CDP 驱动挖象 + 防风控停顿），15 分钟不够；
        # 且重试会再次驱动真实浏览器（可能撞 x5sec 风控），失败留给人工判断。
        COLLECT_TIMEOUT = 2400  # 40分钟
        MAX_RETRIES = 0

    def run_collection():
        all_output = []
        last_error = None
        import time as _clock
        started = _clock.monotonic()
        total_budget = COLLECT_TIMEOUT
        def retry_allowed(failure, attempt):
            decision = retry_decision(failure, attempt=attempt + 1,
                elapsed_seconds=_clock.monotonic() - started,
                max_attempts=MAX_RETRIES + 1, budget_seconds=total_budget, default_delay=RETRY_DELAY)
            all_output.append('RETRY_POLICY ' + json.dumps(decision))
            update_run(run_id, db_path=db_path, stats={'retry_policy': decision,
                'max_attempts': MAX_RETRIES + 1, 'budget_seconds': total_budget})
            if decision['retry']:
                _clock.sleep(decision['delay_seconds'])
            return decision['retry']
        def process_quality(status, actual, message=None):
            record_quality_result(
                run_id, 'process_exit_code', db_path=db_path,
                expected_value=0, actual_value=actual,
                status=status, message=message,
            )
        try:
            for attempt in range(MAX_RETRIES + 1):
                if _clock.monotonic() - started >= total_budget:
                    with _state_lock:
                        collect_tasks[source_key] = {'status': 'failed', 'run_id': run_id,
                            'last_run': datetime.now().isoformat(), 'output': all_output,
                            'error': '采集总时间预算已耗尽', 'attempts': attempt}
                    update_run(run_id, status='failed', db_path=db_path,
                               error_code='TIME_BUDGET_EXHAUSTED', error_message='采集总时间预算已耗尽')
                    upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                                      status='failed', error_code='TIME_BUDGET_EXHAUSTED')
                    process_quality('failed', 'time_budget_exhausted')
                    save_collect_state()
                    return
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
                    process_env = loopback_proxy_env()
                    process_env['PYTHONIOENCODING'] = 'utf-8'
                    process_env['TMALL_COLLECT_RUN_ID'] = run_id
                    process_env['TMALL_WINDOW_START'] = window_start
                    process_env['TMALL_SHOP_ID'] = shop_id
                    process_env['TMALL_WINDOW_END'] = window_end
                    process_env['TMALL_DB_PATH'] = db_path
                    _apply_browser_env(process_env, browser_config)
                    if browser_config is not None:
                        # Revalidate on every retry, not only before the request queues.
                        require_browser_identity(browser_config)
                    process_env['TMALL_COLLECTOR_VERSION'] = APP_VERSION
                    # 单品流量采集的商品数上限。采集器默认已是 200，这里再固化一次，
                    # 避免部署环境未设置时回落到旧的 50 造成覆盖度断崖。
                    process_env.setdefault('TMALL_ITEM_MAX_ITEMS', '50')  # 用户要求TOP50
                    proc = subprocess.Popen(
                        [collect_python, '-u', script_path],
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
                        stdout, _ = proc.communicate(timeout=max(0.01, min(COLLECT_TIMEOUT, total_budget - (_clock.monotonic() - started))))
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
                        if retry_allowed(classify_collection_failure(['timeout']), attempt):
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
                        evidence = collection_completion_evidence(output_lines, run_id=run_id,
                            source_key=source_key, window_start=window_start, window_end=window_end, db_path=db_path)
                        if not evidence['ok']:
                            update_run(run_id, status=evidence['status'], db_path=db_path,
                                error_code=evidence['code'], error_message='采集完成证据未通过，禁止发布旧分区快照',
                                stats={'completion_evidence': evidence})
                            upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                                status='failed', error_code=evidence['code'])
                            process_quality('failed', evidence['code'])
                            with _state_lock:
                                collect_tasks[source_key] = {'status': evidence['status'], 'run_id': run_id,
                                    'last_run': datetime.now().isoformat(), 'output': all_output, 'error': evidence['code']}
                            save_collect_state()
                            return
                        coverage = evidence['receipt']['coverage']
                        snapshot = None
                        try:
                            # Legacy collectors write facts directly; capture
                            # the resulting partition for unified audit/quality.
                            snapshot = stage_source_snapshot(
                                run_id, source_key, config['table'], config['date_col'],
                                db_path=db_path, window_start=window_start, window_end=window_end,
                                expected_rows=evidence['receipt']['row_count'],
                                required_fields=COLLECTOR_CATALOG.get(source_key, {}).get('fields', []),
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
                                'status': 'pending_quality',
                                'last_run': datetime.now().isoformat(),
                                'output': all_output,
                                'return_code': proc.returncode,
                                'attempts': attempt + 1,
                                'run_id': run_id,
                            }
                        has_output = bool(output_lines)
                        snapshot_ok = bool(snapshot and snapshot.get('status') == 'published'
                                           and snapshot.get('row_count', 0) > 0)
                        gate_ok = has_output and snapshot_ok and snapshot.get('row_count') == evidence['receipt']['row_count']
                        with _state_lock:
                            collect_tasks[source_key]['status'] = 'completed' if gate_ok else 'failed'
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
                            window_start=window_start, window_end=window_end,
                        ), ensure_ascii=False))
                        save_collect_state()
                        return

                    failure_code, last_error = _classify_process_failure(
                        output_lines, proc.returncode,
                    )
                    failure = classify_collection_failure(output_lines, proc.returncode)
                    if retry_allowed(failure, attempt):
                        continue
                    with _state_lock:
                        collect_tasks[source_key] = {
                            'status': failure['status'],
                            'last_run': datetime.now().isoformat(),
                            'output': all_output,
                            'error': last_error,
                            'return_code': proc.returncode,
                            'attempts': attempt + 1,
                            'run_id': run_id,
                        }
                    update_run(run_id, status=failure['status'], db_path=db_path, attempt=attempt + 1,
                               error_code=failure_code, error_message=last_error)
                    process_quality('failed', proc.returncode, last_error)
                    upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                                      status='failed', error_code=failure_code,
                                      error_message=last_error)
                    all_output.append('RESULT_JSON ' + json.dumps(_build_result_event(
                        source_key, run_id, status=failure['status'], return_code=proc.returncode,
                        quality_gate='not_evaluated', error_code=failure_code), ensure_ascii=False))
                    save_collect_state()
                    return
                except Exception as error:
                    last_error = str(error)
                    exception_code = 'BROWSER_NOT_READY' if isinstance(error, BrowserConfigurationError) else 'COLLECTOR_EXCEPTION'
                    failure = classify_collection_failure([type(error).__name__ + ': ' + str(error)])
                    if isinstance(error, BrowserConfigurationError):
                        failure.update(status='blocked', retryable=False)
                    elif failure['category'] != 'unknown':
                        exception_code = failure['code']
                    if not isinstance(error, BrowserConfigurationError) and retry_allowed(failure, attempt):
                        continue
                    with _state_lock:
                        collect_tasks[source_key] = {
                            'status': failure['status'],
                            'last_run': datetime.now().isoformat(),
                            'output': all_output,
                            'error': last_error,
                            'attempts': attempt + 1,
                            'run_id': run_id,
                        }
                    update_run(run_id, status=failure['status'], db_path=db_path, attempt=attempt + 1,
                               error_code=exception_code, error_message=last_error)
                    process_quality('failed', 'exception', last_error)
                    upsert_checkpoint(run_id, 'process', source_key, db_path=db_path,
                                      status='failed', error_code=exception_code,
                                      error_message=last_error)
                    all_output.append('RESULT_JSON ' + json.dumps(_build_result_event(
                        source_key, run_id, status=failure['status'], quality_gate='not_evaluated',
                        error_code=exception_code), ensure_ascii=False))
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
    """获取采集日志；持久化运行记录优先，进程内日志用于补充细节。"""
    if source_key not in DATA_SOURCES:
        return failure('INVALID_SOURCE', '无效的数据源')

    db_path = current_app.config.get('DATABASE_PATH')
    reconcile_stale_runs(db_path=db_path)
    task = collect_tasks.get(source_key, {})
    durable = latest_runs_by_source(
        db_path=db_path, shop_id=get_shop_id(),
    ).get(source_key)
    durable_status = None
    if durable:
        if durable['status'] in {'queued', 'running'}:
            durable_status = durable['status']
        elif durable['status'] in {'succeeded', 'succeeded_with_warnings'}:
            durable_status = 'completed'
        elif durable['status'] == 'partial':
            durable_status = 'partial'
        else:
            durable_status = 'failed'
    status = durable_status or task.get('status', 'idle')
    last_run = (
        (durable.get('finished_at') or durable.get('updated_at')
         or durable.get('started_at') or durable.get('created_at'))
        if durable else task.get('last_run')
    )
    return success({
        'source': source_key,
        'status': status,
        'run_status': durable.get('status') if durable else None,
        'last_run': last_run,
        'run_id': durable.get('id') if durable else task.get('run_id'),
        'output': task.get('output', []),
        'error': task.get('error') or (durable.get('error_message') if durable else None),
    })


@collect_bp.route('/api/collect/runs/<run_id>', methods=['GET'])
def get_collect_run(run_id):
    """Return a durable collector run record by id."""
    db_path = current_app.config.get('DATABASE_PATH')
    shop_id = current_request_shop_id()
    run = get_run(run_id, db_path=db_path, shop_id=shop_id)
    if not run:
        return failure('RUN_NOT_FOUND', '采集运行记录不存在', status=404)
    return success({
        'run': run,
        'checkpoints': list_checkpoints(run_id, db_path=db_path, shop_id=shop_id),
        'quality_results': list_quality_results(run_id, db_path=db_path, shop_id=shop_id),
        'artifacts': list_artifacts(run_id, db_path=db_path, shop_id=shop_id),
        'quality_gate': quality_gate(run_id, db_path=db_path, shop_id=shop_id),
    })


@collect_bp.route('/api/collect/runs/<run_id>/retry', methods=['POST'])
def retry_collect_run(run_id):
    """Preview or execute a retry limited to failed checkpoint units."""
    body = request.get_json(silent=True) or {}
    db_path = current_app.config.get('DATABASE_PATH')
    shop_id = current_request_shop_id()
    try:
        parent = get_run(run_id, db_path=db_path, shop_id=shop_id)
        if not parent:
            return failure('RUN_NOT_FOUND', '采集运行记录不存在', status=404)
        config = DATA_SOURCES.get(parent['source_key'])
        if not config:
            return failure('INVALID_SOURCE', '运行记录对应的数据源不存在', status=422)
        result = start_retry(
            run_id,
            collectors_dir=COLLECTORS_DIR,
            python_executable=resolve_python(PROJECT_ROOT, fallback=VENV_PYTHON) if body.get('execute') else VENV_PYTHON,
            script_name=config['script'],
            db_path=db_path,
            execute=bool(body.get('execute')),
            shop_id=shop_id,
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
            shop_id=current_request_shop_id(),
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
    db_path = current_app.config.get('DATABASE_PATH')
    shop_id = current_request_shop_id()
    run = get_run(run_id, db_path=db_path, shop_id=shop_id)
    if not run:
        return failure('RUN_NOT_FOUND', '采集运行记录不存在', status=404)
    rows = list_data_staging(run_id, db_path=db_path, shop_id=shop_id)
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
            shop_id=current_request_shop_id(),
        )
    except ValueError as exc:
        return failure('RETRY_SCOPE_ERROR', str(exc), status=422)
    if not result:
        return failure('RUN_NOT_FOUND', '父或子采集运行记录不存在', status=404)
    return success(result)

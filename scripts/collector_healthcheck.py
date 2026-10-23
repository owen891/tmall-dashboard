"""Generate a machine-readable collector health report."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def persist_alerts(report, db_path=None):
    """Persist only actionable health conditions; repeated runs upsert."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from services.collector_run_service import (record_health_alert, resolve_health_alert,
        reconcile_date_gaps, list_health_alerts)
    if not report.get('ok'):
        record_health_alert('_monitor', 'endpoint_unreachable', '巡检未能读取健康接口',
                            details={'error_type': report.get('error_type')}, db_path=db_path)
        return
    for alert in list_health_alerts(source_key='_monitor', db_path=db_path):
        if alert['alert_type'] == 'endpoint_unreachable':
            resolve_health_alert('_monitor', alert['alert_type'], alert['fingerprint'], db_path=db_path)
    coverage = report.get('data', {}).get('monitoring', {})
    if coverage and coverage.get('status') != 'active':
        record_health_alert('_monitor', 'healthcheck_heartbeat', '巡检心跳缺失、过期或不可验证',
                            details=coverage, db_path=db_path)
    elif coverage.get('status') == 'active':
        for alert in list_health_alerts(source_key='_monitor', db_path=db_path):
            if alert['alert_type'] == 'healthcheck_heartbeat':
                resolve_health_alert('_monitor', alert['alert_type'], alert['fingerprint'], db_path=db_path)
    for source in report.get('data', {}).get('sources', []):
        key = source['source_key']
        # 未启用的源（enabled=False，如 dts_market）不产生新告警 —— 与
        # api/collect_api.py 的 unhealthy 判定保持同一语义。注意下面的 resolve
        # 循环仍会执行，好把历史上可能残留的 open 告警清掉。
        enabled = source.get('enabled', True)
        conditions = []
        if enabled and source.get('consecutive_failures', 0) >= 3:
            conditions.append(('consecutive_failure', '连续失败/异常运行达到 3 次', 'critical'))
        # 与 api/collect_api.py 的 unhealthy 判定保持同口径：按各源自身的 fresh_days
        # 阈值判断，而不是硬编码 3 天（月表 fresh_days=40，否则会天天误报"延迟 31 天"）。
        if enabled and (source.get('age_days') or 0) > source.get('fresh_days', 3):
            conditions.append(('data_delay', f"最新事实已延迟 {source['age_days']} 天"
                                              f"（阈值 {source.get('fresh_days', 3)} 天）", 'warning'))
        missing = source.get('missing_dates') or []
        acceptance = source.get('coverage_acceptance', {})
        if enabled:
            reconcile_date_gaps(key, set(missing) | set(acceptance.get('rejected_dates', [])),
                verified_dates=acceptance.get('verified_dates', []), db_path=db_path)
        if enabled and acceptance.get('status') in {'unknown', 'partial'}:
            conditions.append(('critical_fields_incomplete', '事实日期或关键字段覆盖未通过验收', 'critical'))
        if enabled and source.get('gap_check_status') == 'unknown':
            conditions.append(('gap_check_unknown', '日期覆盖检查不可验证', 'critical'))
        if enabled and missing:
            shown = ', '.join(missing[:5]) + (' 等' if len(missing) > 5 else '')
            conditions.append(('data_gap',
                               f"近 7 天缺失 {len(missing)} 天：{shown}", 'critical'))
        if enabled and source.get('table_error'):
            conditions.append(('schema_or_table_error', source['table_error'], 'critical'))
        active_types = set()
        for alert_type, message, severity in conditions:
            active_types.add(alert_type)
            record_health_alert(key, alert_type, message, severity=severity,
                                details=source, db_path=db_path)
        for alert_type in ('consecutive_failure', 'data_delay', 'data_gap',
                           'schema_or_table_error', 'gap_check_unknown', 'critical_fields_incomplete'):
            if alert_type not in active_types:
                # Resolve all currently open fingerprints for this source/type.
                from services.collector_run_service import list_health_alerts
                for alert in list_health_alerts(source_key=key, db_path=db_path):
                    if alert['alert_type'] == alert_type:
                        resolve_health_alert(key, alert_type, alert['fingerprint'], db_path=db_path)


def fetch_health(base_url):
    request = urllib.request.Request(
        f'{base_url.rstrip("/")}/api/collect/health',
        headers={'Accept': 'application/json'},
    )
    # 目标是本机看板服务，显式禁用代理：开发/沙箱环境常设 http_proxy，而
    # urllib 默认会把代理用在 127.0.0.1 上，导致本地健康检查莫名失败
    # （表现为 URLError/502，看着像服务没起）。curl 默认跳过 localhost，
    # Python 不跳——这是两者行为差异的坑。
    host = urllib.parse.urlsplit(base_url).hostname or ''
    if host in ('127.0.0.1', 'localhost', '::1'):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    else:
        opener = urllib.request.build_opener()
    with opener.open(request, timeout=15) as response:
        payload = json.loads(response.read().decode('utf-8'))
    if not payload.get('ok'):
        raise RuntimeError(payload.get('message', 'collector health endpoint failed'))
    return payload


def notify_webhook(url, report):
    request = urllib.request.Request(
        url,
        data=json.dumps(report, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status


def deliver_events(*, db_path=None, webhook=None, dry_run=False, sender=None):
    """Unconfigured is never delivered. Stable event ids enable receiver-side dedup."""
    from services.collector_run_service import pending_health_events, record_event_delivery
    sender = sender or notify_webhook
    results = []
    for event in pending_health_events(db_path=db_path):
        status = 'unconfigured'
        if dry_run:
            status = 'dry_run'
        elif webhook:
            try:
                response = sender(webhook, {'event': event})
                status = 'delivered' if 200 <= response < 300 else 'failed'
            except (OSError, urllib.error.URLError, ValueError):
                status = 'failed'
        record_event_delivery(event['id'], status, db_path=db_path)
        results.append({'event_id': event['id'], 'kind': event['kind'], 'status': status})
    return results


def write_heartbeat(path, status):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name, suffix='.tmp', delete=False) as handle:
        temp = Path(handle.name)
        json.dump({'checked_at': datetime.now(timezone.utc).isoformat(), 'status': status}, handle)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description='Generate collector health report')
    parser.add_argument('--base-url', default=os.environ.get('TMALL_DASHBOARD_URL', 'http://127.0.0.1:5000'))
    parser.add_argument('--output', default=None, help='JSON output path; default logs/collector-health-*.json')
    parser.add_argument('--webhook', default=os.environ.get('TMALL_HEALTH_WEBHOOK'),
                        help='optional webhook notified only when health is degraded')
    parser.add_argument('--dry-run-notifications', action='store_true')
    parser.add_argument('--heartbeat', default=str(PROJECT_ROOT / 'logs' / 'collector-health-heartbeat.json'))
    args = parser.parse_args()
    try:
        report = fetch_health(args.base_url)
        report['generated_at'] = datetime.now().isoformat(timespec='seconds')
        exit_code = 0 if report['data']['status'] == 'healthy' else 2
    except (OSError, urllib.error.URLError, ValueError, RuntimeError) as error:
        report = {
            'ok': False, 'generated_at': datetime.now().isoformat(timespec='seconds'),
            'error_type': type(error).__name__, 'error': str(error),
        }
        exit_code = 1
    try:
        persist_alerts(report, os.environ.get('TMALL_DB_PATH'))
        report['notifications'] = deliver_events(db_path=os.environ.get('TMALL_DB_PATH'),
            webhook=args.webhook, dry_run=args.dry_run_notifications)
        if any(event['status'] == 'failed' for event in report['notifications']):
            exit_code = exit_code or 2
    except Exception as error:
        # Do not fabricate delivery when the local ledger itself is unavailable.
        report['notification_error'] = type(error).__name__
        exit_code = 1
    output = Path(args.output) if args.output else PROJECT_ROOT / 'logs' / (
        f"collector-health-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    write_heartbeat(args.heartbeat, 'error' if exit_code == 1 else
                    'degraded' if exit_code == 2 else report.get('data', {}).get('status', 'error'))
    print(json.dumps({'output': str(output.resolve()), 'status': report.get('data', {}).get('status', 'error'),
                      'exit_code': exit_code}, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())

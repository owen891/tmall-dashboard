"""Generate a machine-readable collector health report."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def persist_alerts(report, db_path=None):
    """Persist only actionable health conditions; repeated runs upsert."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from services.collector_run_service import record_health_alert, resolve_health_alert
    for source in report.get('data', {}).get('sources', []):
        key = source['source_key']
        conditions = []
        if source.get('consecutive_failures', 0) >= 3:
            conditions.append(('consecutive_failure', '连续失败/异常运行达到 3 次', 'critical'))
        if (source.get('age_days') or 0) > 3:
            conditions.append(('data_delay', f"最新事实已延迟 {source['age_days']} 天", 'warning'))
        if source.get('table_error'):
            conditions.append(('schema_or_table_error', source['table_error'], 'critical'))
        active_types = set()
        for alert_type, message, severity in conditions:
            active_types.add(alert_type)
            record_health_alert(key, alert_type, message, severity=severity,
                                details=source, db_path=db_path)
        for alert_type in ('consecutive_failure', 'data_delay', 'schema_or_table_error'):
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
    with urllib.request.urlopen(request, timeout=15) as response:
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


def main():
    parser = argparse.ArgumentParser(description='Generate collector health report')
    parser.add_argument('--base-url', default=os.environ.get('TMALL_DASHBOARD_URL', 'http://127.0.0.1:5000'))
    parser.add_argument('--output', default=None, help='JSON output path; default logs/collector-health-*.json')
    parser.add_argument('--webhook', default=os.environ.get('TMALL_HEALTH_WEBHOOK'),
                        help='optional webhook notified only when health is degraded')
    args = parser.parse_args()
    try:
        report = fetch_health(args.base_url)
        report['generated_at'] = datetime.now().isoformat(timespec='seconds')
        persist_alerts(report, os.environ.get('TMALL_DB_PATH'))
        exit_code = 0 if report['data']['status'] == 'healthy' else 2
    except (OSError, urllib.error.URLError, ValueError, RuntimeError) as error:
        report = {
            'ok': False, 'generated_at': datetime.now().isoformat(timespec='seconds'),
            'error_type': type(error).__name__, 'error': str(error),
        }
        exit_code = 1
    output = Path(args.output) if args.output else PROJECT_ROOT / 'logs' / (
        f"collector-health-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if report.get('data', {}).get('status') != 'healthy' and args.webhook and report.get('data'):
        try:
            notify_webhook(args.webhook, report)
        except (OSError, urllib.error.URLError) as error:
            print(json.dumps({'webhook_error': str(error)}, ensure_ascii=False), file=sys.stderr)
    print(json.dumps({'output': str(output.resolve()), 'status': report.get('data', {}).get('status', 'error'),
                      'exit_code': exit_code}, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())

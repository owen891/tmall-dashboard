"""Compare the collector catalog with its persisted schema history."""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.collector_run_service import save_schema_snapshot, record_health_alert


def fetch_catalog(base_url):
    request = urllib.request.Request(
        f'{base_url.rstrip("/")}/api/collect/catalog',
        headers={'Accept': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode('utf-8'))
    if not payload.get('ok'):
        raise RuntimeError(payload.get('message', 'collector catalog endpoint failed'))
    return payload.get('data', payload)


def main():
    parser = argparse.ArgumentParser(description='Check collector catalog schema drift')
    parser.add_argument('--base-url', default=os.environ.get('TMALL_DASHBOARD_URL', 'http://127.0.0.1:5000'))
    parser.add_argument('--db-path', default=os.environ.get('TMALL_DB_PATH'))
    parser.add_argument('--output', default=None)
    args = parser.parse_args()
    try:
        catalog = fetch_catalog(args.base_url)
        sources = catalog.get('sources', []) if isinstance(catalog, dict) else []
        results = []
        changed = []
        for source in sources:
            key = source.get('source_key') or source.get('key')
            if not key:
                continue
            result = save_schema_snapshot(key, source, db_path=args.db_path)
            results.append(result)
            if result['changed']:
                changed.append(result)
                record_health_alert(
                    key, 'schema_changed',
                    f"采集字段目录发生变化: {result['previous_hash']} -> {result['schema_hash']}",
                    severity='critical', fingerprint=result['schema_hash'], details=source,
                    db_path=args.db_path,
                )
        report = {'ok': not changed, 'changed_count': len(changed), 'sources': results}
        exit_code = 2 if changed else 0
    except (OSError, urllib.error.URLError, ValueError, RuntimeError) as error:
        report = {'ok': False, 'error_type': type(error).__name__, 'error': str(error), 'sources': []}
        exit_code = 1
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())

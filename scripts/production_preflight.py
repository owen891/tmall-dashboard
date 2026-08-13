"""本地生产启动前的只读检查。"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FORMAL_ROUTES = (
    '/',
    '/products',
    '/promotion',
    '/lifecycle',
    '/goals',
    '/reviews',
    '/data-center',
    '/settings',
)


def _database_report(database_path):
    connection = sqlite3.connect(database_path)
    try:
        return {
            'path': str(Path(database_path).resolve()),
            'integrity': connection.execute('PRAGMA integrity_check').fetchone()[0],
            'tables': connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0],
        }
    finally:
        connection.close()


def run_preflight(database_path=None):
    if database_path is None:
        with tempfile.TemporaryDirectory(prefix='tmall-production-preflight-') as directory:
            return run_preflight(str(Path(directory) / 'dashboard.db'))

    original_database_path = os.environ.get('TMALL_DB_PATH')
    os.environ['TMALL_DB_PATH'] = str(database_path)
    from app import create_app
    if original_database_path is None:
        os.environ.pop('TMALL_DB_PATH', None)
    else:
        os.environ['TMALL_DB_PATH'] = original_database_path

    app = create_app({'TESTING': False, 'DATABASE_PATH': str(database_path)})
    with app.test_client() as client:
        health_response = client.get('/healthz')
        health_payload = health_response.get_json()
        routes = {}
        for route in FORMAL_ROUTES:
            response = client.get(route)
            routes[route] = response.status_code
            response.close()
        health_response.close()

    database = _database_report(database_path)
    ok = (
        database['integrity'] == 'ok'
        and health_response.status_code == 200
        and health_payload['data']['database'] == 'ok'
        and all(status == 200 for status in routes.values())
    )
    return {
        'ok': ok,
        'database': database,
        'health': {'status': health_response.status_code, 'payload': health_payload},
        'routes': routes,
    }


def main():
    parser = argparse.ArgumentParser(description='检查本地生产启动前的数据库和正式路由。')
    parser.add_argument('--database', default=None, help='要检查的 SQLite 数据库路径；默认使用临时数据库。')
    arguments = parser.parse_args()
    report = run_preflight(arguments.database)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()

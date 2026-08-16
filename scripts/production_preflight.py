"""本地生产启动前的只读检查。"""

import argparse
import base64
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from db import init_db


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


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run_recovery_drill(source_database_path):
    """Verify a source database can be copied and migrated without touching it."""
    source = Path(source_database_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    source_sha256 = _sha256(source)
    with tempfile.TemporaryDirectory(prefix='tmall-recovery-drill-') as directory:
        copy_path = Path(directory) / 'dashboard.db'
        shutil.copy2(source, copy_path)
        copy_sha256_before = _sha256(copy_path)
        integrity_before = _database_report(copy_path)['integrity']
        init_db(str(copy_path))
        after = _database_report(copy_path)
    report = {
        'source_path': str(source),
        'source_sha256': source_sha256,
        'copy_sha256_before': copy_sha256_before,
        'integrity_before': integrity_before,
        'integrity_after': after['integrity'],
        'tables_after': after['tables'],
    }
    report['ok'] = (
        report['source_sha256'] == report['copy_sha256_before']
        and report['integrity_before'] == 'ok'
        and report['integrity_after'] == 'ok'
        and report['tables_after'] > 0
    )
    return report


def run_preflight(database_path=None, *, username=None, password=None, require_auth=False):
    if database_path is None:
        with tempfile.TemporaryDirectory(prefix='tmall-production-preflight-') as directory:
            return run_preflight(
                str(Path(directory) / 'dashboard.db'),
                username=username,
                password=password,
                require_auth=require_auth,
            )

    app_config = {'TESTING': False, 'DATABASE_PATH': str(database_path)}
    if username is not None:
        app_config['DASHBOARD_USERNAME'] = username
    if password is not None:
        app_config['DASHBOARD_PASSWORD'] = password
    app = create_app(app_config)
    with app.test_client() as client:
        health_response = client.get('/healthz')
        health_payload = health_response.get_json()
        routes = {}
        for route in FORMAL_ROUTES:
            response = client.get(route)
            routes[route] = response.status_code
            response.close()
        health_response.close()

        auth_report = {'required': bool(require_auth)}
        if require_auth and username and password:
            credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
            unauthenticated = client.get('/healthz', environ_overrides={'REMOTE_ADDR': '192.168.10.20'})
            authenticated = client.get(
                '/healthz',
                headers={'Authorization': f'Basic {credentials}'},
                environ_overrides={'REMOTE_ADDR': '192.168.10.20'},
            )
            auth_report.update({
                'unauthenticated_external_status': unauthenticated.status_code,
                'authenticated_external_status': authenticated.status_code,
            })
            unauthenticated.close()
            authenticated.close()
        elif require_auth:
            auth_report['error'] = 'AUTH_CONFIGURATION_REQUIRED'

    database = _database_report(database_path)
    ok = (
        database['integrity'] == 'ok'
        and health_response.status_code == 200
        and health_payload['data']['database'] == 'ok'
        and all(status == 200 for status in routes.values())
    )
    if require_auth:
        ok = ok and auth_report.get('unauthenticated_external_status') == 401 and auth_report.get('authenticated_external_status') == 200
    return {
        'ok': ok,
        'database': database,
        'health': {'status': health_response.status_code, 'payload': health_payload},
        'routes': routes,
        'auth': auth_report,
    }


def main():
    parser = argparse.ArgumentParser(description='检查本地生产启动前的数据库和正式路由。')
    parser.add_argument('--database', default=None, help='要检查的 SQLite 数据库路径；默认使用临时数据库。')
    parser.add_argument('--recovery-source', default=None, help='只读复制该数据库并执行恢复演练。')
    parser.add_argument('--require-auth', action='store_true', help='require and verify external Basic Auth')
    arguments = parser.parse_args()
    report = run_recovery_drill(arguments.recovery_source) if arguments.recovery_source else run_preflight(
        arguments.database,
        username=os.environ.get('DASHBOARD_USERNAME'),
        password=os.environ.get('DASHBOARD_PASSWORD'),
        require_auth=arguments.require_auth,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()

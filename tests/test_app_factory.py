import os
import sys
import tempfile
import unittest
import sqlite3
import gzip
import json
import atexit
import subprocess
from pathlib import Path
from unittest.mock import patch

from flask import Flask

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = Path(PROJECT_ROOT, 'VERSION').read_text(encoding='utf-8').strip()
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_TEST_DATA_DIR = tempfile.TemporaryDirectory(prefix='tmall-dashboard-factory-tests-')
atexit.register(_TEST_DATA_DIR.cleanup)


class AppFactoryTests(unittest.TestCase):
    def test_importing_app_factory_does_not_initialize_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'lazy.db')
            environment = os.environ.copy()
            environment['TMALL_DB_PATH'] = database_path
            subprocess.run(
                [sys.executable, '-c', 'import app'],
                check=True,
                cwd=PROJECT_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertFalse(os.path.exists(database_path))

    def test_existing_goal_lock_table_is_migrated_for_year_and_quarter_locks(self):
        path = os.path.join(_TEST_DATA_DIR.name, 'legacy-locks.db')
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE goal_locks (id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, period_type TEXT NOT NULL CHECK(period_type IN ('month','week','date')), period_key TEXT NOT NULL, version INTEGER NOT NULL, locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(year, period_type, period_key))")
        conn.commit(); conn.close()
        from db import init_db
        init_db(path)
        conn = sqlite3.connect(path)
        ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name='goal_locks'").fetchone()[0]
        conn.close()
        self.assertIn("'quarter'", ddl)
        self.assertIn("'year'", ddl)

    def test_database_url_environment_overrides_tmall_db_path(self):
        from app import create_app

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {
            'DATABASE_URL': 'sqlite:///' + os.path.join(temp_dir, 'env.db').replace('\\\\', '/'),
            'TMALL_DB_PATH': os.path.join(temp_dir, 'path.db'),
        }, clear=False):
            app = create_app({'TESTING': True})

        self.assertTrue(app.config['DATABASE_PATH'].endswith(os.path.join(temp_dir, 'env.db')))
        self.assertFalse(os.path.exists(os.path.join(temp_dir, 'path.db')))

    def test_external_missing_scan_root_is_not_created_or_startup_blocking(self):
        from app import create_app

        with tempfile.TemporaryDirectory() as temp_dir:
            external_root = os.path.join(temp_dir, 'external', 'missing')
            app = create_app({'TESTING': True, 'IMPORT_SCAN_ALLOWED_ROOTS': [external_root]})
            self.assertFalse(os.path.exists(external_root))
            self.assertEqual(app.config['IMPORT_SCAN_ALLOWED_ROOTS'][-1], os.path.abspath(external_root))

    def test_database_migration_is_idempotent_and_records_one_applied_step(self):
        from db import SCHEMA_VERSION, init_db

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'idempotent.db')
            init_db(database_path)
            init_db(database_path)
            connection = sqlite3.connect(database_path)
            try:
                rows = connection.execute(
                    'SELECT version, state FROM schema_migrations ORDER BY version'
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(rows, [(SCHEMA_VERSION, 'applied')])

        from db import SCHEMA_VERSION, init_db

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'schema.db')
            init_db(database_path)
            connection = sqlite3.connect(database_path)
            try:
                version = connection.execute('PRAGMA user_version').fetchone()[0]
            finally:
                connection.close()
        self.assertEqual(version, SCHEMA_VERSION)

    def test_database_connections_wait_for_concurrent_writers(self):
        from db import get_connection, init_db

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'busy-timeout.db')
            init_db(database_path)
            connection = get_connection(database_path)
            try:
                self.assertEqual(connection.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
                self.assertEqual(connection.execute('PRAGMA busy_timeout').fetchone()[0], 10000)
            finally:
                connection.close()

    def test_factory_database_path_does_not_mutate_process_environment(self):
        from app import create_app

        original_path = os.environ.get('TMALL_DB_PATH')
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'factory-test.db')
            app = create_app({
                'TESTING': True,
                'DATABASE_PATH': database_path,
            })

        self.assertEqual(app.config['DATABASE_PATH'], database_path)
        self.assertEqual(os.environ.get('TMALL_DB_PATH'), original_path)

    def test_explicit_sqlalchemy_sqlite_uri_is_the_single_database_source(self):
        from app import create_app

        with tempfile.TemporaryDirectory() as temp_dir:
            uri_path = os.path.join(temp_dir, 'orm.db')
            stale_path = os.path.join(temp_dir, 'stale.db')
            app = create_app({
                'TESTING': True,
                'DATABASE_PATH': stale_path,
                'SQLALCHEMY_DATABASE_URI': f"sqlite:///{uri_path.replace(os.sep, '/')}",
            })

            self.assertEqual(app.config['DATABASE_PATH'], os.path.abspath(uri_path))
            self.assertTrue(os.path.exists(uri_path))
            self.assertFalse(os.path.exists(stale_path))

    def test_explicit_relative_sqlalchemy_uri_stays_relative_to_working_directory(self):
        from app import create_app

        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                app = create_app({
                    'TESTING': True,
                    'SQLALCHEMY_DATABASE_URI': 'sqlite:///relative.db',
                })
            finally:
                os.chdir(original_cwd)

            expected = os.path.abspath(os.path.join(temp_dir, 'relative.db'))
            self.assertEqual(app.config['DATABASE_PATH'], expected)
            self.assertTrue(os.path.exists(expected))

    def test_default_database_path_matches_raw_runtime_database(self):
        from app import create_app
        from config import DEFAULT_DATABASE_PATH, Config
        from db import get_db_path

        app = create_app({'TESTING': True})
        self.assertEqual(app.config['DATABASE_PATH'], get_db_path())
        self.assertEqual(app.config['DATABASE_PATH'], os.path.abspath(Config.DATABASE_PATH))
        self.assertTrue(DEFAULT_DATABASE_PATH.endswith(os.path.join('data', 'dashboard.db')))

    def test_lan_requests_require_configured_basic_authentication(self):
        from app import create_app

        app = create_app({
            'TESTING': True,
            'DASHBOARD_USERNAME': 'operator',
            'DASHBOARD_PASSWORD': 'correct-horse',
        })
        client = app.test_client()
        denied = client.get('/api/status', environ_overrides={'REMOTE_ADDR': '192.168.10.20'})
        allowed = client.get(
            '/api/status',
            headers={'Authorization': 'Basic b3BlcmF0b3I6Y29ycmVjdC1ob3JzZQ=='},
            environ_overrides={'REMOTE_ADDR': '192.168.10.20'},
        )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(denied.headers['WWW-Authenticate'], 'Basic realm="tmall-dashboard"')
        self.assertEqual(allowed.status_code, 200)

    def test_lan_requests_are_denied_when_credentials_are_not_configured(self):
        from app import create_app

        app = create_app({
            'TESTING': True,
            'DASHBOARD_USERNAME': None,
            'DASHBOARD_PASSWORD': None,
        })
        response = app.test_client().get('/healthz', environ_overrides={'REMOTE_ADDR': '192.168.10.20'})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['code'], 'AUTH_CONFIGURATION_REQUIRED')

    def test_loopback_request_with_forwarded_client_header_does_not_bypass_auth(self):
        from app import create_app

        app = create_app({'TESTING': True, 'DASHBOARD_USERNAME': None, 'DASHBOARD_PASSWORD': None})
        response = app.test_client().get(
            '/healthz',
            headers={'X-Forwarded-For': '192.168.10.20'},
            environ_overrides={'REMOTE_ADDR': '127.0.0.1'},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['code'], 'AUTH_CONFIGURATION_REQUIRED')

    def test_create_app_returns_configurable_flask_app(self):
        from app import create_app

        app = create_app({'TESTING': True})

        self.assertIsInstance(app, Flask)
        self.assertTrue(app.testing)

    def test_factory_keeps_dashboard_entrypoint(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn('天猫'.encode('utf-8'), response.data)
            response.close()


    def test_removed_legacy_and_demo_routes_are_not_exposed(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            for path in ('/legacy/', '/demo/', '/api/demo/manifest', '/static/js/bundle.min.js'):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 404)
                    response.close()

    def test_unknown_api_routes_use_structured_not_found_error(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            response = client.get('/api/does-not-exist')
            payload = response.get_json()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(payload['code'], 'NOT_FOUND')
        self.assertFalse(payload['ok'])

    def test_version_endpoint_is_current_and_uncached(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            response = client.get('/api/version')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['data']['version'], VERSION)
            self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_factory_serves_the_streamlined_frontend_pages(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            for path in ('/', '/products', '/promotion', '/lifecycle', '/reviews', '/data-center', '/settings'):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b'<!doctype html>', response.data.lower())
                    response.close()

    def test_dashboard_pages_and_assets_do_not_serve_stale_frontend_code(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            for path in ('/promotion', '/assets/shell.js', '/assets/promotion-live.js'):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('no-store', response.headers.get('Cache-Control', ''))
                    response.close()

    def test_security_headers_are_present_on_dashboard_responses(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            response = client.get('/healthz')
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(response.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertEqual(response.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')

    def test_legacy_workbench_routes_redirect_to_their_prd_owners(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            compare_response = client.get('/compare', follow_redirects=False)
            manage_response = client.get('/manage', follow_redirects=False)
            self.assertIn(compare_response.status_code, {301, 302, 307, 308})
            self.assertEqual(compare_response.headers['Location'], '/reviews')
            self.assertIn(manage_response.status_code, {301, 302, 307, 308})
            self.assertEqual(manage_response.headers['Location'], '/settings')
            compare_response.close()
            manage_response.close()

    def test_health_check_confirms_database_connectivity(self):
        from app import create_app

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'health-check.db')
            app = create_app({'TESTING': False, 'DATABASE_PATH': database_path})
            with app.test_client() as client:
                response = client.get('/healthz')
                payload = response.get_json()
            response.close()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['data']['database'], 'ok')
        self.assertEqual(payload['data']['service'], 'tmall-dashboard')

    def test_unexpected_api_failures_use_structured_non_diagnostic_error(self):
        from app import create_app
        from services.import_service import import_service

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'unexpected-error.db')
            app = create_app({'TESTING': False, 'DATABASE_PATH': database_path})
            with patch.object(import_service, 'list_batches', side_effect=RuntimeError('database internals')):
                response = app.test_client().get('/api/imports')

        payload = response.get_json()
        self.assertEqual(response.status_code, 500)
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['code'], 'INTERNAL_ERROR')
        self.assertNotIn('database internals', response.get_data(as_text=True))
        self.assertRegex(payload['requestId'], r'^[0-9a-f]{32}$')

    def test_large_json_responses_are_compressed_when_client_supports_gzip(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            response = client.get('/api/page-capabilities', headers={'Accept-Encoding': 'gzip'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get('Content-Encoding'), 'gzip')
            payload = json.loads(gzip.decompress(response.data))
            self.assertTrue(payload['ok'])

            declined = client.get('/api/page-capabilities', headers={'Accept-Encoding': 'gzip;q=0'})
            self.assertIsNone(declined.headers.get('Content-Encoding'))

    def test_wsgi_module_exposes_factory_application(self):
        from wsgi import application

        self.assertIsInstance(application, Flask)
        self.assertFalse(application.debug)


if __name__ == '__main__':
    unittest.main(verbosity=2)

import os
import sys
import tempfile
import unittest
import sqlite3
import gzip
import io
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
    def test_packaged_read_only_resources_use_persistent_database_directory(self):
        import app as application
        from desktop_runtime import desktop_data_paths, desktop_environment
        from utils.static_release import read_current, publish_release, activate_release
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / 'bundle'
            source = bundle / 'frontend/ui_demo'
            (source / 'assets').mkdir(parents=True)
            (source / 'pages').mkdir()
            (source / 'pages/overview.html').write_text('<head><script src="../assets/a.js"></script></head>')
            (source / 'assets/a.js').write_text('A')
            paths = desktop_data_paths({'APPDATA': str(root / 'roaming'), 'LOCALAPPDATA': str(root / 'local')})
            environment = dict(os.environ, **desktop_environment(paths, {}))
            environment.pop('TMALL_ASSET_RELEASE_ROOT', None)
            real_mkdir = Path.mkdir
            rejected = []

            def read_only_bundle(path, *args, **kwargs):
                if path.is_relative_to(bundle):
                    rejected.append(str(path))
                    raise PermissionError('fixture: read-only installed resources')
                return real_mkdir(path, *args, **kwargs)

            store = Path(paths.database).parent / 'frontend-releases'
            with patch.dict(os.environ, environment, clear=True), patch.object(application, 'project_root', str(bundle)), patch.object(application, 'demo_root', str(source)), patch.object(Path, 'mkdir', read_only_bundle):
                app = application.create_app({'TESTING': True})
                with app.test_client() as client, client.get('/') as response:
                    self.assertEqual(response.status_code, 200)
                    first = read_current(store)
                    self.assertIn(first, response.get_data(as_text=True))
                # Restart must use the persistent pointer, not republish changed
                # package bytes. A normal publish/rollback still controls it.
                (source / 'assets/a.js').write_text('B')
                app = application.create_app({'TESTING': True})
                with app.test_client() as client, client.get('/') as response:
                    self.assertIn(first, response.get_data(as_text=True))
                second = publish_release(source, store)
                with app.test_client() as client, client.get('/') as response:
                    self.assertIn(second, response.get_data(as_text=True))
                activate_release(store, first)
                with app.test_client() as client, client.get('/') as response:
                    self.assertIn(first, response.get_data(as_text=True))
                # Explicit override remains stronger than the DB-sibling default.
                override = root / 'override'
                app = application.create_app({'TESTING': True, 'ASSET_RELEASE_ROOT': str(override)})
                with app.test_client() as client, client.get('/') as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(read_current(override), second)
            self.assertEqual(rejected, [])
            self.assertFalse((bundle / 'data').exists())

    def test_static_release_tabs_publication_and_rollback(self):
        """Real Flask routes, temporary DB/source/store, no browser or sockets."""
        import re
        import app as app_module
        from utils.static_release import build_release, activate_release, read_current
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, store = root / 'source', root / 'releases'
            (source / 'pages').mkdir(parents=True)
            (source / 'assets/runtime').mkdir(parents=True)
            html = '<!doctype html><html><head><link href="../assets/theme.css?v=1" rel="stylesheet"><script src="../assets/shell.js?v=1"></script></head><body>A</body></html>'
            for name in ('overview.html', 'promotion.html', 'product-detail.html'):
                (source / 'pages' / name).write_text(html, encoding='utf-8')
            for name, content in [('shell.js', 'SHELL_A'), ('runtime/lazy.js', 'LAZY_A'), ('theme.css', 'A{}')]:
                (source / 'assets' / name).write_text(content)
            with patch.object(app_module, 'demo_root', str(source)):
                app = app_module.create_app({'TESTING': True, 'DATABASE_PATH': str(root / 'db.sqlite'), 'ASSET_RELEASE_ROOT': str(store)})
                with app.test_client() as client:
                    with client.get('/') as response:
                        self.assertEqual(response.status_code, 200)
                        first_html = response.get_data(as_text=True)
                        self.assertIn('no-store', response.headers['Cache-Control'])
                    first = read_current(store)
                    prefix = '/assets/releases/' + first + '/'
                    self.assertIn(prefix + 'shell.js', first_html)
                    self.assertNotIn('?v=1', first_html)
                    self.assertLess(first_html.index('data-tmall-release-guard'), first_html.index('src="'))
                    with client.get(prefix + 'runtime/lazy.js') as response:
                        self.assertEqual(response.data, b'LAZY_A')
                        self.assertIn('immutable', response.headers['Cache-Control'])
                        etag = response.headers['ETag']
                    with client.get(prefix + 'runtime/lazy.js', headers={'If-None-Match': etag}) as response:
                        self.assertEqual(response.status_code, 304)
                        self.assertIn('immutable', response.headers['Cache-Control'])
                    (source / 'assets/runtime/lazy.js').write_text('LAZY_B')
                    second = build_release(source, store)
                    # Publication has not committed: HTML still selects A.
                    with client.get('/') as response:
                        self.assertEqual(response.get_data(as_text=True), first_html)
                    activate_release(store, second)
                    with client.get('/') as response:
                        self.assertIn('/assets/releases/' + second + '/', response.get_data(as_text=True))
                    # Old tab's first ever delayed request after activation stays A.
                    with client.get(prefix + 'runtime/lazy.js') as response:
                        self.assertEqual(response.data, b'LAZY_A')
                    with client.get('/assets/releases/' + second + '/runtime/lazy.js') as response:
                        self.assertEqual(response.data, b'LAZY_B')
                    activate_release(store, first)
                    with client.get('/') as response:
                        self.assertEqual(response.get_data(as_text=True), first_html)
                    for route in ('/promotion', '/products/p', '/product-detail', '/pages/overview.html'):
                        with client.get(route) as response:
                            self.assertEqual(response.status_code, 200)
                            self.assertIn('no-store', response.headers['Cache-Control'])
                            self.assertIn(prefix, response.get_data(as_text=True))
                    (store / 'releases' / first / 'assets/runtime/lazy.js').unlink()
                    for route in (prefix + 'runtime/lazy.js', '/assets/releases/' + '0' * 64 + '/shell.js'):
                        with client.get(route) as response:
                            self.assertEqual(response.status_code, 410)
                            self.assertEqual(response.get_json()['error']['code'], 'UPDATE_REQUIRED')
                            self.assertIn('no-store', response.headers['Cache-Control'])
                            self.assertNotIn('immutable', response.headers['Cache-Control'])

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
                self.assertEqual(connection.execute('PRAGMA busy_timeout').fetchone()[0], 30000)
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
                'DATABASE_URL': f"sqlite:///{uri_path.replace(os.sep, '/')}",
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
                    'DATABASE_URL': 'sqlite:///relative.db',
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

    def test_import_preview_requires_admin_write_from_external_clients(self):
        """AUTH-01：/api/imports/preview 不是只读接口，不得豁免 admin 写保护。

        ImportService.preview 会把完整原始文件写进 import_previews（BLOB），
        services/import_service.py 的 TTL 只有 24 小时且清理仅在后续
        preview/confirm 时触发，因此没有任何数量或总字节配额。若把该路径放进
        app.py 的 public_mutations 豁免名单，任何通过 Basic Auth 的认证用户
        都能靠重复上传持续持久化 BLOB（CPU/内存/磁盘消耗）。

        鉴权模型（services/shop_scope_service.py:126-134 require_admin_write）：
          1) 外部请求必须先匹配唯一的 DASHBOARD_USERNAME/DASHBOARD_PASSWORD，否则 401；
          2) 若配置了 DASHBOARD_ADMIN_USERS，身份还必须在名单内，否则 403。
        所以「认证用户」与「管理员」是两个不同门槛，测试要分别覆盖。
        """
        from app import create_app

        # 场景一：认证通过但不在 admin 名单 -> 403（这正是报告里 viewer 的处境）
        viewer_app = create_app({
            'TESTING': True,
            'DASHBOARD_USERNAME': 'viewer',
            'DASHBOARD_PASSWORD': 'viewer-pass',
            'DASHBOARD_ADMIN_USERS': ['operator'],
        })
        forbidden = viewer_app.test_client().post(
            '/api/imports/preview',
            headers={'Authorization': 'Basic dmlld2VyOnZpZXdlci1wYXNz'},
            environ_overrides={'REMOTE_ADDR': '192.168.10.20'},
            data={'file': (io.BytesIO(b'date,product_id\n2026-04-01,p1\n'), 'tiny.csv')},
            content_type='multipart/form-data',
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.get_json()['code'], 'FORBIDDEN')

        # 场景二：认证与 admin 名单都通过 -> 不因鉴权被拒
        admin_app = create_app({
            'TESTING': True,
            'DASHBOARD_USERNAME': 'operator',
            'DASHBOARD_PASSWORD': 'operator-pass',
            'DASHBOARD_ADMIN_USERS': ['operator'],
        })
        allowed = admin_app.test_client().post(
            '/api/imports/preview',
            headers={'Authorization': 'Basic b3BlcmF0b3I6b3BlcmF0b3ItcGFzcw=='},
            environ_overrides={'REMOTE_ADDR': '192.168.10.20'},
            data={'file': (io.BytesIO(b'date,product_id\n2026-04-01,p1\n'), 'tiny.csv')},
            content_type='multipart/form-data',
        )
        self.assertNotIn(allowed.status_code, (401, 403))

    def test_public_mutation_exemptions_are_minimal(self):
        """public_mutations 豁免名单必须只包含真正不需要 admin 的路径。

        app.py 的 require_admin_for_external_mutations 会对所有外部写请求
        调 require_admin_write()。每往豁免名单里加一条，就多一个绕过 admin
        写保护的入口，所以名单本身要被断言钉住，避免后续顺手加回
        /api/imports/preview（AUTH-01 已移除的那条）。
        """
        source = Path(__file__).resolve().parents[1].joinpath('app.py').read_text(encoding='utf-8')
        marker = 'public_mutations = {'
        start = source.index(marker)
        end = source.index('}', start)
        block = source[start:end]
        self.assertNotIn('/api/imports/preview', block)
        self.assertIn('/api/frontend-errors', block)

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
            self.assertIn('数据概览'.encode('utf-8'), response.data)
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
            # The active UI release id must be exposed even when it is unknown,
            # so the client can always distinguish "same UI" from "no signal".
            self.assertIn('ui_release', response.get_json()['data'])
            self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_factory_serves_the_streamlined_frontend_pages(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            for path in ('/', '/products', '/promotion', '/new-products', '/creative-board', '/lifecycle', '/reviews', '/data-center', '/settings'):
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


def test_latest_release_http_errors_close_response_and_preserve_best_effort():
    import app as application
    import io
    from urllib.error import HTTPError, URLError
    from unittest.mock import patch
    for status in (400, 403, 429, 500):
        stream = io.BytesIO(b'not a release')
        error = HTTPError('https://fixture.invalid/releases/latest', status, 'failed', {}, stream)
        try:
            with patch.dict(application._release_cache, {'checked_at': 0.0, 'payload': None}),                  patch.object(application, 'urlopen', side_effect=error) as transport:
                assert application._latest_release() is None
                assert stream.closed, status
                assert application._latest_release() is None
                assert transport.call_count == 1
        finally:
            error.close()
    for error in (URLError('offline'), ValueError('invalid')):
        with patch.dict(application._release_cache, {'checked_at': 0.0, 'payload': None}),              patch.object(application, 'urlopen', side_effect=error):
            assert application._latest_release() is None
    for content, expected in ((b'{bad', None), (b'{"tag_name":"v-test","html_url":"https://fixture.invalid/v"}', {'tag_name':'v-test','html_url':'https://fixture.invalid/v'})):
        stream = io.BytesIO(content)
        with patch.dict(application._release_cache, {'checked_at': 0.0, 'payload': None}),              patch.object(application, 'urlopen', return_value=stream):
            assert application._latest_release() == expected
            assert stream.closed

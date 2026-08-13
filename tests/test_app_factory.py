import os
import sys
import tempfile
import unittest
import sqlite3

from flask import Flask

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_TEST_DATA_DIR = tempfile.TemporaryDirectory(prefix='tmall-dashboard-factory-tests-')
os.environ.setdefault('TMALL_DB_PATH', os.path.join(_TEST_DATA_DIR.name, 'dashboard.db'))


class AppFactoryTests(unittest.TestCase):
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


    def test_legacy_dashboard_remains_available(self):
        from app import create_app
        with create_app({'TESTING': True}).test_client() as client:
            response = client.get('/legacy/')
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_demo_manifest_lists_active_pages(self):
        from app import create_app
        with create_app({'TESTING': True}).test_client() as client:
            response = client.get('/api/demo/manifest')
            payload = response.get_json()
            response.close()
        self.assertEqual(payload['data_mode'], 'api')
        self.assertEqual(
            {page['id'] for page in payload['pages']},
            {'overview', 'products', 'promotion', 'lifecycle', 'reviews', 'data-center', 'settings'},
        )
        lifecycle = next(page for page in payload['pages'] if page['id'] == 'lifecycle')
        self.assertEqual(lifecycle['data'], 'api')
        reviews = next(page for page in payload['pages'] if page['id'] == 'reviews')
        self.assertEqual(reviews['data'], 'api')
        data_center = next(page for page in payload['pages'] if page['id'] == 'data-center')
        self.assertEqual(data_center['data'], 'api')
        settings = next(page for page in payload['pages'] if page['id'] == 'settings')
        self.assertEqual(settings['data'], 'api')
        products = next(page for page in payload['pages'] if page['id'] == 'products')
        self.assertEqual(products['data'], 'api')
        promotion = next(page for page in payload['pages'] if page['id'] == 'promotion')
        self.assertEqual(promotion['data'], 'api')

    def test_factory_serves_the_streamlined_frontend_pages(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            for path in ('/', '/products', '/promotion', '/lifecycle', '/reviews', '/data-center', '/settings'):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b'<!doctype html>', response.data.lower())
                    response.close()

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

    def test_manifest_uses_formal_routes(self):
        from app import create_app

        with create_app({'TESTING': True}).test_client() as client:
            response = client.get('/api/demo/manifest')
            payload = response.get_json()
            response.close()
        self.assertEqual(
            [page['path'] for page in payload['pages']],
            ['/', '/products', '/promotion', '/lifecycle', '/reviews', '/data-center', '/settings'],
        )

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

    def test_wsgi_module_exposes_factory_application(self):
        from wsgi import application

        self.assertIsInstance(application, Flask)
        self.assertFalse(application.debug)


if __name__ == '__main__':
    unittest.main(verbosity=2)

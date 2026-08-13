import os
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class ProductionPreflightTests(unittest.TestCase):
    def test_importing_preflight_does_not_create_the_default_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'default.db')
            environment = os.environ.copy()
            environment['TMALL_DB_PATH'] = database_path
            subprocess.run(
                [sys.executable, '-c', 'import scripts.production_preflight'],
                cwd=PROJECT_ROOT,
                env=environment,
                check=True,
            )
            self.assertFalse(os.path.exists(database_path))

    def test_preflight_uses_its_database_during_application_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            default_database_path = os.path.join(temp_dir, 'default.db')
            preflight_database_path = os.path.join(temp_dir, 'preflight.db')
            environment = os.environ.copy()
            environment['TMALL_DB_PATH'] = default_database_path
            subprocess.run(
                [
                    sys.executable,
                    '-c',
                    'from scripts.production_preflight import run_preflight; '
                    f'assert run_preflight({preflight_database_path!r})["ok"]',
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                check=True,
            )
            self.assertFalse(os.path.exists(default_database_path))
            self.assertTrue(os.path.exists(preflight_database_path))

    def test_preflight_checks_an_isolated_database_and_formal_routes(self):
        from scripts.production_preflight import run_preflight

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'preflight.db')
            report = run_preflight(database_path)

        self.assertTrue(report['ok'])
        self.assertEqual(report['database']['integrity'], 'ok')
        self.assertEqual(report['health']['status'], 200)
        self.assertEqual(report['health']['payload']['data']['database'], 'ok')
        self.assertEqual(report['routes']['/'], 200)
        self.assertEqual(report['routes']['/settings'], 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)

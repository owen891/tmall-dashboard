import os
import hashlib
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class ProductionPreflightTests(unittest.TestCase):
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

    def test_preflight_can_require_and_verify_external_basic_auth(self):
        from scripts.production_preflight import run_preflight

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'preflight-auth.db')
            report = run_preflight(
                database_path,
                username='operator',
                password='correct-horse',
                require_auth=True,
            )

        self.assertTrue(report['ok'])
        self.assertTrue(report['auth']['required'])
        self.assertEqual(report['auth']['unauthenticated_external_status'], 401)
        self.assertEqual(report['auth']['authenticated_external_status'], 200)

    def test_preflight_fails_closed_when_auth_is_required_but_missing(self):
        from scripts.production_preflight import run_preflight

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'preflight-auth-missing.db')
            report = run_preflight(database_path, require_auth=True)

        self.assertFalse(report['ok'])
        self.assertEqual(report['auth']['error'], 'AUTH_CONFIGURATION_REQUIRED')

    def test_recovery_drill_copies_source_before_running_migrations(self):
        from db import init_db
        from scripts.production_preflight import run_recovery_drill

        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, 'source.db')
            init_db(source)
            with open(source, 'rb') as handle:
                source_hash = hashlib.sha256(handle.read()).hexdigest()

            report = run_recovery_drill(source)

            with open(source, 'rb') as handle:
                self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), source_hash)
        self.assertEqual(report['source_sha256'], source_hash)
        self.assertTrue(report['ok'])
        self.assertEqual(report['copy_sha256_before'], source_hash)
        self.assertEqual(report['integrity_before'], 'ok')
        self.assertEqual(report['integrity_after'], 'ok')
        self.assertGreater(report['tables_after'], 0)

    def test_online_backup_preserves_source_and_produces_integrity_checked_copy(self):
        from db import init_db
        from scripts.backup_database import backup_database

        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, 'source.db')
            destination = os.path.join(temp_dir, 'backups', 'snapshot.db')
            init_db(source)
            with open(source, 'rb') as handle:
                source_hash = hashlib.sha256(handle.read()).hexdigest()

            report = backup_database(source, destination)

            with open(source, 'rb') as handle:
                self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), source_hash)
            self.assertTrue(os.path.isfile(destination))
        self.assertTrue(report['ok'])
        self.assertEqual(report['source_sha256'], source_hash)
        self.assertEqual(report['integrity'], 'ok')


if __name__ == '__main__':
    unittest.main(verbosity=2)

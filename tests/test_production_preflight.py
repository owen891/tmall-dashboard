import os
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


if __name__ == '__main__':
    unittest.main(verbosity=2)

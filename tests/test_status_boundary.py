import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class StatusBoundaryTests(unittest.TestCase):
    def test_status_repository_exposes_existing_contract(self):
        from repos.system_repo import SystemRepo

        result = SystemRepo.get_status()

        self.assertEqual(
            set(result),
            {'has_data', 'product_count', 'monthly_periods', 'weekly_periods'},
        )

    def test_status_route_is_owned_by_status_blueprint(self):
        from app import create_app

        app = create_app({'TESTING': True})
        rule = next(rule for rule in app.url_map.iter_rules()
                    if rule.rule == '/api/status')

        self.assertEqual(rule.endpoint, 'status.get_status')
        response = app.test_client().get('/api/status')
        self.assertEqual(response.status_code, 200)

    def test_status_reports_distinct_periods_not_fact_row_counts(self):
        from app import create_app
        from db import get_db

        with tempfile.TemporaryDirectory(prefix='tmall-dashboard-status-tests-') as temp_dir:
            database_path = os.path.join(temp_dir, 'dashboard.db')
            app = create_app({'TESTING': True, 'DATABASE_PATH': database_path})
            with app.app_context(), get_db() as connection:
                connection.executemany(
                    'INSERT INTO monthly_data (product_id, month) VALUES (?, ?)',
                    [('p1', '2026-01'), ('p2', '2026-01'), ('p1', '2026-02')],
                )
                connection.executemany(
                    'INSERT INTO weekly_data (product_id, week_start) VALUES (?, ?)',
                    [('p1', '2026-01-05'), ('p2', '2026-01-05'), ('p1', '2026-01-12')],
                )
                connection.commit()

            payload = app.test_client().get('/api/status').get_json()

            self.assertEqual(payload['monthly_periods'], 2)
            self.assertEqual(payload['weekly_periods'], 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)

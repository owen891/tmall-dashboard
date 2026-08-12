import os
import sys
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


if __name__ == '__main__':
    unittest.main(verbosity=2)

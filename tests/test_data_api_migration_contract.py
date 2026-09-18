import ast
import re
import unittest
from pathlib import Path

from app import create_app


ROOT = Path(__file__).resolve().parents[1]
DATA_API = ROOT / 'api' / 'data_api.py'


class DataApiMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({'TESTING': True})

    def test_data_blueprint_has_no_active_routes_and_runtime_routes_are_unique(self):
        route_keys = []
        for rule in self.app.url_map.iter_rules():
            for method in rule.methods - {'HEAD', 'OPTIONS'}:
                route_keys.append((str(rule), method))
        self.assertEqual(len(route_keys), len(set(route_keys)))
        self.assertFalse(any(rule.endpoint.startswith('data.') for rule in self.app.url_map.iter_rules()))

    def test_migrated_route_comments_have_real_runtime_owners(self):
        text = DATA_API.read_text(encoding='utf-8-sig')
        declarations = re.findall(
            r"#\s*@data_bp\.route\((['\"])(?P<path>.*?)\1,\s*methods=\[(?P<methods>[^]]+)\]\)"
            r"\s*#\s*已迁移到\s*(?P<target>[\w]+)\.py",
            text,
        )
        self.assertEqual(len(declarations), 80)
        for _, path, methods_text, target in declarations:
            methods = re.findall(r"['\"]([A-Z]+)['\"]", methods_text)
            for method in methods:
                matches = [
                    rule for rule in self.app.url_map.iter_rules()
                    if str(rule) == path and method in rule.methods
                ]
                self.assertTrue(matches, f'missing migrated route: {method} {path}')
                self.assertTrue(
                    any(rule.endpoint.startswith(target.replace('_api', '')) for rule in matches),
                    f'wrong migration owner: {method} {path} -> {target}',
                )

    def test_representative_routes_are_owned_by_split_blueprints(self):
        expected = {
            ('/api/kpi', 'GET'): 'overview_legacy.',
            ('/api/compare', 'GET'): 'data_legacy.',
            ('/api/products', 'GET'): 'products_legacy.',
            ('/api/alerts', 'GET'): 'alerts.',
            ('/api/user_kpis', 'GET'): 'goals_legacy.',
            ('/api/reviews/summary', 'GET'): 'reviews.',
            ('/api/market/rankings', 'GET'): 'market_legacy.',
            ('/api/tasks', 'GET'): 'system_legacy.',
            ('/api/report', 'GET'): 'misc_legacy.',
        }
        for (path, method), owner in expected.items():
            rules = [rule for rule in self.app.url_map.iter_rules() if str(rule) == path and method in rule.methods]
            self.assertEqual(len(rules), 1, f'{method} {path}')
            self.assertTrue(rules[0].endpoint.startswith(owner), rules[0].endpoint)

    def test_removed_scheduler_routes_are_owned_by_system_legacy(self):
        for path, method in (
            ('/api/scheduled_tasks', 'GET'),
            ('/api/scheduled_tasks', 'POST'),
            ('/api/scheduled_tasks/<int:task_id>', 'PUT'),
            ('/api/scheduled_tasks/<int:task_id>', 'DELETE'),
            ('/api/scheduled_tasks/<int:task_id>/run', 'POST'),
        ):
            rules = [rule for rule in self.app.url_map.iter_rules() if str(rule) == path and method in rule.methods]
            self.assertEqual(len(rules), 1, f'{method} {path}')
            self.assertTrue(rules[0].endpoint.startswith('system_legacy.'))


if __name__ == '__main__':
    unittest.main()

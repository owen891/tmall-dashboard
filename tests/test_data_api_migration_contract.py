import json
import tempfile
import unittest
from pathlib import Path

from app import create_app


ROOT = Path(__file__).resolve().parents[1]
DATA_API = ROOT / 'api' / 'data_api.py'
MIGRATION_LEDGER = ROOT / 'tests' / 'data_api_migration_ledger.json'


class DataApiMigrationContractTests(unittest.TestCase):
    """data_api.py 已瘦身为共享工具模块；80 条旧路由的归属由台账 fixture 永久守护。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='tmall-migration-contract-')
        cls.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': str(Path(cls.tmp.name) / 'dashboard.db'),
        })

    def _runtime_routes(self):
        routes = {}
        for rule in self.app.url_map.iter_rules():
            for method in rule.methods - {'HEAD', 'OPTIONS'}:
                routes[(str(rule), method)] = rule.endpoint
        return routes

    def test_data_api_is_helper_module_and_runtime_routes_are_unique(self):
        routes = self._runtime_routes()
        self.assertEqual(len(routes), len(set(routes)))
        self.assertFalse(any(endpoint.startswith('data.') for endpoint in routes.values()))
        text = DATA_API.read_text(encoding='utf-8-sig')
        self.assertNotIn('@data_bp.route', text)
        self.assertNotIn('Blueprint(', text)

    def test_all_migrated_routes_are_owned_by_split_blueprints(self):
        ledger = json.loads(MIGRATION_LEDGER.read_text(encoding='utf-8'))
        self.assertEqual(len(ledger), 29)
        routes = self._runtime_routes()
        for path, methods, target in ledger:
            for method in methods:
                endpoint = routes.get((path, method))
                self.assertTrue(endpoint, f'missing migrated route: {method} {path}')
                self.assertTrue(
                    endpoint.startswith(target.replace('_api', '')),
                    f'wrong migration owner: {method} {path} -> {endpoint}',
                )

    def test_representative_routes_are_owned_by_split_blueprints(self):
        expected = {
            ('/api/compare', 'GET'): 'data_legacy.',
            ('/api/products', 'GET'): 'products_legacy.',
            ('/api/alerts', 'GET'): 'alerts.',
            ('/api/target_progress', 'GET'): 'goals_legacy.',
            ('/api/reviews/summary', 'GET'): 'reviews.',
            ('/api/logs', 'GET'): 'system_legacy.',
        }
        for (path, method), owner in expected.items():
            rules = [rule for rule in self.app.url_map.iter_rules() if str(rule) == path and method in rule.methods]
            self.assertEqual(len(rules), 1, f'{method} {path}')
            self.assertTrue(rules[0].endpoint.startswith(owner), rules[0].endpoint)


if __name__ == '__main__':
    unittest.main()

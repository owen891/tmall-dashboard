import os
import tempfile
import unittest


class PageCapabilityServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-page-capability-')
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db'),
        })

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_registry_has_eleven_unique_pages_and_valid_surfaces(self):
        from services.page_capability_service import (
            PAGE_DEFINITIONS,
            SURFACE_DEFINITIONS,
            validate_registry,
        )

        result = validate_registry()
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(PAGE_DEFINITIONS), 11)
        self.assertEqual(len({item['key'] for item in PAGE_DEFINITIONS}), 11)
        self.assertGreaterEqual(len(SURFACE_DEFINITIONS), 1)
        self.assertTrue(all(item['modal_kind'] in {
            'detail', 'edit', 'config', 'flow'
        } for item in SURFACE_DEFINITIONS))

    def test_registry_definitions_declare_delivery_ownership_and_acceptance_metadata(self):
        from services.page_capability_service import (
            CAPABILITY_DEFINITIONS,
            PAGE_DEFINITIONS,
            SURFACE_DEFINITIONS,
        )

        for definition in (*PAGE_DEFINITIONS, *CAPABILITY_DEFINITIONS, *SURFACE_DEFINITIONS):
            self.assertTrue(definition.get('owner'), definition)
            self.assertTrue(definition.get('target_files'), definition)
            self.assertTrue(definition.get('acceptance_selectors'), definition)
            self.assertIn('navigation_params', definition)

    def test_surfaces_point_to_current_rendered_selectors(self):
        from services.page_capability_service import SURFACE_DEFINITIONS

        surfaces = {item['key']: item for item in SURFACE_DEFINITIONS}
        self.assertEqual(surfaces['promotion.drilldown-detail']['selector'], '[data-promotion-dialog]')
        self.assertNotIn('data-promotion-drawer', surfaces['promotion.drilldown-detail']['selector'])
        self.assertEqual(surfaces['manage.schedule']['modal_kind'], 'flow')

    def test_registry_endpoints_match_real_flask_routes(self):
        from services.page_capability_service import validate_registry, build_page_catalog

        registry = validate_registry(self.app)
        self.assertEqual(registry['errors'], [])
        catalog = build_page_catalog(self.app.config['DATABASE_PATH'], app=self.app)
        self.assertEqual(catalog['endpoint_missing'], [])
        self.assertEqual(catalog['registry_errors'], [])

    def test_empty_data_disables_conditional_capabilities_without_unclassified(self):
        from services.page_capability_service import build_page_catalog

        result = build_page_catalog(self.app.config['DATABASE_PATH'])
        self.assertEqual(result['summary']['page_count'], 11)
        self.assertEqual(result['summary']['unclassified'], 0)
        self.assertFalse(result['summary']['can_release'])
        overview = next(item for item in result['pages'] if item['key'] == 'overview')
        kpi = next(item for item in overview['capabilities'] if item['key'] == 'overview.view_kpis')
        self.assertEqual(kpi['support_level'], 'conditional')
        self.assertEqual(kpi['interaction_state'], 'disabled')
        self.assertIn('store_daily', kpi['data_domains'])
        self.assertEqual(kpi['evidence_level'], 'insufficient')
        self.assertTrue(kpi['limitations'])
        self.assertIsInstance(kpi['freshness'], dict)

    def test_registered_mutations_cover_formal_page_operations(self):
        from services.page_capability_service import CAPABILITY_DEFINITIONS

        by_key = {item['key']: item for item in CAPABILITY_DEFINITIONS}
        self.assertIn('overview.event_edit', by_key)
        self.assertIn('POST /api/overview/events', by_key['overview.event_edit']['api_endpoints'])
        self.assertIn('products.catalog_edit', by_key)
        self.assertIn('PUT /api/products/:product_id/metadata', by_key['products.catalog_edit']['api_endpoints'])
        self.assertIn('POST /api/imports/preview', by_key['data-center.import']['api_endpoints'])
        self.assertIn('POST /api/alert-rules', by_key['settings.configure_alerts']['api_endpoints'])
        self.assertIn('POST /api/manage/schedules', by_key['manage.schedule']['api_endpoints'])

    def test_advanced_promotion_capabilities_have_explicit_release_boundaries(self):
        from services.page_capability_service import CAPABILITY_DEFINITIONS

        by_key = {item['key']: item for item in CAPABILITY_DEFINITIONS}
        self.assertEqual(by_key['promotion.contribution_analysis']['support_level'], 'conditional')
        self.assertIn('GET /api/promotion', by_key['promotion.contribution_analysis']['api_endpoints'])
        self.assertEqual(by_key['promotion.causal_attribution']['support_level'], 'unsupported')

    def test_conditional_capability_enables_when_prerequisites_are_available(self):
        from services.page_capability_service import _resolved_capability

        capability = _resolved_capability(
            {
                'key': 'promotion.drilldown', 'page_key': 'promotion',
                'label': '推广粒度下钻', 'mode': 'analyze',
                'support_level': 'conditional', 'data_domains': ('promotion_daily',),
                'metric_keys': (), 'api_endpoints': ('GET /api/promotion',),
            },
            {'promotion_daily': 'available'},
        )
        self.assertEqual(capability['support_level'], 'conditional')
        self.assertEqual(capability['interaction_state'], 'enabled')

    def test_catalog_filters_are_precise(self):
        from services.page_capability_service import build_page_catalog

        result = build_page_catalog(
            self.app.config['DATABASE_PATH'],
            page='promotion',
            modal_kind='detail',
        )
        self.assertEqual([item['key'] for item in result['pages']], ['promotion'])
        self.assertTrue(all(item['modal_kind'] == 'detail' for item in result['surfaces']))


if __name__ == '__main__':
    unittest.main()

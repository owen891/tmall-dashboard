import os
import tempfile
import unittest


class DataIntegrationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-data-integration-")
        from app import create_app

        self.app = create_app({
            "TESTING": True,
            "DATABASE_PATH": os.path.join(self.temp_dir.name, "dashboard.db"),
            "IMPORT_SCAN_ALLOWED_ROOTS": [self.temp_dir.name],
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_catalog_merges_live_sources_with_planned_capabilities(self):
        response = self.client.get("/api/data-integration/catalog")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["summary"]["total"], 17)
        self.assertEqual(data["summary"]["connected"], 6)
        self.assertGreaterEqual(data["summary"]["blocked"], 1)
        self.assertIn("inventory_eye", {item["key"] for item in data["sources"]})

    def test_catalog_supports_domain_and_readiness_filters(self):
        response = self.client.get("/api/data-integration/catalog?readiness=blocked")
        self.assertEqual(response.status_code, 200)
        sources = response.get_json()["data"]["sources"]
        self.assertTrue(sources)
        self.assertTrue(all(item["readiness"] == "blocked" for item in sources))

        response = self.client.get("/api/data-integration/catalog?domain=inventory")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(item["domain"] == "inventory" for item in response.get_json()["data"]["sources"]))

    def test_catalog_rejects_unknown_filters(self):
        response = self.client.get("/api/data-integration/catalog?readiness=unknown")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["code"], "VALIDATION_ERROR")

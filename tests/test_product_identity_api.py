import os
import tempfile
import unittest


class ProductIdentityApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-product-identity-api-')
        from app import create_app
        from db import get_db
        self.path = os.path.join(self.temp.name, 'dashboard.db')
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': self.path})
        self.client = self.app.test_client()
        with get_db(self.path) as connection:
            connection.execute("INSERT INTO products (product_id, title) VALUES ('catalog-1', '商品一')")
            connection.execute(
                """INSERT INTO promotion_daily_facts
                   (shop_id, date, channel, product_id, grain, ad_spend, attributed_payment_amount)
                   VALUES ('default', '2026-09-20', 'search', 'external-1', 'product', 10, 20)"""
            )
            connection.execute(
                """INSERT INTO product_identity_map
                   (shop_id, source_system, external_product_id, identity_status,
                    display_title, fact_row_count, ad_spend, attributed_payment_amount)
                   VALUES ('default', 'promotion', 'external-1', 'unresolved',
                           'external-1', 1, 10, 20)"""
            )
            connection.commit()

    def tearDown(self):
        self.temp.cleanup()

    def test_list_candidates_exposes_evidence_and_pagination(self):
        response = self.client.get('/api/product-identities?status=unresolved')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['data']['total'], 1)
        self.assertEqual(payload['data']['items'][0]['external_product_id'], 'external-1')
        self.assertIn('evidence', payload['data']['items'][0])

    def test_resolve_requires_existing_catalog_product_and_audits(self):
        response = self.client.post(
            '/api/product-identities/external-1/resolve',
            json={'canonical_product_id': 'catalog-1', 'reason': '人工核对'},
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            from db import get_db
            with get_db(self.path) as connection:
                row = connection.execute(
                    "SELECT identity_status, canonical_product_id FROM product_identity_map WHERE external_product_id='external-1'"
                ).fetchone()
                audit = connection.execute(
                    "SELECT action, entity_type FROM audit_logs WHERE entity_type='product_identity' ORDER BY id DESC LIMIT 1"
                ).fetchone()
        self.assertEqual(tuple(row), ('catalog_linked', 'catalog-1'))
        self.assertEqual(tuple(audit), ('resolve', 'product_identity'))

    def test_resolve_rejects_unknown_catalog_product(self):
        response = self.client.post(
            '/api/product-identities/external-1/resolve',
            json={'canonical_product_id': 'missing'},
        )
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()

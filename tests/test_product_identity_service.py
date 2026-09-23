import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backfill_product_identity_map import build_report
from services.product_identity_service import classify_external_product


class ProductIdentityServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-product-identity-")
        self.database = Path(self.temp_dir.name) / "dashboard.db"
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE products (product_id TEXT PRIMARY KEY, title TEXT, image_url TEXT);
            CREATE TABLE promotion_daily_facts (
                shop_id TEXT, date TEXT, product_id TEXT, grain TEXT,
                ad_spend REAL, attributed_payment_amount REAL, source_batch_id TEXT
            );
            CREATE TABLE promotion_campaign_items (
                shop_id TEXT, product_id TEXT, product_name TEXT, image_url TEXT,
                updated_at TEXT
            );
            CREATE TABLE promotion_creatives (
                shop_id TEXT, product_id TEXT, product_name TEXT, image_url TEXT,
                updated_at TEXT
            );
            INSERT INTO products VALUES ('catalog-1', 'Catalog Product', '');
            INSERT INTO promotion_daily_facts VALUES
                ('shop-1', '2026-09-20', 'catalog-1', 'product', 1, 2, 'batch-1'),
                ('shop-1', '2026-09-20', 'external-1', 'product', 3, 4, 'batch-1'),
                ('shop-1', '2026-09-20', '-998', 'product', 5, 6, NULL);
            INSERT INTO promotion_campaign_items VALUES
                ('shop-1', 'external-1', 'External Product', '', '2026-09-20');
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_classification_uses_catalog_and_edges_without_inserting_products(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        linked = classify_external_product(connection, shop_id="shop-1", external_product_id="catalog-1")
        external = classify_external_product(connection, shop_id="shop-1", external_product_id="external-1")
        negative = classify_external_product(connection, shop_id="shop-1", external_product_id="-998")
        connection.close()
        self.assertEqual(linked["identity_status"], "catalog_linked")
        self.assertEqual(external["identity_status"], "external_only")
        self.assertEqual(external["display_title"], "External Product")
        self.assertEqual(negative["identity_status"], "non_product_identifier")

    def test_preview_is_read_only_and_apply_creates_identity_rows(self):
        before = self.database.read_bytes()
        preview = build_report(self.database)
        self.assertEqual(preview["summary"]["row_count"], 3)
        self.assertEqual(self.database.read_bytes(), before)
        backup = Path(self.temp_dir.name) / "before-identity-map.db"
        applied = build_report(
            self.database,
            apply=True,
            backup_destination=backup,
        )
        self.assertEqual(applied["summary"]["applied_count"], 3)
        self.assertTrue(applied["backup"]["ok"])
        self.assertTrue(backup.is_file())
        connection = sqlite3.connect(self.database)
        rows = connection.execute("SELECT external_product_id, identity_status FROM product_identity_map ORDER BY external_product_id").fetchall()
        product_count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        connection.close()
        self.assertEqual(rows, [('-998', 'non_product_identifier'), ('catalog-1', 'catalog_linked'), ('external-1', 'external_only')])
        self.assertEqual(product_count, 1)

    def test_apply_without_backup_is_rejected_without_writing(self):
        before = self.database.read_bytes()
        report = build_report(self.database, apply=True)
        self.assertIn("backup_destination_required_for_apply", report["errors"])
        self.assertEqual(self.database.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

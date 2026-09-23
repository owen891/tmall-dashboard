import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.product_linkage_audit import build_report, main


class ProductLinkageAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-product-linkage-")
        self.database = Path(self.temp_dir.name) / "dashboard.db"
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE products (product_id TEXT PRIMARY KEY, title TEXT);
            CREATE TABLE daily_data (product_id TEXT, date TEXT);
            CREATE TABLE promotion_campaign_items (product_id TEXT, campaign_id TEXT);
            CREATE TABLE import_batches (id TEXT PRIMARY KEY, source_type TEXT, status TEXT, created_at TEXT);
            CREATE TABLE promotion_daily_facts (
                shop_id TEXT, date TEXT, channel TEXT, product_id TEXT,
                grain TEXT, ad_spend REAL, attributed_payment_amount REAL,
                source_batch_id TEXT
            );
            INSERT INTO products VALUES ('catalog-1', '商品');
            INSERT INTO daily_data VALUES ('backfill-1', '2026-09-20');
            INSERT INTO promotion_campaign_items VALUES ('backfill-1', 'campaign-1');
            INSERT INTO import_batches VALUES ('batch-1', 'promotion', 'completed', '2026-09-20');
            INSERT INTO promotion_daily_facts VALUES ('shop-1', '2026-09-20', 'x', 'catalog-1', 'product', 1, 2, 'batch-1');
            INSERT INTO promotion_daily_facts VALUES ('shop-1', '2026-09-20', 'x', 'backfill-1', 'product', 3, 4, 'batch-1');
            INSERT INTO promotion_daily_facts VALUES ('shop-1', '2026-09-20', 'x', '-998', 'product', 5, 6, NULL);
            INSERT INTO promotion_daily_facts VALUES ('shop-1', '2026-09-20', 'x', 'unresolved-1', 'product', 7, 8, NULL);
            INSERT INTO promotion_daily_facts VALUES ('shop-1', '2026-09-20', 'x', 'campaign-1', 'campaign', 9, 10, NULL);
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_classifies_missing_catalog_ids_without_mutating_database(self):
        before = self.database.read_bytes()
        report = build_report(self.database)
        self.assertEqual(report["summary"]["missing_product_count"], 3)
        self.assertEqual(report["summary"]["missing_fact_row_count"], 3)
        self.assertEqual(
            report["classifications"]["catalog_backfill_candidate"]["product_count"], 1
        )
        self.assertEqual(
            report["classifications"]["non_product_identifier"]["product_count"], 1
        )
        self.assertEqual(
            report["classifications"]["unresolved_product"]["product_count"], 1
        )
        self.assertEqual(self.database.read_bytes(), before)

    def test_cli_writes_json_report(self):
        output = Path(self.temp_dir.name) / "linkage.json"
        exit_code = main(["--database", str(self.database), "--output", str(output)])
        self.assertEqual(exit_code, 0)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["summary"]["missing_product_count"], 3)


if __name__ == "__main__":
    unittest.main()

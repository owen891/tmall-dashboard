import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.db_inventory import build_report, declared_tables, main


class DbInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-db-inventory-")
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "dashboard.db"
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE products (id INTEGER PRIMARY KEY, product_id TEXT);
            CREATE TABLE runtime_only (id INTEGER PRIMARY KEY, value TEXT);
            CREATE INDEX idx_runtime_only_value ON runtime_only(value);
            """
        )
        connection.commit()
        connection.close()
        self.schema = self.root / "db.py"
        self.schema.write_text(
            "CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY);",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_report_lists_schema_drift_and_columns(self):
        report = build_report(self.database, schema_source=self.schema)

        self.assertEqual(report["schema"]["table_count"], 2)
        self.assertEqual(report["schema"]["tables_not_declared_by_db_py"], ["runtime_only"])
        self.assertEqual(report["schema"]["declared_tables_missing_from_database"], [])
        runtime = next(
            item for item in report["schema"]["tables"] if item["name"] == "runtime_only"
        )
        self.assertEqual(runtime["row_count"], 0)
        self.assertEqual(runtime["indexes"][0]["name"], "idx_runtime_only_value")

    def test_skip_row_counts_keeps_inventory_read_only(self):
        before = self.database.read_bytes()
        report = build_report(
            self.database, schema_source=self.schema, include_row_counts=False
        )

        self.assertIsNone(report["schema"]["tables"][0]["row_count"])
        self.assertEqual(self.database.read_bytes(), before)

    def test_missing_database_is_reported(self):
        report = build_report(self.root / "missing.db", schema_source=self.schema)
        self.assertFalse(report["database"]["exists"])
        self.assertIn("database_not_found", report["errors"])

    def test_cli_writes_json_report(self):
        output = self.root / "inventory.json"
        exit_code = main(
            [
                "--database",
                str(self.database),
                "--schema-source",
                str(self.schema),
                "--output",
                str(output),
                "--skip-row-counts",
            ]
        )

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"]["table_count"], 2)

    def test_declared_tables_ignores_sql_comments(self):
        source = self.root / "schema.py"
        source.write_text(
            "# CREATE TABLE fake_table (id INTEGER)\n"
            "CREATE TABLE IF NOT EXISTS real_table (id INTEGER)\n",
            encoding="utf-8",
        )
        self.assertEqual(declared_tables(source), {"real_table"})


if __name__ == "__main__":
    unittest.main()

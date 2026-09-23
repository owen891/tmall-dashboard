import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.schema_baseline import build_baseline, main


class SchemaBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-schema-baseline-")
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "dashboard.db"
        self.schema = self.root / "db.py"
        self.schema.write_text(
            "CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY);",
            encoding="utf-8",
        )
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE products (id INTEGER PRIMARY KEY);
            CREATE TABLE sycm_flow_source_daily (id INTEGER PRIMARY KEY, stat_date TEXT);
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY, name TEXT, state TEXT, applied_at TEXT
            );
            INSERT INTO schema_migrations VALUES (1, 'baseline', 'applied', '2026-09-21');
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_runtime_table_is_classified_with_owner(self):
        report = build_baseline(self.database, schema_source=self.schema)
        runtime = next(
            table for table in report["tables"]
            if table["name"] == "sycm_flow_source_daily"
        )
        self.assertEqual(runtime["ownership"], "runtime")
        self.assertEqual(runtime["domain"], "source_facts")
        self.assertIn("sycm_flow", runtime["owner"])
        self.assertEqual(report["migrations"][0]["name"], "baseline")

    def test_baseline_is_read_only_and_cli_writes_report(self):
        before = self.database.read_bytes()
        output = self.root / "schema-baseline.json"
        self.assertEqual(main([
            "--database", str(self.database),
            "--schema-source", str(self.schema),
            "--output", str(output),
        ]), 0)
        self.assertEqual(self.database.read_bytes(), before)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["manifest_version"], 1)
        self.assertEqual(len(payload["tables"]), 3)


if __name__ == "__main__":
    unittest.main()

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_database import main, run


class AnalyzeDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-analyze-db-")
        self.database = Path(self.temp_dir.name) / "dashboard.db"
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE products (id INTEGER PRIMARY KEY, product_id TEXT);
            CREATE INDEX idx_products_product_id ON products(product_id);
            INSERT INTO products(product_id) VALUES ('p1'), ('p2');
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dry_run_does_not_mutate_database(self):
        before = self.database.read_bytes()
        report = run(self.database)
        self.assertEqual(report["errors"], [])
        self.assertFalse(report["after"]["has_sqlite_stat1"])
        self.assertEqual(self.database.read_bytes(), before)

    def test_apply_requires_backup(self):
        before = self.database.read_bytes()
        report = run(self.database, apply=True)
        self.assertIn("backup_destination_required_for_apply", report["errors"])
        self.assertEqual(self.database.read_bytes(), before)

    def test_apply_creates_statistics_and_backup(self):
        backup = Path(self.temp_dir.name) / "before-analyze.db"
        report = run(self.database, apply=True, backup_destination=backup)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["backup"]["ok"])
        self.assertTrue(backup.is_file())
        self.assertTrue(report["after"]["has_sqlite_stat1"])
        self.assertGreater(report["after"]["stat1_count"], 0)
        connection = sqlite3.connect(self.database)
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        connection.close()

    def test_cli_writes_report(self):
        output = Path(self.temp_dir.name) / "analyze.json"
        exit_code = main(
            ["--database", str(self.database), "--output", str(output)]
        )
        self.assertEqual(exit_code, 0)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(payload["apply"])


if __name__ == "__main__":
    unittest.main()

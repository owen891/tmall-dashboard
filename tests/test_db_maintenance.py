import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.db_maintenance import build_report, main


class DatabaseMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-maintenance-")
        self.database = Path(self.temp_dir.name) / "dashboard.db"
        conn = sqlite3.connect(self.database)
        conn.executescript(
            """
            CREATE TABLE daily_data_observations (
              id INTEGER PRIMARY KEY, shop_id TEXT, product_id TEXT, date TEXT,
              observed_at TEXT
            );
            CREATE INDEX idx_obs ON daily_data_observations(shop_id, product_id, date, observed_at DESC, id DESC);
            CREATE TABLE daily_data (shop_id TEXT, product_id TEXT, date TEXT);
            CREATE INDEX idx_daily ON daily_data(shop_id, date);
            CREATE TABLE collector_data_staging (published_at TEXT, status TEXT);
            INSERT INTO collector_data_staging VALUES ('2020-01-01', 'published');
            CREATE TABLE monthly_source_payload (month TEXT);
            INSERT INTO monthly_source_payload VALUES ('2020-01');
            """
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_report_is_read_only_and_has_candidates(self):
        before = self.database.read_bytes()
        report = build_report(self.database, {"collector_data_staging": 1})
        self.assertEqual(report["integrity_check"], "ok")
        self.assertEqual(report["tables"]["collector_data_staging"]["eligible_count"], 1)
        self.assertFalse(report["policy"]["mutations_performed"])
        self.assertEqual(self.database.read_bytes(), before)

    def test_cli_writes_json(self):
        output = Path(self.temp_dir.name) / "report.json"
        self.assertEqual(main(["--database", str(self.database), "--output", str(output)]), 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["manifest_version"], 1)


if __name__ == "__main__":
    unittest.main()

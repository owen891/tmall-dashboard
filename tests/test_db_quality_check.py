import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.db_quality_check import build_report, main


class DbQualityCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="tmall-db-quality-")
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "dashboard.db"
        self.schema = self.root / "db.py"
        self.schema.write_text(
            "\n".join(
                [
                    "CREATE TABLE daily_data (id INTEGER);",
                    "CREATE TABLE daily_data_observations (id INTEGER);",
                    "CREATE TABLE products (id INTEGER);",
                    "CREATE TABLE promotion_daily_facts (id INTEGER);",
                    "CREATE TABLE collector_runs (id INTEGER);",
                    "CREATE TABLE collector_artifacts (id INTEGER);",
                    "CREATE TABLE collector_data_staging (id INTEGER);",
                ]
            ),
            encoding="utf-8",
        )
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE products (product_id TEXT PRIMARY KEY);
            CREATE TABLE daily_data (
                shop_id TEXT, product_id TEXT, date TEXT,
                UNIQUE(shop_id, product_id, date)
            );
            CREATE TABLE daily_data_observations (
                shop_id TEXT, product_id TEXT, date TEXT
            );
            CREATE TABLE promotion_daily_facts (
                shop_id TEXT, grain TEXT, product_id TEXT,
                campaign_id TEXT, date TEXT, source_batch_id TEXT
            );
            CREATE TABLE collector_runs (
                id TEXT PRIMARY KEY, source_key TEXT, shop_id TEXT,
                status TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE collector_artifacts (
                id INTEGER PRIMARY KEY, run_id TEXT, path TEXT
            );
            CREATE TABLE collector_data_staging (
                id INTEGER PRIMARY KEY, status TEXT, created_at TEXT,
                published_at TEXT
            );
            INSERT INTO products VALUES ('p1');
            INSERT INTO daily_data VALUES ('shop-a', 'p1', '2026-09-19');
            INSERT INTO daily_data VALUES ('shop-a', 'p2', '2026-09-19');
            INSERT INTO daily_data_observations VALUES ('shop-a', 'p1', '2026-09-19');
            INSERT INTO promotion_daily_facts VALUES ('shop-a', 'product', 'p1', 'c1', '2026-09-19', NULL);
            INSERT INTO promotion_daily_facts VALUES ('shop-a', '', 'p2', 'c2', '2026-09-19', 'missing-batch');
            INSERT INTO collector_runs VALUES (
                'run-1', 'bi_daily', 'shop-a', 'running',
                '2026-01-01T00:00:00', '2026-01-01T00:00:00'
            );
            INSERT INTO collector_artifacts VALUES (1, 'run-1', 'missing/artifact.json');
            INSERT INTO collector_data_staging VALUES (
                1, 'published', '2026-01-01T00:00:00', NULL
            );
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_report_detects_orphans_grain_stale_run_and_artifact(self):
        report = build_report(
            self.database,
            schema_source=self.schema,
            staging_retention_days=14,
            stale_run_hours=2,
        )
        checks = {check["key"]: check for check in report["checks"]}

        self.assertEqual(report["summary"]["status"], "error")
        self.assertEqual(
            checks["provenance_and_orphans"]["metrics"][
                "daily_observations_without_daily_fact"
            ]["count"],
            0,
        )
        self.assertEqual(
            checks["provenance_and_orphans"]["metrics"]["promotion_facts_without_product"][
                "count"
            ],
            1,
        )
        self.assertEqual(
            checks["provenance_and_orphans"]["metrics"][
                "promotion_facts_without_import_batch"
            ]["row_count"],
            1,
        )
        self.assertEqual(checks["promotion_grain"]["metrics"]["blank_count"], 1)
        self.assertEqual(checks["collector_runs"]["metrics"]["stale_count"], 1)
        self.assertEqual(checks["collector_artifacts"]["metrics"]["missing_count"], 1)
        self.assertEqual(
            checks["staging_retention"]["metrics"]["published_without_timestamp"], 1
        )

    def test_report_is_read_only(self):
        before = self.database.read_bytes()
        build_report(self.database, schema_source=self.schema)
        self.assertEqual(self.database.read_bytes(), before)

    def test_registered_runtime_table_is_not_schema_drift(self):
        connection = sqlite3.connect(self.database)
        connection.execute(
            "CREATE TABLE sycm_flow_source_daily (id INTEGER PRIMARY KEY)"
        )
        connection.commit()
        connection.close()

        report = build_report(self.database, schema_source=self.schema)
        alignment = next(
            check for check in report["checks"] if check["key"] == "schema_alignment"
        )
        self.assertNotIn(
            "sycm_flow_source_daily",
            alignment["metrics"]["undeclared_tables"],
        )

    def test_identity_map_suppresses_resolved_promotion_linkage_warnings(self):
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE product_identity_map (
                shop_id TEXT, source_system TEXT, external_product_id TEXT,
                identity_status TEXT
            );
            INSERT INTO product_identity_map VALUES
                ('shop-a', 'promotion', 'p2', 'external_only');
            """
        )
        connection.commit()
        connection.close()
        report = build_report(self.database, schema_source=self.schema)
        provenance = next(
            check for check in report["checks"] if check["key"] == "provenance_and_orphans"
        )
        self.assertEqual(
            provenance["metrics"]["promotion_facts_without_product"]["by_identity_status"],
            [{"identity_status": "external_only", "row_count": 1}],
        )
        self.assertNotIn(
            "promotion_product_identity_unresolved",
            {issue["code"] for issue in provenance["issues"]},
        )

    def test_product_identity_statuses_do_not_retrigger_unresolved_warning(self):
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE product_identity_map (
                shop_id TEXT, source_system TEXT, external_product_id TEXT,
                identity_status TEXT
            );
            INSERT INTO product_identity_map VALUES
                ('shop-a', 'promotion', 'p2', 'external_only'),
                ('shop-a', 'promotion', '-9', 'non_product_identifier');
            INSERT INTO promotion_daily_facts VALUES
                ('shop-a', 'product', '-9', 'c3', '2026-09-19', NULL);
            """
        )
        connection.commit()
        connection.close()
        report = build_report(self.database, schema_source=self.schema)
        provenance = next(check for check in report['checks'] if check['key'] == 'provenance_and_orphans')
        self.assertNotIn(
            'promotion_product_identity_unresolved',
            {issue['code'] for issue in provenance['issues']},
        )

    def test_action_history_orphans_are_reported_without_mutation(self):
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE product_actions (id TEXT PRIMARY KEY);
            CREATE TABLE product_action_history (
                id INTEGER PRIMARY KEY, action_id TEXT, from_status TEXT,
                to_status TEXT, detail TEXT, operator TEXT, version INTEGER,
                created_at TEXT
            );
            INSERT INTO product_actions VALUES ('valid-action');
            INSERT INTO product_action_history VALUES
                (1, 'valid-action', NULL, 'draft', 'created', 'test', 1, '2026-09-28');
            INSERT INTO product_action_history VALUES
                (2, 'missing-action', 'draft', 'blocked', 'legacy', 'test', 2, '2026-09-29');
            """
        )
        connection.commit()
        connection.close()
        before = self.database.read_bytes()
        report = build_report(self.database, schema_source=self.schema)
        check = next(item for item in report['checks'] if item['key'] == 'action_history_orphans')
        self.assertEqual(check['status'], 'error')
        self.assertEqual(check['metrics']['history_count'], 2)
        self.assertEqual(check['metrics']['parent_count'], 1)
        self.assertEqual(check['metrics']['orphan_count'], 1)
        self.assertEqual(check['issues'][0]['code'], 'orphan_action_history')
        self.assertEqual(check['issues'][0]['history_id'], 2)
        self.assertFalse(check['issues'][0]['parent_exists'])
        self.assertEqual(self.database.read_bytes(), before)

        connection = sqlite3.connect(self.database)
        connection.execute(
            "INSERT INTO daily_data VALUES ('shop-a', 'p3', '2026-09-22')"
        )
        connection.commit()
        connection.close()

        report = build_report(
            self.database,
            schema_source=self.schema,
            as_of_date="2026-09-21",
        )
        future = next(check for check in report["checks"] if check["key"] == "future_facts")
        self.assertEqual(future["status"], "error")
        daily = next(
            item for item in future["metrics"]["tables"]
            if item["table"] == "daily_data"
        )
        self.assertEqual(
            daily["future_count"],
            1,
        )
        self.assertIn(
            "future_operational_fact",
            {issue["code"] for issue in future["issues"]},
        )

    def test_future_fact_check_supports_monthly_cutoff(self):
        connection = sqlite3.connect(self.database)
        connection.execute("CREATE TABLE monthly_data (month TEXT)")
        connection.execute("INSERT INTO monthly_data VALUES ('2026-10')")
        connection.commit()
        connection.close()

        report = build_report(
            self.database,
            schema_source=self.schema,
            as_of_date="2026-09-21",
        )
        future = next(check for check in report["checks"] if check["key"] == "future_facts")
        monthly = next(item for item in future["metrics"]["tables"] if item["table"] == "monthly_data")
        self.assertEqual(monthly["future_count"], 1)

    def test_cli_writes_report_and_strict_fails_on_warnings(self):
        output = self.root / "quality.json"
        exit_code = main(
            [
                "--database",
                str(self.database),
                "--schema-source",
                str(self.schema),
                "--output",
                str(output),
                "--strict",
            ]
        )

        self.assertEqual(exit_code, 1)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["summary"]["status"], "error")
        self.assertGreater(payload["summary"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()

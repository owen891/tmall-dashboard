"""Read-only database growth report with explicit, safe retention previews.

The command never deletes rows and never runs VACUUM.  It reports the rows
that *would* be eligible for a future archive, plus integrity and index-plan
signals, so an operator can review a manifest before any destructive change.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta, timezone, datetime
from pathlib import Path


DEFAULT_TABLES = {
    "collector_data_staging": ("published_at", 14),
    "collector_artifacts": ("created_at", 30),
    "collector_checkpoints": ("updated_at", 30),
    "monthly_source_payload": ("month", 180),
    "bi_product_daily_raw": ("date", 180),
}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _cutoff(column: str, days: int) -> str:
    if column == "month":
        return (date.today().replace(day=1) - timedelta(days=days)).isoformat()[:7]
    return (date.today() - timedelta(days=days)).isoformat()


def build_report(database: str | Path, retention_days: dict[str, int] | None = None) -> dict:
    path = Path(database).resolve()
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = {}
        retention_days = retention_days or {}
        configured = {}
        if _table_exists(conn, "retention_policies"):
            for row in conn.execute(
                "SELECT source_table, retention_days, mode, protected "
                "FROM retention_policies"
            ):
                configured[row[0]] = {
                    "retention_days": int(row[1]),
                    "mode": row[2],
                    "protected": bool(row[3]),
                }
        table_specs = {}
        for table, (column, default_days) in DEFAULT_TABLES.items():
            policy = configured.get(table, {})
            table_specs[table] = (
                column,
                int(retention_days.get(
                    table, policy.get("retention_days", default_days)
                )),
                policy,
            )
        for table, (column, default_days, policy) in table_specs.items():
            item = {"exists": _table_exists(conn, table), "table": table,
                    "column": column, "retention_days": default_days,
                    "mode": policy.get("mode", "archive"),
                    "protected": policy.get("protected", False),
                    "policy_source": "database" if table in configured else "default"}
            if not item["exists"]:
                tables[table] = item
                continue
            cutoff = _cutoff(column, item["retention_days"])
            item["cutoff"] = cutoff
            item["row_count"] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            item["eligible_count"] = conn.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" < ?', (cutoff,)
            ).fetchone()[0]
            item["min_value"], item["max_value"] = conn.execute(
                f'SELECT MIN("{column}"), MAX("{column}") FROM "{table}"'
            ).fetchone()
            tables[table] = item

        archive_catalog = {"exists": _table_exists(conn, "archive_catalog")}
        if archive_catalog["exists"]:
            archive_catalog["row_count"] = conn.execute(
                "SELECT COUNT(*) FROM archive_catalog"
            ).fetchone()[0]
            archive_catalog["verified_count"] = conn.execute(
                "SELECT COUNT(*) FROM archive_catalog WHERE status = 'verified'"
            ).fetchone()[0]

        plans = {
            "daily_observation_latest": conn.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM daily_data_observations "
                "WHERE shop_id=? AND product_id=? AND date=? "
                "ORDER BY observed_at DESC, id DESC LIMIT 1",
                ("default", "__probe__", "1970-01-01"),
            ).fetchall() if _table_exists(conn, "daily_data_observations") else [],
            "daily_scope_date": conn.execute(
                "EXPLAIN QUERY PLAN SELECT product_id FROM daily_data "
                "WHERE shop_id=? AND date BETWEEN ? AND ?",
                ("default", "1970-01-01", "1970-01-02"),
            ).fetchall() if _table_exists(conn, "daily_data") else [],
        }
        return {
            "manifest_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": str(path),
            "dry_run": True,
            "integrity_check": conn.execute("PRAGMA quick_check").fetchone()[0],
            "tables": tables,
            "archive_catalog": archive_catalog,
            "query_plans": {
                key: [row[3] for row in rows] for key, rows in plans.items()
            },
            "policy": {
                "mutations_performed": False,
                "protected_tables": ["daily_data_observations", "fact_field_lineage"],
                "vacuum_performed": False,
                "delete_performed": False,
            },
        }
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create a read-only SQLite growth report")
    parser.add_argument("--database", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = build_report(args.database)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

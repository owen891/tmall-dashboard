"""Preview or apply product identity rows derived from promotion facts.

Default mode is read-only. Use ``--apply`` only after reviewing the JSON
report. The script never inserts placeholder rows into ``products``.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Iterable

try:
    from scripts.db_inventory import DEFAULT_DATABASE, connect_readonly
    from services.product_identity_service import classify_external_product, upsert_identity_rows
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.db_inventory import DEFAULT_DATABASE, connect_readonly  # type: ignore
    from services.product_identity_service import classify_external_product, upsert_identity_rows  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _writeable_connection(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def build_rows(connection: sqlite3.Connection) -> list[dict]:
    shop_rows = connection.execute(
        """SELECT COALESCE(shop_id, 'default') AS shop_id, product_id,
                  COUNT(*) AS fact_row_count, MIN(date) AS first_seen_date,
                  MAX(date) AS last_seen_date, SUM(COALESCE(ad_spend, 0)) AS ad_spend,
                  SUM(COALESCE(attributed_payment_amount, 0)) AS attributed_payment_amount,
                  MIN(NULLIF(source_batch_id, '')) AS first_source_batch_id,
                  MAX(NULLIF(source_batch_id, '')) AS last_source_batch_id
           FROM promotion_daily_facts
           WHERE grain = 'product' AND NULLIF(TRIM(product_id), '') IS NOT NULL
           GROUP BY COALESCE(shop_id, 'default'), product_id
           ORDER BY shop_id, product_id"""
    ).fetchall()
    rows = []
    for fact in shop_rows:
        resolution = classify_external_product(
            connection,
            shop_id=fact["shop_id"],
            external_product_id=fact["product_id"],
        )
        rows.append({
            "shop_id": fact["shop_id"],
            "source_system": "promotion",
            "external_product_id": fact["product_id"],
            **resolution,
            "first_seen_date": fact["first_seen_date"],
            "last_seen_date": fact["last_seen_date"],
            "fact_row_count": int(fact["fact_row_count"] or 0),
            "ad_spend": float(fact["ad_spend"] or 0),
            "attributed_payment_amount": float(fact["attributed_payment_amount"] or 0),
            "first_source_batch_id": fact["first_source_batch_id"],
            "last_source_batch_id": fact["last_source_batch_id"],
        })
    return rows


def build_report(
    database_path: str | os.PathLike[str],
    *,
    apply: bool = False,
    backup_destination: str | os.PathLike[str] | None = None,
) -> dict:
    database = Path(database_path).resolve()
    report = {
        "database": str(database),
        "apply": apply,
        "backup": None,
        "errors": [],
        "summary": {},
        "rows": [],
    }
    if not database.is_file():
        report["errors"].append("database_not_found")
        return report
    if apply and not backup_destination:
        report["errors"].append("backup_destination_required_for_apply")
        return report
    try:
        if apply:
            from scripts.backup_database import backup_database

            report["backup"] = backup_database(database, backup_destination)
            if not report["backup"]["ok"]:
                report["errors"].append("database_backup_integrity_failed")
                return report
        if apply:
            with closing(_writeable_connection(database)) as connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS product_identity_map (
                    shop_id TEXT NOT NULL DEFAULT 'default', source_system TEXT NOT NULL,
                    external_product_id TEXT NOT NULL, canonical_product_id TEXT,
                    identity_status TEXT NOT NULL DEFAULT 'unresolved', display_title TEXT NOT NULL DEFAULT '',
                    image_url TEXT NOT NULL DEFAULT '', first_seen_date DATE, last_seen_date DATE,
                    fact_row_count INTEGER NOT NULL DEFAULT 0, ad_spend REAL NOT NULL DEFAULT 0,
                    attributed_payment_amount REAL NOT NULL DEFAULT 0, first_source_batch_id TEXT,
                    last_source_batch_id TEXT, resolution_reason TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (shop_id, source_system, external_product_id),
                    FOREIGN KEY (canonical_product_id) REFERENCES products(product_id)
                )""")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_product_identity_status ON product_identity_map(shop_id, identity_status)")
                rows = build_rows(connection)
                upsert_identity_rows(connection, rows)
                connection.commit()
        else:
            with closing(connect_readonly(database)) as connection:
                rows = build_rows(connection)
        report["rows"] = rows
        counts = Counter(row["identity_status"] for row in rows)
        report["summary"] = {
            "row_count": len(rows),
            "fact_row_count": sum(row["fact_row_count"] for row in rows),
            "by_status": dict(sorted(counts.items())),
            "applied_count": len(rows) if apply else 0,
        }
    except sqlite3.Error as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill product identity map")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--output", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--backup-destination",
        default=None,
        help="Required with --apply: destination for an integrity-checked SQLite backup",
    )
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error("--backup-destination is required with --apply")
    report = build_report(
        args.database,
        apply=args.apply,
        backup_destination=args.backup_destination,
    )
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": report["summary"], "errors": report["errors"]}, ensure_ascii=False))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

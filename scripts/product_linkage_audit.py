"""Read-only audit for product-grain promotion facts without catalog rows.

The promotion tables contain historical and external identifiers that are not
always present in ``products``.  This audit keeps those facts intact and
classifies the missing identifiers using evidence from other local sources.
It never opens the database in write mode.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    from scripts.db_inventory import (
        DEFAULT_DATABASE,
        connect_readonly,
        quote_identifier,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from db_inventory import DEFAULT_DATABASE, connect_readonly, quote_identifier  # type: ignore


PRODUCT_SOURCES = (
    "products",
    "daily_data",
    "bi_product_daily_raw",
    "keyword_promotion_products",
    "promotion_campaign_items",
    "promotion_creatives",
    "promotion_creative_daily",
)


def _has_table(connection: sqlite3.Connection, table: str) -> bool:
    return bool(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
    )


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    if not _has_table(connection, table):
        return set()
    return {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({quote_identifier(table)})")
    }


def _count_distinct(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    product_id: str,
) -> int:
    if column not in _columns(connection, table):
        return 0
    return int(
        connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table)} "
            f"WHERE CAST({quote_identifier(column)} AS TEXT) = ?",
            (product_id,),
        ).fetchone()[0]
    )


def _source_evidence(
    connection: sqlite3.Connection,
    product_id: str,
) -> dict[str, int]:
    evidence = {}
    for table in PRODUCT_SOURCES:
        if not _has_table(connection, table):
            continue
        column = "product_id" if "product_id" in _columns(connection, table) else None
        evidence[table] = _count_distinct(connection, table, column, product_id) if column else 0
    return evidence


def _classify(
    product_id: str,
    shop_id: str,
    evidence: dict[str, int],
) -> tuple[str, str]:
    if re.fullmatch(r"-[0-9]+", product_id):
        return "non_product_identifier", "negative identifier used by external report"
    if product_id == shop_id:
        return "possible_shop_identifier", "identifier equals the active shop scope"
    if evidence.get("products", 0):
        return "catalog_linked", "catalog row exists"
    if any(
        evidence.get(table, 0)
        for table in (
            "daily_data",
            "bi_product_daily_raw",
            "keyword_promotion_products",
            "promotion_campaign_items",
            "promotion_creatives",
            "promotion_creative_daily",
        )
    ):
        return "catalog_backfill_candidate", "identifier exists in another local product source"
    return "unresolved_product", "no local product evidence found"


def _batch_evidence(connection: sqlite3.Connection, batch_ids: list[str]) -> list[dict]:
    if not batch_ids or not _has_table(connection, "import_batches"):
        return []
    columns = _columns(connection, "import_batches")
    if "id" not in columns:
        return []
    placeholders = ",".join("?" for _ in batch_ids)
    select_columns = [
        column
        for column in (
            "id",
            "shop_id",
            "source_type",
            "source_filename",
            "status",
            "created_at",
            "completed_at",
        )
        if column in columns
    ]
    rows = connection.execute(
        f"SELECT {', '.join(quote_identifier(column) for column in select_columns)} "
        f"FROM import_batches WHERE id IN ({placeholders}) ORDER BY created_at",
        batch_ids,
    ).fetchall()
    return [dict(row) for row in rows]


def build_report(database_path: str | os.PathLike[str]) -> dict:
    """Build a read-only product linkage report."""
    database = Path(database_path).resolve()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(database),
        "errors": [],
        "scope": {
            "fact_table": "promotion_daily_facts",
            "grain": "product",
            "catalog_table": "products",
        },
        "summary": {},
        "classifications": {},
        "rows": [],
    }
    if not database.is_file():
        report["errors"].append("database_not_found")
        return report

    try:
        with closing(connect_readonly(database)) as connection:
            if not _has_table(connection, "promotion_daily_facts"):
                report["errors"].append("promotion_daily_facts_not_found")
                return report

            columns = _columns(connection, "promotion_daily_facts")
            required = {"product_id", "grain"}
            if not required.issubset(columns):
                report["errors"].append("promotion_product_columns_not_found")
                return report

            shop_id = "default"
            if "shop_id" in columns:
                row = connection.execute(
                    """SELECT COALESCE(shop_id, 'default')
                       FROM promotion_daily_facts
                       WHERE grain = 'product' AND NULLIF(TRIM(product_id), '') IS NOT NULL
                       GROUP BY COALESCE(shop_id, 'default')
                       ORDER BY COUNT(*) DESC LIMIT 1"""
                ).fetchone()
                if row:
                    shop_id = str(row[0])

            optional = {
                name
                for name in (
                    "shop_id",
                    "date",
                    "channel",
                    "source_batch_id",
                    "ad_spend",
                    "attributed_payment_amount",
                )
                if name in columns
            }
            select_columns = ["product_id", *sorted(optional)]
            rows = connection.execute(
                f"""SELECT {', '.join(quote_identifier(column) for column in select_columns)},
                           COUNT(*) AS row_count,
                           COUNT(DISTINCT date) AS date_count,
                           MIN(date) AS first_date,
                           MAX(date) AS last_date,
                           SUM(COALESCE(ad_spend, 0)) AS ad_spend,
                           SUM(COALESCE(attributed_payment_amount, 0)) AS attributed_payment_amount
                    FROM promotion_daily_facts
                    WHERE grain = 'product'
                      AND NULLIF(TRIM(product_id), '') IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM products p
                          WHERE p.product_id = promotion_daily_facts.product_id
                      )
                    GROUP BY product_id"""
            ).fetchall()

            classifications = Counter()
            classification_rows = Counter()
            batch_ids: set[str] = set()
            for row in rows:
                product_id = str(row["product_id"])
                evidence = _source_evidence(connection, product_id)
                classification, reason = _classify(product_id, shop_id, evidence)
                classifications[classification] += 1
                classification_rows[classification] += int(row["row_count"] or 0)
                batch_id = row["source_batch_id"] if "source_batch_id" in row.keys() else None
                if batch_id:
                    batch_ids.add(str(batch_id))
                report["rows"].append(
                    {
                        "product_id": product_id,
                        "classification": classification,
                        "reason": reason,
                        "row_count": int(row["row_count"] or 0),
                        "date_count": int(row["date_count"] or 0),
                        "first_date": row["first_date"],
                        "last_date": row["last_date"],
                        "ad_spend": float(row["ad_spend"] or 0),
                        "attributed_payment_amount": float(
                            row["attributed_payment_amount"] or 0
                        ),
                        "source_batch_ids": sorted(
                            {
                                str(item[0])
                                for item in connection.execute(
                                    """SELECT DISTINCT source_batch_id
                                       FROM promotion_daily_facts
                                       WHERE grain = 'product' AND product_id = ?
                                         AND NULLIF(TRIM(source_batch_id), '') IS NOT NULL""",
                                    (product_id,),
                                ).fetchall()
                            }
                        )
                        if "source_batch_id" in columns
                        else [],
                        "source_evidence": evidence,
                    }
                )

            report["rows"].sort(
                key=lambda item: (-item["row_count"], item["classification"], item["product_id"])
            )
            report["summary"] = {
                "missing_product_count": len(report["rows"]),
                "missing_fact_row_count": sum(item["row_count"] for item in report["rows"]),
                "missing_ad_spend": round(sum(item["ad_spend"] for item in report["rows"]), 2),
                "missing_attributed_payment_amount": round(
                    sum(item["attributed_payment_amount"] for item in report["rows"]), 2
                ),
                "active_shop_id": shop_id,
                "source_batch_ids_without_import_record": [],
            }
            report["classifications"] = {
                name: {
                    "product_count": classifications[name],
                    "fact_row_count": classification_rows[name],
                }
                for name in sorted(classifications)
            }
            batch_rows = _batch_evidence(connection, sorted(batch_ids))
            known_batch_ids = {str(row.get("id")) for row in batch_rows if row.get("id") is not None}
            report["summary"]["source_batch_ids_without_import_record"] = sorted(
                batch_ids - known_batch_ids
            )
            report["import_batches"] = batch_rows
    except sqlite3.Error as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit product linkage for promotion facts")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args(argv)
    report = build_report(args.database)
    output = None
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "database": report["database"],
                "summary": report.get("summary", {}),
                "classifications": report.get("classifications", {}),
                "output": str(output) if output else None,
                "errors": report["errors"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

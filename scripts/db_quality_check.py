"""Read-only cross-domain quality checks for the dashboard SQLite database."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    from scripts.db_inventory import (
        DEFAULT_DATABASE,
        DEFAULT_SCHEMA_SOURCE,
        connect_readonly,
        declared_tables,
        quote_identifier,
    )
except ModuleNotFoundError:
    # Support both ``python -m scripts.db_quality_check`` and direct
    # execution from the repository root.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from db_inventory import (  # type: ignore
        DEFAULT_DATABASE,
        DEFAULT_SCHEMA_SOURCE,
        connect_readonly,
        declared_tables,
        quote_identifier,
    )

try:
    from scripts.schema_baseline import RUNTIME_TABLES
except ModuleNotFoundError:
    from schema_baseline import RUNTIME_TABLES  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def _result(key: str, status: str, metrics: dict | None = None, issues: list | None = None) -> dict:
    return {
        "key": key,
        "status": status,
        "metrics": metrics or {},
        "issues": issues or [],
    }


def _status_for_issues(issues: list[dict], *, warning_is_bad: bool = False) -> str:
    if any(issue.get("severity") == "error" for issue in issues):
        return "error"
    if issues:
        return "warning" if warning_is_bad else "ok"
    return "ok"


def check_integrity(connection: sqlite3.Connection) -> dict:
    value = connection.execute("PRAGMA quick_check").fetchone()[0]
    issues = [] if value == "ok" else [
        {"severity": "error", "code": "quick_check_failed", "value": value}
    ]
    return _result("integrity", "error" if issues else "ok", {"quick_check": value}, issues)


def check_schema_alignment(
    connection: sqlite3.Connection,
    schema_source: str | os.PathLike[str] | None = None,
) -> dict:
    actual = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    declared = declared_tables(schema_source or DEFAULT_SCHEMA_SOURCE)
    declared |= set(RUNTIME_TABLES)
    undeclared = sorted(actual - declared)
    missing = sorted(declared - actual)
    issues = []
    if undeclared:
        issues.append(
            {
                "severity": "warning",
                "code": "runtime_tables_not_declared",
                "tables": undeclared,
            }
        )
    if missing:
        issues.append(
            {
                "severity": "error",
                "code": "declared_tables_missing",
                "tables": missing,
            }
        )
    return _result(
        "schema_alignment",
        "error" if any(item["severity"] == "error" for item in issues) else (
            "warning" if issues else "ok"
        ),
        {
            "actual_table_count": len(actual),
            "declared_table_count": len(declared),
            "undeclared_tables": undeclared,
            "missing_declared_tables": missing,
        },
        issues,
    )


def _duplicate_groups(
    connection: sqlite3.Connection,
    table: str,
    keys: tuple[tuple[str, ...], ...],
) -> tuple[int, tuple[str, ...] | None]:
    if not _has_table(connection, table):
        return 0, None
    available = _columns(connection, table)
    key = next((candidate for candidate in keys if set(candidate).issubset(available)), None)
    if key is None:
        return 0, None
    group = ", ".join(quote_identifier(column) for column in key)
    count = connection.execute(
        f"""SELECT COUNT(*) FROM (
                SELECT {group}
                FROM {quote_identifier(table)}
                GROUP BY {group}
                HAVING COUNT(*) > 1
            )"""
    ).fetchone()[0]
    return count, key


def check_duplicates(connection: sqlite3.Connection) -> dict:
    checks = {
        "daily_data": ("daily_data", (("shop_id", "product_id", "date"),)),
        "monthly_data": (
            "monthly_data",
            (("shop_id", "product_id", "month"), ("product_id", "month")),
        ),
        "store_daily_facts": ("store_daily_facts", (("shop_id", "date"),)),
        "promotion_daily_facts": (
            "promotion_daily_facts",
            (("shop_id", "date", "channel", "campaign_id", "unit_id", "product_id"),
             ("shop_id", "date", "channel", "campaign_id", "product_id")),
        ),
    }
    metrics = {}
    issues = []
    for label, (table, keys) in checks.items():
        count, key = _duplicate_groups(connection, table, keys)
        metrics[label] = {
            "duplicate_groups": count,
            "key": list(key) if key else None,
        }
        if count:
            issues.append(
                {
                    "severity": "error",
                    "code": "duplicate_business_key",
                    "table": table,
                    "key": list(key or ()),
                    "count": count,
                }
            )
    return _result("duplicate_business_keys", "error" if issues else "ok", metrics, issues)


def _orphan_count(
    connection: sqlite3.Connection,
    child_table: str,
    parent_table: str,
    key_columns: tuple[str, ...],
) -> int | None:
    if not _has_table(connection, child_table) or not _has_table(connection, parent_table):
        return None
    if not set(key_columns).issubset(_columns(connection, child_table)):
        return None
    if not set(key_columns).issubset(_columns(connection, parent_table)):
        return None
    predicates = " AND ".join(
        f"child.{quote_identifier(column)} = parent.{quote_identifier(column)}"
        for column in key_columns
    )
    return connection.execute(
        f"""SELECT COUNT(*)
            FROM {quote_identifier(child_table)} child
            WHERE NOT EXISTS (
                SELECT 1
                FROM {quote_identifier(parent_table)} parent
                WHERE {predicates}
            )"""
    ).fetchone()[0]


def _daily_observation_orphan_metrics(connection: sqlite3.Connection) -> dict:
    if not _has_table(connection, "daily_data_observations"):
        return {
            "count": None,
            "unregistered_batch_count": None,
            "completed_batch_count": None,
        }
    has_fact = _has_table(connection, "daily_data")
    if not has_fact:
        return {
            "count": None,
            "unregistered_batch_count": None,
            "completed_batch_count": None,
        }
    observation_columns = _columns(connection, "daily_data_observations")
    fact_columns = _columns(connection, "daily_data")
    required_observation = {"shop_id", "product_id", "date"}
    required_fact = {"shop_id", "product_id", "date"}
    if not required_observation.issubset(observation_columns) or not required_fact.issubset(fact_columns):
        return {
            "count": None,
            "unregistered_batch_count": None,
            "completed_batch_count": None,
        }
    orphan_predicate = """NOT EXISTS (
        SELECT 1 FROM daily_data d
        WHERE d.shop_id = o.shop_id
          AND d.product_id = o.product_id
          AND d.date = o.date
    )"""
    base_count = connection.execute(
        f"SELECT COUNT(*) FROM daily_data_observations o WHERE {orphan_predicate}"
    ).fetchone()[0]
    if "source_batch_id" not in observation_columns:
        return {
            "count": base_count,
            "unregistered_batch_count": None,
            "completed_batch_count": None,
        }
    batch_join = ""
    batch_columns = "NULL AS batch_status"
    if _has_table(connection, "import_batches"):
        batch_join = "LEFT JOIN import_batches b ON b.id = o.source_batch_id"
        batch_columns = "b.status AS batch_status"
    rows = connection.execute(
        f"""SELECT o.source_batch_id, {batch_columns}
            FROM daily_data_observations o
            {batch_join}
            WHERE {orphan_predicate}"""
    ).fetchall()
    unregistered = 0
    completed = 0
    for row in rows:
        status = row[1]
        if not row[0] or status is None:
            unregistered += 1
        elif status in {"completed", "succeeded", "published"}:
            completed += 1
    return {
        "count": len(rows),
        "unregistered_batch_count": unregistered,
        "completed_batch_count": completed,
    }


def _promotion_product_linkage_metrics(connection: sqlite3.Connection) -> dict:
    table = "promotion_daily_facts"
    if not _has_table(connection, table) or not _has_table(connection, "products"):
        return {
            "count": None,
            "by_grain": [],
            "by_classification": [],
            "by_identity_status": [],
        }
    rows = connection.execute(
        f"""SELECT COALESCE(p.grain, '') AS grain, COUNT(*) AS row_count,
                   COUNT(DISTINCT p.product_id) AS product_count
            FROM {quote_identifier(table)} p
            WHERE NULLIF(TRIM(p.product_id), '') IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM products x WHERE x.product_id = p.product_id
              )
            GROUP BY COALESCE(p.grain, '')
            ORDER BY row_count DESC"""
    ).fetchall()
    metrics = {
        "count": sum(row[1] for row in rows),
        "by_grain": [
            {"grain": row[0], "row_count": row[1], "product_count": row[2]}
            for row in rows
        ],
    }
    product_rows = connection.execute(
        f"""SELECT COALESCE(p.shop_id, 'default') AS shop_id,
                   p.product_id, COUNT(*) AS row_count
            FROM {quote_identifier(table)} p
            WHERE COALESCE(p.grain, '') = 'product'
              AND NULLIF(TRIM(p.product_id), '') IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM products x WHERE x.product_id = p.product_id
              )
            GROUP BY COALESCE(p.shop_id, 'default'), p.product_id"""
    ).fetchall()
    identity_rows = connection.execute(
        f"""SELECT COALESCE(p.shop_id, 'default') AS shop_id,
                   p.product_id, COUNT(*) AS row_count
            FROM {quote_identifier(table)} p
            WHERE NULLIF(TRIM(p.product_id), '') IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM products x WHERE x.product_id = p.product_id
              )
            GROUP BY COALESCE(p.shop_id, 'default'), p.product_id"""
    ).fetchall()
    classifications = {
        "negative_identifier": {"product_count": 0, "row_count": 0},
        "shop_identifier": {"product_count": 0, "row_count": 0},
        "catalog_backfill_candidate": {"product_count": 0, "row_count": 0},
        "unresolved_product": {"product_count": 0, "row_count": 0},
    }
    source_tables = (
        "daily_data",
        "bi_product_daily_raw",
        "keyword_promotion_products",
        "promotion_campaign_items",
        "promotion_creatives",
        "promotion_creative_daily",
    )
    source_columns = {
        source: "product_id" in _columns(connection, source)
        for source in source_tables
        if _has_table(connection, source)
    }
    shop_ids = {
        str(row[0])
        for row in connection.execute(
            f"""SELECT DISTINCT shop_id FROM {quote_identifier(table)}
                WHERE NULLIF(TRIM(shop_id), '') IS NOT NULL"""
        ).fetchall()
    } if "shop_id" in _columns(connection, table) else set()
    has_identity_map = _has_table(connection, "product_identity_map")
    identity_status_counts = {}
    for row in identity_rows:
        shop_id = str(row[0])
        product_id = str(row[1])
        mapped_status = None
        if has_identity_map:
            mapped = connection.execute(
                """SELECT identity_status FROM product_identity_map
                   WHERE shop_id = ? AND source_system = 'promotion'
                     AND external_product_id = ?""",
                (shop_id, product_id),
            ).fetchone()
            mapped_status = mapped[0] if mapped else None
        if mapped_status:
            identity_status_counts[mapped_status] = identity_status_counts.get(mapped_status, 0) + int(row[2] or 0)

    for row in product_rows:
        shop_id = str(row[0])
        product_id = str(row[1])
        mapped_status = None
        if has_identity_map:
            mapped = connection.execute(
                """SELECT identity_status FROM product_identity_map
                   WHERE shop_id = ? AND source_system = 'promotion'
                     AND external_product_id = ?""",
                (shop_id, product_id),
            ).fetchone()
            mapped_status = mapped[0] if mapped else None
        if mapped_status == "external_only":
            classification = "catalog_backfill_candidate"
        elif mapped_status == "non_product_identifier":
            classification = "negative_identifier"
        elif mapped_status == "shop_identifier":
            classification = "shop_identifier"
        elif mapped_status == "unresolved":
            classification = "unresolved_product"
        elif product_id.startswith("-") and product_id[1:].isdigit():
            classification = "negative_identifier"
        elif product_id in shop_ids:
            classification = "shop_identifier"
        else:
            has_source = any(
                connection.execute(
                    f"SELECT 1 FROM {quote_identifier(source)} "
                    "WHERE CAST(product_id AS TEXT) = ? LIMIT 1",
                    (product_id,),
                ).fetchone()
                for source, available in source_columns.items()
                if available
            )
            classification = "catalog_backfill_candidate" if has_source else "unresolved_product"
        classifications[classification]["product_count"] += 1
        classifications[classification]["row_count"] += int(row[2] or 0)
    metrics["by_classification"] = [
        {"classification": key, **value}
        for key, value in classifications.items()
        if value["product_count"]
    ]
    metrics["by_identity_status"] = [
        {"identity_status": key, "row_count": value}
        for key, value in sorted(identity_status_counts.items())
    ]
    return metrics


def _promotion_unregistered_batch_metrics(connection: sqlite3.Connection) -> dict:
    table = "promotion_daily_facts"
    if not _has_table(connection, table) or "source_batch_id" not in _columns(connection, table):
        return {
            "row_count": None,
            "batch_count": None,
            "legacy_migration_row_count": None,
            "legacy_migration_batch_count": None,
            "by_grain": [],
        }
    if not _has_table(connection, "import_batches"):
        row = connection.execute(
            f"""SELECT COUNT(*), COUNT(DISTINCT source_batch_id)
                FROM {quote_identifier(table)}
                WHERE NULLIF(TRIM(source_batch_id), '') IS NOT NULL
                  AND source_batch_id NOT LIKE 'daily_data_migration_%'"""
        ).fetchone()
        legacy = connection.execute(
            f"""SELECT COUNT(*), COUNT(DISTINCT source_batch_id)
                FROM {quote_identifier(table)}
                WHERE source_batch_id LIKE 'daily_data_migration_%'"""
        ).fetchone()
        return {
            "row_count": int(row[0] or 0),
            "batch_count": int(row[1] or 0),
            "legacy_migration_row_count": int(legacy[0] or 0),
            "legacy_migration_batch_count": int(legacy[1] or 0),
            "by_grain": [],
        }
    rows = connection.execute(
        f"""SELECT COALESCE(p.grain, '') AS grain, COUNT(*) AS row_count,
                   COUNT(DISTINCT p.source_batch_id) AS batch_count
            FROM {quote_identifier(table)} p
            WHERE NULLIF(TRIM(p.source_batch_id), '') IS NOT NULL
              AND p.source_batch_id NOT LIKE 'daily_data_migration_%'
              AND NOT EXISTS (
                  SELECT 1 FROM import_batches b WHERE b.id = p.source_batch_id
              )
            GROUP BY COALESCE(p.grain, '')
            ORDER BY row_count DESC"""
    ).fetchall()
    return {
        "row_count": sum(int(row[1]) for row in rows),
        "batch_count": sum(int(row[2]) for row in rows),
        "legacy_migration_row_count": int(connection.execute(
            f"""SELECT COUNT(*) FROM {quote_identifier(table)}
                WHERE source_batch_id LIKE 'daily_data_migration_%'"""
        ).fetchone()[0] or 0),
        "legacy_migration_batch_count": int(connection.execute(
            f"""SELECT COUNT(DISTINCT source_batch_id) FROM {quote_identifier(table)}
                WHERE source_batch_id LIKE 'daily_data_migration_%'"""
        ).fetchone()[0] or 0),
        "by_grain": [
            {"grain": row[0], "row_count": row[1], "batch_count": row[2]}
            for row in rows
        ],
    }


def check_provenance_and_orphans(connection: sqlite3.Connection) -> dict:
    observation_metrics = _daily_observation_orphan_metrics(connection)
    relations = [
        ("lineage_without_daily_fact", "fact_field_lineage", "daily_data",
         ("shop_id", "product_id", "date")),
        ("monthly_payload_without_monthly_fact", "monthly_source_payload", "monthly_data",
         ("product_id", "month")),
    ]
    promotion_metrics = _promotion_product_linkage_metrics(connection)
    promotion_batch_metrics = _promotion_unregistered_batch_metrics(connection)
    metrics = {
        "daily_observations_without_daily_fact": {
            "count": observation_metrics["count"],
            "unregistered_batch_count": observation_metrics["unregistered_batch_count"],
            "completed_batch_count": observation_metrics["completed_batch_count"],
            "child": "daily_data_observations",
            "parent": "daily_data",
        },
        "promotion_facts_without_product": {
            "count": promotion_metrics["count"],
            "by_grain": promotion_metrics["by_grain"],
            "by_classification": promotion_metrics["by_classification"],
            "by_identity_status": promotion_metrics["by_identity_status"],
            "child": "promotion_daily_facts",
            "parent": "products",
            "note": "推广单元和历史报表可能携带非商品主键，仅作为关联风险提示",
        },
        "promotion_facts_without_import_batch": promotion_batch_metrics,
    }
    issues = []
    if observation_metrics["completed_batch_count"]:
        issues.append(
            {
                "severity": "error",
                "code": "orphan_rows_from_completed_batch",
                "relation": "daily_observations_without_daily_fact",
                "count": observation_metrics["completed_batch_count"],
                "key": ["shop_id", "product_id", "date"],
            }
        )
    elif observation_metrics["unregistered_batch_count"]:
        issues.append(
            {
                "severity": "warning",
                "code": "unregistered_observation_batch",
                "relation": "daily_observations_without_daily_fact",
                "count": observation_metrics["unregistered_batch_count"],
                "key": ["shop_id", "product_id", "date"],
            }
        )
    product_linkage_rows = next(
        (
            item["row_count"]
            for item in promotion_metrics["by_classification"]
            if item["classification"] == "unresolved_product"
        ),
        sum(
            item["row_count"]
            for item in promotion_metrics["by_grain"]
            if item["grain"] == "product"
        ),
    )
    if product_linkage_rows:
        issues.append(
            {
                "severity": "warning",
                "code": "promotion_product_identity_unresolved",
                "relation": "promotion_daily_facts -> product_identity_map",
                "count": product_linkage_rows,
                "key": ["shop_id", "date", "channel", "campaign_id", "unit_id", "product_id"],
                "note": "仅将真正商品粒度列为告警；unit_month/campaign_month 的商品标识不作为硬外键",
            }
        )
    if promotion_batch_metrics["row_count"]:
        issues.append(
            {
                "severity": "warning",
                "code": "promotion_fact_without_import_batch",
                "relation": "promotion_daily_facts -> import_batches",
                "count": promotion_batch_metrics["row_count"],
                "batch_count": promotion_batch_metrics["batch_count"],
                "key": ["source_batch_id"],
                "by_grain": promotion_batch_metrics["by_grain"],
            }
        )
    for label, child, parent, key in relations:
        count = _orphan_count(connection, child, parent, key)
        metrics[label] = {"count": count, "child": child, "parent": parent}
        if count:
            issues.append(
                {
                    "severity": "error",
                    "code": "orphan_rows",
                    "relation": label,
                    "count": count,
                    "key": list(key),
                }
            )
    return _result(
        "provenance_and_orphans",
        "error" if any(i["severity"] == "error" for i in issues) else (
            "warning" if issues else "ok"
        ),
        metrics,
        issues,
    )


def check_foreign_keys(connection: sqlite3.Connection) -> dict:
    # foreign_keys is a connection setting in SQLite, so explicitly enable it
    # for this audit and report violations separately from the setting.
    connection.execute("PRAGMA foreign_keys=ON")
    violations = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
    issues = [
        {"severity": "error", "code": "foreign_key_violation", "violation": row}
        for row in violations[:100]
    ]
    if len(violations) > 100:
        issues.append(
            {
                "severity": "error",
                "code": "foreign_key_violation_overflow",
                "additional_count": len(violations) - 100,
            }
        )
    return _result(
        "foreign_keys",
        "error" if issues else "ok",
        {"enabled_for_audit": connection.execute("PRAGMA foreign_keys").fetchone()[0],
         "violation_count": len(violations)},
        issues,
    )


def check_promotion_grain(connection: sqlite3.Connection) -> dict:
    table = "promotion_daily_facts"
    if not _has_table(connection, table):
        return _result("promotion_grain", "skipped", {"table_present": False})
    columns = _columns(connection, table)
    if "grain" not in columns:
        return _result(
            "promotion_grain",
            "error",
            {"table_present": True, "grain_column": False},
            [{"severity": "error", "code": "grain_column_missing", "table": table}],
        )
    blank = connection.execute(
        f"""SELECT COUNT(*) FROM {quote_identifier(table)}
            WHERE grain IS NULL OR TRIM(grain) = ''"""
    ).fetchone()[0]
    by_grain = [
        {"grain": row[0], "row_count": row[1]}
        for row in connection.execute(
            f"""SELECT grain, COUNT(*)
                FROM {quote_identifier(table)}
                GROUP BY grain
                ORDER BY COUNT(*) DESC, grain"""
        )
    ]
    issues = []
    if blank:
        issues.append(
            {"severity": "error", "code": "blank_promotion_grain", "count": blank}
        )
    return _result(
        "promotion_grain",
        "error" if issues else "ok",
        {"blank_count": blank, "by_grain": by_grain},
        issues,
    )


def check_staging_retention(connection: sqlite3.Connection, retention_days: int = 14) -> dict:
    table = "collector_data_staging"
    if not _has_table(connection, table):
        return _result("staging_retention", "skipped", {"table_present": False})
    columns = _columns(connection, table)
    metrics = {
        "table_present": True,
        "row_count": connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table)}"
        ).fetchone()[0],
    }
    issues = []
    if "status" in columns:
        metrics["published_count"] = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table)} WHERE status = 'published'"
        ).fetchone()[0]
    if {"status", "created_at"}.issubset(columns):
        old_published = connection.execute(
            f"""SELECT COUNT(*) FROM {quote_identifier(table)}
                WHERE status = 'published'
                  AND datetime(created_at) < datetime('now', ?)""",
            (f"-{retention_days} days",),
        ).fetchone()[0]
        metrics["published_older_than_retention"] = old_published
        if old_published:
            issues.append(
                {
                    "severity": "warning",
                    "code": "published_staging_exceeds_retention",
                    "count": old_published,
                    "retention_days": retention_days,
                }
            )
    if {"status", "published_at"}.issubset(columns):
        unpublished_timestamp = connection.execute(
            f"""SELECT COUNT(*) FROM {quote_identifier(table)}
                WHERE status = 'published' AND published_at IS NULL"""
        ).fetchone()[0]
        metrics["published_without_timestamp"] = unpublished_timestamp
        if unpublished_timestamp:
            issues.append(
                {
                    "severity": "warning",
                    "code": "published_without_published_at",
                    "count": unpublished_timestamp,
                }
            )
    return _result("staging_retention", "warning" if issues else "ok", metrics, issues)


def check_collector_runs(connection: sqlite3.Connection, stale_hours: int = 2) -> dict:
    table = "collector_runs"
    if not _has_table(connection, table):
        return _result("collector_runs", "skipped", {"table_present": False})
    statuses = [
        {"status": row[0], "count": row[1]}
        for row in connection.execute(
            f"""SELECT status, COUNT(*)
                FROM {quote_identifier(table)}
                GROUP BY status
                ORDER BY status"""
        )
    ]
    stale = connection.execute(
        f"""SELECT id, source_key, shop_id, status, updated_at, created_at
            FROM {quote_identifier(table)}
            WHERE status IN ('running', 'queued')
              AND datetime(COALESCE(updated_at, created_at)) < datetime('now', ?)""",
        (f"-{stale_hours} hours",),
    ).fetchall()
    issues = [
        {
            "severity": "error",
            "code": "stale_collector_run",
            "run_id": row["id"],
            "source_key": row["source_key"],
            "shop_id": row["shop_id"],
            "status": row["status"],
            "updated_at": row["updated_at"],
        }
        for row in stale
    ]
    return _result(
        "collector_runs",
        "error" if issues else "ok",
        {"statuses": statuses, "stale_hours": stale_hours, "stale_count": len(stale)},
        issues,
    )


def check_artifacts(connection: sqlite3.Connection) -> dict:
    table = "collector_artifacts"
    if not _has_table(connection, table):
        return _result("collector_artifacts", "skipped", {"table_present": False})
    rows = connection.execute(
        f"SELECT id, run_id, path FROM {quote_identifier(table)}"
    ).fetchall()
    missing = []
    for row in rows:
        path = Path(row["path"])
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.is_file():
            missing.append(
                {"id": row["id"], "run_id": row["run_id"], "path": row["path"]}
            )
    issues = [
        {
            "severity": "error",
            "code": "collector_artifact_missing",
            "count": len(missing),
            "samples": missing[:20],
        }
    ] if missing else []
    return _result(
        "collector_artifacts",
        "error" if issues else "ok",
        {"artifact_count": len(rows), "missing_count": len(missing)},
        issues,
    )


def check_shop_scope(connection: sqlite3.Connection) -> dict:
    tables = ["daily_data", "monthly_data", "store_daily_facts", "promotion_daily_facts"]
    metrics = {}
    for table in tables:
        if "shop_id" not in _columns(connection, table):
            continue
        rows = connection.execute(
            f"""SELECT shop_id, COUNT(*)
                FROM {quote_identifier(table)}
                GROUP BY shop_id
                ORDER BY COUNT(*) DESC"""
        ).fetchall()
        metrics[table] = {
            "distinct_shop_count": len(rows),
            "shops": [{"shop_id": row[0], "row_count": row[1]} for row in rows],
        }
    return _result("shop_scope", "ok", metrics)


def check_analyze(connection: sqlite3.Connection) -> dict:
    has_stat1 = bool(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_stat1'"
        ).fetchone()
    )
    issues = [] if has_stat1 else [
        {"severity": "warning", "code": "sqlite_stat1_missing"}
    ]
    return _result(
        "query_statistics",
        "warning" if issues else "ok",
        {"has_sqlite_stat1": has_stat1},
        issues,
    )


def check_future_facts(connection: sqlite3.Connection, as_of_date: str | None = None) -> dict:
    """Reject operational facts dated after the audit reference date."""
    reference = as_of_date or datetime.now(timezone.utc).date().isoformat()
    try:
        datetime.strptime(reference, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError(f"invalid as_of_date: {reference}") from error

    date_columns = (
        ("daily_data", "date", "date"),
        ("daily_data_observations", "date", "date"),
        ("fact_field_lineage", "date", "date"),
        ("store_daily_facts", "date", "date"),
        ("promotion_daily_facts", "date", "date"),
        ("bi_product_daily_raw", "date", "date"),
        ("sycm_flow_source_daily", "stat_date", "date"),
        ("sycm_item_flow_source_daily", "stat_date", "date"),
        ("sycm_market_item_rank", "stat_date", "date"),
        ("sycm_market_rival_item", "stat_date", "date"),
        ("sycm_market_rival_shop", "stat_date", "date"),
        ("sycm_market_search_rank", "stat_date", "date"),
        ("sycm_trade_summary_daily", "stat_date", "date"),
    )
    month_columns = (
        ("monthly_data", "month", "month"),
        ("monthly_source_payload", "month", "month"),
    )
    metrics = {"as_of_date": reference, "tables": []}
    issues = []

    for table, column, kind in (*date_columns, *month_columns):
        if not _has_table(connection, table) or column not in _columns(connection, table):
            continue
        cutoff = reference if kind == "date" else reference[:7]
        row = connection.execute(
            f'''SELECT COUNT(*), MAX("{column}")
                FROM "{table}"
                WHERE NULLIF(TRIM(CAST("{column}" AS TEXT)), '') IS NOT NULL
                  AND CAST("{column}" AS TEXT) > ?''',
            (cutoff,),
        ).fetchone()
        count = int(row[0] or 0)
        latest = row[1]
        metrics["tables"].append({
            "table": table,
            "column": column,
            "kind": kind,
            "future_count": count,
            "latest_future_value": latest,
        })
        if count:
            issues.append({
                "severity": "error",
                "code": "future_operational_fact",
                "table": table,
                "column": column,
                "count": count,
                "latest_future_value": latest,
                "as_of_date": reference,
            })

    return _result(
        "future_facts",
        "error" if issues else "ok",
        metrics,
        issues,
    )


def collect_checks(
    connection: sqlite3.Connection,
    *,
    schema_source: str | os.PathLike[str] | None = None,
    staging_retention_days: int = 14,
    stale_run_hours: int = 2,
    as_of_date: str | None = None,
) -> list[dict]:
    return [
        check_integrity(connection),
        check_schema_alignment(connection, schema_source),
        check_duplicates(connection),
        check_future_facts(connection, as_of_date),
        check_provenance_and_orphans(connection),
        check_foreign_keys(connection),
        check_promotion_grain(connection),
        check_staging_retention(connection, staging_retention_days),
        check_collector_runs(connection, stale_run_hours),
        check_artifacts(connection),
        check_shop_scope(connection),
        check_analyze(connection),
    ]


def build_report(
    database_path: str | os.PathLike[str],
    *,
    schema_source: str | os.PathLike[str] | None = None,
    staging_retention_days: int = 14,
    stale_run_hours: int = 2,
    as_of_date: str | None = None,
) -> dict:
    database = Path(database_path).resolve()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(database),
        "exists": database.is_file(),
        "summary": {"status": "error", "checks": 0, "errors": 0, "warnings": 0},
        "checks": [],
        "errors": [],
    }
    if not database.is_file():
        report["errors"].append("database_not_found")
        return report
    try:
        with closing(connect_readonly(database)) as connection:
            report["checks"] = collect_checks(
                connection,
                schema_source=schema_source or DEFAULT_SCHEMA_SOURCE,
                staging_retention_days=staging_retention_days,
                stale_run_hours=stale_run_hours,
                as_of_date=as_of_date,
            )
    except sqlite3.Error as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
        return report

    error_count = sum(
        1
        for check in report["checks"]
        for issue in check["issues"]
        if issue.get("severity") == "error"
    )
    warning_count = sum(
        1
        for check in report["checks"]
        for issue in check["issues"]
        if issue.get("severity") == "warning"
    )
    report["summary"] = {
        "status": "error" if error_count else ("warning" if warning_count else "ok"),
        "checks": len(report["checks"]),
        "errors": error_count,
        "warnings": warning_count,
    }
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only SQLite data quality audit")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--schema-source", default=str(DEFAULT_SCHEMA_SOURCE))
    parser.add_argument("--output", required=True)
    parser.add_argument("--strict", action="store_true", help="Return non-zero for warnings")
    parser.add_argument("--staging-retention-days", type=int, default=14)
    parser.add_argument("--stale-run-hours", type=int, default=2)
    parser.add_argument(
        "--as-of-date",
        help="Reference date for future-fact checks (YYYY-MM-DD); defaults to UTC today",
    )
    args = parser.parse_args(argv)

    report = build_report(
        args.database,
        schema_source=args.schema_source,
        staging_retention_days=args.staging_retention_days,
        stale_run_hours=args.stale_run_hours,
        as_of_date=args.as_of_date,
    )
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "status": report["summary"]["status"],
                "errors": report["summary"]["errors"],
                "warnings": report["summary"]["warnings"],
            },
            ensure_ascii=False,
        )
    )
    if report["errors"] or report["summary"]["errors"]:
        return 1
    return 2 if args.strict and report["summary"]["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

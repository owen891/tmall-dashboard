"""Export a read-only schema baseline for the SQLite dashboard database."""

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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scripts.db_inventory import (  # noqa: E402
        DEFAULT_DATABASE,
        DEFAULT_SCHEMA_SOURCE,
        build_report as build_inventory,
        connect_readonly,
    )
except ModuleNotFoundError:
    from db_inventory import (  # type: ignore  # noqa: E402
        DEFAULT_DATABASE,
        DEFAULT_SCHEMA_SOURCE,
        build_report as build_inventory,
        connect_readonly,
    )


RUNTIME_TABLES = {
    "product_identity_map": {
        "domain": "identity_resolution",
        "owner": "services/product_identity_service.py",
        "lifecycle": "upsert_by_external_identity",
    },
    "bi_product_daily_raw": {
        "domain": "raw_evidence",
        "owner": "bi-daily-importer (private tool)",
        "lifecycle": "archiveable",
    },
    "keyword_promotion_products": {
        "domain": "feature_snapshot",
        "owner": "runtime/import_keyword_promotion",
        "lifecycle": "replaceable",
    },
    "market_analysis_runs": {
        "domain": "market_analysis",
        "owner": "scripts/import_market_ranking.py",
        "lifecycle": "append_by_run",
    },
    "market_category_stats": {
        "domain": "market_analysis",
        "owner": "scripts/import_market_ranking.py",
        "lifecycle": "append_by_run",
    },
    "market_keywords": {
        "domain": "market_analysis",
        "owner": "scripts/import_market_ranking.py",
        "lifecycle": "append_by_run",
    },
    "market_overlap_shops": {
        "domain": "market_analysis",
        "owner": "scripts/import_market_ranking.py",
        "lifecycle": "append_by_run",
    },
    "market_products": {
        "domain": "market_analysis",
        "owner": "scripts/import_market_ranking.py",
        "lifecycle": "append_by_run",
    },
    "sycm_flow_source_daily": {
        "domain": "source_facts",
        "owner": "external collector: sycm_flow",
        "lifecycle": "replace_by_date",
    },
    "sycm_item_flow_source_daily": {
        "domain": "source_facts",
        "owner": "external collector: sycm_item_flow",
        "lifecycle": "replace_by_date",
    },
    "sycm_market_item_rank": {
        "domain": "source_facts",
        "owner": "external collector: sycm_market",
        "lifecycle": "replace_by_date",
    },
    "sycm_market_rival_item": {
        "domain": "source_facts",
        "owner": "external collector: sycm_market",
        "lifecycle": "replace_by_date",
    },
    "sycm_market_rival_shop": {
        "domain": "source_facts",
        "owner": "external collector: sycm_market",
        "lifecycle": "replace_by_date",
    },
    "sycm_market_search_rank": {
        "domain": "source_facts",
        "owner": "external collector: sycm_market",
        "lifecycle": "replace_by_date",
    },
    "sycm_trade_summary_daily": {
        "domain": "source_facts",
        "owner": "external collector: sycm_trade_summary",
        "lifecycle": "replace_by_date",
    },
    # --- DMP 采集器落库（2026-10-08 登记）---
    # 这批表由外部 DMP 采集器在运行时动态 CREATE，db.py 的迁移脚本里没有建表
    # 语句，因此长期以「undeclared table」形式出现在 db_quality_check 的
    # schema_alignment warning 里（95 张实际 vs 83 张声明）。它们被
    # api/dmp_api.py、api/collect_api.py、services/data_capability_service.py
    # 读取，属真实在用的运行期表，登记为 runtime 归属以消除该误报。
    # 注意：登记只影响 schema_baseline 的 ownership/domain 标注，不建表、
    # 不迁移、不改变任何运行时行为。
    "dmp_shop_runs": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_shop",
        "lifecycle": "append_by_run",
    },
    "dmp_shop_overview": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_shop",
        "lifecycle": "replace_by_run_period",
    },
    "dmp_shop_items": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_shop",
        "lifecycle": "replace_by_run_period",
    },
    "dmp_shop_item_indicators": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_shop",
        "lifecycle": "replace_by_run_period",
    },
    "dmp_shop_indicator_dict": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_shop",
        "lifecycle": "replace_by_run",
    },
    "dmp_competition_runs": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_competition",
        "lifecycle": "append_by_run",
    },
    "dmp_competitors_detection": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_competition",
        "lifecycle": "replace_by_run",
    },
    "dmp_competitor_monitor": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_competition",
        "lifecycle": "replace_by_run",
    },
    "dmp_competition_indicators": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_competition",
        "lifecycle": "replace_by_run",
    },
    "dmp_competition_ad_strategy": {
        "domain": "dmp_collector",
        "owner": "external collector: dmp_competition",
        "lifecycle": "replace_by_run",
    },
    # 一次性导出导入的店铺排行快照（scripts/import_market_oneclick_exports.py）。
    "market_snapshot_shop_rank": {
        "domain": "market_snapshot",
        "owner": "scripts/import_market_oneclick_exports.py",
        "lifecycle": "append_by_batch",
    },
    # SYCM 商品排名日快照（外部采集器）。
    "sycm_item_rank_daily": {
        "domain": "source_facts",
        "owner": "external collector: sycm_item_rank",
        "lifecycle": "replace_by_date",
    },
}


def _table_sql(connection: sqlite3.Connection, table: str) -> str | None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else None


def _migration_rows(connection: sqlite3.Connection) -> list[dict]:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if not exists:
        return []
    return [dict(row) for row in connection.execute(
        "SELECT version, name, state, applied_at FROM schema_migrations ORDER BY version"
    )]


def build_baseline(
    database_path: str | os.PathLike[str],
    *,
    schema_source: str | os.PathLike[str] | None = None,
) -> dict:
    inventory = build_inventory(
        database_path,
        schema_source=schema_source or DEFAULT_SCHEMA_SOURCE,
        include_row_counts=True,
    )
    result = {
        "manifest_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": inventory["database"],
        "schema_source": str(Path(schema_source or DEFAULT_SCHEMA_SOURCE).resolve()),
        "pragmas": inventory.get("pragmas", {}),
        "drift": {
            "undeclared_tables": inventory["schema"]["tables_not_declared_by_db_py"],
            "missing_declared_tables": inventory["schema"]["declared_tables_missing_from_database"],
        },
        "migrations": [],
        "tables": [],
        "errors": list(inventory.get("errors", [])),
    }
    if not inventory["database"]["exists"]:
        return result

    with closing(connect_readonly(database_path)) as connection:
        result["migrations"] = _migration_rows(connection)
        for table in inventory["schema"]["tables"]:
            metadata = RUNTIME_TABLES.get(table["name"], {})
            result["tables"].append({
                **table,
                "declared_in_db_py": table["name"] not in result["drift"]["undeclared_tables"],
                "ownership": "runtime" if metadata else "db.py",
                "domain": metadata.get("domain", "core_or_operational"),
                "owner": metadata.get("owner", "db.py:_run_init_migrations"),
                "lifecycle": metadata.get("lifecycle", "managed"),
                "create_sql": _table_sql(connection, table["name"]),
            })
    return result


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a read-only schema baseline")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--schema-source", default=str(DEFAULT_SCHEMA_SOURCE))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = build_baseline(args.database, schema_source=args.schema_source)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "table_count": len(report["tables"]),
        "runtime_table_count": sum(item["ownership"] == "runtime" for item in report["tables"]),
        "migration_count": len(report["migrations"]),
        "errors": report["errors"],
    }, ensure_ascii=False))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

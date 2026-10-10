"""Read-only SQLite schema and storage inventory.

This module deliberately does not import ``db.py`` or call application
initialization. It is safe to run against the production database while the
dashboard is serving requests.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = Path(os.environ.get("TMALL_DB_PATH", PROJECT_ROOT / "data" / "dashboard.db"))
DEFAULT_SCHEMA_SOURCE = PROJECT_ROOT / "db.py"


def quote_identifier(identifier: str) -> str:
    """Quote a SQLite identifier returned by sqlite_master."""
    return '"' + identifier.replace('"', '""') + '"'


def connect_readonly(database_path: str | os.PathLike[str]) -> sqlite3.Connection:
    """Open a database without permitting writes.

    2026-10-08：补 ``PRAGMA temp_store=MEMORY``。SQLite 默认 ``temp_store=FILE``
    (0)，大 ``GROUP BY`` / ``ORDER BY`` 会把中间结果落到系统临时目录；当 Temp
    不可写（磁盘满、受限账户、沙箱）时报 **"unable to open database file"**——
    一个与数据库本身毫无关系的误导性错误。实测 ``promotion_daily_facts`` 按
    (shop_id, product_id) 聚合即触发，导致 ``backfill_product_identity_map``
    的只读预览整体失败。

    应用主连接（``db.get_connection``）早已设置该 pragma，此处补齐以保持一致：
    内存临时表既避免了对系统 Temp 的依赖，也更快。注意 ``SQLITE_TMPDIR``
    环境变量对本场景**无效**（已实测），必须用 pragma。
    """
    path = Path(database_path).resolve()
    uri = f"file:{path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA temp_store=MEMORY")
    return connection


def declared_tables(schema_source: str | os.PathLike[str]) -> set[str]:
    """Extract tables declared by the application's schema initializer."""
    path = Path(schema_source)
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"--[^\r\n]*", "", text)
    text = re.sub(r"(?m)^[ \t]*\#[^\r\n]*", "", text)
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:[`\"\[])?([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    )
    return {match.group(1) for match in pattern.finditer(text)}


def _table_names(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """SELECT name
           FROM sqlite_master
           WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
           ORDER BY name"""
    ).fetchall()
    return [row[0] for row in rows]


def _pragma_rows(connection: sqlite3.Connection, pragma: str, table: str) -> list[dict]:
    rows = connection.execute(f"PRAGMA {pragma}({quote_identifier(table)})").fetchall()
    return [dict(row) for row in rows]


def _table_inventory(connection: sqlite3.Connection, table: str, include_row_count: bool) -> dict:
    columns = _pragma_rows(connection, "table_info", table)
    indexes = _pragma_rows(connection, "index_list", table)
    foreign_keys = _pragma_rows(connection, "foreign_key_list", table)
    result = {
        "name": table,
        "row_count": None,
        "columns": [
            {
                "name": column["name"],
                "type": column["type"],
                "not_null": bool(column["notnull"]),
                "default": column["dflt_value"],
                "primary_key_position": column["pk"],
            }
            for column in columns
        ],
        "indexes": [
            {
                "name": index["name"],
                "unique": bool(index["unique"]),
                "origin": index["origin"],
                "partial": bool(index["partial"]),
            }
            for index in indexes
        ],
        "foreign_keys": [
            {
                "table": foreign_key["table"],
                "from": foreign_key["from"],
                "to": foreign_key["to"],
                "on_update": foreign_key["on_update"],
                "on_delete": foreign_key["on_delete"],
            }
            for foreign_key in foreign_keys
        ],
    }
    if include_row_count:
        result["row_count"] = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table)}"
        ).fetchone()[0]
    return result


def _pragma_summary(connection: sqlite3.Connection) -> dict:
    def scalar(name: str):
        return connection.execute(f"PRAGMA {name}").fetchone()[0]

    return {
        "journal_mode": scalar("journal_mode"),
        "foreign_keys": scalar("foreign_keys"),
        "user_version": scalar("user_version"),
        "page_count": scalar("page_count"),
        "freelist_count": scalar("freelist_count"),
        "has_sqlite_stat1": bool(
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_stat1'"
            ).fetchone()
        ),
        "quick_check": scalar("quick_check"),
    }


def build_report(
    database_path: str | os.PathLike[str],
    *,
    schema_source: str | os.PathLike[str] | None = None,
    include_row_counts: bool = True,
) -> dict:
    """Build a complete inventory without modifying the database."""
    database = Path(database_path).resolve()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": {
            "path": str(database),
            "exists": database.is_file(),
            "size_bytes": database.stat().st_size if database.is_file() else 0,
        },
        "pragmas": {},
        "schema": {
            "table_count": 0,
            "declared_table_count": 0,
            "tables_not_declared_by_db_py": [],
            "declared_tables_missing_from_database": [],
            "tables": [],
        },
        "errors": [],
    }
    if not database.is_file():
        report["errors"].append("database_not_found")
        return report

    source = Path(schema_source or DEFAULT_SCHEMA_SOURCE).resolve()
    declared = declared_tables(source)
    try:
        with closing(connect_readonly(database)) as connection:
            actual = _table_names(connection)
            report["pragmas"] = _pragma_summary(connection)
            report["schema"]["table_count"] = len(actual)
            report["schema"]["declared_table_count"] = len(declared)
            report["schema"]["tables_not_declared_by_db_py"] = sorted(set(actual) - declared)
            report["schema"]["declared_tables_missing_from_database"] = sorted(
                declared - set(actual)
            )
            report["schema"]["tables"] = [
                _table_inventory(connection, table, include_row_counts)
                for table in actual
            ]
    except sqlite3.Error as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    return report


def _write_report(report: dict, output: str | os.PathLike[str] | None) -> Path | None:
    if not output:
        return None
    target = Path(output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only SQLite schema inventory")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--schema-source", default=str(DEFAULT_SCHEMA_SOURCE))
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument(
        "--skip-row-counts",
        action="store_true",
        help="Skip COUNT(*) queries for a faster schema-only scan",
    )
    args = parser.parse_args(argv)

    report = build_report(
        args.database,
        schema_source=args.schema_source,
        include_row_counts=not args.skip_row_counts,
    )
    output = _write_report(report, args.output)
    print(
        json.dumps(
            {
                "database": report["database"]["path"],
                "table_count": report["schema"]["table_count"],
                "undeclared_table_count": len(
                    report["schema"]["tables_not_declared_by_db_py"]
                ),
                "output": str(output) if output else None,
                "errors": report["errors"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

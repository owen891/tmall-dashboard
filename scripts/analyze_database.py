"""Refresh SQLite query statistics safely.

SQLite stores planner statistics in ``sqlite_stat1`` after ``ANALYZE``.
This command is read-only by default; applying it requires an explicit
rollback snapshot so maintenance cannot silently mutate the production DB.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import get_db_path  # noqa: E402


def _has_stat1(connection: sqlite3.Connection) -> bool:
    return bool(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_stat1'"
        ).fetchone()
    )


def _stat1_count(connection: sqlite3.Connection) -> int:
    if not _has_stat1(connection):
        return 0
    return int(connection.execute("SELECT COUNT(*) FROM sqlite_stat1").fetchone()[0])


def run(
    database: str | os.PathLike[str],
    *,
    apply: bool = False,
    backup_destination: str | os.PathLike[str] | None = None,
) -> dict:
    database_path = Path(database).resolve()
    report = {
        "database": str(database_path),
        "apply": bool(apply),
        "backup": None,
        "before": {},
        "after": {},
        "errors": [],
    }
    if not database_path.is_file():
        report["errors"].append("database_not_found")
        return report
    if apply and not backup_destination:
        report["errors"].append("backup_destination_required_for_apply")
        return report

    try:
        if apply:
            from scripts.backup_database import backup_database

            report["backup"] = backup_database(database_path, backup_destination)
            if not report["backup"]["ok"]:
                report["errors"].append("database_backup_integrity_failed")
                return report

        with closing(sqlite3.connect(str(database_path), timeout=600)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=600000")
            report["before"] = {
                "has_sqlite_stat1": _has_stat1(connection),
                "stat1_count": _stat1_count(connection),
            }
            if apply:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("ANALYZE")
                connection.commit()
            report["after"] = {
                "has_sqlite_stat1": _has_stat1(connection),
                "stat1_count": _stat1_count(connection),
                "integrity": connection.execute("PRAGMA integrity_check").fetchone()[0],
            }
            if report["after"]["integrity"] != "ok":
                report["errors"].append("integrity_check_failed")
    except sqlite3.Error as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh SQLite query statistics safely")
    parser.add_argument("--database", default=get_db_path())
    parser.add_argument("--output", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--backup-destination",
        help="Required with --apply: destination for an integrity-checked SQLite backup",
    )
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error("--backup-destination is required with --apply")

    report = run(
        args.database,
        apply=args.apply,
        backup_destination=args.backup_destination,
    )
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "apply": report["apply"],
                "before": report["before"],
                "after": report["after"],
                "errors": report["errors"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

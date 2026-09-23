"""Reconcile abandoned collector runs.

The command is intentionally dry-run by default. Use ``--apply`` only after
reviewing the JSON output. It changes collector run metadata, not business
fact tables.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.collector_run_service import reconcile_stale_runs  # noqa: E402
from scripts.db_inventory import connect_readonly  # noqa: E402


DEFAULT_DATABASE = Path(
    os.environ.get("TMALL_DB_PATH", PROJECT_ROOT / "data" / "dashboard.db")
)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile abandoned collector runs")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--stale-run-hours", type=float, default=2)
    parser.add_argument("--apply", action="store_true", help="Persist the reconciliation")
    parser.add_argument("--backup-destination", help="Required with --apply: integrity-checked SQLite backup path")
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error("--backup-destination is required with --apply")

    threshold = max(1, int(args.stale_run_hours * 3600))
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(Path(args.database).resolve()),
        "stale_run_hours": args.stale_run_hours,
        "apply": args.apply,
        "changed": [],
        "status": "dry_run",
    }
    if args.apply:
        from scripts.backup_database import backup_database
        result["backup"] = backup_database(args.database, args.backup_destination)
        if not result["backup"]["ok"]:
            raise RuntimeError("database backup integrity check failed")
        result["changed"] = reconcile_stale_runs(
            db_path=args.database,
            stale_after_seconds=threshold,
        )
        result["status"] = "applied"
    else:
        # Use a rollback transaction to inspect the same candidates without
        # changing the database. Read-only mode also avoids PRAGMA writes.
        from contextlib import closing

        with closing(connect_readonly(args.database)) as connection:
            rows = connection.execute(
                '''SELECT id, source_key, shop_id, status, updated_at, created_at
                   FROM collector_runs
                   WHERE status IN ('queued', 'running')
                   AND datetime(COALESCE(updated_at, created_at)) < datetime('now', ?)
                   AND NOT EXISTS (
                       SELECT 1 FROM collector_leases lease
                       WHERE lease.run_id = collector_runs.id
                         AND datetime(lease.lease_until) >= datetime('now')
                   )''',
                (f"-{threshold} seconds",),
            ).fetchall()
        result["changed"] = [
            {
                "id": row["id"],
                "source_key": row["source_key"],
                "shop_id": row["shop_id"],
                "previous_status": row["status"],
                "status": "failed",
                "error_code": "STALE_RUN",
            }
            for row in rows
        ]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reconcile legacy daily observations to durable import batch IDs.

The historical BI daily importer stored a filename in ``source_batch_id``
before durable import batches were introduced.  This command is read-only by
default and only updates observations when the matching batch is unique by
shop, source type, filename, date and row count.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import get_db_path  # noqa: E402


def _basename(value: str | None) -> str:
    return Path(str(value or '')).name


def _quality_date(summary: str | None) -> tuple[str | None, str | None]:
    try:
        payload = json.loads(summary or '{}')
    except (TypeError, json.JSONDecodeError):
        return None, None
    if payload.get('date'):
        return str(payload['date']), str(payload['date'])
    date_range = payload.get('date_range') or {}
    return date_range.get('start'), date_range.get('end')


def _observation_groups(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT o.shop_id, o.source_system, o.source_type,
               o.source_batch_id, o.source_filename,
               MIN(o.date) AS min_date, MAX(o.date) AS max_date,
               COUNT(*) AS row_count
        FROM daily_data_observations o
        LEFT JOIN import_batches b ON b.id = o.source_batch_id
        WHERE b.id IS NULL
        GROUP BY o.shop_id, o.source_system, o.source_type,
                 o.source_batch_id, o.source_filename
        ORDER BY min_date, o.source_type, o.source_filename
        """
    ).fetchall()


def _batch_candidates(connection: sqlite3.Connection, group: sqlite3.Row) -> list[dict]:
    candidates = []
    rows = connection.execute(
        """
        SELECT id, shop_id, source_type, source_filename, status,
               valid_rows, quality_summary, created_at
        FROM import_batches
        WHERE shop_id = ?
          AND source_type = ?
          AND status IN ('completed', 'validated')
        ORDER BY created_at, id
        """,
        (group['shop_id'] or 'default', group['source_type']),
    ).fetchall()
    for row in rows:
        if _basename(row['source_filename']) != _basename(group['source_filename']):
            continue
        start, end = _quality_date(row['quality_summary'])
        if start != group['min_date'] or end != group['max_date']:
            continue
        if int(row['valid_rows'] or 0) != int(group['row_count'] or 0):
            continue
        candidates.append(dict(row))
    return candidates


def plan(connection: sqlite3.Connection) -> dict:
    groups = _observation_groups(connection)
    report = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'groups': [],
        'summary': {
            'unregistered_group_count': len(groups),
            'unregistered_row_count': sum(int(row['row_count'] or 0) for row in groups),
            'unique_group_count': 0,
            'unique_row_count': 0,
            'ambiguous_group_count': 0,
            'ambiguous_row_count': 0,
            'unmatched_group_count': 0,
            'unmatched_row_count': 0,
        },
    }
    for group in groups:
        candidates = _batch_candidates(connection, group)
        if len(candidates) == 1:
            classification = 'unique'
            report['summary']['unique_group_count'] += 1
            report['summary']['unique_row_count'] += int(group['row_count'] or 0)
        elif candidates:
            classification = 'ambiguous'
            report['summary']['ambiguous_group_count'] += 1
            report['summary']['ambiguous_row_count'] += int(group['row_count'] or 0)
        else:
            classification = 'unmatched'
            report['summary']['unmatched_group_count'] += 1
            report['summary']['unmatched_row_count'] += int(group['row_count'] or 0)
        report['groups'].append({
            'classification': classification,
            'shop_id': group['shop_id'],
            'source_system': group['source_system'],
            'source_type': group['source_type'],
            'source_batch_id': group['source_batch_id'],
            'source_filename': group['source_filename'],
            'min_date': group['min_date'],
            'max_date': group['max_date'],
            'row_count': int(group['row_count'] or 0),
            'candidates': [
                {
                    'id': item['id'],
                    'source_filename': item['source_filename'],
                    'valid_rows': item['valid_rows'],
                    'created_at': item['created_at'],
                }
                for item in candidates
            ],
        })
    return report


def apply_plan(connection: sqlite3.Connection, report: dict) -> dict:
    updated = 0
    batches = set()
    for group in report.get('groups', []):
        if group.get('classification') != 'unique':
            continue
        batch_id = group['candidates'][0]['id']
        cursor = connection.execute(
            """
            UPDATE daily_data_observations
            SET source_batch_id = ?
            WHERE shop_id = ?
              AND source_type = ?
              AND source_batch_id IS ?
              AND source_filename IS ?
            """,
            (
                batch_id,
                group['shop_id'],
                group['source_type'],
                group['source_batch_id'],
                group['source_filename'],
            ),
        )
        updated += max(0, int(cursor.rowcount or 0))
        batches.add(batch_id)
    return {'updated_rows': updated, 'updated_batch_count': len(batches)}


def run(
    database: str | os.PathLike[str],
    *,
    apply: bool = False,
    backup_destination: str | os.PathLike[str] | None = None,
    output: str | os.PathLike[str] | None = None,
) -> dict:
    database_path = Path(database).resolve()
    report = {
        'database': str(database_path),
        'apply': bool(apply),
        'backup': None,
        'written': {'updated_rows': 0, 'updated_batch_count': 0},
    }
    if apply and not backup_destination:
        raise ValueError('backup_destination is required when apply=True')
    if apply:
        from scripts.backup_database import backup_database

        report['backup'] = backup_database(database_path, backup_destination)
        if not report['backup']['ok']:
            raise RuntimeError('database backup integrity check failed')

    connection = sqlite3.connect(database_path, timeout=300)
    connection.row_factory = sqlite3.Row
    try:
        report.update(plan(connection))
        if apply and report['summary']['unique_row_count']:
            connection.execute('BEGIN IMMEDIATE')
            report['written'] = apply_plan(connection, report)
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    if output:
        target = Path(output).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Reconcile legacy observation batch IDs')
    parser.add_argument('--database', default=get_db_path())
    parser.add_argument('--output')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument(
        '--backup-destination',
        help='Required with --apply: destination for an integrity-checked SQLite backup',
    )
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')
    report = run(
        args.database,
        apply=args.apply,
        backup_destination=args.backup_destination,
        output=args.output,
    )
    print(json.dumps({key: value for key, value in report.items() if key != 'groups'}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

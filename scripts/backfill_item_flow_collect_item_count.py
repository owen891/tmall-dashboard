"""Backfill the standard item-flow collection metric from its legacy alias."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

try:
    from scripts.backup_database import backup_database
except ModuleNotFoundError:  # direct ``python scripts/<name>.py`` execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.backup_database import backup_database


TABLE = 'sycm_item_flow_source_daily'


def inspect(connection):
    row = connection.execute(
        f'''SELECT COUNT(*) AS count, MIN(stat_date) AS min_date, MAX(stat_date) AS max_date
            FROM {TABLE}
            WHERE collect_item_count IS NULL AND collect_count IS NOT NULL'''
    ).fetchone()
    return {
        'eligible_rows': int(row['count'] or 0),
        'min_date': row['min_date'],
        'max_date': row['max_date'],
    }


def apply(database: Path, backup: Path) -> dict:
    backup_report = backup_database(database, backup)
    if not backup_report['ok']:
        raise RuntimeError('backup integrity check failed')

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        before = inspect(connection)
        connection.execute('BEGIN IMMEDIATE')
        cursor = connection.execute(
            f'''UPDATE {TABLE}
                SET collect_item_count = collect_count
                WHERE collect_item_count IS NULL AND collect_count IS NOT NULL'''
        )
        changed = int(cursor.rowcount or 0)
        connection.commit()
        integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
        after = inspect(connection)
        if integrity != 'ok' or after['eligible_rows'] != 0:
            raise RuntimeError(f'backfill verification failed: integrity={integrity}, remaining={after}')
        return {
            'database': str(database),
            'backup': backup_report,
            'before': before,
            'changed_rows': changed,
            'after': after,
            'integrity': integrity,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Backfill collect_item_count from collect_count')
    parser.add_argument('--database', required=True)
    parser.add_argument('--backup-destination', required=False)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    database = Path(args.database).resolve()
    connection = sqlite3.connect(database)
    try:
        connection.row_factory = sqlite3.Row
        before = inspect(connection)
    finally:
        connection.close()
    report = {
        'database': str(database),
        'dry_run': not args.apply,
        'before': before,
    }
    if args.apply:
        if not args.backup_destination:
            parser.error('--backup-destination is required with --apply')
        report.update(apply(database, Path(args.backup_destination).resolve()))
        report['dry_run'] = False
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'output': str(output),
        'dry_run': report['dry_run'],
        'eligible_rows': report['before']['eligible_rows'],
        'changed_rows': report.get('changed_rows', 0),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

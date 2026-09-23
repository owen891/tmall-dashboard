"""Move explicitly identified orphan observations to an auditable quarantine.

The command is dry-run by default. It never guesses which observations are
safe to remove: callers must provide exact observation IDs or source batch IDs,
and every selected row must still be orphaned from ``daily_data``.
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


def _ensure_table(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily_data_observations_quarantine (
            quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_id INTEGER NOT NULL UNIQUE,
            shop_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            date DATE NOT NULL,
            source_system TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_batch_id TEXT,
            source_filename TEXT,
            payload_json TEXT NOT NULL,
            field_presence_json TEXT NOT NULL DEFAULT '{}',
            quality_status TEXT NOT NULL DEFAULT 'passed',
            observed_at TIMESTAMP,
            quarantine_reason TEXT NOT NULL,
            quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_observation_quarantine_key
            ON daily_data_observations_quarantine(shop_id, product_id, date);
        """
    )


def _select_rows(
    connection: sqlite3.Connection,
    *,
    observation_ids: Iterable[int] = (),
    source_batch_ids: Iterable[str] = (),
) -> list[sqlite3.Row]:
    ids = sorted({int(value) for value in observation_ids})
    batches = sorted({str(value).strip() for value in source_batch_ids if str(value).strip()})
    if not ids and not batches:
        raise ValueError('observation_ids or source_batch_ids is required')
    clauses = []
    params: list[object] = []
    if ids:
        clauses.append('o.id IN (%s)' % ','.join('?' for _ in ids))
        params.extend(ids)
    if batches:
        clauses.append('o.source_batch_id IN (%s)' % ','.join('?' for _ in batches))
        params.extend(batches)
    return connection.execute(
        f"""
        SELECT o.*
        FROM daily_data_observations o
        WHERE {' OR '.join(clauses)}
        ORDER BY o.id
        """,
        params,
    ).fetchall()


def plan(
    database: str | os.PathLike[str],
    *,
    observation_ids: Iterable[int] = (),
    source_batch_ids: Iterable[str] = (),
    reason: str = 'explicitly identified orphan observation',
) -> dict:
    database_path = Path(database).resolve()
    report = {
        'database': str(database_path),
        'reason': reason,
        'selected_count': 0,
        'eligible_count': 0,
        'blocked': [],
        'rows': [],
    }
    with closing(sqlite3.connect(f'file:{database_path.as_posix()}?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        rows = _select_rows(
            connection,
            observation_ids=observation_ids,
            source_batch_ids=source_batch_ids,
        )
        report['selected_count'] = len(rows)
        for row in rows:
            fact = connection.execute(
                """SELECT 1 FROM daily_data
                   WHERE shop_id = ? AND product_id = ? AND date = ?""",
                (row['shop_id'], row['product_id'], row['date']),
            ).fetchone()
            import_batch = connection.execute(
                "SELECT 1 FROM import_batches WHERE id = ?",
                (row['source_batch_id'],),
            ).fetchone()
            blocked = bool(fact)
            entry = {
                'id': row['id'],
                'shop_id': row['shop_id'],
                'product_id': row['product_id'],
                'date': row['date'],
                'source_batch_id': row['source_batch_id'],
                'source_filename': row['source_filename'],
                'has_daily_fact': bool(fact),
                'has_import_batch': bool(import_batch),
                'eligible': not blocked,
            }
            report['rows'].append(entry)
            if blocked:
                report['blocked'].append({
                    'id': row['id'],
                    'reason': 'daily_fact_exists_for_observation_key',
                })
        report['eligible_count'] = sum(1 for row in report['rows'] if row['eligible'])
    return report


def apply_plan(
    database: str | os.PathLike[str],
    report: dict,
    *,
    reason: str,
) -> dict:
    if report['blocked']:
        raise RuntimeError('quarantine plan contains blocked rows')
    ids = [row['id'] for row in report['rows'] if row['eligible']]
    if not ids:
        return {'archived_count': 0, 'deleted_count': 0}
    with closing(sqlite3.connect(str(Path(database).resolve()), timeout=600)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        _ensure_table(connection)
        connection.execute('BEGIN IMMEDIATE')
        rows = connection.execute(
            'SELECT * FROM daily_data_observations WHERE id IN (%s) ORDER BY id'
            % ','.join('?' for _ in ids),
            ids,
        ).fetchall()
        for row in rows:
            connection.execute(
                """INSERT OR IGNORE INTO daily_data_observations_quarantine
                   (original_id, shop_id, product_id, date, source_system, source_type,
                    source_batch_id, source_filename, payload_json, field_presence_json,
                    quality_status, observed_at, quarantine_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row['id'], row['shop_id'], row['product_id'], row['date'],
                    row['source_system'], row['source_type'], row['source_batch_id'],
                    row['source_filename'], row['payload_json'], row['field_presence_json'],
                    row['quality_status'], row['observed_at'], reason,
                ),
            )
        deleted = connection.execute(
            'DELETE FROM daily_data_observations WHERE id IN (%s)' % ','.join('?' for _ in ids),
            ids,
        ).rowcount
        connection.commit()
        return {'archived_count': len(rows), 'deleted_count': max(0, int(deleted or 0))}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Quarantine explicitly identified orphan observations')
    parser.add_argument('--database', default=get_db_path())
    parser.add_argument('--observation-id', action='append', type=int, default=[])
    parser.add_argument('--source-batch-id', action='append', default=[])
    parser.add_argument('--reason', default='explicitly identified orphan observation')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-destination')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')
    report = plan(
        args.database,
        observation_ids=args.observation_id,
        source_batch_ids=args.source_batch_id,
        reason=args.reason,
    )
    report['apply'] = bool(args.apply)
    report['backup'] = None
    if args.apply:
        if report['blocked']:
            raise RuntimeError('quarantine plan contains blocked rows')
        from scripts.backup_database import backup_database
        report['backup'] = backup_database(args.database, args.backup_destination)
        if not report['backup']['ok']:
            raise RuntimeError('database backup integrity check failed')
        report['applied'] = apply_plan(args.database, report, reason=args.reason)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'output': str(output),
        'selected_count': report['selected_count'],
        'eligible_count': report['eligible_count'],
        'blocked_count': len(report['blocked']),
        'applied': report.get('applied'),
    }, ensure_ascii=False))
    return 1 if report['blocked'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

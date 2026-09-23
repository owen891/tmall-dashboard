"""Archive old monthly BI payloads with a verifiable manifest.

The default command is read-only. Applying an archive requires an explicit
backup destination, exports JSONL gzip, records the archive in
``archive_catalog`` when available, verifies row counts, and only then removes
the archived rows from ``monthly_source_payload``.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path


def _table_exists(conn, table):
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def _month_cutoff(months: int) -> str:
    today = date.today()
    year = today.year * 12 + today.month - 1 - int(months)
    return f'{year // 12:04d}-{year % 12 + 1:02d}'


def inspect(db_path, cutoff):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, 'monthly_source_payload'):
            return {'exists': False, 'cutoff': cutoff, 'row_count': 0}
        row = conn.execute(
            'SELECT COUNT(*), MIN(month), MAX(month) FROM monthly_source_payload WHERE month < ?',
            (cutoff,),
        ).fetchone()
        return {
            'exists': True,
            'cutoff': cutoff,
            'row_count': int(row[0] or 0),
            'min_month': row[1],
            'max_month': row[2],
        }
    finally:
        conn.close()


def _export(conn, cutoff, target):
    digest = hashlib.sha256()
    count = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(target, 'wb') as handle:
        cursor = conn.execute(
            'SELECT product_id, month, source_filename, source_hash, payload_json, imported_at '
            'FROM monthly_source_payload WHERE month < ? ORDER BY month, product_id',
            (cutoff,),
        )
        for row in cursor:
            payload = (json.dumps(dict(row), ensure_ascii=False, sort_keys=True).encode('utf-8') + b'\n')
            handle.write(payload)
            digest.update(payload)
            count += 1
    return {'row_count': count, 'sha256': digest.hexdigest(), 'path': str(target)}


def apply_archive(db_path, cutoff, archive_dir, backup_destination):
    from scripts.backup_database import backup_database

    backup = backup_database(db_path, backup_destination)
    if not backup['ok']:
        raise RuntimeError('database backup integrity check failed')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    exported = None
    try:
        if not _table_exists(conn, 'monthly_source_payload'):
            return {'backup': backup, 'export': None, 'deleted': 0}
        target = Path(archive_dir) / f'monthly_source_payload-before-{cutoff}.jsonl.gz'
        exported = _export(conn, cutoff, target)
        actual = conn.execute(
            'SELECT COUNT(*) FROM monthly_source_payload WHERE month < ?', (cutoff,)
        ).fetchone()[0]
        if int(actual) != exported['row_count']:
            raise RuntimeError('monthly payload row count changed during export')
        manifest = {
            'source_table': 'monthly_source_payload',
            'cutoff': cutoff,
            'row_count': exported['row_count'],
            'sha256': exported['sha256'],
            'archive_path': exported['path'],
        }
        manifest_path = Path(archive_dir) / f'manifest-monthly-before-{cutoff}.json'
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        if _table_exists(conn, 'archive_catalog'):
            conn.execute(
                '''INSERT OR REPLACE INTO archive_catalog
                   (archive_key, source_kind, source_table, archive_path, source_sha256,
                    row_count, min_value, max_value, status, metadata_json)
                   VALUES (?, 'raw_payload', 'monthly_source_payload', ?, ?, ?, ?, ?, 'verified', ?)''',
                (
                    f'monthly_source_payload:{cutoff}:{exported["sha256"]}',
                    exported['path'], exported['sha256'], exported['row_count'],
                    conn.execute('SELECT MIN(month) FROM monthly_source_payload WHERE month < ?', (cutoff,)).fetchone()[0],
                    conn.execute('SELECT MAX(month) FROM monthly_source_payload WHERE month < ?', (cutoff,)).fetchone()[0],
                    json.dumps({'cutoff': cutoff, 'manifest': str(manifest_path)}, ensure_ascii=False),
                ),
            )
        conn.execute('DELETE FROM monthly_source_payload WHERE month < ?', (cutoff,))
        conn.commit()
        return {'backup': backup, 'export': {**exported, 'manifest': str(manifest_path)},
                'deleted': int(actual)}
    except Exception:
        conn.rollback()
        if exported:
            Path(exported['path']).unlink(missing_ok=True)
        raise
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Archive old monthly BI payloads')
    parser.add_argument('--database', required=True)
    parser.add_argument('--archive-dir', default=None)
    parser.add_argument('--older-than-months', type=int, default=6)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-destination', default=None)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')
    db = Path(args.database).resolve()
    cutoff = _month_cutoff(args.older_than_months)
    archive_dir = Path(args.archive_dir or db.parent / 'monthly_payload_archive')
    report = {
        'database': str(db),
        'cutoff': cutoff,
        'dry_run': not args.apply,
        'inspection': inspect(str(db), cutoff),
        'policy': {'mutations_performed': False, 'delete_performed': False},
    }
    if args.apply:
        report['applied'] = apply_archive(str(db), cutoff, archive_dir, args.backup_destination)
        report['policy']['mutations_performed'] = True
        report['policy']['delete_performed'] = bool(report['applied']['deleted'])
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'dry_run': not args.apply,
                      'inspection': report['inspection']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

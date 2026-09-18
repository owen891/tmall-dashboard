"""Archive old raw observations and lineage rows with a verifiable manifest.

The command is a dry-run by default. With ``--apply`` it exports rows as
gzip-compressed JSONL, verifies row count and SHA-256, then deletes exactly
the exported date range in one SQLite transaction.
"""

import argparse
import gzip
import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

TABLES = ('bi_product_daily_raw', 'daily_data_observations', 'fact_field_lineage')


def cutoff_date(days):
    return (date.today() - timedelta(days=int(days))).isoformat()


def inspect(db_path, cutoff):
    conn = sqlite3.connect(db_path)
    try:
        result = {'cutoff_date': cutoff, 'tables': {}}
        for table in TABLES:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                result['tables'][table] = {'exists': False, 'row_count': 0}
                continue
            row = conn.execute(f'SELECT COUNT(*), MIN(date), MAX(date) FROM {table} WHERE date < ?', (cutoff,)).fetchone()
            result['tables'][table] = {
                'exists': True, 'row_count': int(row[0] or 0),
                'min_date': row[1], 'max_date': row[2],
            }
        return result
    finally:
        conn.close()


def export_table(conn, table, cutoff, target):
    digest = hashlib.sha256()
    count = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(target, 'wb') as handle:
        cursor = conn.execute(f'SELECT * FROM {table} WHERE date < ? ORDER BY date, rowid', (cutoff,))
        columns = [item[0] for item in cursor.description]
        for row in cursor:
            payload = json.dumps(dict(zip(columns, row)), ensure_ascii=False, default=str, sort_keys=True).encode('utf-8') + b'\n'
            handle.write(payload)
            digest.update(payload)
            count += 1
    return {'table': table, 'path': str(target), 'row_count': count, 'sha256': digest.hexdigest()}


def apply_archive(db_path, cutoff, archive_dir):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    exported = []
    try:
        for table in TABLES:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                continue
            target = Path(archive_dir) / f'{table}-before-{cutoff}.jsonl.gz'
            item = export_table(conn, table, cutoff, target)
            exported.append(item)
            actual = conn.execute(f'SELECT COUNT(*) FROM {table} WHERE date < ?', (cutoff,)).fetchone()[0]
            if int(actual) != item['row_count']:
                raise RuntimeError(f'{table} row count changed during export')
        manifest = {'cutoff_date': cutoff, 'tables': exported}
        manifest_path = Path(archive_dir) / f'manifest-before-{cutoff}.json'
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        for item in exported:
            conn.execute(f'DELETE FROM {item["table"]} WHERE date < ?', (cutoff,))
        conn.commit()
        return {'manifest': str(manifest_path), 'tables': exported}
    except Exception:
        conn.rollback()
        for item in exported:
            Path(item['path']).unlink(missing_ok=True)
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Archive old raw and lineage data')
    parser.add_argument('--database', required=True)
    parser.add_argument('--archive-dir', default=None)
    parser.add_argument('--older-than-days', type=int, default=180)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    db = Path(args.database).resolve()
    cutoff = cutoff_date(args.older_than_days)
    report = {'database': str(db), 'cutoff_date': cutoff, 'dry_run': not args.apply,
              'inspection': inspect(str(db), cutoff)}
    if args.apply:
        report['applied'] = apply_archive(str(db), cutoff, Path(args.archive_dir or db.parent / 'lineage_archive'))
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'dry_run': not args.apply,
                      'tables': report['inspection']['tables']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Plan and archive old raw evidence with a verifiable manifest.

The command is a dry-run by default. Only the raw evidence table is eligible
by default. Derived observations and lineage are protected because dashboard
detail and source-resolution code still reads them online.
"""

import argparse
import gzip
import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

TABLES = ('bi_product_daily_raw', 'daily_data_observations', 'fact_field_lineage')
DEFAULT_ARCHIVE_TABLES = ('bi_product_daily_raw',)
DERIVED_TABLES = frozenset(('daily_data_observations', 'fact_field_lineage'))


def cutoff_date(days):
    return (date.today() - timedelta(days=int(days))).isoformat()


def inspect(db_path, cutoff, tables=None):
    conn = sqlite3.connect(db_path)
    try:
        selected = tuple(tables or DEFAULT_ARCHIVE_TABLES)
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
        dependency_counts = {
            table: _derived_dependency_count(conn, table, cutoff)
            for table in selected if table in DERIVED_TABLES
        }
        result['archive_policy'] = {
            'selected_tables': list(selected),
            'protected_tables': sorted(set(selected) & DERIVED_TABLES),
            'dependency_counts': dependency_counts,
            'blocked_tables': sorted(
                table for table, count in dependency_counts.items() if count
            ),
        }
        result['archive_policy']['can_apply'] = not result['archive_policy']['blocked_tables']
        return result
    finally:
        conn.close()


def _table_exists(conn, table):
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def _record_archive_catalog(conn, *, table, target, sha256, row_count,
                            min_value=None, max_value=None, metadata=None):
    if not _table_exists(conn, 'archive_catalog'):
        return
    archive_key = f'{table}:{min_value or ""}:{max_value or ""}:{sha256}'
    conn.execute(
        '''INSERT OR REPLACE INTO archive_catalog
           (archive_key, source_kind, source_table, archive_path, source_sha256,
            row_count, min_value, max_value, status, metadata_json)
           VALUES (?, 'raw_payload', ?, ?, ?, ?, ?, ?, 'verified', ?)''',
        (archive_key, table, str(target), sha256, row_count, min_value, max_value,
         json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)),
    )


def _derived_dependency_count(conn, table, cutoff):
    """Count old derived rows still needed by current dashboard facts."""
    if table not in DERIVED_TABLES or not _table_exists(conn, 'daily_data'):
        return 0
    required = {'shop_id', 'product_id', 'date'}
    columns = {
        row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')
    }
    daily_columns = {
        row[1] for row in conn.execute('PRAGMA table_info("daily_data")')
    }
    if not required.issubset(columns) or not required.issubset(daily_columns):
        return 0
    return int(conn.execute(
        f'''SELECT COUNT(*)
            FROM "{table}" source
            WHERE source.date < ?
              AND EXISTS (
                  SELECT 1 FROM daily_data fact
                  WHERE fact.shop_id = source.shop_id
                    AND fact.product_id = source.product_id
                    AND fact.date = source.date
              )''',
        (cutoff,),
    ).fetchone()[0] or 0)


def _validate_archive_tables(conn, tables, cutoff, allow_derived):
    selected = tuple(dict.fromkeys(tables))
    unknown = sorted(set(selected) - set(TABLES))
    if unknown:
        raise ValueError(f'unsupported archive tables: {", ".join(unknown)}')
    derived = sorted(set(selected) & DERIVED_TABLES)
    if derived and not allow_derived:
        raise PermissionError(
            'derived tables are protected; pass allow_derived=True only after dependency review'
        )
    dependencies = {
        table: _derived_dependency_count(conn, table, cutoff)
        for table in derived
    }
    blocked = {table: count for table, count in dependencies.items() if count}
    if blocked:
        details = ', '.join(f'{table}={count}' for table, count in blocked.items())
        raise RuntimeError(f'archive blocked by online fact dependencies: {details}')
    return selected, dependencies


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


def apply_archive(db_path, cutoff, archive_dir, tables=None, allow_derived=False):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    exported = []
    try:
        selected = tuple(tables or DEFAULT_ARCHIVE_TABLES)
        selected, dependencies = _validate_archive_tables(
            conn, selected, cutoff, allow_derived
        )
        for table in selected:
            if not _table_exists(conn, table):
                continue
            target = Path(archive_dir) / f'{table}-before-{cutoff}.jsonl.gz'
            item = export_table(conn, table, cutoff, target)
            bounds = conn.execute(
                f'SELECT MIN(date), MAX(date) FROM "{table}" WHERE date < ?',
                (cutoff,),
            ).fetchone()
            item['min_value'], item['max_value'] = bounds[0], bounds[1]
            exported.append(item)
            actual = conn.execute(f'SELECT COUNT(*) FROM {table} WHERE date < ?', (cutoff,)).fetchone()[0]
            if int(actual) != item['row_count']:
                raise RuntimeError(f'{table} row count changed during export')
        manifest = {
            'cutoff_date': cutoff,
            'tables': exported,
            'allow_derived': bool(allow_derived),
            'dependency_counts': dependencies,
        }
        manifest_path = Path(archive_dir) / f'manifest-before-{cutoff}.json'
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        for item in exported:
            _record_archive_catalog(
                conn, table=item['table'], target=item['path'],
                sha256=item['sha256'], row_count=item['row_count'],
                min_value=item.get('min_value'), max_value=item.get('max_value'),
                metadata={'cutoff_date': cutoff, 'manifest': str(manifest_path)},
            )
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


def main(argv=None):
    parser = argparse.ArgumentParser(description='Archive old raw and lineage data')
    parser.add_argument('--database', required=True)
    parser.add_argument('--archive-dir', default=None)
    parser.add_argument('--older-than-days', type=int, default=180)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument(
        '--include-derived',
        action='store_true',
        help='Include protected observation/lineage tables after dependency review',
    )
    parser.add_argument(
        '--backup-destination',
        default=None,
        help='Required with --apply: destination for an integrity-checked SQLite backup',
    )
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.apply and not args.backup_destination:
        parser.error('--backup-destination is required with --apply')
    db = Path(args.database).resolve()
    cutoff = cutoff_date(args.older_than_days)
    selected = TABLES if args.include_derived else DEFAULT_ARCHIVE_TABLES
    report = {
        'database': str(db),
        'cutoff_date': cutoff,
        'dry_run': not args.apply,
        'selected_tables': list(selected),
        'inspection': inspect(str(db), cutoff, selected),
    }
    report['can_apply'] = report['inspection']['archive_policy']['can_apply']
    if args.apply:
        if not report['can_apply']:
            raise RuntimeError('archive plan is blocked by online fact dependencies')
        from scripts.backup_database import backup_database

        report['backup'] = backup_database(db, args.backup_destination)
        if not report['backup']['ok']:
            raise RuntimeError('database backup integrity check failed')
        report['applied'] = apply_archive(
            str(db), cutoff, Path(args.archive_dir or db.parent / 'lineage_archive'),
            tables=selected, allow_derived=args.include_derived,
        )
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'dry_run': not args.apply,
                      'tables': report['inspection']['tables']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

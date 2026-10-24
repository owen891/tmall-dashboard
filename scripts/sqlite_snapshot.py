"""Read-only, WAL-aware snapshots with executable content verification.

The manifest and backup share one explicitly pinned SQLite read transaction.
Hashes cover typed values, NULLs and blobs (not just counts/sums). Verification
after additive migrations projects the original columns, tolerating new schema
but never silently tolerating changes to the snapshotted business values.
"""
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def readonly(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', timeout=30, uri=True)
    connection.execute('PRAGMA query_only=ON')
    return connection


def _quote(value):
    return '"' + value.replace('"', '""') + '"'


def _value(value):
    if value is None:
        return ['null']
    if isinstance(value, bytes):
        return ['blob', value.hex()]
    if isinstance(value, float):
        return ['float', value.hex()]
    return [type(value).__name__, value]


def content_manifest(connection, template=None):
    """Bounded-memory full-value digest; SQLite handles deterministic row sort.

    PRAGMA table_info omits generated columns; these are derived rather than
    stored business inputs. Internal sqlite_* tables are excluded. Batch tables
    are included just like facts, including every batch ID/status/value.
    """
    tables = {}
    names = (sorted(template['tables']) if template is not None else [r[0] for r in
             connection.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                "AND name NOT LIKE 'sqlite_%' ORDER BY name")])
    for name in names:
        info = connection.execute('PRAGMA table_info(' + _quote(name) + ')').fetchall()
        columns = template['tables'][name]['columns'] if template else [r[1] for r in info]
        if not columns or not set(columns).issubset({r[1] for r in info}):
            raise ValueError('SNAPSHOT_SCHEMA_MISMATCH: ' + name)
        selection = ','.join(_quote(c) for c in columns)
        primary = [r[1] for r in sorted(info, key=lambda r: r[5]) if r[5] and r[1] in columns]
        order = ','.join(_quote(c) for c in primary) if primary else selection
        digest = hashlib.sha256()
        count = 0
        totals = {}
        summary_columns = [i for i, c in enumerate(columns) if any(
            word in c.lower() for word in ('amount', 'cost', 'payment', 'sales', 'spend', 'revenue', 'profit', 'refund', 'gmv'))]
        # Explicit names, never SELECT *, allow additive migration verification.
        for row in connection.execute(f'SELECT {selection} FROM {_quote(name)} ORDER BY {order}'):
            payload = json.dumps([_value(v) for v in row], ensure_ascii=True,
                                 separators=(',', ':')).encode('ascii')
            digest.update(len(payload).to_bytes(8, 'big'))
            digest.update(payload)
            count += 1
            for i in summary_columns:
                if isinstance(row[i], (int, float)):
                    totals[columns[i]] = totals.get(columns[i], Decimal(0)) + Decimal(str(row[i]))
        dates = {}
        for column in columns:
            if column in ('date', 'business_date', 'stat_date', 'data_date', 'month', 'created_at'):
                lo, hi = connection.execute(
                    f'SELECT MIN({_quote(column)}),MAX({_quote(column)}) FROM {_quote(name)}').fetchone()
                dates[column] = {'min': lo, 'max': hi}
        tables[name] = {'columns': columns, 'rows': count, 'sha256': digest.hexdigest(), 'dates': dates,
                        'numeric_totals': {c: str(v) for c, v in sorted(totals.items())}}
    schema = connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    schema_digest = hashlib.sha256(json.dumps(schema, ensure_ascii=True).encode('ascii')).hexdigest()
    return {'version': 1, 'tables': tables, 'schema_sha256': schema_digest,
            'batch_summary': {n: t for n, t in tables.items() if 'batch' in n}}


def verify_manifest(path, expected, *, allow_schema_changes=False):
    with closing(readonly(path)) as connection:
        connection.execute('BEGIN')
        integrity_rows = [r[0] for r in connection.execute('PRAGMA integrity_check')]
        if integrity_rows != ['ok']:
            raise ValueError('SNAPSHOT_INTEGRITY_FAILED: ' + '; '.join(integrity_rows))
        actual = content_manifest(connection, expected if allow_schema_changes else None)
        if not allow_schema_changes and actual['schema_sha256'] != expected['schema_sha256']:
            raise ValueError('SNAPSHOT_SCHEMA_MISMATCH')
        if actual['tables'] != expected['tables'] or actual['batch_summary'] != expected['batch_summary']:
            mismatches = [name for name in expected['tables']
                          if actual['tables'].get(name) != expected['tables'][name]]
            raise ValueError('SNAPSHOT_CONTENT_MISMATCH: ' + ', '.join(mismatches))
        return {'integrity': 'ok', 'content_matches': True, 'manifest': actual}


def create_snapshot(source, destination):
    """Create a new verified snapshot; never overwrite, migrate or prune source.

    A failed attempt leaves its partial file WITHOUT a verified sidecar, for
    investigation; it cannot enter managed retention. Callers must choose a new
    destination on retry. Exclusive creation closes the exists()/open race.
    """
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source == destination:
        raise ValueError('backup destination must differ from source')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb'):
        pass
    with closing(readonly(source)) as connection:
        connection.execute('BEGIN')
        # First read pins the snapshot even when the database has no user tables.
        connection.execute('SELECT count(*) FROM sqlite_master').fetchone()
        manifest = content_manifest(connection)
        with closing(sqlite3.connect(destination)) as output:
            connection.backup(output)
    verification = verify_manifest(destination, manifest)
    return {'ok': True, 'source': str(source), 'destination': str(destination),
            'source_sha256': sha256(source), 'destination_sha256': sha256(destination),
            'source_hash_scope': 'main_file_only_not_snapshot_identity',
            'integrity': verification['integrity'], 'manifest': manifest,
            'size_bytes': destination.stat().st_size,
            'snapshot_at': datetime.now(timezone.utc).isoformat()}


def sidecar_path(path):
    return Path(str(path) + '.manifest.json')


def write_verified_sidecar(report):
    path = sidecar_path(report['destination'])
    with path.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=True, indent=2)
        handle.flush()
        import os
        os.fsync(handle.fileno())
    return str(path)

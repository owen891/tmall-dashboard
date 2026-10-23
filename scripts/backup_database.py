"""Create an integrity-checked SQLite backup without mutating the source DB."""

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity(path):
    connection = sqlite3.connect(path)
    try:
        return connection.execute('PRAGMA integrity_check').fetchone()[0]
    finally:
        connection.close()


def backup_database(source, destination=None, *, prune=True):
    """Verified snapshot plus managed retention; experiments use prune=False.

    Positional API remains compatible. The old generic prune primitive still
    has C1-C6 semantics; formal backups now prune ONLY verified sidecar members.
    """
    try:
        from scripts.sqlite_snapshot import create_snapshot, write_verified_sidecar
        from scripts.backup_retention import prune_verified_backups, retention_settings
    except ImportError:
        from sqlite_snapshot import create_snapshot, write_verified_sidecar
        from backup_retention import prune_verified_backups, retention_settings
    source_path = Path(source).resolve()
    if destination is None:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        destination = source_path.parent / 'backups' / f'{source_path.stem}-{stamp}.db'
    # Any exception before the verified sidecar publication exits WITHOUT prune.
    report = create_snapshot(source_path, destination)
    report['manifest_path'] = write_verified_sidecar(report)
    report['pruned'] = []
    if prune:
        try:
            keep, cap = retention_settings()
            retention = {}
            report['pruned'] = [str(item) for item in prune_verified_backups(
                Path(destination).resolve().parent, keep_newest=keep,
                max_total_bytes=cap, protected=[source_path, Path(destination).resolve()],
                report=retention, source=source_path)]
            report['retention'] = retention
            if retention.get('warnings'):
                report['prune_warning'] = '; '.join(retention['warnings'])
        except Exception as error:
            report['pruned'] = None
            report['prune_warning'] = str(error)
    return report


def main():
    parser = argparse.ArgumentParser(description='Create an integrity-checked SQLite backup')
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', default=None)
    parser.add_argument('--no-prune', action='store_true', help='isolated experiment; never prune')
    args = parser.parse_args()
    report = backup_database(args.source, args.destination, prune=not args.no_prune)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()

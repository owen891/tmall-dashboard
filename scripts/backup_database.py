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


def backup_database(source, destination=None):
    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if destination is None:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        destination = source_path.parent / 'backups' / f'{source_path.stem}-{stamp}.db'
    destination_path = Path(destination).resolve()
    if source_path == destination_path:
        raise ValueError('backup destination must differ from source')
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        raise FileExistsError(destination_path)

    source_connection = sqlite3.connect(source_path)
    destination_connection = sqlite3.connect(destination_path)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()

    integrity = _integrity(destination_path)
    return {
        'ok': integrity == 'ok',
        'source': str(source_path),
        'destination': str(destination_path),
        'source_sha256': _sha256(source_path),
        'destination_sha256': _sha256(destination_path),
        'integrity': integrity,
        'size_bytes': destination_path.stat().st_size,
    }


def main():
    parser = argparse.ArgumentParser(description='Create an integrity-checked SQLite backup')
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', default=None)
    args = parser.parse_args()
    report = backup_database(args.source, args.destination)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()

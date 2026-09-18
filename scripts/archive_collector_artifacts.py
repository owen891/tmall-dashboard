"""Archive old collector artifacts without deleting evidence.

Default mode is a dry-run. ``--apply`` copies each eligible artifact to an
archive directory, verifies its hash, updates the database path, and only then
removes the original file.
"""

import argparse
import hashlib
import json
import shutil
import sqlite3
import gzip
from datetime import datetime, timedelta, timezone
from pathlib import Path


def file_hash(path):
    digest = hashlib.sha256()
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def plan_archive(db_path, archive_dir, older_than_days=30):
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    archive_root = Path(archive_dir).resolve()
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            '''SELECT id, run_id, artifact_type, path, sha256, size_bytes, created_at
               FROM collector_artifacts ORDER BY id''').fetchall()
    finally:
        conn.close()
    planned = []
    for row in rows:
        source = Path(row['path']).resolve()
        try:
            created = datetime.fromisoformat(str(row['created_at']).replace('Z', '+00:00'))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if created > cutoff or not source.is_file():
            continue
        target = archive_root / source.name
        planned.append({**dict(row), 'source': str(source), 'target': str(target),
                        'source_exists': True, 'actual_sha256': file_hash(source)})
    return planned


def apply_archive(db_path, planned):
    archive_paths = []
    conn = sqlite3.connect(db_path)
    try:
        try:
            for item in planned:
                if item['actual_sha256'] != item['sha256']:
                    raise ValueError(f"artifact hash mismatch: {item['source']}")
                target = Path(item['target'])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item['source'], target)
                if file_hash(target) != item['sha256']:
                    raise ValueError(f"archive hash mismatch: {target}")
                conn.execute('UPDATE collector_artifacts SET path=? WHERE id=?',
                             (str(target), item['id']))
                archive_paths.append((item['source'], str(target)))
            conn.commit()
        except Exception:
            conn.rollback()
            for _, target in archive_paths:
                Path(target).unlink(missing_ok=True)
            raise
    finally:
        conn.close()
    for source, _ in archive_paths:
        Path(source).unlink(missing_ok=True)
    return len(archive_paths)


def main():
    parser = argparse.ArgumentParser(description='Archive old collector artifacts')
    parser.add_argument('--database', required=True)
    parser.add_argument('--archive-dir', default=None)
    parser.add_argument('--older-than-days', type=int, default=30)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', default=None)
    args = parser.parse_args()
    db = Path(args.database).resolve()
    archive = Path(args.archive_dir or db.parent / 'collector_artifacts_archive')
    planned = plan_archive(str(db), str(archive), args.older_than_days)
    applied = apply_archive(str(db), planned) if args.apply else 0
    report = {'database': str(db), 'archive_dir': str(archive.resolve()),
              'older_than_days': args.older_than_days, 'dry_run': not args.apply,
              'planned_count': len(planned), 'applied_count': applied,
              'items': planned}
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'planned_count': len(planned), 'applied_count': applied,
                      'dry_run': not args.apply}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

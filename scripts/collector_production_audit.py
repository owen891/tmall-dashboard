"""Export a read-only production collector audit bundle."""

import argparse
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def default_collectors_dir():
    candidates = (
        PROJECT_ROOT / 'collectors',
        PROJECT_ROOT.parent / 'BI采集' / 'collectors',
    )
    return str(next((candidate for candidate in candidates if candidate.is_dir()), candidates[0]))


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def database_summary(path):
    target = Path(path).resolve()
    if not target.is_file():
        return {'path': str(target), 'exists': False}
    conn = sqlite3.connect(target)
    try:
        return {
            'path': str(target), 'exists': True, 'size_bytes': target.stat().st_size,
            'sha256': sha256(target),
            'integrity': conn.execute('PRAGMA integrity_check').fetchone()[0],
            'table_count': conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0],
        }
    finally:
        conn.close()


def task_inventory():
    try:
        completed = subprocess.run(
            ['schtasks.exe', '/Query', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, encoding=('mbcs' if os.name == 'nt' else 'utf-8'), errors='replace', timeout=20,
        )
        lines = [line for line in completed.stdout.splitlines()
                 if any(token.lower() in line.lower() for token in
                        ('tmall', 'bi', 'sycm', '万相台', 'backup', '备份'))]
        return {'available': completed.returncode == 0, 'tasks': lines}
    except (OSError, subprocess.SubprocessError) as exc:
        return {'available': False, 'error': str(exc), 'tasks': []}


def build_audit(database, collectors_dir, *, state_file=None, log_dir=None):
    collectors = Path(collectors_dir).resolve()
    state = Path(state_file or PROJECT_ROOT / 'data' / 'collect_state.json')
    logs = Path(log_dir or PROJECT_ROOT / 'logs')
    recent_logs = []
    if logs.is_dir():
        recent_logs = [
            {'name': item.name, 'size_bytes': item.stat().st_size,
             'modified_at': datetime.fromtimestamp(item.stat().st_mtime).isoformat(timespec='seconds')}
            for item in sorted(logs.glob('*.log'), key=lambda item: item.stat().st_mtime, reverse=True)[:30]
        ]
    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'python': platform.python_version(),
        'database': database_summary(database),
        'collector_dir': str(collectors),
        'collector_scripts': [
            {'name': path.name, 'size_bytes': path.stat().st_size, 'sha256': sha256(path)}
            for path in sorted(collectors.glob('*.py'))
        ] if collectors.is_dir() else [],
        'state_file': {
            'path': str(state.resolve()), 'exists': state.is_file(),
            'size_bytes': state.stat().st_size if state.is_file() else 0,
        },
        'scheduled_tasks': task_inventory(),
        'recent_logs': recent_logs,
    }


def main():
    parser = argparse.ArgumentParser(description='Export a read-only collector production audit')
    parser.add_argument('--database', default=os.environ.get('TMALL_DB_PATH', str(PROJECT_ROOT / 'data' / 'dashboard.db')))
    parser.add_argument('--collectors-dir', default=os.environ.get('TMALL_COLLECTORS_DIR') or default_collectors_dir())
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = build_audit(args.database, args.collectors_dir)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'scripts': len(report['collector_scripts']),
                      'tasks_available': report['scheduled_tasks']['available']}, ensure_ascii=False))
    return 0 if report['database'].get('integrity') == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())

"""Create an auditable manifest for the external collector package."""

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(collector_dir):
    root = Path(collector_dir).resolve()
    scripts = []
    for path in sorted(root.glob('*.py')):
        scripts.append({'name': path.name, 'sha256': sha256(path), 'size_bytes': path.stat().st_size})
    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'collector_dir': str(root),
        'python': sys.executable,
        'python_version': platform.python_version(),
        'database_path': os.environ.get('TMALL_DB_PATH', ''),
        'cdp_port': int(os.environ.get('TMALL_CDP_PORT', '9223')),
        'collector_version': os.environ.get('TMALL_COLLECTOR_VERSION', 'unversioned'),
        'scripts': scripts,
    }


def main():
    parser = argparse.ArgumentParser(description='Generate external collector manifest')
    parser.add_argument('--collector-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = build_manifest(args.collector_dir)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'script_count': len(report['scripts'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()

from __future__ import annotations

import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')


def read_version() -> str:
    version = (PROJECT_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f'Invalid desktop version: {version!r}; expected MAJOR.MINOR.PATCH')
    return version


def update_json(path: Path, version: str, *, update_lock_root: bool = False) -> None:
    document = json.loads(path.read_text(encoding='utf-8'))
    document['version'] = version
    if update_lock_root:
        root_package = document.get('packages', {}).get('')
        if isinstance(root_package, dict):
            root_package['version'] = version
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    version = read_version()
    update_json(PROJECT_ROOT / 'desktop' / 'package.json', version)
    lock_path = PROJECT_ROOT / 'desktop' / 'package-lock.json'
    if lock_path.exists():
        update_json(lock_path, version, update_lock_root=True)
    print(version)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Build the bundled Flask backend for the current desktop runner platform."""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / 'packaging' / 'tmall_dashboard_backend.spec'
DIST_PATH = PROJECT_ROOT / 'build' / 'desktop'
WORK_PATH = PROJECT_ROOT / 'build' / 'pyinstaller'
VERSION_PATTERN = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')


def assert_release_version_contract() -> str:
    version_path = PROJECT_ROOT / 'VERSION'
    try:
        version = version_path.read_text(encoding='utf-8').strip()
    except OSError as error:
        raise SystemExit(f'Release VERSION file is unavailable: {version_path}') from error
    if not VERSION_PATTERN.fullmatch(version):
        raise SystemExit(f'Invalid release version: {version!r}; expected MAJOR.MINOR.PATCH')

    package_path = PROJECT_ROOT / 'desktop' / 'package.json'
    package = json.loads(package_path.read_text(encoding='utf-8'))
    if package.get('version') != version:
        raise SystemExit(f'Desktop package version {package.get("version")!r} does not match VERSION {version!r}')

    lock_path = PROJECT_ROOT / 'desktop' / 'package-lock.json'
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding='utf-8'))
        lock_version = lock.get('packages', {}).get('', {}).get('version')
        if lock_version != version:
            raise SystemExit(f'Desktop lock version {lock_version!r} does not match VERSION {version!r}')

    web_version_path = PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'version.js'
    expected_web_version = f'window.TMALL_WEB_VERSION = {json.dumps(version)};\n'
    if web_version_path.read_text(encoding='utf-8') != expected_web_version:
        raise SystemExit(f'Web version asset does not match VERSION {version!r}: {web_version_path}')
    return version


def main() -> int:
    assert_release_version_contract()
    if not SPEC_PATH.is_file():
        raise SystemExit(f'Backend spec not found: {SPEC_PATH}')
    command = [
        sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
        f'--distpath={DIST_PATH}', f'--workpath={WORK_PATH}', str(SPEC_PATH),
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    executable_name = 'TmallDashboardServer.exe' if platform.system() == 'Windows' else 'TmallDashboardServer'
    executable = DIST_PATH / 'backend' / executable_name
    if not executable.is_file():
        raise SystemExit(f'Packaged backend executable was not created: {executable}')
    if platform.system() != 'Windows':
        executable.chmod(executable.stat().st_mode | 0o111)
    print(executable)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

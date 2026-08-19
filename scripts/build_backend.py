"""Build the bundled Flask backend for the current desktop runner platform."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / 'packaging' / 'tmall_dashboard_backend.spec'
DIST_PATH = PROJECT_ROOT / 'build' / 'desktop'
WORK_PATH = PROJECT_ROOT / 'build' / 'pyinstaller'


def main() -> int:
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

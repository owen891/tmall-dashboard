"""Install/resolve only the lockfile-pinned gate browser in an application cache.

Never discover installed Chrome, reuse a user profile, or relax sandbox/ACLs.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sanitize_browser_environment(environ):
    """Strip actual Playwright controls and getFromENV's npm aliases only.

    Keep unrelated npm registry/cache/proxy settings. PWDEBUG has no underscore;
    PWDEBUGIMPL and PWTEST_* are also consumed by the pinned Playwright library.
    DEBUG_FILE would redirect the diagnostics logger outside the owned log root.
    """
    env = dict(environ)
    for key in list(env):
        name = key.upper()
        for prefix in ('NPM_PACKAGE_CONFIG_', 'NPM_CONFIG_'):
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        if (name.startswith(('PLAYWRIGHT_', 'PW_', 'PWDEBUG', 'PWTEST_'))
                or name in ('NODE_OPTIONS', 'NODE_PATH', 'DEBUG_FILE')):
            env.pop(key)
    return env


def browser_installation_root(environ=None, platform=None):
    env = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    if platform == 'win32':
        base = env.get('LOCALAPPDATA')
        if not base:
            # Isolated unit-fixture environments may omit OS variables; do not
            # consult a browser selection or the repository as a fallback.
            base = str(Path.home() / 'AppData' / 'Local')
    elif platform == 'darwin':
        base = str(Path(env.get('HOME') or Path.home()) / 'Library' / 'Caches')
    else:
        base = env.get('XDG_CACHE_HOME') or str(Path(env.get('HOME') or Path.home()) / '.cache')
    base = Path(base)
    if not base.is_absolute():
        raise ValueError('gate browser cache base must be absolute')
    destination = base / 'TmallDashboard' / 'gate-browsers'
    if destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError('gate browser cache must not redirect through symlinks')
    return destination.resolve()


def pinned_playwright(root=ROOT):
    root = Path(root)
    lock = json.loads((root / 'desktop/package-lock.json').read_text(encoding='utf-8'))
    versions = {}
    for name in ('playwright', 'playwright-core'):
        package = root / 'desktop/node_modules' / name
        if package.is_symlink() or not package.resolve().is_relative_to((root / 'desktop/node_modules').resolve()):
            raise ValueError('gate playwright package escaped project dependencies')
        installed = json.loads((package / 'package.json').read_text(encoding='utf-8'))
        expected = lock['packages']['node_modules/' + name]['version']
        if installed.get('name') != name or installed.get('version') != expected:
            raise ValueError('gate playwright version differs from package-lock: ' + name)
        versions[name] = expected
    cli = root / 'desktop/node_modules/playwright/cli.js'
    if not cli.is_file() or cli.is_symlink() or not cli.resolve().is_relative_to(cli.parent.resolve()):
        raise ValueError('gate playwright CLI escaped project dependencies')
    return versions


def installation_environment(environ=None):
    env = dict(os.environ if environ is None else environ)
    destination = browser_installation_root(env)
    # Exact local CLI, no npx resolution, custom executable, mirror or NODE hooks.
    env = sanitize_browser_environment(env)
    env['PLAYWRIGHT_BROWSERS_PATH'] = str(destination)
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-path', action='store_true')
    args = parser.parse_args(argv)
    env = installation_environment()
    versions = pinned_playwright()
    print(json.dumps({'browser_root': env['PLAYWRIGHT_BROWSERS_PATH'], 'versions': versions}), flush=True)
    if args.print_path:
        return 0
    Path(env['PLAYWRIGHT_BROWSERS_PATH']).mkdir(parents=True, exist_ok=True)
    return subprocess.run(['node', str(ROOT / 'desktop/node_modules/playwright/cli.js'),
                           'install', 'chromium'], cwd=ROOT, env=env, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())

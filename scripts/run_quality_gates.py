"""One cross-platform gate plan. No user DB, browser, or service reuse."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

if __package__:
    from .gate_browser_install import browser_installation_root, pinned_playwright, sanitize_browser_environment
else:
    from gate_browser_install import browser_installation_root, pinned_playwright, sanitize_browser_environment

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name('quality_gates.json')
TIERS = {'fast': 0, 'integration': 1, 'release': 2}


def load_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    ids = [gate['id'] for gate in manifest['gates']]
    if manifest['schema_version'] != 1 or len(ids) != len(set(ids)):
        raise ValueError('invalid gate manifest')
    return manifest


def selected_gates(tier):
    return [gate for gate in load_manifest()['gates'] if TIERS[gate['tier']] <= TIERS[tier]]


def isolated_environment(directory, inherited=None):
    directory = Path(directory).resolve(strict=True)
    env = dict(os.environ if inherited is None else inherited)
    browser_root = browser_installation_root(env)
    env = sanitize_browser_environment(env)
    # The manifest, not a shell's pytest options/plugins/import paths, owns
    # collection. PYTHONPATH can inject sitecustomize before pytest starts;
    # PYTHONOPTIMIZE can remove assertions in imported helpers.
    for key in list(env):
        if key.upper().startswith(('PYTEST_', 'PYTHON')):
            env.pop(key)
    # Do not inherit a user's service/browser/collector selection. The category
    # label and legacy shop id are deployment-private: leaving them set makes
    # category-filtered fixtures resolve to a label the seeded rows do not
    # carry, so local gates fail on data that CI never has.
    for key in ('DATABASE_URL', 'TMALL_PORT', 'TMALL_SMOKE_BASE', 'BASE', 'TMALL_CDP_PORT',
                'TMALL_CHROME', 'TMALL_CHROME_PATH', 'PW_CHROMIUM', 'NODE_OPTIONS',
                'TMALL_SHOP_ID', 'TMALL_LEGACY_SHOP_ID', 'TMALL_CATEGORY_LABEL',
                'TMALL_CAPABILITY_ONLY', 'TMALL_SMOKE_PAGE',
                'TMALL_GATE_SERVER_MODE', 'TMALL_GATE_PORT', 'TMALL_GATE_READY',
                'TMALL_GATE_BROWSER_SCOPE', 'TMALL_GATE_PYTEST_PHASE'):
        env.pop(key, None)
    for key, relative in {'TMALL_DB_PATH': 'data/dashboard.db',
                          'TMALL_UPLOAD_FOLDER': 'uploads',
                          'IMPORT_SCAN_ALLOWED_ROOTS': 'inbox',
                          'APPDATA': 'roaming', 'LOCALAPPDATA': 'local',
                          'TMALL_ASSET_RELEASE_ROOT': 'frontend-releases',
                          'TMP': 'tmp', 'TEMP': 'tmp', 'TMPDIR': 'tmp'}.items():
        target = directory / relative
        (target.parent if key == 'TMALL_DB_PATH' else target).mkdir(parents=True, exist_ok=True)
        env[key] = str(target)
    env.update({'TMALL_GATE_ROOT': str(directory), 'TMALL_GATE_NONCE': secrets.token_hex(24),
                'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1', 'PYTHONWARNINGS': 'error::ResourceWarning',
                'PYTHONNOUSERSITE': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                'DASHBOARD_USERNAME': 'gate-fixture', 'DASHBOARD_PASSWORD': secrets.token_hex(24),
                'PLAYWRIGHT_BROWSERS_PATH': str(browser_root)})
    for key in ('NO_PROXY', 'no_proxy'):
        values = [v.strip() for v in env.get(key, '').split(',') if v.strip()]
        env[key] = ','.join(dict.fromkeys([*values, '127.0.0.1', 'localhost', '::1']))
    return env


def stop_owned(process):
    """Only a live Popen handle created by this runner is ever terminated."""
    if process.poll() is None:
        if os.name == 'nt':
            # The exact live child's tree, never an image name or port owner.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def verify_owner(record, process, env, opener=None):
    if process.poll() is not None:
        raise RuntimeError('owned service exited before readiness')
    port = record.get('port')
    if not isinstance(port, int) or port <= 1023 or port in (5000, 9223):
        raise RuntimeError('unsafe gate service port')
    if record.get('pid') != process.pid or record.get('nonce') != env['TMALL_GATE_NONCE']:
        raise RuntimeError('gate service ownership mismatch')
    base = f'http://127.0.0.1:{port}'
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base + '/__gate_owner/' + env['TMALL_GATE_NONCE'], timeout=2) as response:
        actual = json.load(response)
    if actual != record:
        raise RuntimeError('gate service nonce handshake mismatch')
    return base


@contextmanager
def owned_service(env, log_directory):
    env = dict(env)
    ready = Path(env['TMALL_GATE_ROOT']) / ('service-ready-' + secrets.token_hex(12) + '.json')
    env['TMALL_GATE_READY'] = str(ready)
    with (log_directory / 'service.stdout.txt').open('wb') as stdout, (log_directory / 'service.stderr.txt').open('wb') as stderr:
        # Windows venv python.exe is a redirector with a different child PID.
        # Launch the base interpreter directly, retaining this venv's imports,
        # so the readiness PID is the exact owned Popen handle on both OSes.
        bootstrap = f'import sys,runpy;sys.path[:0]={sys.path!r};runpy.run_path({str(ROOT / "scripts/run_test_server.py")!r},run_name="__main__")'
        process = subprocess.Popen([getattr(sys, '_base_executable', sys.executable), '-W', 'error::ResourceWarning', '-c', bootstrap],
                                   cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                                   start_new_session=os.name != 'nt')
        try:
            deadline = time.monotonic() + 30
            while not ready.exists():
                if process.poll() is not None:
                    raise RuntimeError(f'test server exited: {process.returncode}')
                if time.monotonic() >= deadline:
                    raise TimeoutError('owned test server readiness timed out')
                time.sleep(.05)
            record = json.loads(ready.read_text())
            base = verify_owner(record, process, env)
            yield base, record
        finally:
            stop_owned(process)


def commands(gate, values):
    if gate.get('kind') == 'js-syntax':
        return [['node', '--check', str(path)] for path in sorted((ROOT / 'frontend/ui_demo/assets').rglob('*.js'))]
    if gate.get('kind') == 'browser-pytest':
        return [[sys.executable, '-W', 'error::ResourceWarning', '-m', 'pytest',
                 *load_manifest()['browser_pytest_nodes'], '-q', '-p', 'scripts.gate_pytest_plugin',
                 '-W', 'error::pytest.PytestUnraisableExceptionWarning',
                 '-W', 'error::pytest.PytestUnhandledThreadExceptionWarning', '-o', 'addopts=']]
    return [[argument.format(**values) for argument in gate['argv']]]


def execute(command, env, logs, label, timeout=900):
    with (logs / f'{label}.stdout.txt').open('wb') as stdout, (logs / f'{label}.stderr.txt').open('wb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                                   start_new_session=os.name != 'nt')
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            stop_owned(process)
            raise
    (logs / f'{label}.exit.txt').write_text(str(code))
    print(f'{label}: exit={code}', flush=True)
    if code:
        raise RuntimeError(f'gate {label} failed; see {logs}')
    # Finalizer warnings can be printed after pytest has finished and still
    # leave a zero process exit status. Preserve that literal status, but fail
    # the gate rather than treating interpreter-shutdown leaks as success.
    errors = (logs / f'{label}.stderr.txt').read_text(encoding='utf-8', errors='replace')
    if any('ResourceWarning:' in line for line in errors.splitlines()):
        raise RuntimeError(f'gate {label} emitted ResourceWarning despite exit 0; see {logs}')


def configure_browser(env, base, record):
    versions = pinned_playwright(ROOT)
    expression = "process.stdout.write(require('./desktop/node_modules/playwright').chromium.executablePath())"
    executable = subprocess.check_output(['node', '-e', expression], cwd=ROOT, env=env, text=True, timeout=20).strip()
    path = Path(executable).resolve(strict=True)
    if not path.is_file() or not path.is_relative_to(Path(env['PLAYWRIGHT_BROWSERS_PATH']).resolve()):
        raise RuntimeError('browser is outside the dedicated gate installation')
    for key in ('TMALL_CHROME', 'TMALL_CHROME_PATH', 'PW_CHROMIUM'):
        env[key] = str(path)
    env['TMALL_SMOKE_BASE'] = base
    scope = {'root': env['TMALL_GATE_ROOT'], 'base': base, 'nonce': record['nonce'],
             'browser': str(path), 'browser_root': env['PLAYWRIGHT_BROWSERS_PATH'],
             'playwright_versions': versions}
    marker = Path(env['TMALL_GATE_ROOT']) / 'browser-scope.json'
    marker.write_text(json.dumps(scope), encoding='utf-8')
    env['TMALL_GATE_BROWSER_SCOPE'] = str(marker)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier', choices=TIERS, default='fast')
    parser.add_argument('--list', action='store_true', help='print plan without executing or creating fixtures')
    parser.add_argument('--log-dir', type=Path)
    args = parser.parse_args(argv)
    gates = selected_gates(args.tier)
    if args.list:
        print(json.dumps({'tier': args.tier, 'gates': gates, 'browser_pytest_nodes': load_manifest()['browser_pytest_nodes']}, indent=2))
        return 0
    logs = (args.log_dir or Path(tempfile.mkdtemp(prefix='tmall-gate-logs-'))).resolve()
    logs.mkdir(parents=True, exist_ok=True)
    print(f'GATE_LOGS={logs}', flush=True)
    with tempfile.TemporaryDirectory(prefix='tmall-gates-') as directory:
        env = isolated_environment(directory)
        values = {'python': sys.executable, 'npm': shutil.which('npm') or 'npm',
                  'database': env['TMALL_DB_PATH'], 'production_port': '0'}
        ledger = []
        def run(gate):
            local_env = dict(env, **gate.get('env', {}))
            if gate['tier'] == 'integration':
                # Playwright otherwise hides successful launch stderr. Its
                # browser logger records child argv/stdout/stderr into execute's
                # persistent stderr file; CDP launches also retain raw files.
                local_env['DEBUG'] = 'pw:browser'
            if gate['id'] == 'browser-pytest':
                local_env['TMALL_GATE_PYTEST_PHASE'] = 'browser'
            for index, command in enumerate(commands(gate, values)):
                ledger.append({'id': gate['id'], 'command': command, 'database': env['TMALL_DB_PATH']})
                (logs / 'commands.json').write_text(json.dumps(ledger, indent=2))
                execute(command, local_env, logs, f"{gate['id']}-{index}")
        for gate in gates:
            if gate['tier'] == 'fast':
                run(gate)
        if TIERS[args.tier] >= TIERS['integration']:
            # Unit tests may deliberately mutate their default fixture. Browser
            # gates and release checks must not inherit that mutable state.
            integration_data = Path(directory) / 'integration'
            integration_data.mkdir()
            env['TMALL_DB_PATH'] = str(integration_data / 'dashboard.db')
            env['TMALL_ASSET_RELEASE_ROOT'] = str(integration_data / 'frontend-releases')
            with owned_service(env, logs) as (base, record):
                configure_browser(env, base, record)
                try:
                    for gate in gates:
                        if gate['tier'] == 'integration':
                            run(gate)
                finally:
                    diagnostics = Path(directory) / 'browser-diagnostics'
                    if diagnostics.exists():
                        shutil.copytree(diagnostics, logs / ('browser-diagnostics-' + env['TMALL_GATE_NONCE']),
                                        dirs_exist_ok=False)
        release_data = Path(directory) / 'release'
        release_data.mkdir()
        env['TMALL_DB_PATH'] = str(release_data / 'dashboard.db')
        env['TMALL_ASSET_RELEASE_ROOT'] = str(release_data / 'frontend-releases')
        values['database'] = env['TMALL_DB_PATH']
        for gate in gates:
            if gate['tier'] == 'release':
                run(gate)
    print('QUALITY_GATES_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Pure install/resolution contracts; never downloads or launches a browser."""
import io
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from scripts import gate_browser_install as install
from scripts import run_quality_gates as gates


class GateBrowserInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gate-install-contract-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        packages = {}
        for name in ('playwright', 'playwright-core'):
            package = self.root / 'desktop/node_modules' / name
            package.mkdir(parents=True)
            (package / 'package.json').write_text(json.dumps({'name': name, 'version': '1.55.0'}))
            packages['node_modules/' + name] = {'version': '1.55.0'}
        (self.root / 'desktop/node_modules/playwright/cli.js').write_text('// fixture, never executed')
        (self.root / 'desktop/package-lock.json').write_text(json.dumps({'packages': packages}))

    def test_platform_cache_is_outside_repository_and_ignores_browser_override(self):
        for platform, suffix in [('win32', Path()), ('darwin', Path('Library/Caches')), ('linux', Path('.cache'))]:
            with self.subTest(platform=platform):
                env = {'LOCALAPPDATA': str(self.root), 'HOME': str(self.root),
                       'PLAYWRIGHT_BROWSERS_PATH': '/foreign', 'TMALL_CHROME': '/user/chrome'}
                self.assertEqual(install.browser_installation_root(env, platform),
                                 (self.root / suffix / 'TmallDashboard/gate-browsers').resolve())
        with self.assertRaises(ValueError):
            install.browser_installation_root({'LOCALAPPDATA': 'relative'}, 'win32')

    def test_isolation_resolves_cache_before_replacing_appdata_and_drops_mirrors(self):
        inherited = {'LOCALAPPDATA': str(self.root / 'host-local'),
                'HOME': str(self.root / 'host-home'), 'NODE_PATH': '/foreign',
                'PLAYWRIGHT_BROWSERS_PATH': '/user-browser', 'PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH': '/user',
                'PLAYWRIGHT_DOWNLOAD_HOST': 'https://untrusted.invalid', 'PW_CHROMIUM': '/user'}
        env = gates.isolated_environment(self.root, inherited)
        self.assertEqual(env['PLAYWRIGHT_BROWSERS_PATH'], str(install.browser_installation_root(inherited)))
        self.assertNotEqual(Path(env['PLAYWRIGHT_BROWSERS_PATH']), self.root / 'local/TmallDashboard/gate-browsers')
        self.assertNotIn('PLAYWRIGHT_DOWNLOAD_HOST', env)
        self.assertNotIn('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH', env)
        self.assertNotIn('NODE_PATH', env)
        self.assertNotIn('PW_CHROMIUM', env)

    def test_installed_packages_must_match_lock_and_cli_must_exist(self):
        self.assertEqual(install.pinned_playwright(self.root)['playwright'], '1.55.0')
        package = self.root / 'desktop/node_modules/playwright-core/package.json'
        package.write_text(json.dumps({'name': 'playwright-core', 'version': '0.0.0'}))
        with self.assertRaisesRegex(ValueError, 'package-lock'):
            install.pinned_playwright(self.root)
        package.write_text(json.dumps({'name': 'playwright-core', 'version': '1.55.0'}))
        (self.root / 'desktop/node_modules/playwright/cli.js').unlink()
        with self.assertRaisesRegex(ValueError, 'CLI'):
            install.pinned_playwright(self.root)

    def test_install_uses_exact_project_cli_and_no_inherited_node_or_mirror(self):
        inherited = {'LOCALAPPDATA': str(self.root), 'HOME': str(self.root), 'NODE_OPTIONS': '--require foreign',
                     'NODE_PATH': '/foreign', 'PLAYWRIGHT_DOWNLOAD_HOST': 'https://foreign.invalid'}
        env = install.installation_environment(inherited)
        self.assertNotIn('NODE_OPTIONS', env)
        self.assertNotIn('NODE_PATH', env)
        self.assertNotIn('PLAYWRIGHT_DOWNLOAD_HOST', env)
        with patch.object(install, 'ROOT', self.root), patch.object(install, 'pinned_playwright', return_value={'playwright': '1.55.0'}), \
             patch.object(install, 'installation_environment', return_value=env), \
             patch.object(install.subprocess, 'run', return_value=Mock(returncode=0)) as run, \
             patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(install.main([]), 0)
            self.assertEqual(run.call_args.args[0], ['node', str(self.root / 'desktop/node_modules/playwright/cli.js'), 'install', 'chromium'])
            run.reset_mock()
            self.assertEqual(install.main(['--print-path']), 0)
            run.assert_not_called()

    def test_version_failure_never_starts_installer_or_resolver(self):
        with patch.object(install, 'pinned_playwright', side_effect=ValueError('lock mismatch')), \
             patch.object(install.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                install.main([])
            run.assert_not_called()
        with patch.object(gates, 'pinned_playwright', side_effect=ValueError('lock mismatch')), \
             patch.object(gates.subprocess, 'check_output') as resolve:
            with self.assertRaises(ValueError):
                gates.configure_browser({}, '', {})
            resolve.assert_not_called()

    def test_foreign_executable_cannot_create_browser_scope(self):
        foreign = self.root / 'user-browser.exe'
        foreign.write_text('not executable')
        dedicated = self.root / 'dedicated'
        dedicated.mkdir()
        env = {'PLAYWRIGHT_BROWSERS_PATH': str(dedicated), 'TMALL_GATE_ROOT': str(self.root)}
        with patch.object(gates, 'pinned_playwright', return_value={}), \
             patch.object(gates.subprocess, 'check_output', return_value=str(foreign)):
            with self.assertRaisesRegex(RuntimeError, 'outside'):
                gates.configure_browser(env, 'http://127.0.0.1:49001', {'nonce': 'a' * 48})
        self.assertFalse((self.root / 'browser-scope.json').exists())

    def test_browser_failure_preserves_raw_diagnostics_outside_temporary_scope(self):
        @contextmanager
        def owned(env, logs):
            yield 'http://127.0.0.1:49001', {'nonce': env['TMALL_GATE_NONCE']}
        def execute(command, env, logs, label):
            self.assertEqual(env['DEBUG'], 'pw:browser')
            raw = Path(env['TMALL_GATE_ROOT']) / 'browser-diagnostics/owned-launch'
            raw.mkdir(parents=True)
            (raw / 'stderr.txt').write_text('REAL_DIAGNOSTIC_SENTINEL')
            raise RuntimeError('gate failed')
        logs = self.root / 'persistent-logs'
        with patch.object(gates, 'selected_gates', return_value=[{'id': 'fixture', 'tier': 'integration', 'argv': ['mock']}]), \
             patch.object(gates, 'owned_service', owned), patch.object(gates, 'configure_browser'), \
             patch.object(gates, 'execute', side_effect=execute), patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaisesRegex(RuntimeError, 'gate failed'):
                gates.main(['--tier', 'integration', '--log-dir', str(logs)])
        retained = list(logs.glob('browser-diagnostics-*/owned-launch/stderr.txt'))
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].read_text(), 'REAL_DIAGNOSTIC_SENTINEL')

    def test_actual_pinned_playwright_cannot_consume_debug_or_mirror_aliases(self):
        # Real installed library in fresh Node children: no browser/network API.
        install.pinned_playwright(gates.ROOT)
        library = gates.ROOT / 'desktop/node_modules/playwright-core/lib/server/utils'
        script = ("const p=" + json.dumps(str(library)) + ";"
                  "const path=require('node:path');"
                  "const read=require(path.join(p,'env.js')).getFromENV;"
                  "require(path.join(p,'debugLogger.js'));"
                  "console.log(JSON.stringify({debug:require(path.join(p,'debug.js')).debugMode(),"
                  "mirror:read('PLAYWRIGHT_DOWNLOAD_HOST')||null,"
                  "chromiumMirror:read('PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST')||null,"
                  "debugFile:process.env.DEBUG_FILE||null}));")
        prefixes = ('', 'npm_config_', 'npm_package_config_')
        cases = [{}]
        for prefix in prefixes:
            for key, value in [('PWDEBUG', '1'), ('PLAYWRIGHT_DOWNLOAD_HOST', 'https://foreign.invalid'),
                               ('PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST', 'https://chromium.invalid')]:
                cases.append({prefix + (key.lower() if prefix else key): value})
        for mode in ('gate', 'install'):
            for index, poison in enumerate(cases):
                with self.subTest(mode=mode, poison=poison):
                    redirect = self.root / f'forbidden-log-{mode}-{index}.txt'
                    inherited = dict(os.environ, npm_config_registry='https://registry.npmjs.org',
                        npm_config_user_agent='fixture-package-manager', HTTP_PROXY='http://proxy.invalid:9',
                        DEBUG_FILE=str(redirect), PWDEBUGIMPL='1', PWTEST_WATCH='1')
                    inherited.update(poison)
                    env = gates.isolated_environment(self.root, inherited) if mode == 'gate' else install.installation_environment(inherited)
                    self.assertEqual(env['npm_config_registry'], inherited['npm_config_registry'])
                    self.assertEqual(env['npm_config_user_agent'], inherited['npm_config_user_agent'])
                    self.assertEqual(env['HTTP_PROXY'], inherited['HTTP_PROXY'])
                    result = subprocess.run(['node', '-e', script], cwd=gates.ROOT, env=env,
                        capture_output=True, text=True, encoding='utf-8', timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), {'debug': '', 'mirror': None, 'chromiumMirror': None, 'debugFile': None})
                    self.assertNotIn('PWDEBUGIMPL', env)
                    self.assertNotIn('PWTEST_WATCH', env)
                    self.assertFalse(redirect.exists())

    def test_alias_sanitizer_is_case_insensitive_and_retains_unrelated_npm(self):
        env = {'NPM_CONFIG_PWDEBUG': '1', 'Npm_Package_Config_Playwright_Download_Host': 'foreign',
               'npm_config_cache': '/npm-cache', 'npm_config_registry': 'registry', 'PWD': '/working',
               'npm_config_debug_file': '/foreign-log'}
        self.assertEqual(install.sanitize_browser_environment(env),
                         {'npm_config_cache': '/npm-cache', 'npm_config_registry': 'registry', 'PWD': '/working'})

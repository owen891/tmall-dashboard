"""Safety contracts: only mocks, temporary files and unused local sockets."""
import ast
import io
import json
import os
import sqlite3
import shutil
import sys
from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import run_quality_gates as gates
from scripts import run_test_server as service


class GateRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gate-contract-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = gates.isolated_environment(self.root, {'HTTP_PROXY': 'http://proxy.invalid:9', 'NO_PROXY': 'internal'})

    def test_environment_drops_user_browser_and_production_selection_not_remote_proxy(self):
        inherited = dict(self.env, TMALL_CDP_PORT='9223', TMALL_SMOKE_BASE='http://127.0.0.1:5000',
                         DATABASE_URL='sqlite:///production.db', TMALL_CHROME='user.exe', BASE='http://remote',
                         # 部署私有的品类标签与店铺 scope：漏进隔离环境会让 fixture
                         # 与断言各按不同标签解析，本地门禁假失败（CI 无此变量）。
                         TMALL_CATEGORY_LABEL='部署私有品类', TMALL_LEGACY_SHOP_ID='3828498662')
        env = gates.isolated_environment(self.root, inherited)
        for key in ('TMALL_CDP_PORT', 'TMALL_SMOKE_BASE', 'DATABASE_URL', 'TMALL_CHROME', 'BASE',
                    'TMALL_CATEGORY_LABEL', 'TMALL_LEGACY_SHOP_ID'):
            self.assertNotIn(key, env)
        self.assertEqual(env['HTTP_PROXY'], inherited['HTTP_PROXY'])
        self.assertIn('internal', env['NO_PROXY'])
        self.assertIn('127.0.0.1', env['NO_PROXY'])
        # isolated_environment resolves its root (macOS: /var -> /private/var),
        # so compare resolved paths instead of the raw temp-dir spelling.
        self.assertTrue(Path(env['TMALL_DB_PATH']).resolve().is_relative_to(self.root.resolve()))
        self.assertEqual(env['PYTHONWARNINGS'], 'error::ResourceWarning')

    def test_inherited_pytest_and_python_controls_cannot_change_the_gate(self):
        poison = dict(os.environ, PYTEST_ADDOPTS='--collect-only', PYTEST_PLUGINS='foreign',
                      PYTEST_DISABLE_PLUGIN_AUTOLOAD='0', PYTEST_FUTURE_OPTION='foreign',
                      PYTHONPATH='foreign', PYTHONHOME='foreign', PYTHONUSERBASE='foreign',
                      PYTHONOPTIMIZE='2', PYTHONSTARTUP='foreign')
        env = gates.isolated_environment(self.root, poison)
        for key in poison:
            if key.upper().startswith(('PYTEST_', 'PYTHON')) and key not in (
                    'PYTHONIOENCODING', 'PYTHONUTF8', 'PYTHONWARNINGS',
                    'PYTHONNOUSERSITE', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD'):
                self.assertNotIn(key, env)
        self.assertEqual(env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'], '1')
        self.assertEqual(env['PYTHONNOUSERSITE'], '1')

    def test_real_pytest_selection_poison_is_blocked_by_actual_runner(self):
        # Real child pytest + production gate plugin; no browser or app import.
        for mode in ('ignore', 'keyword', 'collect_only', 'plugin', 'pythonpath', 'ini', 'control'):
            with self.subTest(mode=mode):
                root = self.root / mode
                (root / 'tests').mkdir(parents=True)
                (root / 'scripts').mkdir()
                (root / 'scripts/__init__.py').write_text('')
                for name in ('gate_pytest_plugin.py', 'quality_gates.json'):
                    shutil.copyfile(gates.ROOT / 'scripts' / name, root / 'scripts' / name)
                (root / 'tests/test_ui_system_contract.py').write_text(
                    'def test_date_picker_smoke_gate_runs_when_chrome_available():\n assert False\n')
                (root / 'tests/test_control.py').write_text('def test_control():\n assert True\n')
                (root / 'tests/test_required.py').write_text(
                    'def test_required():\n ' + ('assert True\n' if mode == 'control' else 'assert False, "MUST_RUN_SENTINEL"\n'))
                poison = dict(os.environ)
                options = {'ignore': '--ignore=tests/test_required.py', 'keyword': '-k control',
                           'collect_only': '--collect-only'}
                if mode in options:
                    poison['PYTEST_ADDOPTS'] = options[mode]
                if mode == 'plugin':
                    (root / 'foreign_plugin.py').write_text(
                        'def pytest_collection_modifyitems(items):\n items[:]=[i for i in items if "test_required" not in i.nodeid]\n')
                    poison['PYTEST_PLUGINS'] = 'foreign_plugin'
                if mode == 'pythonpath':
                    injection = root / 'injected'
                    injection.mkdir()
                    (injection / 'sitecustomize.py').write_text(
                        'import os\nos.environ["PYTEST_ADDOPTS"]="--ignore=tests/test_required.py"\n')
                    poison['PYTHONPATH'] = str(injection)
                if mode == 'ini':
                    (root / 'pytest.ini').write_text('[pytest]\naddopts=--ignore=tests/test_required.py\n')
                env = gates.isolated_environment(root, poison)
                command = gates.commands(gates.selected_gates('fast')[0], {'python': sys.executable})[0]
                with patch.object(gates, 'ROOT', root):
                    if mode == 'control':
                        gates.execute(command, env, root, mode)
                    else:
                        with self.assertRaises(RuntimeError):
                            gates.execute(command, env, root, mode)
                self.assertEqual((root / f'{mode}.exit.txt').read_text(), '0' if mode == 'control' else '1')
                output = (root / f'{mode}.stdout.txt').read_text(encoding='utf-8')
                self.assertIn('2 passed, 1 deselected' if mode == 'control' else 'MUST_RUN_SENTINEL', output)

    def test_all_old_ci_gates_and_additive_tiers(self):
        fast, integration, release = [set(g['id'] for g in gates.selected_gates(tier)) for tier in gates.TIERS]
        self.assertLess(fast, integration)
        self.assertLess(integration, release)
        self.assertEqual(integration - fast, {'browser-pytest', 'core-pages', 'browser-prd', 'browser-capability',
                                            'core-interactions', 'ui-contrast', 'popover', 'date-picker'})
        self.assertEqual(release - integration, {'production-preflight', 'production-smoke', 'release-audit'})
        self.assertTrue({'pytest', 'js-syntax', 'frontend-runtime', 'static-release-runtime', 'ui-contract',
                         'css-syntax', 'design-system', 'css-tokens', 'event-binding', 'frontend-types',
                         'desktop-test', 'desktop-build'} <= fast)
        self.assertEqual(gates.selected_gates('fast')[0]['argv'][5:7], ['tests', '-q'])

    def test_list_never_starts_process_or_creates_fixtures(self):
        with patch.object(gates.subprocess, 'Popen', side_effect=AssertionError('NO_PROCESS')), \
             patch.object(gates.tempfile, 'TemporaryDirectory', side_effect=AssertionError('NO_FIXTURE')), \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(gates.main(['--tier', 'release', '--list']), 0)
            self.assertEqual(json.loads(output.getvalue())['tier'], 'release')

    def test_zero_exit_shutdown_resource_warning_still_fails_gate(self):
        process = Mock()
        process.wait.return_value = 0
        def spawn(*args, **kwargs):
            kwargs['stderr'].write(b'ResourceWarning: Implicitly cleaning up TemporaryDirectory\n')
            return process
        with patch.object(gates.subprocess, 'Popen', side_effect=spawn):
            with self.assertRaisesRegex(RuntimeError, 'ResourceWarning despite exit 0'):
                gates.execute(['mock'], self.env, self.root, 'late-warning')
        self.assertEqual((self.root / 'late-warning.exit.txt').read_text(), '0')
        self.assertIn('ResourceWarning:', (self.root / 'late-warning.stderr.txt').read_text())

    def test_zero_exit_normal_stderr_is_preserved_without_failure(self):
        process = Mock()
        process.wait.return_value = 0
        def spawn(*args, **kwargs):
            kwargs['stderr'].write(b'ordinary diagnostic\n')
            return process
        with patch.object(gates.subprocess, 'Popen', side_effect=spawn):
            gates.execute(['mock'], self.env, self.root, 'ordinary')
        self.assertEqual((self.root / 'ordinary.exit.txt').read_text(), '0')

    def test_service_rejects_missing_and_escaped_paths_before_factory_or_socket(self):
        factory, binder = Mock(), Mock()
        for mutation in ({'TMALL_GATE_NONCE': ''}, {'TMALL_DB_PATH': str(self.root.parent / 'production.db')},
                         {'TMALL_ASSET_RELEASE_ROOT': str(self.root.parent / 'assets')}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                service.serve(dict(self.env, **mutation), factory, binder)
        factory.assert_not_called()
        binder.assert_not_called()

    def test_bind_failure_never_initializes_database(self):
        factory = Mock()
        with self.assertRaisesRegex(OSError, 'occupied'):
            service.serve(self.env, factory, Mock(side_effect=OSError('occupied')))
        factory.assert_not_called()
        self.assertFalse(Path(self.env['TMALL_DB_PATH']).exists())

    def test_factory_failure_closes_owned_listener(self):
        server = Mock(server_port=49001)
        with self.assertRaisesRegex(RuntimeError, 'factory-failed'):
            service.serve(self.env, Mock(side_effect=RuntimeError('factory-failed')), Mock(return_value=server))
        server.server_close.assert_called_once()
        server.serve_forever.assert_not_called()

    def test_nonce_pid_and_port_mismatch_never_connects(self):
        process = Mock(pid=42)
        process.poll.return_value = None
        record = {'pid': 42, 'port': 49001, 'nonce': self.env['TMALL_GATE_NONCE']}
        opener = Mock()
        for mutation in ({'pid': 41}, {'nonce': 'foreign'}, {'port': 5000}, {'port': 9223}):
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                gates.verify_owner(dict(record, **mutation), process, self.env, opener)
        opener.open.assert_not_called()

    def test_health_body_must_match_exact_owned_record(self):
        process = Mock(pid=42)
        process.poll.return_value = None
        record = {'pid': 42, 'port': 49001, 'nonce': self.env['TMALL_GATE_NONCE']}
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps(record).encode())
        self.assertEqual(gates.verify_owner(record, process, self.env, opener), 'http://127.0.0.1:49001')
        opener.open.return_value = io.BytesIO(b'{"ok":true}')
        with self.assertRaisesRegex(RuntimeError, 'handshake'):
            gates.verify_owner(record, process, self.env, opener)

    def test_already_exited_process_is_not_killed(self):
        process = Mock()
        process.poll.return_value = 1
        with patch.object(gates.subprocess, 'run') as run:
            gates.stop_owned(process)
        run.assert_not_called()
        process.kill.assert_not_called()

    def test_handshake_failure_stops_only_owned_process(self):
        process = Mock(pid=42)
        process.poll.return_value = None
        def spawn(*args, **kwargs):
            Path(kwargs['env']['TMALL_GATE_READY']).write_text('{}')
            return process
        with patch.object(gates.subprocess, 'Popen', side_effect=spawn), \
             patch.object(gates, 'verify_owner', side_effect=RuntimeError('forged')), \
             patch.object(gates, 'stop_owned') as stop:
            with self.assertRaisesRegex(RuntimeError, 'forged'):
                with gates.owned_service(self.env, self.root):
                    self.fail('must not yield')
        stop.assert_called_once_with(process)

    def test_smoke_does_not_reference_or_copy_user_db_and_preserves_test_count(self):
        source = (gates.ROOT / 'tests/test_smoke.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        self.assertNotIn('_SOURCE_DB_PATH', source)
        self.assertNotIn('copy2(', source)
        self.assertEqual(sum(isinstance(n, ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(tree)), 55)
        self.assertEqual(sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr.startswith('assert') for n in ast.walk(tree)), 96)

    def test_unknown_future_tests_stay_selected_and_browser_has_explicit_owner(self):
        from scripts import gate_pytest_plugin as plugin
        browser = gates.load_manifest()['browser_pytest_nodes'][0]
        items = [Mock(nodeid=browser), Mock(nodeid='tests/new_future_test.py::test_unknown')]
        config = Mock()
        with patch.dict(os.environ, {'TMALL_GATE_PYTEST_PHASE': 'fast'}):
            plugin.pytest_collection_modifyitems(config, items)
        self.assertEqual([item.nodeid for item in items], ['tests/new_future_test.py::test_unknown'])
        config.hook.pytest_deselected.assert_called_once()
        with patch.dict(os.environ, {'TMALL_GATE_PYTEST_PHASE': 'browser'}):
            selected = [Mock(nodeid=browser)]
            plugin.pytest_collection_modifyitems(config, selected)
            self.assertEqual(len(selected), 1)

    def test_skips_are_failures_not_gate_success(self):
        from scripts import gate_pytest_plugin as plugin
        with patch.object(plugin, '_skips', []):
            session = Mock(exitstatus=0)
            plugin.pytest_sessionfinish(session, 0)
            self.assertEqual(session.exitstatus, 0)
            plugin.pytest_runtest_logreport(Mock(skipped=True, nodeid='fixture-skip', longrepr=('fixture', 1, 'Skipped: invented reason')))
            plugin.pytest_sessionfinish(session, 0)
            self.assertEqual(session.exitstatus, 1)

    def test_existing_skip_requires_exact_node_reason_and_active_platform_condition(self):
        from scripts import gate_pytest_plugin as plugin
        node = 'tests/test_auto_collect_launcher.py::AutoCollectLauncherTests::test_bi_sources_and_utf8_logs'
        with patch.object(plugin.sys, 'platform', 'darwin'):
            self.assertTrue(plugin.allowed_existing_skip(node, 'Windows launcher'))
            self.assertFalse(plugin.allowed_existing_skip(node + '_new', 'Windows launcher'))
            self.assertFalse(plugin.allowed_existing_skip(node, 'new reason'))
        with patch.object(plugin.sys, 'platform', 'win32'), patch.object(plugin.shutil, 'which', return_value='powershell.exe'):
            self.assertFalse(plugin.allowed_existing_skip(node, 'Windows launcher'))
        external = 'tests/test_sycm_item_flow_collector.py::SycmItemFlowCollectorTests::test_call_api_retries_empty_response'
        with patch.dict(os.environ, {'TMALL_SYCM_ITEM_FLOW_COLLECTOR': str(self.root / 'absent.py')}):
            self.assertTrue(plugin.allowed_existing_skip(external, 'external sycm item-flow collector is unavailable'))
        (self.root / 'present.py').write_text('# fixture')
        with patch.dict(os.environ, {'TMALL_SYCM_ITEM_FLOW_COLLECTOR': str(self.root / 'present.py')}):
            self.assertFalse(plugin.allowed_existing_skip(external, 'external sycm item-flow collector is unavailable'))

    def test_all_browser_entrypoints_consume_scope_and_keep_existing_ui_assertions(self):
        for name in ('smoke_core_pages', 'browser_prd_gates', 'audit_core_interactions', 'audit_ui_contrast'):
            with self.subTest(name=name):
                source = (gates.ROOT / f'scripts/{name}.cjs').read_text(encoding='utf-8')
                self.assertIn('gateChromium()', source)
                self.assertIn('assertBase(', source)
                self.assertNotIn('connectOverCDP(', source)
        for name in ('smoke_popover', 'smoke_date_picker'):
            source = (gates.ROOT / f'scripts/{name}.cjs').read_text(encoding='utf-8')
            self.assertIn('await launchGateChrome(BASE)', source)
            self.assertIn('safeSocketUrl(socketUrl, owned.port)', source)
            self.assertNotIn('findChrome', source)
            self.assertNotIn('[SKIP]', source)

    def test_deterministic_fixture_is_repeatable_and_has_positive_september_sales(self):
        from scripts.gate_fixture import seed_database
        results = []
        for name in ('one.db', 'two.db'):
            database = self.root / name
            with closing(sqlite3.connect(database)) as connection:
                connection.executescript('''
                    CREATE TABLE products (product_id TEXT PRIMARY KEY, title TEXT, tier TEXT, style TEXT, status TEXT, shop_label TEXT);
                    CREATE TABLE daily_data (product_id TEXT, date TEXT, ipv INTEGER, pv INTEGER,
                        payment_amount REAL, buyers INTEGER, net_sales REAL, shop_id TEXT,
                        PRIMARY KEY (product_id, date, shop_id));
                    CREATE TABLE monthly_data (product_id TEXT, month TEXT,
                        payment_amount REAL, net_sales REAL, visitors INTEGER, buyers INTEGER,
                        PRIMARY KEY (product_id, month));
                ''')
                seed_database(database)
                seed_database(database)
                rows = connection.execute('SELECT * FROM daily_data ORDER BY date').fetchall()
                self.assertEqual(len(rows), 8)
                self.assertTrue(all(row[4] > 0 for row in rows))
                month = connection.execute('SELECT * FROM monthly_data').fetchall()
                self.assertEqual(month, [('gate-product-001', '2026-09', 1600.0, 1600.0, 800, 80)])
                results.append(rows)
        self.assertEqual(*results)

    def test_fixture_is_visible_to_browser_default_category_and_daily_contract(self):
        import os
        from unittest.mock import patch
        from app import create_app
        from scripts.gate_fixture import seed_database, SHOP_ID, PRODUCT_ID
        # 店铺 scope 经环境注入（legacy_shop_id() 运行时读取），fixture 与守卫保持一致
        env_patch = patch.dict('os.environ', {'TMALL_LEGACY_SHOP_ID': SHOP_ID})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        database = self.root / 'browser-fixture.db'
        app = create_app({'TESTING': True, 'DATABASE_PATH': str(database), 'SHOP_ID': SHOP_ID,
                          'ASSET_RELEASE_ROOT': str(self.root / 'assets')})
        seed_database(database)
        with app.test_client() as client:
            for url in ('/api/products?dim=daily&limit=1',
                        '/api/products?dim=daily&start=2026-09-10&end=2026-09-17&category_mode=sock'):
                with client.get(url) as response:
                    self.assertEqual(response.status_code, 200)
                    rows = response.get_json()['data']['rows']
                    self.assertTrue(rows)
                    self.assertEqual(rows[0]['product_id'], PRODUCT_ID)
                    if 'start=' in url:
                        self.assertGreater(rows[0]['payment_amount'], 0)

            with client.get('/api/lifecycle?category_mode=sock') as response:
                self.assertEqual(response.status_code, 200)
                rows = response.get_json()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['product_id'], PRODUCT_ID)
                self.assertEqual(rows[0]['total_gsv'], 1600.0)
                self.assertEqual(rows[0]['active_months'], 1)
            with client.get('/api/lifecycle', query_string={'product_id': PRODUCT_ID}) as response:
                self.assertEqual(response.status_code, 200)
                rows = response.get_json()
                self.assertEqual(len(rows), 1)
                self.assertEqual((rows[0]['month'], rows[0]['gsv'], rows[0]['visitors']),
                                 ('2026-09', 1600.0, 800))
            with client.get('/api/lifecycle/assessments?category_mode=sock') as response:
                self.assertEqual(response.status_code, 200)
                result = response.get_json()
                row = result['data'][0]
                self.assertEqual(row['continuous_valid_days'], 8)
                self.assertEqual(row['complete_months'], 0)
                self.assertEqual(row['stage'], 'data_accumulating')
                self.assertFalse(result['capabilities']['can_edit_stage'])
                self.assertFalse(result['capabilities']['can_infer_seasonality'])

            # Source table exists but contains no fabricated collector observations.
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM sycm_item_flow_source_daily').fetchone()[0], 0)
                fields = {row[1] for row in connection.execute('PRAGMA table_info(sycm_item_flow_source_daily)')}
                self.assertTrue({'stat_date', 'item_id', 'channel_name', 'belong', 'uv', 'collect_item_count', 'raw_data'} <= fields)
            for query in ('?belong=farthest', '?belong=all&start=2026-09-10&end=2026-09-17'):
                with client.get('/api/sycm/item-flow/summary' + query) as response:
                    self.assertEqual(response.status_code, 200)
                    payload = response.get_json()
                    self.assertEqual(payload['availability'], 'no-data')
                    self.assertEqual(payload['evidence_level'], 'insufficient')
                    self.assertEqual(payload['data']['channels'], [])
                    self.assertEqual(payload['data']['data_days'], 0)
                    self.assertTrue(payload['limitations'])

            with client.get('/api/products?dim=daily&start=2026-07-14&end=2026-08-12&category_mode=sock&limit=20') as response:
                self.assertEqual(response.status_code, 200)
                rows = response.get_json()['data']['rows']
                self.assertEqual({row['product_id'] for row in rows}, {PRODUCT_ID, 'gate-product-002'})
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM products').fetchone()[0], 2)
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM daily_data').fetchone()[0], 8)
                self.assertEqual(connection.execute('SELECT SUM(payment_amount) FROM daily_data').fetchone()[0], 1600)
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM monthly_data').fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM daily_data WHERE product_id='gate-product-002'").fetchone()[0], 0)

    def test_production_bind_failure_cannot_create_app_or_ready_record(self):
        factory, ready = Mock(), Mock()
        with patch('scripts.start_dev_server.bind_listener', side_effect=OSError('occupied')), self.assertRaisesRegex(OSError, 'occupied'):
            service.production_server(factory, 49001, ready)
        factory.assert_not_called()
        ready.assert_not_called()

    def test_production_failure_closes_dispatcher_partial_channels_and_listener(self):
        listener, dispatcher, server, channel = Mock(), Mock(), Mock(), Mock()
        def create(*args, **kwargs):
            kwargs['map']['owned-channel'] = channel
            self.assertEqual(kwargs['sockets'], [listener])
            self.assertEqual(kwargs['trusted_proxy'], '127.0.0.1')
            return server
        with patch('scripts.start_dev_server.bind_listener', return_value=listener), \
             patch('waitress.task.ThreadedTaskDispatcher', return_value=dispatcher), \
             patch('waitress.create_server', side_effect=create):
            with self.assertRaisesRegex(RuntimeError, 'app-failure'):
                service.production_server(Mock(side_effect=RuntimeError('app-failure')), 0, Mock())
        dispatcher.set_thread_count.assert_not_called()
        dispatcher.shutdown.assert_called_once()
        server.close.assert_called_once()
        channel.close.assert_called_once()
        listener.close.assert_called_once()

    def test_production_owner_failure_cannot_probe_foreign_service(self):
        from scripts import production_smoke
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(gates, 'owned_service', side_effect=RuntimeError('nonce mismatch')), \
             patch.object(production_smoke, '_request') as request:
            with self.assertRaisesRegex(RuntimeError, 'nonce mismatch'):
                production_smoke.run_smoke(port=0, username='fixture', password='fixture', database_path=self.env['TMALL_DB_PATH'])
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()

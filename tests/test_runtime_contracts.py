import os
import unittest


class RuntimeContractsTests(unittest.TestCase):
    def test_test_server_and_smoke_script_share_default_port(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'scripts', 'run_test_server.py'), encoding='utf-8') as handle:
            server = handle.read()
        with open(os.path.join(root, 'scripts', 'smoke_core_pages.cjs'), encoding='utf-8') as handle:
            smoke = handle.read()

        self.assertIn("make('127.0.0.1', 0", server)
        self.assertIn("env['TMALL_DB_PATH']", server)
        self.assertIn("TMALL_GATE_NONCE", server)
        self.assertNotIn("os.path.abspath('data/dashboard.db')", server)
        self.assertIn("assertBase(base)", smoke)


    def test_upload_limit_has_one_documented_value(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'config.py'), encoding='utf-8') as handle:
            config = handle.read()

        self.assertIn('MAX_CONTENT_LENGTH = 25 * 1024 * 1024', config)

    def test_production_launcher_fails_closed_and_uses_trusted_proxy(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'scripts', 'start_production.ps1'), encoding='utf-8') as handle:
            launcher = handle.read()

        self.assertIn('DASHBOARD_USERNAME', launcher)
        self.assertIn('DASHBOARD_PASSWORD', launcher)
        self.assertIn('[string]$ListenHost', launcher)
        self.assertNotIn('[string]$Host', launcher)
        self.assertIn('Get-NetTCPConnection -State Listen -LocalPort $Port', launcher)
        self.assertIn('production_preflight.py --database $databasePath --require-auth', launcher)
        self.assertIn('--trusted-proxy=127.0.0.1', launcher)
        self.assertIn('--trusted-proxy-headers=x-forwarded-for', launcher)

    def test_quality_gate_exercises_the_production_wsgi_stack(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, '.github', 'workflows', 'quality-gate.yml'), encoding='utf-8') as handle:
            workflow = handle.read()

        import json
        self.assertIn('python scripts/run_quality_gates.py --tier release', workflow)
        with open(os.path.join(root, 'scripts', 'quality_gates.json'), encoding='utf-8') as handle:
            manifest = json.load(handle)
        gates = {gate['id']: gate for gate in manifest['gates']}
        self.assertEqual(gates['production-smoke']['tier'], 'release')
        self.assertEqual(gates['production-smoke']['argv'][1:], [
            'scripts/production_smoke.py', '--database', '{database}', '--port', '{production_port}'
        ])
        self.assertEqual(gates['release-audit']['argv'][1:], [
            'scripts/release_audit.py', '--database', '{database}', '--strict'
        ])
        with open(os.path.join(root, 'scripts', 'run_quality_gates.py'), encoding='utf-8') as handle:
            runner = handle.read()
        self.assertIn("'DASHBOARD_USERNAME': 'gate-fixture'", runner)
        self.assertIn("'DASHBOARD_PASSWORD': secrets.token_hex(24)", runner)
        self.assertIn("'database': env['TMALL_DB_PATH']", runner)



if __name__ == '__main__':
    unittest.main()

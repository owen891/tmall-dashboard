import os
import unittest


class RuntimeContractsTests(unittest.TestCase):
    def test_test_server_and_smoke_script_share_default_port(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'scripts', 'run_test_server.py'), encoding='utf-8') as handle:
            server = handle.read()
        with open(os.path.join(root, 'scripts', 'smoke_core_pages.cjs'), encoding='utf-8') as handle:
            smoke = handle.read()

        self.assertIn("os.environ.get('TMALL_PORT', '8770')", server)
        self.assertIn("os.environ.get('TMALL_DB_PATH')", server)
        self.assertIn("'http://127.0.0.1:8770'", smoke)

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


if __name__ == '__main__':
    unittest.main()

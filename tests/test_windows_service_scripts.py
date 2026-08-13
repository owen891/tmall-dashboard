import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class WindowsServiceScriptsTests(unittest.TestCase):
    def _read(self, relative_path):
        with open(os.path.join(PROJECT_ROOT, relative_path), encoding='utf-8') as source:
            return source.read()

    def test_autostart_uses_programdata_runtime_database(self):
        source = self._read('scripts/start_local_production.ps1')

        self.assertIn("Join-Path $env:ProgramData 'TMallDashboard\\data\\dashboard.db'", source)
        self.assertIn('TMALL_DB_PATH', source)
        self.assertIn('--host=127.0.0.1', source)

    def test_installer_preserves_existing_runtime_database(self):
        source = self._read('scripts/install_local_autostart.ps1')

        self.assertIn("if (-not (Test-Path -LiteralPath $database))", source)
        self.assertIn('Copy-Item -LiteralPath $sourceDatabase -Destination $database', source)
        self.assertIn("Join-Path $env:LOCALAPPDATA 'Programs\\Python\\Python314\\python.exe'", source)
        self.assertNotIn('-DatabasePath `"$database`"', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)

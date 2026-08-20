import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DesktopPackagingContractTests(unittest.TestCase):
    def test_pyinstaller_spec_bundles_required_runtime_assets(self):
        spec = (ROOT / 'packaging' / 'tmall_dashboard_backend.spec').read_text(encoding='utf-8')

        for asset in ('frontend/ui_demo', 'templates', 'static', 'config.yaml'):
            self.assertIn(asset, spec)
        self.assertIn("name='TmallDashboardServer'", spec)
        self.assertIn("name='backend'", spec)

    def test_desktop_requirements_pin_pyinstaller(self):
        requirements = (ROOT / 'requirements-desktop.txt').read_text(encoding='utf-8')

        self.assertIn('-r requirements.txt', requirements)
        self.assertIn('pyinstaller==6.22.1', requirements.lower())

    def test_build_script_fails_when_backend_executable_is_missing(self):
        script = (ROOT / 'scripts' / 'build_backend.ps1').read_text(encoding='utf-8')

        self.assertIn('packaging\\tmall_dashboard_backend.spec', script)
        self.assertIn('build\\desktop\\backend\\TmallDashboardServer.exe', script)
        self.assertIn('throw', script)

    def test_python_backend_build_checks_all_release_version_artifacts(self):
        script = (ROOT / 'scripts' / 'build_backend.py').read_text(encoding='utf-8')

        self.assertIn('assert_release_version_contract', script)
        self.assertIn("desktop' / 'package.json", script)
        self.assertIn("frontend' / 'ui_demo' / 'assets' / 'version.js", script)

    def test_desktop_smoke_uses_project_version_and_checks_runtime_apis(self):
        script = (ROOT / 'scripts' / 'desktop_smoke.ps1').read_text(encoding='utf-8')

        self.assertIn("Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\\VERSION')", script)
        self.assertNotIn('TmallDashboard-Setup-1.0.0-x64.exe', script)
        self.assertIn('/api/anomalies?dim=monthly', script)
        self.assertIn('/api/report?dim=monthly', script)
        self.assertIn('backend.log', script)


if __name__ == '__main__':
    unittest.main(verbosity=2)

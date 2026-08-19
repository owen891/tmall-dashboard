import io
import os
import pathlib
import sys
import tempfile
import time
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix='tmall-release-gates-')
        from app import create_app
        self.app = create_app({
            'TESTING': True,
            'DATABASE_PATH': os.path.join(self.temp_dir.name, 'dashboard.db'),
            'MAX_CONTENT_LENGTH': 1024,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_import_preview_rejects_request_over_configured_upload_limit(self):
        response = self.client.post('/api/imports/preview', data={
            'file': (io.BytesIO(b'x' * 2048), 'oversized.xlsx'),
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 413)
        payload = response.get_json()
        response.close()
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['code'], 'PAYLOAD_TOO_LARGE')

    def test_overview_main_region_completes_under_five_seconds(self):
        started = time.perf_counter()
        response = self.client.get('/api/overview?start=2026-04-01&end=2026-04-30')
        elapsed = time.perf_counter() - started
        response.close()
        self.assertLess(elapsed, 5.0)

    def test_shop_target_requires_a_valid_period(self):
        response = self.client.post('/api/targets/shop', json={})
        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        response.close()
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['code'], 'VALIDATION_ERROR')

    def test_browser_gate_covers_capabilities_context_and_flow_impact(self):
        script = pathlib.Path(PROJECT_ROOT, 'scripts', 'browser_prd_gates.cjs').read_text(encoding='utf-8')
        for marker in (
            'can_drilldown', 'can_edit_stage', 'product_id',
            'data-modal-kind="flow"', '影响',
        ):
            self.assertIn(marker, script)

    def test_release_notes_bound_phase_one_scope(self):
        notes = pathlib.Path(PROJECT_ROOT, 'docs', 'RELEASE_NOTES.md').read_text(encoding='utf-8')
        self.assertIn('Phase 1', notes)
        for excluded in ('利润', '库存', '用户 cohort', '因果归因', '市场机会'):
            self.assertIn(excluded, notes)

    def test_phase_two_catalog_is_covered_by_release_gates(self):
        script = pathlib.Path(PROJECT_ROOT, 'scripts', 'browser_prd_gates.cjs').read_text(encoding='utf-8')
        for marker in (
            'data-capability-summary', 'data-capability-filter="search"',
            'data-capability-detail', 'data-modal-kind',
            '当前不承诺完整市场机会分析',
        ):
            self.assertIn(marker, script)
        notes = pathlib.Path(PROJECT_ROOT, 'docs', 'RELEASE_NOTES.md').read_text(encoding='utf-8')
        self.assertIn('Phase 2', notes)
        self.assertIn('只读', notes)
        self.assertIn('证据', notes)

    def test_browser_gate_restores_only_writable_settings(self):
        script = pathlib.Path(PROJECT_ROOT, 'scripts', 'browser_prd_gates.cjs').read_text(encoding='utf-8')
        self.assertIn('restoreWritableSettings', script)
        self.assertIn("delete writableSettings.field_catalog", script)

    def test_browser_gate_uses_a_unique_promotion_template_name(self):
        script = pathlib.Path(PROJECT_ROOT, 'scripts', 'browser_prd_gates.cjs').read_text(encoding='utf-8')
        self.assertIn('const promotionTemplateName = `浏览器推广模板-${Date.now()}`', script)
        self.assertIn('savedPromotionTemplate !== promotionTemplateName', script)

    def test_desktop_release_uploads_installer_and_updater_assets(self):
        workflow = pathlib.Path(PROJECT_ROOT, '.github', 'workflows', 'desktop-release.yml').read_text(encoding='utf-8')
        self.assertIn('scripts/build_desktop.ps1', workflow)
        self.assertIn('latest.yml', workflow)
        self.assertIn('*.exe.blockmap', workflow)
        self.assertIn('softprops/action-gh-release', workflow)
        self.assertIn('contents: write', workflow)
        self.assertIn('macos-13', workflow)
        self.assertIn('macos-14', workflow)
        self.assertIn('scripts/build_backend.py', workflow)
        self.assertIn('*.dmg', workflow)
        self.assertIn('*.zip', workflow)
        self.assertIn('merge_mac_update_metadata.py', workflow)

    def test_mac_update_metadata_merges_both_architectures(self):
        from scripts.merge_mac_update_metadata import merge_metadata

        merged = merge_metadata([
            {'version': '1.0.5', 'files': [{'url': 'TmallDashboard-1.0.5-x64.zip', 'sha512': 'x', 'size': 1}]},
            {'version': '1.0.5', 'files': [{'url': 'TmallDashboard-1.0.5-arm64.zip', 'sha512': 'a', 'size': 2}]},
        ])
        self.assertEqual(merged['version'], '1.0.5')
        self.assertEqual({item['url'] for item in merged['files']}, {
            'TmallDashboard-1.0.5-x64.zip', 'TmallDashboard-1.0.5-arm64.zip',
        })

    def test_desktop_build_uses_the_root_version_and_complete_pipeline(self):
        script = pathlib.Path(PROJECT_ROOT, 'scripts', 'build_desktop.ps1').read_text(encoding='utf-8')
        for marker in (
            'sync_desktop_version.py', 'build_backend.ps1',
            'npm test', 'npm run build', 'npm run dist',
            'latest.yml', '.exe.blockmap',
        ):
            self.assertIn(marker, script)

        sync = pathlib.Path(PROJECT_ROOT, 'scripts', 'sync_desktop_version.py').read_text(encoding='utf-8')
        self.assertIn("PROJECT_ROOT / 'VERSION'", sync)
        self.assertIn("PROJECT_ROOT / 'desktop' / 'package.json'", sync)


if __name__ == '__main__':
    unittest.main()

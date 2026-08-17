from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_scan_dialog_has_its_own_live_status_region():
    markup = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'pages' / 'settings.html').read_text(encoding='utf-8')
    script = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'settings-live.js').read_text(encoding='utf-8')

    assert 'data-scan-form-status' in markup
    assert "document.querySelector('[data-scan-form-status]')" in script

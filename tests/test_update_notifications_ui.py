from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_import_and_scan_flows_announce_completion_results():
    data_center = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'data-center-live.js').read_text(encoding='utf-8')
    settings = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'settings-live.js').read_text(encoding='utf-8')

    assert 'showToast' in data_center
    assert 'showToast' in settings
    assert '扫描完成' in settings
    assert '导入完成' in data_center

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_import_and_scan_flows_announce_completion_results():
    data_center = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'pages' / 'data-center' / 'import-workflow.js').read_text(encoding='utf-8')
    settings = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'settings-live.js').read_text(encoding='utf-8')

    assert 'showToast' in data_center
    assert 'showToast' in settings
    assert '扫描完成' in settings
    assert '导入完成' in data_center


def test_web_update_checker_is_loaded_by_the_common_shell():
    shell = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'shell.js').read_text(encoding='utf-8')
    checker = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'version-check.js').read_text(encoding='utf-8')
    version = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'version.js').read_text(encoding='utf-8')

    # shell.js 给动态加载的脚本带 ?v= 穿透 7 天静态缓存，断言表达契约本身
    #（用 new URL(name, assetBase) 加载 version.js / version-check.js），
    # 不要写死「无查询串」的字面量 —— 那样一 bump 缓存串就误报。
    assert re.search(r"new URL\('version\.js(?:\?[^']*)?', assetBase\)", shell)
    assert re.search(r"new URL\('version-check\.js(?:\?[^']*)?', assetBase\)", shell)
    assert "new URL('../api/version?client=web', assetBase)" in checker
    assert '立即刷新' in checker
    assert 'TMALL_WEB_VERSION' in version


def test_web_update_checker_validates_versions_and_uses_dom_text_nodes():
    checker = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'version-check.js').read_text(encoding='utf-8')

    assert 'SEMVER_PATTERN' in checker
    assert 'textContent' in checker
    assert 'banner.innerHTML' not in checker
    assert 'newerThan(version, currentVersion)' in checker


def test_web_update_checker_throttles_release_requests_across_page_navigation():
    checker = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'version-check.js').read_text(encoding='utf-8')
    desktop = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'desktop-integration.js').read_text(encoding='utf-8')

    assert "tmall-update-release-last-check" in checker
    assert 'releaseCheckInterval' in checker
    assert 'localStorage.setItem(releaseCheckKey' in checker
    assert 'markReleaseCheck()' in checker
    assert 'button?.addEventListener(\'click\', checkRelease)' in desktop
    assert '    checkRelease()\n' not in desktop


def test_shell_only_scans_unprocessed_lucide_nodes():
    shell = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'shell.js').read_text(encoding='utf-8')

    assert '[data-lucide]:not([data-lucide-rendered])' in shell
    assert "setAttribute('data-lucide-rendered', 'true')" in shell


def test_shared_charts_avoid_expensive_animation_and_resize_storms():
    charts = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'charts.js').read_text(encoding='utf-8')

    assert 'animation: false' in charts
    assert 'requestAnimationFrame' in charts
    assert 'chart.resize({' in charts
    assert 'cancelAnimationFrame' in charts


def test_table_controls_coalesce_viewport_work():
    controls = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'table-controls.js').read_text(encoding='utf-8')

    assert 'scheduleViewportSync' in controls
    assert "requestAnimationFrame(() =>" in controls
    assert "passive: true" in controls

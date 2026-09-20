from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_overview_kpis_have_daily_matrix_fallback():
    script = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'overview-live.js').read_text(encoding='utf-8')

    assert 'function deriveKpiFallback' in script
    # renderKpis 现在接收第 4 个参数 targets（经营目标进度），断言跟着同步；
    # 原断言少了 targets，从该参数引入起这个测试就一直是红的。
    assert 'renderKpis(overviewResponse.data, comparison, matrix.data, targets)' in script

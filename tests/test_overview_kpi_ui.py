from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_overview_kpis_have_daily_matrix_fallback():
    script = (PROJECT_ROOT / 'frontend' / 'ui_demo' / 'assets' / 'overview-live.js').read_text(encoding='utf-8')

    assert 'function deriveKpiFallback' in script
    assert 'renderKpis(overviewResponse.data, comparison, matrix.data)' in script

from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_overview_kpis_have_daily_matrix_fallback():
    """Execute the real JS renderer: aggregate fallback and preserve authoritative zero."""
    result = subprocess.run(
        ['node', str(PROJECT_ROOT / 'scripts' / 'test_overview_ux_runtime.cjs'),
         '--root', str(PROJECT_ROOT)],
        capture_output=True, text=True, encoding='utf-8', timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS matrix fallback aggregates buyers over visitors' in result.stdout
    assert 'PASS authoritative zero cannot be overwritten by matrix fallback' in result.stdout
    assert 'PASS absent matrix input remains unknown' in result.stdout

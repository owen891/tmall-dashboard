import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / 'README.md'
CAPTURE_SCRIPT = ROOT / 'scripts' / 'capture_readme_screenshots.cjs'
ASSET_DIR = ROOT / 'docs' / 'assets' / 'readme'
SCREENSHOTS = ('overview.png', 'products.png', 'data-center.png')


def _png_dimensions(path):
    with path.open('rb') as source:
        signature = source.read(8)
        chunk_length = struct.unpack('>I', source.read(4))[0]
        chunk_type = source.read(4)
        width, height = struct.unpack('>II', source.read(8))
    assert signature == b'\x89PNG\r\n\x1a\n'
    assert chunk_length == 13
    assert chunk_type == b'IHDR'
    return width, height


def test_readme_references_fixed_size_product_screenshots():
    readme = README.read_text(encoding='utf-8')

    for filename in SCREENSHOTS:
        asset = ASSET_DIR / filename
        assert f'docs/assets/readme/{filename}' in readme
        assert asset.is_file()
        assert asset.stat().st_size > 50_000
        assert _png_dimensions(asset) == (1440, 900)


def test_capture_script_rejects_non_demo_data_sources():
    script = CAPTURE_SCRIPT.read_text(encoding='utf-8')

    assert '/api/products?' in script
    assert "startsWith('DEMO-')" in script
    assert "remark === '演示数据'" in script
    assert 'TMALL_PLAYWRIGHT_MODULE' in script

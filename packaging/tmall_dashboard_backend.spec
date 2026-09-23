from pathlib import Path


project_root = Path(SPECPATH).resolve().parent

datas = [
    (str(project_root / 'frontend' / 'ui_demo'), 'frontend/ui_demo'),
    (str(project_root / 'config.yaml'), '.'),
    (str(project_root / 'VERSION'), '.'),
]

a = Analysis(
    [str(project_root / 'desktop_backend.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TmallDashboardServer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='backend',
)

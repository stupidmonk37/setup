# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['../gv_tui.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/jjensen/git/setup/groq/bin-groq/gv-tui/dashboard.css', '.')],
    hiddenimports=['textual.widgets._tab'],
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
    a.binaries,
    a.datas,
    [],
    name='gv_tui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

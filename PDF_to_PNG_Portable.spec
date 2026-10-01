# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['pdf_to_png.py'],
    pathex=[], binaries=[],
    datas=collect_data_files('customtkinter') + [('assets/pdf_to_png.ico', 'assets')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['numpy', 'pandas', 'scipy', 'pytest', 'IPython', 'matplotlib'],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='PDF_to_PNG_Portable', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, disable_windowed_traceback=False,
    icon='assets/pdf_to_png.ico', version='packaging/version_info.txt',
    runtime_tmpdir=None,
)

"""Shared PyInstaller configuration for both supported Windows builds."""
import runpy
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = runpy.run_path(str(ROOT / "pdf_lover/version.py"))["APP_FILE_NAME"]
ICON = str(ROOT / "pdf_lover/assets/pdf_to_png.ico")
VERSION_INFO = str(ROOT / "packaging/version_info.txt")


def analysis_options():
    return dict(
        scripts=[str(ROOT / "main.py")],
        pathex=[str(ROOT)],
        binaries=[],
        datas=collect_data_files("customtkinter") + collect_data_files("tkinterdnd2")
              + [(ICON, "pdf_lover/assets")],
        hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
        excludes=["numpy", "pandas", "scipy", "pytest", "IPython", "matplotlib"],
        noarchive=False, optimize=0,
    )

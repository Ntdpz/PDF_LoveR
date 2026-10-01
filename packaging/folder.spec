from pathlib import Path
import runpy

config = runpy.run_path(str(Path(SPECPATH) / "spec_common.py"))
a = Analysis(**config["analysis_options"]())
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name=config["APP_NAME"], debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False, disable_windowed_traceback=False,
    icon=config["ICON"], version=config["VERSION_INFO"],
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True,
               upx_exclude=[], name=config["APP_NAME"])

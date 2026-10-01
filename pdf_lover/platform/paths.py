"""User output locations, including redirected Windows Documents folders."""
import ctypes
import sys
from pathlib import Path


def documents_folder() -> Path:
    if sys.platform == "win32":
        folder = ctypes.create_unicode_buffer(32768)
        # CSIDL_PERSONAL resolves the user's actual Documents location, which
        # can be redirected to OneDrive or another drive by Windows.
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, folder) == 0 and folder.value:
            return Path(folder.value)
    return Path.home() / "Documents"

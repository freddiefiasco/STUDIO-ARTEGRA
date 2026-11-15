"""Expose the package's verified Microsoft DLLs to an isolated engine process.

Callers load this exact file with runpy and retain the returned namespace for
the process lifetime: closing the directory handle removes it from DLL search.
Source checkouts keep using their normal Python environment.
"""
import os
from pathlib import Path
import sys


_DLL_DIRECTORY_HANDLE = None
if sys.platform == "win32":
    _directory = Path(__file__).resolve().parents[1] / "desktop-runtime/Lib/site-packages/shiboken6"
    if _directory.is_dir():
        _DLL_DIRECTORY_HANDLE = os.add_dll_directory(str(_directory))

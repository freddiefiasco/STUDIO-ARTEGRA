"""Internal installer worker. Output is rendered by the setup wizard, never a terminal."""
from __future__ import annotations
import argparse
import ctypes
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time

from host.installation import Installation, SetupError, default_state


def protocol_text(value):
    """Installer pipes must also work on legacy non-Unicode Windows code pages."""
    value = str(value).translate(str.maketrans({"…": "...", "·": " - ", "’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-"}))
    return value.replace("|", " ").replace("\n", " ").replace("\r", " ").encode("ascii", "replace").decode("ascii")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--data-directory", type=Path)
    parser.add_argument("--accept-terms", action="store_true")
    parser.add_argument("--cancel-file", type=Path)
    args = parser.parse_args(argv)
    state = args.state or default_state()
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    cancel, finished = threading.Event(), threading.Event()
    parent_handle = None
    kernel = None
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        parent_handle = kernel.OpenProcess(0x100000, False, os.getppid())
    last = [0.0, ""]
    def progress(event):
        now = time.monotonic()
        message = protocol_text(event["message"])
        # Rate limit pipe/UI traffic without hiding stage changes.
        if now-last[0] >= .25 or message != last[1] or event["fraction"] >= 1:
            print(f"ARTEGRA|{int(event['fraction']*100)}|{message}", flush=True)
            last[:] = [now, message]
    def watch_cancel():
        while not finished.wait(.1):
            if args.cancel_file and args.cancel_file.exists():
                cancel.set()
                return
            if parent_handle and kernel.WaitForSingleObject(parent_handle, 0) == 0:
                cancel.set()
                return
    watcher = threading.Thread(target=watch_cancel, daemon=True)
    watcher.start()
    try:
        state.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=str(state / "installation.log"), level=logging.INFO, encoding="utf-8")
        install = Installation(root, state, progress=progress, cancel=cancel, data_directory=args.data_directory)
        install.run(accept_terms=args.accept_terms)
        return 0
    except Exception as exc:
        logging.exception("Installation did not complete")
        message = str(exc) if isinstance(exc, (SetupError, ValueError)) else "Setup could not finish. Your downloaded files are saved. Check your connection and free disk space, then choose Retry."
        print("ARTEGRA-ERROR|" + protocol_text(message), flush=True)
        return 130 if cancel.is_set() else 1
    finally:
        finished.set()
        watcher.join(timeout=1)
        if parent_handle:
            kernel.CloseHandle(parent_handle)


if __name__ == "__main__":
    raise SystemExit(main())

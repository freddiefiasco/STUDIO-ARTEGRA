"""The running app's record and the uninstaller's quit path.

While the app runs it keeps <state>/run/host.json: its own process and its launcher, each as PID, creation time and
executable path. `ArtegraEnhancer.exe --quit-running` asks a running app to stop and close through its single-instance
connection, waits for exactly those processes to end, and, only if they do not, ends the ones whose PID, creation time
and path all still match the record. It never looks processes up by name and never touches any other process; the
app's Job object then ends the image engine with it.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import time

SCHEMA = 1
QUIT_MESSAGE = b"quit"
# Exit code of a process the quit path had to end. The launcher stays quiet for it (installer/launcher.cs).
QUIT_EXIT_CODE = 0x41E0
# Exit code of --quit-running when something of the app could not be closed (the uninstaller then stops).
STILL_RUNNING = 2
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
STILL_ACTIVE = 259


def record_path(state: Path) -> Path:
    return Path(state) / "run" / "host.json"


def server_name(state: Path) -> str:
    """The single-instance connection name of the app window that uses this state folder (same rule as host.app)."""
    return "artegra-enhancer-" + hashlib.sha256(str(Path(state)).encode()).hexdigest()[:24]


def _kernel():
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    return k


def _describe(kernel, handle):
    from ctypes import wintypes
    created, exited, kernel_t, user_t = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_t), ctypes.byref(user_t)):
        return None
    size = wintypes.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(size.value)
    if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
        return None
    code = wintypes.DWORD(0)
    if kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != STILL_ACTIVE:
        return None
    return {"created": (created.dwHighDateTime << 32) | created.dwLowDateTime, "image": buffer.value}


def identity(pid: int):
    """{pid, created, image} of a running process, or None."""
    if os.name != "nt" or not pid:
        return None
    kernel = _kernel()
    handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None
    try:
        found = _describe(kernel, handle)
        return dict(found, pid=int(pid)) if found else None
    finally:
        kernel.CloseHandle(handle)


def _same_path(a, b) -> bool:
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def matches(entry) -> bool:
    """True while the recorded process still runs: the same PID, creation time and executable path."""
    if not isinstance(entry, dict):
        return False
    now = identity(entry.get("pid") or 0)
    return bool(now) and now["created"] == entry.get("created") and _same_path(now["image"], entry.get("image", ""))


def write(state: Path, app_root: Path, launcher_pid=None) -> dict:
    """Record this process (and the desktop launcher that started it, when it is the app's own launcher)."""
    host = identity(os.getpid())
    launcher = None
    if launcher_pid:
        found = identity(int(launcher_pid))
        if found and _same_path(found["image"], Path(app_root) / "ArtegraEnhancer.exe"):
            launcher = found
    data = {"schema": SCHEMA, "host": host, "launcher": launcher, "state": str(state), "app_root": str(app_root),
            "written": time.time()}
    path = record_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return data


def read(state: Path):
    try:
        data = json.loads(record_path(state).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("schema") == SCHEMA else None


def remove(state: Path) -> None:
    """Remove the record on a normal exit, but only this process's own record."""
    data = read(state)
    if data and isinstance(data.get("host"), dict) and data["host"].get("pid") == os.getpid():
        try:
            record_path(state).unlink()
        except OSError:
            pass


def _end(entry) -> bool:
    """End one recorded process if, and only if, it is still the recorded one. True when it is gone."""
    if os.name != "nt":
        return not matches(entry)
    kernel = _kernel()
    handle = kernel.OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, int(entry.get("pid") or 0))
    if not handle:
        return True
    try:
        found = _describe(kernel, handle)
        if not found or found["created"] != entry.get("created") or not _same_path(found["image"], entry.get("image", "")):
            return True
        kernel.TerminateProcess(handle, QUIT_EXIT_CODE)
        return kernel.WaitForSingleObject(handle, 10000) == 0
    finally:
        kernel.CloseHandle(handle)


def _ask_to_quit(state: Path) -> bool:
    try:
        from PySide6.QtNetwork import QLocalSocket
    except ImportError:
        return False
    socket = QLocalSocket()
    socket.connectToServer(server_name(state))
    if not socket.waitForConnected(1500):
        return False
    socket.write(QUIT_MESSAGE)
    socket.waitForBytesWritten(1500)
    socket.disconnectFromServer()
    return True


def default_states():
    from host.installation import known_folder
    root = (known_folder("local") / "Studio Artegra" / "Artegra Enhancer").resolve()
    return [root / "production", root / "demo"]


def quit_running(states, timeout=30.0, clock=time.monotonic, sleep=time.sleep) -> int:
    """Close every app window that uses one of these state folders. 0 when nothing of the app is left running,
    STILL_RUNNING when a recorded process could not be closed."""
    pending = []
    for state in states:
        state = Path(state)
        data = read(state)
        entries = [e for e in ((data or {}).get("host"), (data or {}).get("launcher")) if isinstance(e, dict)]
        live = [e for e in entries if matches(e)]
        if not live:
            continue
        _ask_to_quit(state)
        pending.extend(live)
    deadline = clock() + timeout
    while pending and clock() < deadline:
        pending = [e for e in pending if matches(e)]
        if pending:
            sleep(0.2)
    pending = [e for e in pending if not _end(e)]
    return 0 if not pending else STILL_RUNNING


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ArtegraEnhancer --quit-running")
    parser.add_argument("--state", action="append", type=Path, default=[],
                        help="a state root (its production and demo folders are checked); default: the per-user location")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    states = []
    for root in args.state:
        root = Path(root).expanduser().resolve()
        states += [root, root / "production", root / "demo"] if root.name not in ("production", "demo") else [root]
    if not args.state:
        states = default_states()
    return quit_running(states, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())

"""Prepare the pinned image engine with resumable, app-owned installation state."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

if __package__:
    from runtime.compatibility import require_supported_platform
else:
    # Embedded Python's ._pth and python -I omit the script directory. Resolve
    # this exact sibling without adding arbitrary directories to sys.path.
    import importlib.util
    _compat_spec = importlib.util.spec_from_file_location(
        "runtime_compatibility", Path(__file__).with_name("compatibility.py"))
    _compat = importlib.util.module_from_spec(_compat_spec)
    _compat_spec.loader.exec_module(_compat)
    require_supported_platform = _compat.require_supported_platform

ROOT = Path(__file__).resolve().parent
PYTHON_VERSION = "3.13.14"
COMFY_COMMIT = "bcba14f618eaea6e63dac15d1ef45051945ea54e"
COMFY_BASE = "3f438ca69f3d0efc5f748de055daeea9ba26ee50"
ASSETS = {
    "python": ("https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip", "90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907"),
    "comfyui": (f"https://codeload.github.com/Comfy-Org/ComfyUI/zip/{COMFY_BASE}", "37803ef2b38aedf68eab60cb550c926b131d13c4449f2e135cbc8353c29be3d4"),
    "pip": ("https://files.pythonhosted.org/packages/07/25/ee8c38ae72d66b844ce8eb9711ba905dba21ca1a8a0c960057c41cd23337/pip-26.3-py3-none-any.whl", "f3b60b20ffaadd4415ed7957212a38ac63fa4c5fa375bd0f4a797777940fad13"),
}
OFFICIAL_HOSTS = {"www.python.org", "codeload.github.com", "files.pythonhosted.org"}
PATCH_SHA256 = "ba855cdc951f9285b7101060435d94ea75f9cfe27f068e2a879da019fbef47a1"
OWNER_FILE = ".artegra-runtime.json"
INCOMPLETE_FILE = "SETUP-INCOMPLETE.txt"
CHUNK_SIZE = 1024 * 1024


class SetupCancelled(InterruptedError):
    code = "cancelled"


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise SetupCancelled("Installation paused. Open setup again to continue.")


def _progress(callback, stage, message, completed=0, total=0):
    if callback:
        callback(dict(stage=stage, message=message, completed=completed, total=total))
    elif not total or completed == total:
        print(message, flush=True)


def _linked(path):
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _owned_path(root, path):
    """Reject links before any write, including junctions on Windows."""
    path = Path(path)
    if not path.is_relative_to(root):
        raise ValueError("Installation files must stay in the application data folder.")
    for candidate in (path, *path.parents):
        if _linked(candidate):
            raise ValueError("The installation folder contains a link. Choose another location.")
        if candidate == root:
            break
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Installation files must stay in the application data folder.")
    return path


def _write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    if _linked(path) or _linked(temporary):
        raise ValueError("The installation record is a link.")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _recipe():
    return {"schema": 1, "owner": "Studio Artegra runtime setup", "python": PYTHON_VERSION,
            "comfy_commit": COMFY_COMMIT, "patch": PATCH_SHA256,
            "requirements": sha256(ROOT / "requirements-win.lock"),
            "constraints": sha256(ROOT / "constraints-win.txt"),
            "source_manifest": sha256(ROOT / "source-manifest.json"),
            "assets": {name: digest for name, (_, digest) in ASSETS.items()}}


@contextmanager
def _installation_lock(destination):
    path = _owned_path(destination, destination / ".setup.lock")
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise OSError("Installation is already running. Wait for the other setup window.") from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise OSError("Installation is already running. Wait for the other setup window.") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def sha256(path: Path, *, cancel=None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            _check_cancel(cancel)
            digest.update(chunk)
    return digest.hexdigest()


def _official_url(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme == "https" and parsed.hostname in OFFICIAL_HOSTS and not parsed.username and not parsed.password


class _OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _official_url(newurl):
            raise ValueError("Unexpected runtime download redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str, expected: str, destination: Path, *, progress=None, cancel=None) -> None:
    if not _official_url(url):
        raise ValueError("Runtime downloads must use an approved official HTTPS source.")
    _check_cancel(cancel)
    part = destination.with_name(destination.name + ".part")
    if _linked(destination) or _linked(part):
        raise ValueError("The installation download is a link.")
    if destination.is_file() and sha256(destination, cancel=cancel) == expected:
        _progress(progress, "download", "Previously downloaded files are ready.", 1, 1)
        return
    if part.is_file() and sha256(part, cancel=cancel) == expected:
        _check_cancel(cancel)
        os.replace(part, destination)
        _progress(progress, "download", "Previously downloaded files are ready.", 1, 1)
        return
    offset = part.stat().st_size if part.is_file() else 0
    headers = {"User-Agent": "ArtegraEnhancer-Setup", "Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    opener = urllib.request.build_opener(_OfficialRedirect())
    try:
        response = opener.open(request, timeout=10)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and offset:
            # A complete but invalid interrupted response cannot be ranged again.
            # Only this download's partial file is discarded; a fresh transfer
            # still has to pass the pinned checksum before publication.
            exc.close()
            part.unlink(missing_ok=True)
            return download(url, expected, destination, progress=progress, cancel=cancel)
        raise
    with response:
        _check_cancel(cancel)
        if not _official_url(response.url):
            raise ValueError("Unexpected runtime download redirect.")
        length = int(response.headers.get("Content-Length", "0"))
        if response.status == 206:
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if not match or int(match[1]) != offset or int(match[2]) < offset or int(match[3]) <= int(match[2]):
                raise ValueError("The download could not be resumed safely. Please retry installation.")
            total = int(match[3])
            if length and length != int(match[2]) - offset + 1:
                raise ValueError("The download server returned an inconsistent file size.")
            mode = "ab"
        elif response.status == 200:
            offset, total, mode = 0, length, "wb"
        else:
            raise ValueError("The download server did not return an installation file.")
        completed = offset
        # read1 returns available bytes rather than waiting to fill a megabyte,
        # so continuously dribbling peers cannot postpone cancellation forever.
        read = getattr(response, "read1", response.read)
        with part.open(mode) as stream:
            while True:
                _check_cancel(cancel)
                chunk = read(CHUNK_SIZE)
                _check_cancel(cancel)
                if not chunk:
                    break
                stream.write(chunk)
                completed += len(chunk)
                if total and completed > total:
                    raise ValueError("The download exceeded its expected size.")
                _progress(progress, "download", "Downloading image-processing files…", completed, total)
        if total and completed != total:
            raise OSError("The connection ended early. Retry to continue the download.")
    if sha256(part, cancel=cancel) != expected:
        part.unlink(missing_ok=True)
        raise ValueError("Runtime download checksum did not match. Setup stopped.")
    _check_cancel(cancel)
    os.replace(part, destination)


def safe_extract(archive: Path, destination: Path, *, strip_root: bool = False, cancel=None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            _check_cancel(cancel)
            parts = Path(item.filename.replace("\\", "/")).parts
            if strip_root:
                parts = parts[1:]
            if not parts:
                continue
            target = destination.joinpath(*parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Unsafe archive member.")
            target = _owned_path(destination, target)
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Runtime archive symlinks are not supported.")
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(item) as source, target.open("wb") as output:
                    while chunk := source.read(CHUNK_SIZE):
                        _check_cancel(cancel)
                        output.write(chunk)


def apply_patch(root: Path, patch: Path) -> None:
    """Apply this exact text-only unified diff; reject mismatched context."""
    if sha256(patch) != PATCH_SHA256:
        raise ValueError("The bundled source patch checksum did not match.")
    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)
    index = 0
    while index < len(lines):
        if not lines[index].startswith("--- "):
            index += 1
            continue
        old = lines[index][4:].strip()
        new = lines[index + 1][4:].strip()
        index += 2
        if not new.startswith("b/") or (old != "/dev/null" and not old.startswith("a/")):
            raise ValueError("Unexpected patch path.")
        path = root / new[2:]
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsafe patch path.")
        path = _owned_path(root, path)
        original = path.read_text(encoding="utf-8").splitlines(keepends=True) if old != "/dev/null" and path.exists() else []
        result, cursor = [], 0
        while index < len(lines) and lines[index].startswith("@@ "):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[index])
            if not match:
                raise ValueError("Malformed patch hunk.")
            start = max(0, int(match.group(1)) - 1)
            result.extend(original[cursor:start])
            cursor = start
            index += 1
            while index < len(lines) and lines[index][:1] in (" ", "+", "-") and not lines[index].startswith(("--- ", "+++ ")):
                action, text = lines[index][0], lines[index][1:]
                if action in (" ", "-"):
                    if cursor >= len(original) or original[cursor] != text:
                        raise ValueError("Pinned ComfyUI source does not match its patch.")
                    cursor += 1
                if action in (" ", "+"):
                    result.append(text)
                index += 1
        result.extend(original[cursor:])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes("".join(result).encode("utf-8"))


def verify_source(root: Path, manifest: dict, *, cancel=None, allow_generated=False, allow_extra=False) -> None:
    expected = manifest["files"]
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
              and not (allow_generated and ("__pycache__" in path.parts or path.suffix == ".pyc"))}
    if (not set(expected).issubset(actual)) or (not allow_extra and actual != set(expected)):
        raise ValueError("The ComfyUI source file list does not match the pinned commit.")
    for relative, info in expected.items():
        _check_cancel(cancel)
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsafe source manifest path.")
        path = _owned_path(root, path)
        data = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob != info["blob"]:
            raise ValueError(f"The pinned source checksum does not match: {relative}")


def _run_command(args, *, env, log_path, cancel, progress=None):
    """Run an owned background process and retain details only in its local log."""
    _check_cancel(cancel)
    job = None
    if os.name == "nt":
        try:
            from service.windows_job import WindowsJobProcess
        except ImportError:
            # A source-only runtime folder may omit the host. Its wheel-only pip
            # operation needs no compiler descendants; the regular release uses
            # the owned Job implementation included by PyInstaller.
            WindowsJobProcess = None
        if WindowsJobProcess is not None:
            job = WindowsJobProcess(list(map(str, args)), cwd=str(log_path.parent), env=env,
                                    log_path=log_path, memory_limit_bytes=8 * 1024**3)
    last = time.monotonic()
    if job is not None:
        try:
            while (code := job.poll_root()) is None:
                _check_cancel(cancel)
                time.sleep(0.1)
                if time.monotonic() - last >= 2:
                    _progress(progress, "packages", "Preparing image processing. This may take a few minutes…")
                    last = time.monotonic()
            _check_cancel(cancel)
            if code:
                raise subprocess.CalledProcessError(code, args)
        finally:
            job.close(timeout=2)
        return
    # Non-Windows fallback keeps unit tests portable and the developer CLI usable.
    with log_path.open("ab") as log:
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(list(map(str, args)), env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, **options)
        try:
            while (code := process.poll()) is None:
                _check_cancel(cancel)
                time.sleep(0.1)
            _check_cancel(cancel)
            if code:
                raise subprocess.CalledProcessError(code, args)
        finally:
            if process.poll() is None:
                if os.name != "nt":
                    import signal
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait(timeout=5)


VALIDATION = """import importlib.metadata as metadata, json, runpy, sys
from pathlib import Path
_dll_search_support = runpy.run_path(sys.argv[2])
import torch, torchvision
expected = dict(line.split('==', 1) for line in Path(sys.argv[1]).read_text().splitlines() if line and not line.startswith('#'))
expected.update(torch='2.14.1+cu132', torchvision='0.29.1+cu132')
mismatches = {name: [version, metadata.version(name)] for name, version in expected.items() if metadata.version(name) != version}
if sys.version_info[:3] != (3, 13, 14) or mismatches or torch.cuda.is_initialized():
    raise RuntimeError('Runtime validation failed: ' + repr(mismatches))
print(json.dumps({'python': sys.version.split()[0], 'verified_packages': len(expected), 'cuda_initialized': False}))
"""


def _receipt():
    return {"schema": 1, "installed": True, "python": "python/python.exe", "site_packages": "python/Lib/site-packages",
            "comfy_main": "ComfyUI/main.py", "python_version": PYTHON_VERSION, "comfy_commit": COMFY_COMMIT,
            "comfy_base": COMFY_BASE, "torch": "2.14.1+cu132", "torchvision": "0.29.1+cu132"}


def _complete(destination):
    try:
        receipt_path = _owned_path(destination, destination / "runtime-receipt.json")
        if (destination / INCOMPLETE_FILE).exists():
            return False
        info = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(info, dict) or any(info.get(key) != value for key, value in _receipt().items()):
            return False
        for field in ("python", "site_packages", "comfy_main"):
            path = _owned_path(destination, destination / info[field])
            if not (path.is_dir() if field == "site_packages" else path.is_file()):
                return False
        return True
    except (OSError, ValueError):
        return False


def _environment(temporary_dir):
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith(("PYTHON", "PIP_", "UV_"))}
    env.update(TEMP=str(temporary_dir), TMP=str(temporary_dir), TMPDIR=str(temporary_dir),
               CUDA_VISIBLE_DEVICES="-1", PYTHONUTF8="1")
    return env


def _validate(destination, env, log_path, cancel, progress):
    _progress(progress, "verify", "Checking the installed image-processing files…")
    python = destination / "python" / "python.exe"
    _run_command([python, "-m", "pip", "--isolated", "check"], env=env, log_path=log_path,
                 cancel=cancel, progress=progress)
    _run_command([python, "-c", VALIDATION, ROOT / "constraints-win.txt", ROOT / "windows_dlls.py"], env=env,
                 log_path=log_path, cancel=cancel, progress=progress)


def install(destination: Path, *, progress=None, cancel=None) -> None:
    """Install or continue only an Artegra-owned runtime; preserve external folders.

    ``progress`` receives stage/message/completed/total dictionaries. A total of
    zero means an indeterminate operation; download events report real byte counts.
    Setting the cancellation Event leaves verified downloads available for retry.
    """
    _check_cancel(cancel)
    require_supported_platform()
    original = destination.expanduser().absolute()
    for path in (original, *original.parents):
        if _linked(path):
            raise ValueError("The installation folder contains a link. Choose another location.")
    destination = original.resolve()
    recipe = _recipe()
    complete = destination.is_dir() and _complete(destination)
    owned = False
    if destination.exists():
        try:
            owner_path = _owned_path(destination, destination / OWNER_FILE)
            owned = json.loads(owner_path.read_text(encoding="utf-8")) == recipe
        except (OSError, ValueError):
            pass
        if not owned and not complete:
            raise FileExistsError("This folder belongs to another installation. Choose a different location.")
    else:
        destination.mkdir(parents=True, exist_ok=False)
        _write_json(destination / OWNER_FILE, recipe)
        owned = True
    with _installation_lock(destination):
        _check_cancel(cancel)
        cache_dir = _owned_path(destination, destination / ".cache")
        temporary_dir = _owned_path(destination, destination / ".tmp")
        cache_dir.mkdir(exist_ok=True)
        temporary_dir.mkdir(exist_ok=True)
        log_path = _owned_path(destination, destination / "setup-details.log")
        env = _environment(temporary_dir)
        if complete:
            # A receipt alone never hides a broken interpreter or changed packages.
            try:
                verify_source(destination / "ComfyUI", json.loads((ROOT / "source-manifest.json").read_text()),
                              cancel=cancel, allow_generated=True, allow_extra=True)
                _validate(destination, env, log_path, cancel, progress)
            except SetupCancelled:
                raise
            except (OSError, ValueError, subprocess.CalledProcessError):
                if not owned:
                    raise ValueError("The existing image-processing installation needs repair. Choose a new installation location.")
                _progress(progress, "repair", "Repairing image processing automatically…")
            else:
                _progress(progress, "complete", "Image processing is ready.", 1, 1)
                return
        marker = _owned_path(destination, destination / INCOMPLETE_FILE)
        marker.write_text("Artegra Enhancer installation is incomplete. Open setup to continue.\n", encoding="utf-8")
        receipt_path = _owned_path(destination, destination / "runtime-receipt.json")
        receipt_path.unlink(missing_ok=True)
        assets_dir = _owned_path(destination, cache_dir / "assets")
        _owned_path(destination, cache_dir / "pip")
        assets_dir.mkdir(exist_ok=True)
        assets = {}
        for name, (url, digest) in ASSETS.items():
            _check_cancel(cancel)
            filename = f"{name}-{digest[:16]}" + (".whl" if name == "pip" else ".zip")
            asset = _owned_path(destination, assets_dir / filename)
            download(url, digest, asset, progress=progress, cancel=cancel)
            assets[name] = asset
        _progress(progress, "extract", "Preparing the application’s image-processing files…")
        python_dir = _owned_path(destination, destination / "python")
        comfy_dir = _owned_path(destination, destination / "ComfyUI")
        # Re-extracting the pinned base restores interrupted source writes. Added
        # patch files are replaced idempotently, and installed wheels stay in Lib.
        safe_extract(assets["python"], python_dir, cancel=cancel)
        safe_extract(assets["comfyui"], comfy_dir, strip_root=True, cancel=cancel)
        _check_cancel(cancel)
        apply_patch(comfy_dir, ROOT / "patches" / "0001-reference-runtime.patch")
        verify_source(comfy_dir, json.loads((ROOT / "source-manifest.json").read_text()),
                      cancel=cancel, allow_generated=True, allow_extra=complete)
        site_packages = _owned_path(destination, python_dir / "Lib" / "site-packages")
        site_packages.mkdir(parents=True, exist_ok=True)
        _owned_path(destination, python_dir / "python313._pth").write_text(
            "python313.zip\n.\nLib/site-packages\nimport site\n", encoding="utf-8")
        python = python_dir / "python.exe"
        code = "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('pip',run_name='__main__')"
        _progress(progress, "packages", "Installing image processing. Downloads continue automatically…")
        # Reinstall uses the persistent pip cache but repairs any wheel unpacking
        # interrupted after its metadata was written. No source builds are allowed.
        _run_command([python, "-c", code, assets["pip"], "--isolated", "install", "--force-reinstall",
                      "--disable-pip-version-check", "--no-input", "--no-warn-script-location",
                      "--only-binary=:all:", "--require-hashes", "--cache-dir", cache_dir / "pip",
                      "--index-url", "https://pypi.org/simple", "-r", ROOT / "requirements-win.lock"],
                     env=env, log_path=log_path, cancel=cancel, progress=progress)
        _validate(destination, env, log_path, cancel, progress)
        _check_cancel(cancel)
        _write_json(receipt_path, _receipt())
        marker.unlink()
        _progress(progress, "complete", "Image processing is ready.", 1, 1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or resume the app-managed image engine. Downloads several GB; does not download models.")
    parser.add_argument("--install", action="store_true", help="Explicitly authorize downloading and installing the runtime")
    parser.add_argument("--directory", type=Path, help="New destination or this setup program's existing installation")
    args = parser.parse_args(argv)
    if not args.install or not args.directory:
        parser.print_help()
        return 0
    try:
        install(args.directory)
    except (KeyboardInterrupt, SetupCancelled):
        print("Setup paused. No completed runtime was recorded. Run setup again to continue.", file=sys.stderr)
        return 130
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f"Setup stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

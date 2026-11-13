"""Install the pinned engine into a NEW folder, only on explicit user request."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, expected: str, destination: Path) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
        raise ValueError("Runtime downloads must use an approved official HTTPS source.")
    with urllib.request.urlopen(url, timeout=120) as response:
        final = urllib.parse.urlsplit(response.url)
        if final.scheme != "https" or final.hostname not in OFFICIAL_HOSTS:
            raise ValueError("Unexpected runtime download redirect.")
        with destination.open("wb") as stream:
            shutil.copyfileobj(response, stream)
    if sha256(destination) != expected:
        destination.unlink(missing_ok=True)
        raise ValueError("Runtime download checksum did not match. Setup stopped.")


def safe_extract(archive: Path, destination: Path, *, strip_root: bool = False) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            parts = Path(item.filename.replace("\\", "/")).parts
            if strip_root:
                parts = parts[1:]
            if not parts:
                continue
            target = destination.joinpath(*parts).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("Unsafe archive member.")
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Runtime archive symlinks are not supported.")
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)


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
        path = (root / new[2:]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Unsafe patch path.")
        original = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []
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


def verify_source(root: Path, manifest: dict) -> None:
    expected = manifest["files"]
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if actual != set(expected):
        raise ValueError("The ComfyUI source file list does not match the pinned commit.")
    for relative, info in expected.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Unsafe source manifest path.")
        data = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob != info["blob"]:
            raise ValueError(f"The pinned source checksum does not match: {relative}")


def install(destination: Path) -> None:
    if sys.platform != "win32":
        raise ValueError("This runtime lock supports Windows x64 only.")
    destination = destination.expanduser().resolve()
    # Exclusive creation prevents setup from modifying ANY existing runtime.
    destination.mkdir(parents=True, exist_ok=False)
    marker = destination / "SETUP-INCOMPLETE.txt"
    marker.write_text("Setup has not completed. This folder can be removed and setup retried.\n")
    with tempfile.TemporaryDirectory(prefix="artegra-download-") as scratch:
        scratch = Path(scratch)
        for name, (url, digest) in ASSETS.items():
            print(f"Downloading verified {name}…", flush=True)
            download(url, digest, scratch / name)
        python_dir = destination / "python"
        comfy_dir = destination / "ComfyUI"
        safe_extract(scratch / "python", python_dir)
        safe_extract(scratch / "comfyui", comfy_dir, strip_root=True)
        apply_patch(comfy_dir, ROOT / "patches" / "0001-reference-runtime.patch")
        verify_source(comfy_dir, json.loads((ROOT / "source-manifest.json").read_text()))
        (python_dir / "Lib" / "site-packages").mkdir(parents=True)
        (python_dir / "python313._pth").write_text("python313.zip\n.\nLib/site-packages\nimport site\n")
        python = python_dir / "python.exe"
        pip_wheel = scratch / "pip.whl"
        (scratch / "pip").rename(pip_wheel)
        env = {key: value for key, value in os.environ.items() if not key.startswith(("PYTHON", "PIP_", "UV_"))}
        code = "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('pip',run_name='__main__')"
        print("Installing pinned engine packages. This downloads several gigabytes; no models are included.", flush=True)
        subprocess.run([str(python), "-c", code, str(pip_wheel), "--isolated", "install", "--disable-pip-version-check", "--no-input", "--only-binary=:all:", "--require-hashes", "--index-url", "https://pypi.org/simple", "-r", str(ROOT / "requirements-win.lock")], env=env, check=True)
        subprocess.run([str(python), "-c", "import sys, torch, torchvision; assert sys.version_info[:3] == (3,13,14); assert torch.__version__ == '2.14.1+cu132'; assert torchvision.__version__ == '0.29.1+cu132'"], env=env, check=True)
    receipt = {"schema": 1, "installed": True, "python": "python/python.exe", "site_packages": "python/Lib/site-packages", "comfy_main": "ComfyUI/main.py", "python_version": PYTHON_VERSION, "comfy_commit": COMFY_COMMIT, "comfy_base": COMFY_BASE, "torch": "2.14.1+cu132", "torchvision": "0.29.1+cu132"}
    (destination / "runtime-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    marker.unlink()
    print(f"Runtime installed. Choose this folder in Artegra Enhancer: {destination}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Install the pinned image engine into a new, separate folder. Downloads several GB; does not download models.")
    parser.add_argument("--install", action="store_true", help="Explicitly authorize downloading and installing the runtime")
    parser.add_argument("--directory", type=Path, help="New destination folder; it must not already exist")
    args = parser.parse_args(argv)
    if not args.install or not args.directory:
        parser.print_help()
        return 0
    try:
        install(args.directory)
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f"Setup stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

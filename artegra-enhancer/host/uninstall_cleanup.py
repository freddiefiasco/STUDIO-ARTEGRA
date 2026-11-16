"""What the uninstaller may remove besides the app itself, when the person ticks the options.

  --remove-files     the downloaded enhancement files the app manages: the model files named in models.manifest.json
                     (with their partial and set-aside copies) and the managed image engine, only inside the app's
                     own data folder, never a folder the person chose themselves
  --remove-settings  the app's settings, logs and records (the state folders and the Qt settings key)
  --measure          print the size the files option would free, in bytes, and remove nothing

Enhanced images are never removed: no output folder and no image is in scope. Links and junctions are never followed.
Every action is written to a log file in %TEMP%.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import time

MANIFEST = "models.manifest.json"
APP_STATE_PARTS = ("Studio Artegra", "Artegra Enhancer")
SETTINGS_KEY = "Software\\Studio Artegra\\Artegra Enhancer"


class Log:
    def __init__(self, path=None):
        self.path = path
        self.lines = []

    def __call__(self, text):
        self.lines.append(text)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as stream:
                stream.write(time.strftime("%H:%M:%S ") + text + "\n")


def _is_link(path) -> bool:
    """A symbolic link or any reparse point (a junction too). Never resolved, never followed."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)   # FILE_ATTRIBUTE_REPARSE_POINT


def _norm(path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _inside(child, parent) -> bool:
    child, parent = _norm(child), _norm(parent)
    return child != parent and child.startswith(parent.rstrip("\\/") + os.sep)


def _chain_has_link(path, top) -> bool:
    """True when `path` or any folder between it and `top` (both included) is a link or junction."""
    current = Path(os.path.abspath(str(path)))
    stop = _norm(top)
    while True:
        if _is_link(current):
            return True
        if _norm(current) == stop or current.parent == current:
            return False
        current = current.parent


def _read_json(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def state_root(state_root_arg=None) -> Path:
    if state_root_arg:
        return Path(state_root_arg).expanduser()
    from host.installation import known_folder
    return known_folder("local").joinpath(*APP_STATE_PARTS)


def data_folder(root: Path) -> Path:
    """The app's data folder as setup recorded it (installation-location.json), else the default beside the states."""
    saved = _read_json(root / "production" / "installation-location.json") or {}
    value = saved.get("data_directory")
    return Path(value) if isinstance(value, str) and value else root / "data"


def _managed(root: Path, data: Path, key: str, default: str):
    """The folder setup chose for `key` when it is exactly the app-managed default inside the data folder (compared as
    written, never through links), else None."""
    choices = _read_json(root / "production" / "folders.json") or {}
    value = choices.get(key) or str(data / default)
    if _norm(value) != _norm(data / default):
        return None
    managed = Path(os.path.abspath(str(data / default)))
    return None if _chain_has_link(managed, data) else managed


def model_targets(app_root: Path, models: Path):
    """The manifest's files under the managed models folder, with their .part and .damaged-* siblings."""
    manifest = _read_json(app_root / MANIFEST) or {}
    entries = manifest.get("models")
    if isinstance(entries, dict):
        entries = list(entries.values())
    out = []
    for model in entries or []:
        if not isinstance(model, dict):
            continue
        folder, filename = model.get("folder"), model.get("filename")
        if not isinstance(folder, str) or not isinstance(filename, str) or "/" in filename or "\\" in filename or ".." in (folder, filename):
            continue
        directory = models / folder
        if not _inside(directory, models) or _is_link(directory) or not directory.is_dir():
            continue
        for candidate in directory.iterdir():
            name = candidate.name
            if name == filename or (name.startswith(filename + ".") and (name.endswith(".part") or ".damaged-" in name)):
                out.append(candidate)
    return out


def engine_target(runtime: Path):
    """The managed image engine folder, when it carries both of setup's own records."""
    if runtime is None or _is_link(runtime) or not runtime.is_dir():
        return None
    if (runtime / "runtime-receipt.json").is_file() and (runtime / ".artegra-runtime.json").is_file():
        return runtime
    return None


def _size(path: Path) -> int:
    if _is_link(path):
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for base, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not _is_link(Path(base) / d)]
        for name in files:
            try:
                total += os.lstat(Path(base) / name).st_size
            except OSError:
                pass
    return total


def _remove_link(path: Path, log) -> None:
    """Remove a link or junction itself; what it points to is never touched."""
    try:
        os.rmdir(path)
    except OSError:
        try:
            os.unlink(path)
        except OSError as exc:
            log(f"could not remove the link {path}: {exc}")
            return
    log(f"removed the link {path} (not what it points to)")


def _remove_tree(path: Path, log) -> None:
    """Remove a real folder: links and junctions inside it are removed as links, never entered."""
    try:
        entries = list(os.scandir(path))
    except OSError as exc:
        log(f"could not read {path}: {exc}")
        return
    for entry in entries:
        child = Path(entry.path)
        if _is_link(child):
            _remove_link(child, log)
        elif entry.is_dir(follow_symlinks=False):
            _remove_tree(child, log)
        else:
            try:
                os.chmod(child, stat.S_IWRITE)
                os.unlink(child)
            except OSError as exc:
                log(f"could not remove {child}: {exc}")
    try:
        os.rmdir(path)
    except OSError as exc:
        log(f"could not remove {path}: {exc}")


def _remove(path: Path, log) -> None:
    if _is_link(path):
        log(f"skipped a link: {path}")
        return
    if path.is_dir():
        _remove_tree(path, log)
    elif path.exists():
        try:
            os.chmod(path, stat.S_IWRITE)
            path.unlink()
        except OSError as exc:
            log(f"could not remove {path}: {exc}")
            return
    log(f"removed {path}")


def _prune_empty(start: Path, stop: Path, log) -> None:
    """Remove empty real folders from `start` up to `stop` (included), never above it and never a link."""
    current = Path(os.path.abspath(str(start)))
    while _inside(current, stop) or _norm(current) == _norm(stop):
        if _is_link(current):
            return
        try:
            if any(current.iterdir()):
                return
            os.rmdir(current)
            log(f"removed empty folder {current}")
        except OSError:
            return
        if _norm(current) == _norm(stop):
            return
        current = current.parent


def plan_files(app_root: Path, root: Path):
    """[(path, kind)] the files option would remove."""
    data = data_folder(root)
    out = []
    models = _managed(root, data, "models_dir", "models")
    if models is not None and models.is_dir() and not _is_link(models):
        out += [(p, "model") for p in model_targets(app_root, models)]
    runtime = engine_target(_managed(root, data, "runtime_dir", "engine-v1"))
    if runtime is not None:
        out.append((runtime, "engine"))
    return data, models, out


def remove_files(app_root: Path, root: Path, log) -> None:
    data, models, targets = plan_files(app_root, root)
    for path, kind in targets:
        _remove(path, log)
    if models is not None:
        for folder in sorted({p.parent for p, kind in targets if kind == "model"}, key=lambda p: -len(p.parts)):
            _prune_empty(folder, models, log)
    if data.is_dir() and not _is_link(data):
        _prune_empty(data, data, log)


def _protected(root: Path):
    """Folders that may hold images: every state's outputs folder and the chosen output folder."""
    out = []
    for name in ("production", "demo"):
        out.append(root / name / "outputs")
        choices = _read_json(root / name / "folders.json") or {}
        if isinstance(choices.get("output_dir"), str) and choices["output_dir"]:
            out.append(Path(choices["output_dir"]))
    return out


def remove_settings(root: Path, log) -> None:
    keep = _protected(root)
    if _is_link(root):
        log(f"skipped {root}: it is a link")
        return
    for name in ("production", "demo"):
        folder = root / name
        if not folder.is_dir() or _is_link(folder):
            continue
        for child in folder.iterdir():
            if _is_link(child):
                log(f"kept the link {child}")
                continue
            if any(_norm(child) == _norm(k) or _inside(k, child) or _inside(child, k) for k in keep):
                log(f"kept {child} (it can hold images)")
                continue
            _remove(child, log)
        _prune_empty(folder, folder, log)
    for name in ("cache", "qmlcache"):
        folder = root / name
        if folder.is_dir() and not _is_link(folder):
            _remove(folder, log)
    if os.name == "nt":
        _delete_key(SETTINGS_KEY, log)
        _delete_key(SETTINGS_KEY.rsplit("\\", 1)[0], log, only_if_empty=True)
    _prune_empty(root, root, log)
    if root.parent.name == APP_STATE_PARTS[0]:
        _prune_empty(root.parent, root.parent, log)


def _delete_key(path, log, only_if_empty=False):
    """Delete one HKCU key the app's settings created, with its subkeys (nothing outside it)."""
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ)
    except OSError:
        return
    with key:
        subkeys = []
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, len(subkeys)))
            except OSError:
                break
        if only_if_empty:
            try:
                winreg.EnumValue(key, 0)
                return
            except OSError:
                if subkeys:
                    return
    for sub in subkeys:
        _delete_key(path + "\\" + sub, log)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        log("removed the settings key HKCU\\" + path)
    except OSError as exc:
        log(f"could not remove the settings key HKCU\\{path}: {exc}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ArtegraEnhancer --uninstall-cleanup")
    parser.add_argument("--remove-files", action="store_true")
    parser.add_argument("--remove-settings", action="store_true")
    parser.add_argument("--measure", action="store_true")
    parser.add_argument("--out", default=None, help="with --measure: write the byte count to this file")
    parser.add_argument("--state", help="the state root the installer recorded (default: the per-user location)")
    parser.add_argument("--app-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--log", default=None)
    args = parser.parse_args(argv)
    root = state_root(args.state)
    app_root = Path(args.app_root)
    if args.measure:
        _, _, targets = plan_files(app_root, root)
        total = sum(_size(p) for p, _ in targets)
        if args.out:
            Path(args.out).write_text(str(total), encoding="ascii")
        print(total)
        return 0
    log_path = args.log or str(Path(os.environ.get("TEMP") or Path.home()) / time.strftime("ArtegraEnhancer-uninstall-%Y%m%d-%H%M%S.log"))
    log = Log(log_path)
    log(f"cleanup: files={args.remove_files} settings={args.remove_settings} state={root}")
    if args.remove_files:
        remove_files(app_root, root, log)
    if args.remove_settings:
        remove_settings(root, log)
    log("cleanup finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

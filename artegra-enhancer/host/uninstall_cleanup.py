"""What the uninstaller may remove besides the app itself, when the person ticks the options.

  --remove-files     the downloaded enhancement files the app manages, only inside the app's own data folder, never a
                     folder the person chose themselves: the model files named in models.manifest.json (with their
                     partial and set-aside copies) and what runtime setup put in the managed image engine folder. There,
                     only setup's own entries are removed, by exact name (ENGINE_TREES, ENGINE_FILES, ENGINE_RECORDS),
                     and in its ComfyUI folder only the files that are, byte for byte, the pinned source listed in
                     runtime/source-manifest.json. Anything else in the engine folder is kept and logged.
  --remove-settings  the app's own settings, logs and records: only the entries the app itself creates in its state
                     folders, by exact name (OWNED_DIRS, OWNED_FILES), the Qt caches and the Qt settings key.
                     Anything else in a state folder is kept and logged, whatever it is.
  --measure          print the size the files option would free, in bytes, and remove nothing

Enhanced images are never removed. The output folders the app's records name (folders.json, the service's
settings.json, config.json and each job record) are collected once, before either option runs, and both options keep
them: a recorded output folder is never entered or removed, and an app or engine folder that is one, holds one, or
holds a file named like a result (<name>_cu<N>x...) is kept whole. Links and junctions are never followed.
Every action is written to a log file in %TEMP%.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

MANIFEST = "models.manifest.json"
APP_STATE_PARTS = ("Studio Artegra", "Artegra Enhancer")
SETTINGS_KEY = "Software\\Studio Artegra\\Artegra Enhancer"
STATES = ("production", "demo")
# What the host and the service create in a state folder. Only these are removed; "outputs" is never one of them.
OWNED_DIRS = frozenset({"jobs", "media", "work", "workers", "logs", "run", "notify"})
OWNED_FILES = frozenset({
    "settings.json", "settings-meta.json", "settings-extra.json", "config.json", "folders.json", "service.json",
    "service.lock", "notifications.jsonl", "preferences.ini", "preferences.ini.lock", "installation-location.json",
    "installation-consent.json", "installation.json", "installation.lock", "model-licence-acceptance.json",
    "host.log", "host-service.log", "installation.log", "installation-graphics.log",
})
SESSION_TOKEN_RE = re.compile(r"^session-[0-9a-f]{16}\.token$")
# A left-over atomic-write temp file of an owned file: <name>.tmp, <name>.<pid>.<hex>.tmp or <name>.<uuid>.tmp.
OWNED_TEMP_RE = re.compile(r"^(.+?)\.(?:\d+\.[0-9a-f]{6}\.|[0-9a-f]{32}\.)?tmp$")
# A result or its recipe file, as the service names them: <stem>_cu<N>x[_bolt|_fast][_n].<ext> (and dot-named partials).
RESULT_RE = re.compile(r"_cu\d+x.*\.(?:png|tiff?|jpe?g|webp|exr|json)$", re.IGNORECASE)
# What runtime setup (runtime/setup_runtime.py, the same names since alpha 1) creates at the top of the managed image
# engine folder, compared in lower case. The app never writes there after setup: the engine's workers keep their input,
# output, temp and user folders in the state folder (service/workers.comfy_command) and run Python with -B.
ENGINE_TREES = frozenset({"python", ".cache", ".tmp"})      # removed whole unless an output folder or a result is there
ENGINE_SOURCE = "comfyui"                                   # only the pinned source's own files are removed
ENGINE_FILES = frozenset({"setup-details.log", "setup-incomplete.txt", ".setup.lock",
                          "runtime-receipt.json.tmp", ".artegra-runtime.json.tmp"})
# Setup's records mark the folder as setup's own: removed last, and only when nothing else is left in the folder, so
# setup still recognises a folder whose other files were kept.
ENGINE_RECORDS = frozenset({"runtime-receipt.json", ".artegra-runtime.json"})
SOURCE_MANIFEST = ("runtime", "source-manifest.json")


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


def _prune_empty(start: Path, stop: Path, log, keep=None) -> None:
    """Remove empty real folders from `start` up to `stop` (included), never above it, never a link and, with `keep`,
    never a recorded output folder or a folder that holds one."""
    current = Path(os.path.abspath(str(start)))
    while _inside(current, stop) or _norm(current) == _norm(stop):
        if _is_link(current) or (keep is not None and keep.holds(current)):
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


def _tree_facts(path: Path):
    """(the first file named like a result, the total size) of a real folder, in one walk; links are never entered."""
    total, folders = 0, [path]
    while folders:
        try:
            entries = list(os.scandir(folders.pop()))
        except OSError:
            continue
        for entry in entries:
            child = Path(entry.path)
            if _is_link(child):
                continue
            if entry.is_dir(follow_symlinks=False):
                folders.append(child)
                continue
            if RESULT_RE.search(entry.name):
                return child, total
            try:
                total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                pass
    return None, total


def _git_blob(path: Path):
    """The file's git blob id, as runtime/source-manifest.json records each source file, or None if it can't be read."""
    try:
        digest = hashlib.sha1(b"blob %d\0" % os.lstat(path).st_size)
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _source_manifest(app_root: Path):
    """{relative path, normalised: blob id} of the engine source setup installs, or None when the list can't be read."""
    files = (_read_json(app_root.joinpath(*SOURCE_MANIFEST)) or {}).get("files")
    if not isinstance(files, dict):
        return None
    out = {os.path.normcase(relative): info["blob"] for relative, info in files.items()
           if isinstance(relative, str) and isinstance(info, dict) and isinstance(info.get("blob"), str)}
    return out or None


class _EnginePlan:
    """What the files option does in the managed image engine folder, worked out before anything is removed, so the
    size the uninstaller shows (--measure) is exactly what the option removes."""

    def __init__(self, engine: Path):
        self.engine = engine
        self.remove = []        # setup's own folders and files, removed whole
        self.source = []        # files of setup's pinned engine source, removed one by one
        self.folders = []       # source folders to remove once empty, deepest first
        self.records = []       # setup's records, removed last when nothing else is left
        self.kept = []          # (path, reason)
        self.size = 0           # bytes in `remove` and `source`

    def bytes_freed(self) -> int:
        return self.size + (0 if self.kept else sum(_size(p) for p in self.records))


def _plan_source(source: Path, manifest, keep, plan: _EnginePlan) -> None:
    """Setup's ComfyUI folder: only files that are, byte for byte, the source setup installed there (and the .pyc files
    Python compiles from it) are removed. A recorded output folder is never entered; links are never followed."""
    if manifest is None:
        plan.kept.append((source, "the list of the engine's own files could not be read"))
        return
    for base, dirs, files in os.walk(source, followlinks=False):
        here = Path(base)
        for name in sorted(dirs):
            child = here / name
            if _is_link(child) or keep.is_one(child):
                plan.kept.append((child, "a link" if _is_link(child) else "an output folder"))
                dirs.remove(name)
        for name in sorted(files):
            child = here / name
            if _is_link(child):
                plan.kept.append((child, "a link"))
                continue
            expected = manifest.get(os.path.normcase(os.path.relpath(child, source)))
            if child.suffix.lower() == ".pyc" or (expected is not None and _git_blob(child) == expected):
                plan.source.append(child)
                plan.size += _size(child)
            else:
                plan.kept.append((child, "the engine setup did not put it there"))
        plan.folders.append(here)
    plan.folders.reverse()


def plan_engine(engine: Path, app_root: Path, keep) -> _EnginePlan:
    """Sort the engine folder's entries into what setup created (removed) and anything else (kept, with the reason)."""
    plan = _EnginePlan(engine)
    try:
        children = sorted(engine.iterdir())
    except OSError as exc:
        plan.kept.append((engine, f"it could not be read: {exc}"))
        return plan
    manifest = None
    for child in children:
        name = child.name.lower()
        if _is_link(child):
            plan.kept.append((child, "a link"))
        elif child.is_dir() and name == ENGINE_SOURCE:
            if keep.is_one(child):
                plan.kept.append((child, "an output folder"))
            else:
                manifest = manifest or _source_manifest(app_root)
                _plan_source(child, manifest, keep, plan)
        elif child.is_dir() and name in ENGINE_TREES:
            # The service saves results straight into the output folder, never below it, so a tree that only sits
            # inside an output folder holds none unless one is named like a result.
            if keep.holds(child):
                plan.kept.append((child, "an output folder is there"))
                continue
            found, size = _tree_facts(child)
            if found is not None:
                plan.kept.append((child, f"it holds {found.name}, which looks like an enhanced image or its recipe"))
            else:
                plan.remove.append(child)
                plan.size += size
        elif child.is_file() and name in ENGINE_FILES:
            plan.remove.append(child)
            plan.size += _size(child)
        elif child.is_file() and name in ENGINE_RECORDS:
            plan.records.append(child)
        else:
            plan.kept.append((child, "not one of the image engine's own files"))
    return plan


def _apply_engine(plan: _EnginePlan, keep, log) -> None:
    for path in plan.remove:
        _remove(path, log)
    removed = 0
    for path in plan.source:
        try:
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)
            removed += 1
        except OSError as exc:
            log(f"could not remove {path}: {exc}")
    if plan.source:
        log(f"removed {removed} files of the image engine's source")
    for folder in plan.folders:
        try:
            os.rmdir(folder)            # only an empty folder; a folder that still holds anything stays
        except OSError:
            pass
    for path, reason in plan.kept:
        log(f"kept {path} ({reason})")
    try:
        left = [c for c in plan.engine.iterdir() if c.name.lower() not in ENGINE_RECORDS]
    except OSError:
        return
    if left:
        log(f"kept {plan.engine} and setup's records in it: it still holds files that are not the engine's own")
        return
    for path in plan.records:
        _remove(path, log)
    _prune_empty(plan.engine, plan.engine, log, keep)


def plan_files(app_root: Path, root: Path, keep):
    """(data folder, managed models folder, [model files], engine plan or None) for the files option."""
    data = data_folder(root)
    models = _managed(root, data, "models_dir", "models")
    targets = []
    if models is not None and models.is_dir() and not _is_link(models):
        targets = model_targets(app_root, models)
    runtime = engine_target(_managed(root, data, "runtime_dir", "engine-v1"))
    engine = plan_engine(runtime, app_root, keep) if runtime is not None else None
    return data, models, targets, engine


def measure_files(app_root: Path, root: Path, keep) -> int:
    """The bytes the files option would free: the model files and what it removes in the engine folder, nothing kept."""
    _, _, targets, engine = plan_files(app_root, root, keep)
    return sum(_size(p) for p in targets) + (engine.bytes_freed() if engine is not None else 0)


def remove_files(app_root: Path, root: Path, log, keep=None) -> None:
    keep = keep if keep is not None else keep_for(root, files=True)
    data, models, targets, engine = plan_files(app_root, root, keep)
    for path in targets:
        _remove(path, log)
    if models is not None:
        for folder in sorted({p.parent for p in targets}, key=lambda p: -len(p.parts)):
            _prune_empty(folder, models, log, keep)
    if engine is not None:
        _apply_engine(engine, keep, log)
    if data.is_dir() and not _is_link(data):
        _prune_empty(data, data, log, keep)


def _owned(child: Path) -> bool:
    """True for an entry the app itself creates at the top of a state folder (by exact name and kind)."""
    name = child.name.lower()
    if child.is_dir():
        return name in OWNED_DIRS
    if name in OWNED_FILES or SESSION_TOKEN_RE.match(name):
        return True
    temp = OWNED_TEMP_RE.match(name)
    return bool(temp and temp.group(1) in OWNED_FILES)


def _output_folders(root: Path):
    """Every folder the app's own records say images were or will be saved to, in both states: the outputs folders,
    the output folder of folders.json, of the service's settings.json and of config.json, and each job's output folder
    with the folders of its items' results and recipe files. Unreadable records add nothing; the result-name guard covers them."""
    out = []

    def add(value, is_file=False):
        if isinstance(value, str) and value.strip() and os.path.isabs(value.strip()):
            path = Path(value.strip())
            out.append(path.parent if is_file else path)

    for name in STATES:
        state = root / name
        out.append(state / "outputs")
        add((_read_json(state / "folders.json") or {}).get("output_dir"))
        add((_read_json(state / "settings.json") or {}).get("output_dir"))
        add((_read_json(state / "config.json") or {}).get("default_output_dir"))
        jobs = state / "jobs"
        if not jobs.is_dir() or _is_link(jobs):
            continue
        for record in sorted(jobs.glob("j*.json")):
            job = _read_json(record) or {}
            add(job.get("output_dir"))
            for item in job.get("items") if isinstance(job.get("items"), list) else []:
                if not isinstance(item, dict):
                    continue
                add(item.get("output"), is_file=True)
                add(item.get("sidecar"), is_file=True)
                if isinstance(item.get("publishing"), dict):
                    add(item["publishing"].get("output"), is_file=True)
    return out


def _drive(path) -> str:
    return os.path.splitdrive(_norm(path))[0]


def _forms(path, resolve=True) -> set:
    """The path as written and, with `resolve`, as Windows resolves it (long names, links), both normalised."""
    forms = {_norm(path)}
    if resolve:
        try:
            forms.add(os.path.normcase(os.path.realpath(str(path))))
        except (OSError, ValueError):
            pass
    return forms


class _Folders:
    """The output folders, each once, with their forms worked out once. A folder on another drive than the state
    folder (and than `data`, when the files option runs) is compared only as written: resolving it can wait on an
    offline share, and the result-name guard still covers a drive letter that points back into the app's folders."""

    def __init__(self, folders, root: Path, data: Path = None):
        self.unique, seen = [], set()
        for folder in folders:
            key = _norm(folder)
            if key not in seen:
                seen.add(key)
                self.unique.append(Path(folder))
        drives = {_drive(root)} | ({_drive(data)} if data is not None else set())
        self.forms = set()
        for folder in self.unique:
            self.forms |= _forms(folder, resolve=_drive(folder) in drives)

    def touch(self, entry: Path) -> bool:
        """True when `entry` is one of the folders, holds one of them, or sits inside one."""
        for entry_form in _forms(entry):
            for folder_form in self.forms:
                if entry_form == folder_form or _inside(folder_form, entry_form) or _inside(entry_form, folder_form):
                    return True
        return False

    def holds(self, entry: Path) -> bool:
        """True when `entry` is one of the folders or holds one of them."""
        for entry_form in _forms(entry):
            for folder_form in self.forms:
                if entry_form == folder_form or _inside(folder_form, entry_form):
                    return True
        return False

    def is_one(self, entry: Path) -> bool:
        """True when `entry` is one of the folders."""
        return bool(_forms(entry) & self.forms)


def keep_for(root: Path, files: bool = False) -> _Folders:
    """Every output folder the app's records name, collected once, before either option removes anything. Folders on
    the data folder's drive are resolved only when the files option runs (it works there); the settings option never
    looks a folder up on another drive than the state folder's."""
    return _Folders(_output_folders(root), root, data_folder(root) if files else None)


def _first_result(path: Path):
    """The first file named like a result under `path` (links never entered), or None."""
    if not _is_link(path) and path.is_file():
        return path if RESULT_RE.search(path.name) else None
    for base, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not _is_link(Path(base) / d)]
        for name in files:
            if RESULT_RE.search(name):
                return Path(base) / name
    return None


def _remove_owned(entry: Path, keep, log) -> None:
    """Remove one app-owned entry unless it touches an output folder or holds a result-named file."""
    if keep.touch(entry):
        log(f"kept {entry} (an output folder is there)")
        return
    found = _first_result(entry)
    if found is not None:
        log(f"kept {entry} (it holds {found.name}, which looks like an enhanced image or its recipe)")
        return
    _remove(entry, log)


def remove_settings(root: Path, log, keep=None) -> None:
    if _is_link(root):
        log(f"skipped {root}: it is a link")
        return
    keep = keep if keep is not None else keep_for(root)
    for name in STATES:
        folder = root / name
        if not folder.is_dir() or _is_link(folder):
            continue
        for child in sorted(folder.iterdir()):
            if _is_link(child):
                log(f"kept the link {child}")
            elif not _owned(child):
                log(f"kept {child} (not one of the app's own settings, logs or records)")
            else:
                _remove_owned(child, keep, log)
        _prune_empty(folder, folder, log)
    for name in ("cache", "qmlcache"):
        folder = root / name
        if folder.is_dir() and not _is_link(folder):
            _remove_owned(folder, keep, log)
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
        total = measure_files(app_root, root, keep_for(root, files=True))
        if args.out:
            Path(args.out).write_text(str(total), encoding="ascii")
        print(total)
        return 0
    log_path = args.log or str(Path(os.environ.get("TEMP") or Path.home()) / time.strftime("ArtegraEnhancer-uninstall-%Y%m%d-%H%M%S.log"))
    log = Log(log_path)
    log(f"cleanup: files={args.remove_files} settings={args.remove_settings} state={root}")
    if args.remove_files or args.remove_settings:
        # Read every record once, before either option removes anything; both options keep those folders.
        keep = keep_for(root, files=args.remove_files)
        for folder in keep.unique:
            log(f"output folder kept: {folder}")
        if args.remove_files:
            remove_files(app_root, root, log, keep)
        if args.remove_settings:
            remove_settings(root, log, keep)
    log("cleanup finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

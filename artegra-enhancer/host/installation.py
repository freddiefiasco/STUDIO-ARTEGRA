"""One installation lifecycle shared by the Windows installer and desktop recovery UI."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid

from host.config import read_choices, service_configuration, write_json
from host.model_setup import ModelSetup, SetupError, _file_lock
from runtime import setup_runtime
from runtime.compatibility import require_supported_platform, evaluate_nvidia_driver

GIB = 1024 ** 3

# Setup's memory floor (engine design section 8.2). 5.0.1 needs a 64 GB PC (Windows reports about 61.6 GiB of it). The
# 48 GB floor (44 GiB; a 48 GB PC reports about 46-47.7 GiB) waits for gate R6, which measures 48 GB plans and Save GPU
# memory's commit at the 45.2 GB cap; until then the switch stays off and Setup says 5.0.1's words.
FLOOR_GIB = 60
FLOOR_48_GIB = 44
FLOOR_48_ON = False
MEMORY_64 = ("Artegra Enhancer (Beta) needs 64 GB of system memory for normal enhancement. Setup stopped before the large "
             "downloads. A larger pagefile does not replace this.")
MEMORY_48 = ("Artegra Enhancer (Beta) needs 48 GB of system memory or more. A 48 GB PC makes 2× of 3500 × 2188 and "
             "2800 × 3500 renders and 4× of a 1280 × 1600 image, at the lighter setting their size needs; larger "
             "upscales need more memory. Setup stopped before the large downloads. A larger pagefile does not replace this.")


def memory_floor_gib(on=None) -> int:
    """The least system memory (GiB, as Windows reports it) Setup accepts: 60, or 44 once the 48 GB switch is on."""
    return FLOOR_48_GIB if (FLOOR_48_ON if on is None else on) else FLOOR_GIB


def memory_refusal(total_bytes: int, on=None):
    """Setup's words when a computer has less system memory than the floor, else None."""
    on = FLOOR_48_ON if on is None else on
    if total_bytes >= memory_floor_gib(on) * GIB:
        return None
    return MEMORY_48 if on else MEMORY_64


def known_folder(kind: str) -> Path:
    if os.name == "nt":
        buffer = ctypes.create_unicode_buffer(32768)
        code = {"local": 0x1c, "pictures": 0x27}[kind]
        if ctypes.windll.shell32.SHGetFolderPathW(None, code, None, 0, buffer) == 0:
            return Path(buffer.value)
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) if kind == "local" else Path.home() / "Pictures"


def default_state() -> Path:
    return known_folder("local") / "Studio Artegra" / "Artegra Enhancer" / "production"


def check_hardware() -> None:
    """Read driver and memory information before downloading gigabytes."""
    require_supported_platform()
    executable = shutil.which("nvidia-smi")
    if not executable:
        system = ctypes.create_unicode_buffer(32768)
        if os.name == "nt" and ctypes.windll.kernel32.GetSystemDirectoryW(system, len(system)):
            candidate = Path(system.value) / "nvidia-smi.exe"
            executable = str(candidate) if candidate.is_file() else None
    if not executable:
        raise SetupError("An NVIDIA graphics card and driver are required. Install the NVIDIA Studio driver, restart Windows, then choose Retry.", "hardware")
    try:
        result = subprocess.run([executable, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)
        rows = [line.rsplit(",", 2) for line in result.stdout.splitlines() if line.strip()]
        usable = []
        for name, driver, memory in rows:
            if "RTX" in name.upper() and float(memory.strip()) >= 8000:
                report = evaluate_nvidia_driver(driver.strip())
                if not report["errors"]:
                    usable.append(name)
        if not usable:
            raise SetupError("Artegra Enhancer needs an NVIDIA RTX card with at least 8 GB of graphics memory and a compatible driver. Install a current NVIDIA Studio driver, then choose Retry.", "hardware")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SetupError("Windows could not read your NVIDIA graphics card. Update its driver and restart Windows, then choose Retry.", "hardware") from exc
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(key, ctypes.c_ulonglong) for key in
                    ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
    if os.name == "nt":
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        refusal = memory_refusal(status.total) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None
        if refusal:
            raise SetupError(refusal, "hardware")


class Installation:
    def __init__(self, root: Path, state: Path, *, progress=None, cancel=None, data_directory=None):
        self.root, self.state = Path(root).resolve(), Path(state).resolve()
        self.progress = progress or (lambda event: None)
        self.cancel = cancel or threading.Event()
        try:
            saved_location = json.loads((self.state / "installation-location.json").read_text()).get("data_directory")
        except (OSError, ValueError, AttributeError):
            saved_location = None
        self.data = Path(data_directory or saved_location).expanduser().resolve() if (data_directory or saved_location) else self.state.parent / "data"
        self._fraction = 0.0
        self.store = ModelSetup(self.root / "models.manifest.json", self.state / "model-licence-acceptance.json")
        self.required = [key for key, model in self.store.models.items() if model.get("required_for_standard") or model.get("required_for_fast")]
        self.fingerprint = hashlib.sha256((self.root / "models.manifest.json").read_bytes() + (self.root / "LICENSE.txt").read_bytes()).hexdigest()
        try:
            self.choices = read_choices(self.state / "folders.json")
        except (OSError, ValueError):
            self.choices = {}
        defaults = {"runtime_dir": self.data / "engine-v1", "models_dir": self.data / "models", "output_dir": known_folder("pictures") / "Artegra Enhancer"}
        for key, value in defaults.items():
            if not self.choices.get(key):
                self.choices[key] = str(value)
        previous_data = Path(saved_location).resolve() if saved_location else self.state.parent / "data"
        if data_directory and self.data != previous_data:
            # A deliberate storage change in the wizard takes effect even after
            # interruption. Old files remain untouched on their original drive.
            for key in ("runtime_dir", "models_dir"):
                self.choices[key] = str(defaults[key])
        self.terms = [dict(id=key, name=self.store.models[key].get("display_name", key), notice=self.store.models[key].get("acceptance_notice", ""),
                           license_url=self.store.models[key]["license_url"], model_card_url=self.store.models[key]["model_card_url"]) for key in self.required]

    def _emit(self, stage, message, fraction):
        self._check_cancel()
        self._fraction = max(self._fraction, min(1.0, fraction))
        self.progress(dict(stage=stage, message=message, fraction=self._fraction))

    def _check_cancel(self):
        if self.cancel.is_set():
            raise SetupError("Setup is paused. Open Artegra Enhancer or run the installer again to resume.", "cancelled")

    def terms_accepted(self) -> bool:
        try:
            value = json.loads((self.state / "installation-consent.json").read_text())
            return value.get("fingerprint") == self.fingerprint and all(self.store.accepted(key) for key in self.required)
        except (OSError, ValueError, AttributeError):
            return False

    def _inventory(self):
        inventory = {}
        for key in self.required:
            model = self.store.models[key]
            path = Path(self.choices["models_dir"]) / model["folder"] / model["filename"]
            info = path.stat()
            inventory[key] = {"size": info.st_size, "modified_ns": info.st_mtime_ns}
        return inventory

    def is_complete(self) -> bool:
        try:
            receipt = json.loads((self.state / "installation.json").read_text())
            saved = receipt.get("choices", {}) if isinstance(receipt, dict) else {}
            if not isinstance(receipt, dict) or receipt.get("fingerprint") != self.fingerprint or any(saved.get(key) != self.choices[key] for key in ("runtime_dir", "models_dir")) or not self.terms_accepted():
                return False
            service_configuration(self.choices)
            return receipt.get("models") == self._inventory() and receipt.get("ready") is True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def _check_space(self):
        # Account for separate volumes. Engine installation + cache needs headroom;
        # model files are streamed directly to their final volume, not system temp.
        self._check_cancel()
        unavailable = "The selected storage drive is unavailable. Reconnect it or choose another location, then Retry."
        requirements = {}
        runtime = Path(self.choices["runtime_dir"])
        runtime_needed = not (runtime / "runtime-receipt.json").is_file()
        values = [(runtime, 20 * GIB if runtime_needed else 512 * 1024**2)]
        model_bytes = 0
        for key in self.required:
            model = self.store.models[key]
            target = Path(self.choices["models_dir"]) / model["folder"] / model["filename"]
            if not target.is_file():
                part = target.with_name(target.name + "." + model["sha256"][:16] + ".part")
                model_bytes += max(0, model["size_bytes"] - (part.stat().st_size if part.is_file() else 0))
        values.append((Path(self.choices["models_dir"]), model_bytes + GIB))
        for path, needed in values:
            ancestor = path
            try:
                while not ancestor.exists():
                    self._check_cancel()
                    parent = ancestor.parent
                    if parent == ancestor:
                        raise SetupError(unavailable, "storage")
                    ancestor = parent
                device = ancestor.stat().st_dev
            except OSError as exc:
                raise SetupError(unavailable, "storage") from exc
            saved = requirements.setdefault(device, [ancestor, 0])
            saved[1] += needed
        for path, needed in requirements.values():
            self._check_cancel()
            try:
                available = shutil.disk_usage(path).free
            except OSError as exc:
                raise SetupError(unavailable, "storage") from exc
            if available < needed:
                raise SetupError(f"Setup needs about {needed / GIB:.0f} GB of free space on the selected drive. Free some space, or choose another storage location, then retry.", "space")

    def _runtime_progress(self, event):
        stage = event.get("stage", "installing")
        position = {"download": .08, "extract": .15, "packages": .25, "verify": .36, "complete": .4}.get(stage, .2)
        self._emit("installing", event.get("message") or "Preparing image processing…", position)

    def _verify_graphics(self):
        self._emit("checking", "Checking image processing on your graphics card…", .97)
        from service.windows_job import WindowsJobProcess
        python = Path(service_configuration(self.choices)["runtime_python"])
        support = self.root / "runtime" / "windows_dlls.py"
        code = (f"import runpy; _dll_search_support=runpy.run_path({str(support)!r}); "
                "import torch; assert torch.cuda.is_available(), 'NVIDIA graphics processing is unavailable'; x=torch.ones((8,8),device='cuda'); assert float((x@x).sum().item())==512.; torch.cuda.synchronize(); print('GRAPHICS_OK')")
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith(("PYTHON", "CUDA_VISIBLE", "CU_"))}
        log = self.state / "installation-graphics.log"
        child = WindowsJobProcess([str(python), "-I", "-c", code], cwd=str(python.parent), env=env, log_path=log, memory_limit_bytes=8*GIB)
        try:
            deadline = time.monotonic() + 120
            while child.poll_root() is None:
                self._check_cancel()
                if time.monotonic() > deadline:
                    raise SetupError("The graphics-card check took too long. Close other graphics-heavy apps, then choose Retry.", "graphics")
                self.cancel.wait(.15)
            if child.poll_root() != 0 or "GRAPHICS_OK" not in log.read_text(errors="replace"):
                raise SetupError("The graphics-card check did not pass. Install a current NVIDIA Studio driver and restart Windows, then choose Retry. Your downloaded files are saved.", "graphics")
        finally:
            child.close(timeout=3)

    def run(self, accept_terms=False) -> dict:
        self.state.mkdir(parents=True, exist_ok=True)
        with _file_lock(self.state / "installation.lock"):
            try:
                return self._run(accept_terms)
            except Exception:
                self._check_cancel()
                raise

    def _run(self, accept_terms):
        self._fraction = 0.0
        self._emit("checking", "Checking your computer…", .01)
        if accept_terms:
            for key in self.required:
                self.store.accept(key, True)
            write_json(self.state / "installation-consent.json", {"fingerprint": self.fingerprint, "accepted_at": time.time()})
        if not self.terms_accepted():
            raise SetupError("Review and accept the application and model terms to continue.", "acceptance")
        check_hardware()
        self._check_space()
        # Save automatically chosen paths so a restart resumes the same transfer.
        write_json(self.state / "folders.json", self.choices)
        write_json(self.state / "installation-location.json", {"data_directory": str(self.data)})
        self._emit("installing", "Preparing image processing. This may take a few minutes…", .04)
        runtime = Path(self.choices["runtime_dir"])
        try:
            setup_runtime.install(runtime, progress=self._runtime_progress, cancel=self.cancel)
        except (FileExistsError, ValueError):
            # Upgrade from an old manually configured environment: preserve a
            # damaged external copy and prepare a managed replacement automatically.
            managed = self.data / "engine-v1"
            if runtime.resolve() == managed.resolve():
                raise
            self._check_cancel()
            self.choices["runtime_dir"] = str(managed)
            self._check_space()
            write_json(self.state / "folders.json", self.choices)
            setup_runtime.install(managed, progress=self._runtime_progress, cancel=self.cancel)
        directory = Path(self.choices["models_dir"])
        directory.mkdir(parents=True, exist_ok=True)
        total = sum(self.store.models[key]["size_bytes"] for key in self.required)
        completed = 0
        for index, key in enumerate(self.required):
            model = self.store.models[key]
            def progress(event):
                done = min(model["size_bytes"], event.get("completed", 0))
                action = "Downloading" if event.get("stage") == "downloading" else "Checking"
                amount = f"{done/GIB:.1f} of {model['size_bytes']/GIB:.1f} GB"
                self._emit("models", f"{action} enhancement files {index+1} of {len(self.required)} · {amount}", .4 + .54 * (completed + done) / total)
            # A damaged app-managed file is retained separately for safe recovery.
            # Never rename a user's manually selected model file.
            checked = self.store.verify(key, directory, cancel=self.cancel, progress=progress)
            if checked["status"] == "different" and directory.resolve() == (self.data / "models").resolve():
                target = directory / model["folder"] / model["filename"]
                if target.is_symlink() or not target.resolve().is_relative_to(directory.resolve()):
                    raise SetupError("A saved enhancement file points outside its installation. Choose a different storage location.", "path")
                target.rename(target.with_name(target.name + ".damaged-" + uuid.uuid4().hex[:8]))
            for attempt in range(3):
                try:
                    self.store.download(key, directory, cancel=self.cancel, progress=progress)
                    break
                except SetupError as exc:
                    if exc.code != "network" or attempt == 2:
                        raise
                    self._emit("models", "The connection was interrupted. Reconnecting…", .4 + .54 * completed / total)
                    if self.cancel.wait(2 * (attempt+1)):
                        self._check_cancel()
            completed += model["size_bytes"]
        self._emit("checking", "Checking your installation…", .95)
        try:
            output = Path(self.choices["output_dir"])
            output.mkdir(parents=True, exist_ok=True)
            probe = output / (".artegra-write-check-" + uuid.uuid4().hex)
            with probe.open("xb"):
                pass
            probe.unlink()
        except OSError:
            output = known_folder("pictures") / "Artegra Enhancer"
            output.mkdir(parents=True, exist_ok=True)
            self.choices["output_dir"] = str(output)
            write_json(self.state / "folders.json", self.choices)
            self._emit("checking", "Your previous save location is unavailable. Images will save to Pictures / Artegra Enhancer.", .95)
        service_configuration(self.choices)
        self._verify_graphics()
        self._check_cancel()
        write_json(self.state / "installation.json", {"schema": 1, "ready": True, "fingerprint": self.fingerprint,
                    "choices": self.choices, "models": self._inventory(), "verified_at": time.time()})
        self._emit("complete", "Artegra Enhancer is ready.", 1)
        return dict(self.choices)

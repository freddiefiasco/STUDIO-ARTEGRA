"""Engine entry points must work without a system Visual C++ installation."""
import builtins
import importlib.metadata
import os
from pathlib import Path
import runpy
import shutil
import sys
import weakref
from types import SimpleNamespace

import pytest

from host import installation
from runtime import setup_runtime
from service import windows_job


SOURCE = Path(__file__).resolve().parents[1]


@pytest.fixture
def packaged_engine(tmp_path, monkeypatch):
    app = tmp_path / "Artegra user's app \u6f14\u793a"
    (app / "runtime").mkdir(parents=True)
    (app / "service").mkdir()
    support = SOURCE / "runtime/windows_dlls.py"
    if support.exists():
        shutil.copyfile(support, app / "runtime/windows_dlls.py")
    shutil.copyfile(SOURCE / "service/comfy_main.py", app / "service/comfy_main.py")
    directory = app / "desktop-runtime/Lib/site-packages/shiboken6"
    directory.mkdir(parents=True)
    registrations, imported = [], []

    class DirectoryHandle:
        pass

    def add_directory(path):
        assert Path(path).is_absolute() and Path(path) == directory
        handle = DirectoryHandle()
        registrations.append(weakref.ref(handle))
        return handle

    class Tensor:
        def __matmul__(self, other):
            return self

        def sum(self):
            return self

        def item(self):
            return 512.0

    torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True,
                            is_initialized=lambda: False, synchronize=lambda: None),
                            ones=lambda *args, **kwargs: Tensor())
    original_import = builtins.__import__

    def missing_system_runtime(name, *args, **kwargs):
        if name in {"torch", "torchvision"}:
            assert registrations and registrations[-1]() is not None, "MSVCP140.dll unavailable before Torch import"
            imported.append(name)
            return torch if name == "torch" else SimpleNamespace()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("os.add_dll_directory", add_directory, raising=False)
    monkeypatch.setattr(builtins, "__import__", missing_system_runtime)
    return app, imported


def test_comfy_worker_registers_bundled_runtime_before_engine_import(packaged_engine, tmp_path, monkeypatch):
    app, imported = packaged_engine
    comfy = tmp_path / "ComfyUI"
    comfy.mkdir()
    (comfy / "main.py").write_text("import torch\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["comfy_main.py", str(comfy), str(comfy)])
    monkeypatch.setattr(sys, "path", sys.path.copy())
    for name in ("PYTORCH_CUDA_ALLOC_CONF", "PYTORCH_ALLOC_CONF"):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    runpy.run_path(str(app / "service/comfy_main.py"), run_name="__main__")
    assert imported == ["torch"]


def test_setup_validation_registers_bundled_runtime_before_engine_import(packaged_engine, tmp_path, monkeypatch):
    app, imported = packaged_engine
    (app / "runtime/constraints-win.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(setup_runtime, "ROOT", app / "runtime")
    monkeypatch.setattr(sys, "version_info", (3, 13, 14))
    monkeypatch.setattr(importlib.metadata, "version", lambda name: {"torch": "2.14.1+cu132", "torchvision": "0.29.1+cu132"}[name])

    def run(args, **kwargs):
        if "-c" in args:
            position = args.index("-c")
            monkeypatch.setattr(sys, "argv", ["-c", *map(str, args[position + 2:])])
            exec(args[position + 1], {})

    monkeypatch.setattr(setup_runtime, "_run_command", run)
    setup_runtime._validate(tmp_path / "engine", {}, tmp_path / "setup.log", None, None)
    assert imported == ["torch", "torchvision"]


def test_graphics_check_registers_bundled_runtime_before_engine_import(packaged_engine, tmp_path, monkeypatch):
    app, imported = packaged_engine
    probe = object.__new__(installation.Installation)
    probe.root, probe.state, probe.choices = app, tmp_path, {}
    probe._emit = lambda *args: None
    monkeypatch.setattr(installation, "service_configuration", lambda choices: {"runtime_python": str(tmp_path / "python.exe")})

    class Child:
        def __init__(self, args, **kwargs):
            exec(args[args.index("-c") + 1], {})
            kwargs["log_path"].write_text("GRAPHICS_OK", encoding="utf-8")

        def poll_root(self):
            return 0

        def close(self, **kwargs):
            pass

    monkeypatch.setattr(windows_job, "WindowsJobProcess", Child)
    probe._verify_graphics()
    assert imported == ["torch"]


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_source_checkout_does_not_require_packaged_dlls(tmp_path, monkeypatch, platform):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    shutil.copyfile(SOURCE / "runtime/windows_dlls.py", runtime / "windows_dlls.py")
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr("os.add_dll_directory", lambda path: pytest.fail("Source checkout tried registering a missing DLL directory"), raising=False)
    state = runpy.run_path(str(runtime / "windows_dlls.py"))
    assert state["_DLL_DIRECTORY_HANDLE"] is None

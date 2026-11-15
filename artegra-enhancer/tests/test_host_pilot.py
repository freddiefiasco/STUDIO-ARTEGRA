"""CPU-only validation for first-run settings and owned service startup."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from host.config import read_choices, service_configuration, validate_handshake, write_json


def installed_runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "python.exe").touch()
    (runtime / "main.py").touch()
    (runtime / "packages").mkdir()
    write_json(runtime / "runtime-receipt.json", {"schema": 1, "installed": True,
              "python": "python.exe", "comfy_main": "main.py", "site_packages": "packages"})
    return runtime


def test_empty_settings_offer_first_run(tmp_path):
    assert read_choices(tmp_path / "settings.json") == {"models_dir": "", "output_dir": "", "runtime_dir": ""}


def test_runtime_without_installation_record_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Repair installation"):
        service_configuration(dict(models_dir=str(tmp_path), runtime_dir=str(tmp_path), output_dir=str(tmp_path)))


def test_installed_runtime_resolves_relative_paths(tmp_path):
    runtime = installed_runtime(tmp_path)
    settings = service_configuration(dict(models_dir=str(tmp_path), runtime_dir=str(runtime), output_dir=str(tmp_path)))
    assert Path(settings["runtime_python"]) == runtime / "python.exe"
    assert Path(settings["site_packages"]) == runtime / "packages"
    assert settings["models_dir"] == str(tmp_path)


def test_missing_runtime_file_is_rejected(tmp_path):
    runtime = installed_runtime(tmp_path)
    (runtime / "main.py").unlink()
    with pytest.raises(ValueError, match="files are missing"):
        service_configuration(dict(models_dir=str(tmp_path), runtime_dir=str(runtime), output_dir=str(tmp_path)))


def test_demo_does_not_require_gpu_runtime_or_models(tmp_path):
    assert service_configuration({"output_dir": str(tmp_path)}, demo=True) == {"default_output_dir": str(tmp_path)}


@pytest.mark.parametrize("data", [None, {}, {"pid": 43, "port": 18950}, {"pid": 42, "port": 18765}, {"pid": 42, "port": "18950"}])
def test_foreign_or_malformed_handshake_is_refused(data):
    with pytest.raises(ValueError):
        validate_handshake(data, 42)


def test_valid_handshake():
    assert validate_handshake({"pid": 42, "port": 18969}, 42) == 18969


def test_service_listener_is_not_mistaken_for_ready_installation():
    from host.app import startup_health
    assert startup_health({"ok": False, "engine": {"ready": False}, "checking": True})[0] == "checking"
    status, message = startup_health({"ok": False, "engine": {"ready": False},
                                     "problems": ["Update your NVIDIA graphics driver."]})
    assert status == "blocked"
    assert message == "Update your NVIDIA graphics driver."


def test_old_job_warning_does_not_block_usable_workspace():
    from host.app import startup_health
    assert startup_health({"ok": False, "engine": {"ready": True},
                           "problems": ["An old job needs attention."]})[0] == "ready"


@pytest.mark.parametrize("health", [None, {}, {"ok": True}, {"engine": None}, {"engine": {"ready": "yes"}}])
def test_incomplete_health_never_marks_installation_ready(health):
    from host.app import startup_health
    assert startup_health(health)[0] == "checking"


def test_cpu_service_is_authenticated_and_owned(tmp_path):
    from host.app import OwnedService
    service = OwnedService(tmp_path, {"default_output_dir": str(tmp_path)}, True)
    try:
        deadline = time.monotonic() + 15
        port = None
        while time.monotonic() < deadline:
            record = tmp_path / "service.json"
            if record.exists():
                port = validate_handshake(json.loads(record.read_text()), service.pid)
                break
            assert not service.exited(), (tmp_path / "host-service.log").read_text()
            time.sleep(.05)
        assert port is not None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with pytest.raises(urllib.error.HTTPError) as failure:
            opener.open(f"http://127.0.0.1:{port}/health", timeout=3)
        assert failure.value.code == 401
        request = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Authorization": "Bearer " + service.token})
        with opener.open(request, timeout=3) as response:
            assert "engine" in json.load(response)
        if os.name == "nt":
            assert service.process.assert_listener_owned(port, root_only=True)
    finally:
        token_path = service.token_path
        service.close()
    assert not token_path.exists()
    assert service.exited()


def test_windowed_host_uses_its_sibling_console_interpreter(tmp_path, monkeypatch):
    from host import app
    runtime = tmp_path / "desktop-runtime"
    runtime.mkdir()
    console = runtime / "python.exe"
    console.touch()
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "_base_executable", str(runtime / "pythonw.exe"))
    assert Path(app.service_command()[0]) == console


def test_service_launcher_keeps_unicode_output_under_ascii_environment(tmp_path, monkeypatch):
    from host import app
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(app, "ROOT", tmp_path)
    (tmp_path / "cu_service.py").write_text(
        "import json, sys\nprint(json.dumps({'utf8': sys.flags.utf8_mode, "
        "'isolated': sys.flags.isolated, "
        "'no_bytecode': sys.dont_write_bytecode}))\nprint('\\u6f14\\u793a')\n",
        encoding="utf-8")
    env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="ascii")
    result = subprocess.run(app.service_command(), env=env, capture_output=True,
                            encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    # An embedded test interpreter can explicitly import site via its ._pth;
    # this check concerns the UTF-8/isolation flags of the actual subprocess.
    assert json.loads(lines[0]) == {"utf8": 1, "isolated": 1, "no_bytecode": True}
    assert lines[1] == "\u6f14\u793a"


def test_offscreen_host_smoke(tmp_path):
    pytest.importorskip("PySide6")
    root = Path(__file__).resolve().parents[1]
    entry = "import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('host.app',run_name='__main__')"
    result = subprocess.run([sys.executable, "-c", entry, str(root), "--smoke", "--state", str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=50)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"engine_connected": true' in result.stdout


def test_retry_after_crash_discards_old_probe_and_checks_replacement(tmp_path):
    """Drive the actual Qt bridge with deferred probes and no real service."""
    pytest.importorskip("PySide6")
    code = r'''
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, sys.argv[2])
from PySide6 import QtQml, QtWidgets
from host import app as host

engines, probes, services = [], [], []

class CapturedEngine(QtQml.QQmlApplicationEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        engines.append(self)

class DeferredThread:
    def __init__(self, *, target, daemon):
        self.target = target
    def start(self):
        probes.append(self.target)

class FakeService:
    def __init__(self, state, configuration, demo):
        self.pid = 700 + len(services)
        self.token = 'test-token'
        self.failed = self.closed = False
        self.process = SimpleNamespace(assert_listener_owned=lambda *args, **kwargs: True)
        (state / 'service.json').write_text(json.dumps({'pid': self.pid, 'port': 18950}))
        services.append(self)
    def exited(self):
        return self.failed or self.closed
    def close(self):
        self.closed = True

class TestApplication(QtWidgets.QApplication):
    def exec(self):
        bridge = engines[0].rootContext().contextProperty('hostBridge')
        bridge.start()
        bridge.poll()
        assert len(probes) == 1 and bridge.checking
        old_generation = bridge.generation
        services[0].failed = True
        bridge.poll()
        assert not bridge.busy and not bridge.ready and services[0].closed
        bridge.start()  # Retry while the crashed service's probe is still pending.
        assert bridge.busy and len(services) == 2
        bridge.finish_health({'engine': {'ready': True}}, 'http://127.0.0.1:18950', old_generation)
        assert not bridge.ready, 'A stale probe marked the replacement ready'
        bridge.poll()
        assert len(probes) == 2, 'Retry never checked the replacement service'
        assert bridge.checking
        bridge.finish_health({'engine': {'ready': True}}, 'http://127.0.0.1:18950', bridge.generation)
        assert bridge.ready and not bridge.busy and not bridge.checking
        return 0

with patch.object(QtQml, 'QQmlApplicationEngine', CapturedEngine), \
     patch.object(QtWidgets, 'QApplication', TestApplication), \
     patch.object(host, 'OwnedService', FakeService), \
     patch.object(host.threading, 'Thread', DeferredThread):
    assert host.main(['--demo', '--state', sys.argv[1]]) == 0
assert all(service.closed for service in services)
print('retry-recovery-passed')
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path), str(Path(__file__).resolve().parents[1])],
                            cwd=Path(__file__).resolve().parents[1], env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "retry-recovery-passed" in result.stdout

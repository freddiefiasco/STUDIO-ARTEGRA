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
    with pytest.raises(ValueError, match="not set up"):
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


def test_offscreen_host_smoke(tmp_path):
    pytest.importorskip("PySide6")
    result = subprocess.run([sys.executable, "-m", "host.app", "--smoke", "--state", str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=50)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"engine_connected": true' in result.stdout

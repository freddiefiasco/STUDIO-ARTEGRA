"""Exercise installation failure boundaries without downloading an engine."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from runtime import setup_runtime


def fake_assets(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    downloads = []

    def download(url, expected, destination):
        downloads.append(destination)
        destination.write_bytes(b"verified test archive")

    def extract(archive, destination, **kwargs):
        destination.mkdir(parents=True, exist_ok=True)
        (destination / ("main.py" if kwargs.get("strip_root") else "python.exe")).write_bytes(b"")

    monkeypatch.setattr(setup_runtime, "download", download)
    monkeypatch.setattr(setup_runtime, "safe_extract", extract)
    monkeypatch.setattr(setup_runtime, "apply_patch", lambda *args: None)
    monkeypatch.setattr(setup_runtime, "verify_source", lambda *args: None)
    return downloads


def test_all_large_install_work_stays_on_selected_volume(tmp_path, monkeypatch):
    downloads = fake_assets(monkeypatch)
    destination = tmp_path / "new-runtime"
    calls = []
    monkeypatch.setattr(setup_runtime.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setenv("PIP_TARGET", str(tmp_path / "unrelated-runtime"))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "unrelated-runtime"))
    setup_runtime.install(destination)
    assert downloads and all(path.is_relative_to(destination / ".tmp") for path in downloads)
    installer, options = calls[0]
    assert Path(installer[installer.index("--cache-dir") + 1]).is_relative_to(destination)
    for _, options in calls:
        assert all(Path(options["env"][key]).is_relative_to(destination) for key in ("TEMP", "TMP", "TMPDIR"))
        assert "PIP_TARGET" not in options["env"]
        assert "PYTHONPATH" not in options["env"]
    receipt = json.loads((destination / "runtime-receipt.json").read_text())
    assert receipt["installed"] is True
    assert not (destination / "SETUP-INCOMPLETE.txt").exists()


def test_failed_package_install_never_publishes_valid_receipt(tmp_path, monkeypatch):
    fake_assets(monkeypatch)
    destination = tmp_path / "failed-runtime"

    def fail(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(setup_runtime.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        setup_runtime.install(destination)
    assert (destination / "SETUP-INCOMPLETE.txt").is_file()
    assert not (destination / "runtime-receipt.json").exists()
    assert (destination / ".cache").is_dir()
    assert not list((destination / ".tmp").iterdir())


def test_reference_image_processing_dependencies_remain_pinned():
    constraints = setup_runtime.ROOT / "constraints-win.txt"
    versions = dict(line.split("==", 1) for line in constraints.read_text().splitlines() if line and not line.startswith("#"))
    assert versions["transformers"] == "5.19.0"
    assert versions["pillow"] == "12.3.0"
    assert versions["numpy"] == "2.5.4"


def test_interruption_returns_cancelled_status_and_clear_message(tmp_path, monkeypatch, capsys):
    def interrupt(destination):
        raise KeyboardInterrupt

    monkeypatch.setattr(setup_runtime, "install", interrupt)
    assert setup_runtime.main(["--install", "--directory", str(tmp_path / "runtime")]) == 130
    assert "No completed runtime was recorded" in capsys.readouterr().err

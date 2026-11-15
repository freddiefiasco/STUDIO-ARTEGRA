"""Platform admission boundaries: no CUDA, downloads, or system changes."""
from pathlib import Path
import subprocess
import sys

import pytest

from runtime.compatibility import evaluate_nvidia_driver, evaluate_platform
from runtime import setup_runtime


def platform_info(build=19045, architecture="amd64", **changes):
    return dict(system="win32", major=10, minor=0, build=build,
                architecture=architecture, **changes)


@pytest.mark.parametrize("build", [19045, 22621, 22631, 26100, 26200])
def test_supported_windows_client_builds(build):
    assert not evaluate_platform(platform_info(build))["errors"]


@pytest.mark.parametrize("build", [7601, 9600, 17763, 19044, 22000, 22620])
def test_rejects_older_windows_and_windows11_21h2(build):
    assert evaluate_platform(platform_info(build))["errors"]


@pytest.mark.parametrize("architecture", ["arm64", "aarch64", "x86", "unknown"])
def test_rejects_unsupported_native_architecture(architecture):
    assert evaluate_platform(platform_info(architecture=architecture))["errors"]


@pytest.mark.parametrize("version,blocked,warn", [
    ("576.52", True, False), ("580.88", False, True),
    ("591.44", False, True), ("595.71", False, False),
    ("620.00", False, False), ("N/A", False, True),
])
def test_driver_floor_and_minor_compatibility_are_distinct(version, blocked, warn):
    report = evaluate_nvidia_driver(version)
    assert bool(report["errors"]) is blocked
    assert bool(report["warnings"]) is warn


def test_unsupported_platform_stops_before_directory_creation_or_download(tmp_path, monkeypatch):
    destination = tmp_path / "runtime"
    def unsupported():
        raise ValueError("Windows version is unsupported")
    monkeypatch.setattr(setup_runtime, "require_supported_platform", unsupported)
    monkeypatch.setattr(setup_runtime, "download", lambda *args: pytest.fail("must not download"))
    with pytest.raises(ValueError, match="unsupported"):
        setup_runtime.install(destination)
    assert not destination.exists()


def test_direct_setup_help_under_isolated_python_needs_no_search_path(tmp_path):
    script = Path(setup_runtime.__file__).resolve()
    result = subprocess.run([sys.executable, "-I", str(script), "--help"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "--install" in result.stdout
    assert not list(tmp_path.iterdir())

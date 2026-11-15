"""Exercise installation failure boundaries without downloading an engine."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from runtime import setup_runtime


def test_cancelled_before_start_does_not_create_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_runtime, "require_supported_platform", lambda: {})
    cancel = threading.Event()
    cancel.set()
    destination = tmp_path / "cancelled-runtime"
    with pytest.raises(InterruptedError):
        setup_runtime.install(destination, cancel=cancel)
    assert not destination.exists()


def fake_assets(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(setup_runtime, "require_supported_platform", lambda: {})
    downloads = []

    def download(url, expected, destination, **kwargs):
        if not destination.exists():
            downloads.append(destination)
            destination.write_bytes(b"verified test archive")

    def extract(archive, destination, **kwargs):
        destination.mkdir(parents=True, exist_ok=True)
        (destination / ("main.py" if kwargs.get("strip_root") else "python.exe")).write_bytes(b"")

    monkeypatch.setattr(setup_runtime, "download", download)
    monkeypatch.setattr(setup_runtime, "safe_extract", extract)
    monkeypatch.setattr(setup_runtime, "apply_patch", lambda *args: None)
    monkeypatch.setattr(setup_runtime, "verify_source", lambda *args, **kwargs: None)
    return downloads


def test_all_large_install_work_stays_on_selected_volume(tmp_path, monkeypatch):
    downloads = fake_assets(monkeypatch)
    destination = tmp_path / "new-runtime"
    calls = []
    monkeypatch.setattr(setup_runtime, "_run_command", lambda args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setenv("PIP_TARGET", str(tmp_path / "unrelated-runtime"))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "unrelated-runtime"))
    setup_runtime.install(destination)
    assert downloads and all(path.is_relative_to(destination / ".cache") for path in downloads)
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

    monkeypatch.setattr(setup_runtime, "_run_command", fail)
    with pytest.raises(subprocess.CalledProcessError):
        setup_runtime.install(destination)
    assert (destination / "SETUP-INCOMPLETE.txt").is_file()
    assert not (destination / "runtime-receipt.json").exists()
    assert (destination / ".cache").is_dir()
    assert not list((destination / ".tmp").iterdir())


def test_retry_continues_owned_installation_and_reuses_downloads(tmp_path, monkeypatch):
    downloads = fake_assets(monkeypatch)
    destination = tmp_path / "resume runtime \u4e8c"
    events = []
    def fail(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(setup_runtime, "_run_command", fail)
    with pytest.raises(subprocess.CalledProcessError):
        setup_runtime.install(destination, progress=events.append)
    cached = {path: path.read_bytes() for path in downloads}
    assert len(cached) == 3
    assert not any(event["stage"] == "complete" for event in events)
    calls = []
    monkeypatch.setattr(setup_runtime, "_run_command", lambda args, **kw: calls.append(args))
    setup_runtime.install(destination, progress=events.append)
    assert len(downloads) == 3
    assert all(path.read_bytes() == data for path, data in cached.items())
    assert any("--force-reinstall" in args for args in calls)
    assert json.loads((destination / "runtime-receipt.json").read_text())["installed"] is True
    assert events[-1] == {"stage": "complete", "message": "Image processing is ready.", "completed": 1, "total": 1}


def test_complete_installation_checks_readiness_without_downloading_again(tmp_path, monkeypatch):
    downloads = fake_assets(monkeypatch)
    calls = []
    monkeypatch.setattr(setup_runtime, "_run_command", lambda args, **kw: calls.append(args))
    destination = tmp_path / "runtime"
    setup_runtime.install(destination)
    calls.clear()
    setup_runtime.install(destination)
    assert len(downloads) == 3
    assert len(calls) == 2
    assert not any("install" in args for args in calls)


def test_unmanaged_and_forged_installation_folders_are_not_modified(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_runtime, "require_supported_platform", lambda: {})
    destination = tmp_path / "someone-elses-runtime"
    destination.mkdir()
    (destination / setup_runtime.OWNER_FILE).write_text('{"owner":"different application"}')
    sentinel = destination / "keep.txt"
    sentinel.write_text("keep me")
    before = {path.name: path.read_bytes() for path in destination.iterdir()}
    with pytest.raises(FileExistsError):
        setup_runtime.install(destination)
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == before


def test_cancel_during_packages_retains_resume_state_without_success(tmp_path, monkeypatch):
    fake_assets(monkeypatch)
    cancel, events = threading.Event(), []
    destination = tmp_path / "runtime"
    def stop(args, **kwargs):
        cancel.set()
    monkeypatch.setattr(setup_runtime, "_run_command", stop)
    with pytest.raises(InterruptedError):
        setup_runtime.install(destination, cancel=cancel, progress=events.append)
    assert (destination / setup_runtime.INCOMPLETE_FILE).is_file()
    assert len(list((destination / ".cache" / "assets").iterdir())) == 3
    assert not (destination / "runtime-receipt.json").exists()
    assert not any(event["stage"] == "complete" for event in events)


def test_broken_managed_runtime_is_repaired_before_receipt_is_restored(tmp_path, monkeypatch):
    fake_assets(monkeypatch)
    monkeypatch.setattr(setup_runtime, "_run_command", lambda *args, **kwargs: None)
    destination = tmp_path / "runtime"
    setup_runtime.install(destination)
    calls = []
    def broken_once(args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, args)
        if "install" in args:
            assert not (destination / "runtime-receipt.json").exists()
    monkeypatch.setattr(setup_runtime, "_run_command", broken_once)
    setup_runtime.install(destination)
    assert any("--force-reinstall" in args for args in calls)
    assert (destination / "runtime-receipt.json").is_file()


class DownloadResponse(io.BytesIO):
    def __init__(self, body, url, offset=0):
        super().__init__(body[offset:])
        self.url = url
        self.status = 206 if offset else 200
        self.headers = {"Content-Length": str(len(body) - offset)}
        if offset:
            self.headers["Content-Range"] = f"bytes {offset}-{len(body) - 1}/{len(body)}"

    def read1(self, size):
        return self.read(min(size, 4))


def test_download_pause_resume_and_verified_cache_use_real_hash_check(tmp_path, monkeypatch):
    body = b"the pinned runtime download"
    url = "https://www.python.org/test.zip"
    requests = []
    class Opener:
        def open(self, request, **kwargs):
            requests.append(request)
            offset = int(request.get_header("Range", "bytes=0-").split("=")[1].strip("-"))
            return DownloadResponse(body, url, offset)
    monkeypatch.setattr(setup_runtime.urllib.request, "build_opener", lambda *args: Opener())
    destination, cancel = tmp_path / "asset.zip", threading.Event()
    digest = hashlib.sha256(body).hexdigest()
    with pytest.raises(InterruptedError):
        setup_runtime.download(url, digest, destination, cancel=cancel, progress=lambda event: cancel.set())
    assert not destination.exists()
    assert destination.with_name("asset.zip.part").read_bytes() == body[:4]
    cancel.clear()
    setup_runtime.download(url, digest, destination, cancel=cancel)
    setup_runtime.download(url, digest, destination, cancel=cancel)
    assert len(requests) == 2
    assert requests[1].get_header("Range") == "bytes=4-"
    assert destination.read_bytes() == body
    assert not destination.with_name("asset.zip.part").exists()


def test_bad_download_never_replaces_existing_file(tmp_path, monkeypatch):
    url, destination = "https://www.python.org/test.zip", tmp_path / "asset.zip"
    destination.write_bytes(b"existing invalid cache")
    class Opener:
        def open(self, *args, **kwargs):
            return DownloadResponse(b"wrong contents", url)
    monkeypatch.setattr(setup_runtime.urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(ValueError, match="checksum"):
        setup_runtime.download(url, "0" * 64, destination)
    assert destination.read_bytes() == b"existing invalid cache"
    assert not destination.with_name("asset.zip.part").exists()


def test_concurrent_installation_cannot_change_active_setup(tmp_path, monkeypatch):
    fake_assets(monkeypatch)
    entered, release, failures = threading.Event(), threading.Event(), []
    destination = tmp_path / "runtime"
    def command(args, **kwargs):
        if "install" in args:
            entered.set()
            assert release.wait(3)
    monkeypatch.setattr(setup_runtime, "_run_command", command)
    def install():
        try:
            setup_runtime.install(destination)
        except BaseException as exc:
            failures.append(exc)
    worker = threading.Thread(target=install)
    worker.start()
    try:
        assert entered.wait(3)
        with pytest.raises(OSError, match="already running"):
            setup_runtime.install(destination)
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    assert not failures


def test_interrupted_new_patch_file_can_be_applied_again_without_duplication(tmp_path, monkeypatch):
    patch = tmp_path / "patch.diff"
    patch.write_bytes(b"--- /dev/null\n+++ b/added.py\n@@ -0,0 +1,2 @@\n+first = 1\n+second = 2\n")
    monkeypatch.setattr(setup_runtime, "PATCH_SHA256", setup_runtime.sha256(patch))
    root = tmp_path / "source"
    root.mkdir()
    (root / "added.py").write_text("first = 1\n")
    setup_runtime.apply_patch(root, patch)
    setup_runtime.apply_patch(root, patch)
    assert (root / "added.py").read_bytes() == b"first = 1\nsecond = 2\n"


def test_verified_but_unpublished_partial_is_promoted_without_network(tmp_path, monkeypatch):
    destination = tmp_path / "asset.zip"
    body = b"completed before cancellation"
    destination.with_name("asset.zip.part").write_bytes(body)
    monkeypatch.setattr(setup_runtime.urllib.request, "build_opener", lambda *args: pytest.fail("No network needed"))
    setup_runtime.download("https://www.python.org/test.zip", hashlib.sha256(body).hexdigest(), destination)
    assert destination.read_bytes() == body


def test_runtime_redirect_cannot_contact_an_unapproved_host():
    request = setup_runtime.urllib.request.Request("https://www.python.org/test.zip")
    with pytest.raises(ValueError, match="Unexpected runtime download redirect"):
        setup_runtime._OfficialRedirect().redirect_request(request, None, 302, "Found", {}, "https://example.com/file.zip")


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

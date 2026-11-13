"""Model acquisition is tested against an isolated local HTTP publisher, never model weights."""
import hashlib
import errno
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time

import pytest

from host.model_setup import ModelSetup, SetupError


PAYLOAD = b"publisher-model-data\x00" * 150000


def test_shipped_catalogue_loads_standard_fast_and_offline_terms(tmp_path):
    root = Path(__file__).resolve().parents[1]
    store = ModelSetup(root / "models.manifest.json", tmp_path / "acceptance.json")
    assert len(store.models) == 7
    assert sum(bool(m.get("required_for_standard")) for m in store.models.values()) == 5
    assert sum(bool(m.get("required_for_fast")) for m in store.models.values()) == 1
    for identity, model in store.models.items():
        assert not store.accepted(identity)
        saved_terms = root / model["license_file"]
        assert hashlib.sha256(saved_terms.read_bytes()).hexdigest() == model["license_snapshot_sha256"]


@pytest.fixture
def publisher():
    class Handler(BaseHTTPRequestHandler):
        mode = "normal"
        requests = []
        first_byte = threading.Event()

        def log_message(self, *_):
            pass

        def do_GET(self):
            self.requests.append(self.headers.get("Range"))
            if self.mode in {"slow_body", "slow_headers"}:
                try:
                    if self.mode == "slow_headers":
                        self.connection.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    else:
                        self.send_response(200)
                        self.send_header("Content-Length", str(len(PAYLOAD)))
                        self.end_headers()
                        self.wfile.write(b"x")
                        self.wfile.flush()
                    self.first_byte.set()
                    # Keep data arriving much faster than the ten-second idle timeout.
                    for _ in range(150):
                        time.sleep(0.03)
                        self.connection.sendall(b"x")
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    pass
                return
            if self.mode == "drop":
                self.close_connection = True
                return
            start = int(self.headers.get("Range", "bytes=0-").split("=")[1].split("-")[0])
            if self.mode == "error":
                self.send_error(503)
                return
            use_range = start and self.mode != "ignore_range"
            self.send_response(206 if use_range else 200)
            if use_range:
                reported = start + 1 if self.mode == "wrong_range" else start
                self.send_header("Content-Range", f"bytes {reported}-{len(PAYLOAD)-1}/{len(PAYLOAD)}")
            else:
                start = 0
            self.send_header("Content-Length", str(len(PAYLOAD)-start))
            self.end_headers()
            body = PAYLOAD[start:]
            if self.mode == "truncate":
                body = body[:len(body)//2]
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.05), daemon=True)
    thread.start()
    yield Handler, f"http://127.0.0.1:{server.server_port}/weights"
    server.shutdown()
    server.server_close()
    thread.join()


def setup(tmp_path, url, **changes):
    model = dict(id="example", filename="weights.safetensors", folder="checkpoints", display_name="Example model",
                 size_bytes=len(PAYLOAD), sha256=hashlib.sha256(PAYLOAD).hexdigest(), download_url=url,
                 model_card_url="https://huggingface.co/example/model", license_url="https://example.com/license",
                 license="Example terms", download_enabled=True, required_for_standard=True,
                 acceptance_notice="Read the publisher terms.")
    model.update(changes)
    manifest = {"schema_version": 1, "models": [model]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return ModelSetup(path, tmp_path / "acceptance.json", allow_http_loopback=True)


def test_download_requires_individual_acceptance_and_verifies_before_install(tmp_path, publisher):
    handler, url = publisher
    store = setup(tmp_path, url)
    root = tmp_path / "models"
    with pytest.raises(SetupError, match="accept"):
        store.download("example", root)
    assert not handler.requests
    store.accept("example", True)
    events = []
    result = store.download("example", root, progress=events.append)
    assert result["status"] == "verified"
    assert (root / "checkpoints/weights.safetensors").read_bytes() == PAYLOAD
    assert not list(root.rglob("*.part"))
    assert events[-1]["stage"] == "verified"
    count = len(handler.requests)
    assert store.download("example", root)["status"] == "verified"
    assert len(handler.requests) == count


@pytest.mark.parametrize("mode", ["normal", "ignore_range"])
def test_cancel_preserves_partial_and_retry_resumes_or_safely_restarts(tmp_path, publisher, mode):
    handler, url = publisher
    store = setup(tmp_path, url)
    store.accept("example", True)
    root = tmp_path / "models"
    cancel = threading.Event()

    def progress(event):
        if event["stage"] == "downloading" and event["completed"] > 0:
            cancel.set()

    with pytest.raises(SetupError) as error:
        store.download("example", root, cancel=cancel, progress=progress)
    assert error.value.code == "cancelled"
    partial = next(root.rglob("*.part"))
    saved = partial.stat().st_size
    assert 0 < saved < len(PAYLOAD)
    assert not (root / "checkpoints/weights.safetensors").exists()
    handler.mode = mode
    store.download("example", root)
    assert handler.requests[-1] == f"bytes={saved}-"
    assert (root / "checkpoints/weights.safetensors").read_bytes() == PAYLOAD


def test_invalid_content_range_never_appends_to_saved_transfer(tmp_path, publisher):
    handler, url = publisher
    store = setup(tmp_path, url)
    store.accept("example", True)
    root = tmp_path / "models"
    cancel = threading.Event()
    with pytest.raises(SetupError):
        store.download("example", root, cancel=cancel,
                       progress=lambda e: cancel.set() if e["stage"] == "downloading" and e["completed"] else None)
    partial = next(root.rglob("*.part"))
    saved = partial.read_bytes()
    handler.mode = "wrong_range"
    with pytest.raises(SetupError) as error:
        store.download("example", root)
    assert error.value.code == "range"
    assert partial.read_bytes() == saved


def test_truncated_connection_can_resume_without_restarting(tmp_path, publisher):
    handler, url = publisher
    handler.mode = "truncate"
    store = setup(tmp_path, url)
    store.accept("example", True)
    root = tmp_path / "models"
    with pytest.raises(SetupError) as error:
        store.download("example", root)
    assert error.value.code == "network"
    assert next(root.rglob("*.part")).stat().st_size > 0
    handler.mode = "normal"
    store.download("example", root)
    assert (root / "checkpoints/weights.safetensors").read_bytes() == PAYLOAD


def test_wrong_hash_is_never_installed_and_can_be_retried(tmp_path, publisher):
    _, url = publisher
    store = setup(tmp_path, url, sha256="0" * 64)
    store.accept("example", True)
    root = tmp_path / "models"
    with pytest.raises(SetupError) as error:
        store.download("example", root)
    assert error.value.code == "integrity"
    assert not (root / "checkpoints/weights.safetensors").exists()
    assert not list(root.rglob("*.part"))


def test_existing_unrecognized_file_is_never_overwritten(tmp_path, publisher):
    handler, url = publisher
    store = setup(tmp_path, url)
    store.accept("example", True)
    path = tmp_path / "models/checkpoints/weights.safetensors"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"my valuable different model")
    with pytest.raises(SetupError) as error:
        store.download("example", tmp_path / "models")
    assert error.value.code == "existing"
    assert not handler.requests
    assert path.read_bytes() == b"my valuable different model"


def test_acceptance_is_individual_persistent_and_invalidated_by_changed_terms(tmp_path, publisher):
    _, url = publisher
    store = setup(tmp_path, url)
    store.accept("example", True)
    assert setup(tmp_path, url).accepted("example")
    changed = setup(tmp_path, url, acceptance_notice="New terms must be reviewed.")
    assert not changed.accepted("example")
    changed.accept("example", True)
    assert changed.accepted("example")
    changed.accept("example", False)
    assert not changed.accepted("example")


def test_recognized_existing_preview_variant_is_preserved(tmp_path, publisher):
    handler, url = publisher
    variant = b"known fp16 preview"
    store = setup(tmp_path, url, accepted_existing_variants=[dict(name="FP16", size_bytes=len(variant),
                        sha256=hashlib.sha256(variant).hexdigest())])
    path = tmp_path / "models/checkpoints/weights.safetensors"
    path.parent.mkdir(parents=True)
    path.write_bytes(variant)
    store.accept("example", True)
    assert store.download("example", tmp_path / "models")["variant"] == "FP16"
    assert not handler.requests
    assert path.read_bytes() == variant


@pytest.mark.parametrize("changes", [{"folder": "../escape"}, {"filename": "../../escape"},
                                      {"download_url": "https://example.org/untrusted"},
                                      {"download_url": "https://" + "user:password@" + "huggingface.co/model"}])
def test_invalid_manifest_paths_and_nonpublisher_sources_are_rejected(tmp_path, publisher, changes):
    _, url = publisher
    with pytest.raises(SetupError) as error:
        setup(tmp_path, url, **changes)
    assert error.value.code == "manifest"


def test_network_error_does_not_expose_response_or_url_credentials(tmp_path, publisher):
    handler, url = publisher
    handler.mode = "error"
    store = setup(tmp_path, url)
    store.accept("example", True)
    with pytest.raises(SetupError) as error:
        store.download("example", tmp_path / "models")
    assert error.value.code == "network"
    assert "127.0.0.1" not in str(error.value)
    assert "503" not in str(error.value)


def test_low_disk_space_is_recoverable_without_network(tmp_path, publisher, monkeypatch):
    from collections import namedtuple
    import shutil
    handler, url = publisher
    store = setup(tmp_path, url)
    store.accept("example", True)
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda _: usage(100, 100, 0))
    with pytest.raises(SetupError) as error:
        store.download("example", tmp_path / "models")
    assert error.value.code == "space"
    assert not handler.requests


def test_server_dropping_before_headers_is_a_recoverable_error(tmp_path, publisher):
    handler, url = publisher
    handler.mode = "drop"
    store = setup(tmp_path, url)
    store.accept("example", True)
    with pytest.raises(SetupError) as error:
        store.download("example", tmp_path / "models")
    assert error.value.code == "network"
    handler.mode = "normal"
    assert store.download("example", tmp_path / "models")["status"] == "verified"


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows no-replace rename fallback")
def test_filesystem_without_hardlinks_installs_atomically_on_windows(tmp_path, publisher, monkeypatch):
    import os
    _, url = publisher
    store = setup(tmp_path, url)
    store.accept("example", True)
    def unsupported(*_):
        raise OSError(errno.EOPNOTSUPP, "Hard links are not supported")
    monkeypatch.setattr(os, "link", unsupported)
    assert store.download("example", tmp_path / "models")["status"] == "verified"
    assert (tmp_path / "models/checkpoints/weights.safetensors").read_bytes() == PAYLOAD


@pytest.mark.parametrize("mode", ["slow_body", "slow_headers"])
def test_pause_interrupts_a_continuously_dribbling_peer(tmp_path, publisher, mode):
    handler, url = publisher
    handler.mode = mode
    store = setup(tmp_path, url)
    store.accept("example", True)
    cancel = threading.Event()
    errors = []
    def download():
        try:
            store.download("example", tmp_path / "models", cancel=cancel)
        except BaseException as exc:
            errors.append(exc)
    worker = threading.Thread(target=download, daemon=True)
    worker.start()
    assert handler.first_byte.wait(2)
    cancel.set()
    worker.join(2)
    try:
        assert not worker.is_alive(), "Pause must interrupt I/O, not wait for a dribbling peer to fill the read buffer"
        assert len(errors) == 1 and isinstance(errors[0], SetupError)
        assert errors[0].code == "cancelled"
        assert not (tmp_path / "models/checkpoints/weights.safetensors").exists()
    finally:
        worker.join(6)

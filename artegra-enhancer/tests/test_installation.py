"""Complete setup contract without downloading large payloads or touching a GPU."""
import hashlib
import json
from pathlib import Path
import threading

import pytest

from host import installation
from host.config import write_json
from host.model_setup import SetupError
from host.setup_cli import protocol_text


def space_probe(tmp_path):
    app = object.__new__(installation.Installation)
    app.choices = {"runtime_dir": str(tmp_path / "runtime"), "models_dir": str(tmp_path / "models")}
    app.required = []
    app.cancel = threading.Event()
    return app


def test_disconnected_storage_root_fails_promptly_instead_of_looping(tmp_path, monkeypatch):
    app = space_probe(tmp_path)
    calls = []
    def disconnected(path):
        calls.append(path)
        assert len(calls) <= 40, "Missing drive root caused unbounded traversal"
        return False
    with monkeypatch.context() as patch:
        patch.setattr(type(tmp_path), "exists", disconnected)
        with pytest.raises(SetupError, match="drive is unavailable") as error:
            app._check_space()
    assert error.value.code == "storage"


def test_storage_probe_can_be_cancelled_before_disk_access(tmp_path, monkeypatch):
    app = space_probe(tmp_path)
    app.cancel.set()
    monkeypatch.setattr(installation.shutil, "disk_usage", lambda path: pytest.fail("Accessed disk after cancellation"))
    with pytest.raises(SetupError) as error:
        app._check_space()
    assert error.value.code == "cancelled"


def test_drive_disconnecting_during_free_space_check_has_actionable_error(tmp_path, monkeypatch):
    app = space_probe(tmp_path)
    def lost_drive(path):
        raise OSError("Device disconnected")
    monkeypatch.setattr(installation.shutil, "disk_usage", lost_drive)
    with pytest.raises(SetupError, match="Reconnect") as error:
        app._check_space()
    assert error.value.code == "storage"


def test_installer_progress_is_safe_on_japanese_windows_code_page():
    text = protocol_text("Checking enhancement files 1 of 6 · 2.0 GB…\nNext|stage")
    assert text.encode("cp932").decode("cp932") == text
    assert "|" not in text and "\n" not in text


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root, state = tmp_path / "app", tmp_path / "User data" / "production"
    root.mkdir()
    (root / "LICENSE.txt").write_text("Application terms")
    data = b"tiny verified model"
    model = dict(id="test-model", display_name="Test model", folder="checkpoints", filename="test.bin",
                 sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data), required_for_standard=True,
                 license="MIT", download_enabled=True, license_url="https://huggingface.co/test/license",
                 model_card_url="https://huggingface.co/test", download_url="https://huggingface.co/test/model")
    (root / "models.manifest.json").write_text(json.dumps(dict(schema_version=1, models=[model])))
    monkeypatch.setattr(installation, "known_folder", lambda kind: tmp_path / kind)
    monkeypatch.setattr(installation, "check_hardware", lambda: None)
    monkeypatch.setattr(installation.Installation, "_verify_graphics", lambda self: None)
    def runtime(path, **kwargs):
        path.mkdir(parents=True, exist_ok=True)
        (path / "python").mkdir(exist_ok=True)
        (path / "python/python.exe").touch()
        (path / "python/site").mkdir(exist_ok=True)
        (path / "main.py").touch()
        write_json(path / "runtime-receipt.json", dict(schema=1, installed=True, python="python/python.exe", site_packages="python/site", comfy_main="main.py"))
    monkeypatch.setattr(installation.setup_runtime, "install", runtime)
    calls = []
    def download(store, key, directory, **kwargs):
        assert store.accepted(key)
        calls.append(key)
        target = Path(directory) / "checkpoints/test.bin"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"status": "verified"}
    monkeypatch.setattr(installation.ModelSetup, "download", download)
    monkeypatch.setattr(installation.Installation, "_check_space", lambda self: None)
    return root, state, data, calls


def test_fresh_setup_is_usable_without_folder_selection_and_detects_missing_files(setup):
    root, state, _, calls = setup
    events = []
    app = installation.Installation(root, state, progress=events.append)
    assert not app.is_complete()
    app.run(accept_terms=True)
    assert app.is_complete()
    assert events[-1]["fraction"] == 1
    assert calls == ["test-model"]
    reopened = installation.Installation(root, state)
    assert reopened.is_complete() and reopened.terms_accepted()
    (Path(reopened.choices["runtime_dir"]) / "python/python.exe").unlink()
    assert not reopened.is_complete()
    reopened.run()
    assert reopened.is_complete()


def test_terms_required_before_download_and_changed_terms_require_new_consent(setup):
    root, state, _, calls = setup
    app = installation.Installation(root, state)
    with pytest.raises(SetupError, match="Review and accept"):
        app.run()
    assert not calls
    app.run(accept_terms=True)
    (root / "LICENSE.txt").write_text("Changed terms")
    changed = installation.Installation(root, state)
    assert not changed.terms_accepted() and not changed.is_complete()


def test_interruption_saves_paths_and_consent_but_not_success(setup, monkeypatch):
    root, state, _, _ = setup
    def interrupted(*args, **kwargs):
        raise SetupError("connection interrupted", "network")
    original = installation.setup_runtime.install
    monkeypatch.setattr(installation.setup_runtime, "install", interrupted)
    with pytest.raises(SetupError):
        installation.Installation(root, state).run(accept_terms=True)
    resumed = installation.Installation(root, state)
    assert resumed.terms_accepted()
    assert not resumed.is_complete()
    assert (state / "folders.json").is_file()
    monkeypatch.setattr(installation.setup_runtime, "install", original)
    resumed.run()
    assert resumed.is_complete()


def test_upgrade_preserves_existing_paths_and_output(setup):
    root, state, _, _ = setup
    custom = state.parent / "Existing files"
    choices = {"runtime_dir": str(custom / "engine"), "models_dir": str(custom / "models"), "output_dir": str(custom / "Pictures")}
    Path(choices["output_dir"]).mkdir(parents=True)
    image = Path(choices["output_dir"]) / "keep.jpg"
    image.write_bytes(b"original output")
    write_json(state / "folders.json", choices)
    app = installation.Installation(root, state)
    app.run(accept_terms=True)
    assert app.choices == choices and image.read_bytes() == b"original output"


def test_cancel_never_records_success(setup):
    root, state, _, calls = setup
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(SetupError) as error:
        installation.Installation(root, state, cancel=cancel).run(accept_terms=True)
    assert error.value.code == "cancelled"
    assert not calls and not (state / "installation.json").exists()


def test_changing_output_folder_does_not_require_installation_again(setup):
    root, state, _, _ = setup
    app = installation.Installation(root, state)
    app.run(accept_terms=True)
    output = state / "different output"
    output.mkdir()
    app.choices["output_dir"] = str(output)
    write_json(state / "folders.json", app.choices)
    assert installation.Installation(root, state).is_complete()


def test_unavailable_output_recovers_to_pictures_without_manual_setup(setup):
    root, state, _, _ = setup
    app = installation.Installation(root, state)
    blocked = state.parent / "not a folder"
    blocked.mkdir(parents=True)
    file = blocked / "file"
    file.write_text("preserve")
    app.choices["output_dir"] = str(file / "outputs")
    app.run(accept_terms=True)
    assert app.is_complete()
    assert Path(app.choices["output_dir"]) == installation.known_folder("pictures") / "Artegra Enhancer"
    assert file.read_text() == "preserve"


def test_damaged_managed_model_is_preserved_and_repaired(setup):
    root, state, data, _ = setup
    app = installation.Installation(root, state)
    app.run(accept_terms=True)
    target = Path(app.choices["models_dir"]) / "checkpoints/test.bin"
    target.write_bytes(b"damaged")
    assert not app.is_complete()
    app.run()
    assert app.is_complete() and target.read_bytes() == data
    assert next(target.parent.glob("*.damaged-*")).read_bytes() == b"damaged"


def test_failed_graphics_check_does_not_report_ready(setup, monkeypatch):
    root, state, _, _ = setup
    def fail(self):
        raise SetupError("Graphics driver needs attention", "graphics")
    monkeypatch.setattr(installation.Installation, "_verify_graphics", fail)
    app = installation.Installation(root, state)
    with pytest.raises(SetupError, match="driver"):
        app.run(accept_terms=True)
    assert not app.is_complete()


def test_selecting_another_drive_after_setup_changes_managed_paths_and_keeps_original(setup):
    root, state, data, _ = setup
    app = installation.Installation(root, state)
    app.run(accept_terms=True)
    original = Path(app.choices["models_dir"]) / "checkpoints/test.bin"
    selected = state.parent / "Another drive"
    moved = installation.Installation(root, state, data_directory=selected)
    assert Path(moved.choices["runtime_dir"]).is_relative_to(selected)
    moved.run()
    assert moved.is_complete() and original.read_bytes() == data
    reopened = installation.Installation(root, state)
    assert reopened.is_complete() and reopened.data == selected

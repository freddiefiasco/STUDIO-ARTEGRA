"""Complete setup contract without downloading large payloads or touching a GPU."""
import hashlib
import json
from pathlib import Path
import threading
from unittest import mock

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


# --- 5.0.2: Setup's memory floor (engine design 8.2) ---------------------------------------------------------------------

MEMORY_64_TEXT = ("Artegra Enhancer (Beta) needs 64 GB of system memory for normal enhancement. Setup stopped before the large "
                  "downloads. A larger pagefile does not replace this.")


def test_the_memory_floor_is_32_gb():
    """5.0.2: R6 passed, so the 48 GB switch is on, and the planner admits useful upscales at a 32 GB PC's cap, so the 32 GB
    switch is on too: Setup accepts 31 GiB or more (a 32 GB PC reports about 31.7 GiB)."""
    assert installation.FLOOR_48_ON is True and installation.FLOOR_32_ON is True
    assert installation.memory_floor_gib() == 31
    assert installation.memory_refusal(int(31.7 * installation.GIB)) is None             # a 32 GB PC
    assert installation.memory_refusal(31 * installation.GIB) is None                    # with 0.7 GiB reserved
    assert installation.memory_refusal(int(46.5 * installation.GIB)) is None             # a 48 GB PC
    assert installation.memory_refusal(int(61.56 * installation.GIB)) is None
    text = installation.memory_refusal(int(15.7 * installation.GIB))                     # a 16 GB PC
    assert text == installation.MEMORY_32
    assert installation.memory_refusal(int(30.9 * installation.GIB)) == installation.MEMORY_32
    assert "32 GB" in text and "Setup stopped before the large downloads." in text and "pagefile" in text
    assert "larger upscales need more memory" in text


def test_the_earlier_floors_when_the_32_gb_switch_is_off():
    assert installation.MEMORY_64 == MEMORY_64_TEXT          # 5.0.1's words, byte for byte (STRINGS, TROUBLESHOOTING)
    assert installation.memory_floor_gib(on=False, on32=False) == 60
    assert installation.memory_refusal(int(59.9 * installation.GIB), on=False, on32=False) == MEMORY_64_TEXT
    assert installation.memory_refusal(60 * installation.GIB, on=False, on32=False) is None
    assert installation.memory_floor_gib(on=True, on32=False) == 44
    assert installation.memory_refusal(int(46.5 * installation.GIB), on=True, on32=False) is None      # a 48 GB PC
    assert installation.memory_refusal(44 * installation.GIB, on=True, on32=False) is None
    text = installation.memory_refusal(int(31.8 * installation.GIB), on=True, on32=False)               # a 32 GB PC
    assert text == installation.MEMORY_48
    assert "48 GB" in text and "Setup stopped before the large downloads." in text and "pagefile" in text
    with mock.patch.object(installation, "FLOOR_32_ON", False):
        assert installation.memory_floor_gib() == 44
        assert installation.memory_refusal(int(46.5 * installation.GIB)) is None


def test_the_32_gb_text_names_only_sizes_a_32_gb_pc_makes():
    """The sizes the 32 GB text names fit the memory a 32 GB PC may use, at the floor's own cap (31 GiB reported: 28.5 GB)
    and at the usual one (31.7: 29.2), by the planner and the service's own memory check; the next scale of each does not,
    and the Large-image engine takes nothing below the 48 GB class, whatever table the processor has."""
    from engine import banded_plan, planner
    from service.media import ram_refusal
    from service.settings import default_ram_cap_gb
    caps = (default_ram_cap_gb(31.0), default_ram_cap_gb(31.7))
    assert caps == (28.5, 29.2)

    def fits(w, h, f, cap):
        p = planner.plan(w, h, f, ram_cap_gb=cap)
        return p.ok and ram_refusal(p, cap) is None
    named = [(1920, 1080, 2), (960, 540, 4)]
    for cap in caps:
        assert banded_plan.machine_class(cap) is None
        for w, h, f in named:
            assert fits(w, h, f, cap), (w, h, f, cap)
            assert f"{f}× of a {w} × {h} image" in installation.MEMORY_32
            assert not fits(w, h, {2: 4, 4: 6}[f], cap), (w, h, f, cap)
            assert planner.plan(w, h, f, ram_cap_gb=cap).ram_limited      # lightened to fit at that cap
    assert "lighter setting" in installation.MEMORY_32
    for table in (None, banded_plan.PROBE_TABLE):
        with mock.patch.object(banded_plan, "BXF_TABLE", table):
            assert not banded_plan.plan_banded(3500, 2188, 2, 29.2).ok


def test_the_48_gb_text_names_only_sizes_a_48_gb_pc_makes():
    """The sizes the 48 GB text names fit the memory a 48 GB PC may use (settings.default_ram_cap_gb: 45.2 GB of the 47.7
    Windows would report), by the planner and the service's own memory check; the next scale of each does not."""
    from engine import planner
    from service.media import ram_refusal
    from service.settings import default_ram_cap_gb
    cap = default_ram_cap_gb(47.7)
    assert cap == 45.2

    def fits(w, h, f):
        p = planner.plan(w, h, f, ram_cap_gb=cap)
        return p.ok and ram_refusal(p, cap) is None
    named = [(3500, 2188, 2), (2800, 3500, 2), (1280, 1600, 4)]
    for w, h, f in named:
        assert fits(w, h, f), (w, h, f)
        assert f"{f}\u00d7" in installation.MEMORY_48 and f"{w} \u00d7 {h}" in installation.MEMORY_48
        assert not fits(w, h, {2: 4, 4: 6}[f]), (w, h, f)      # with no processor table (Classic only)
    assert "lighter setting" in installation.MEMORY_48       # each of them is lightened to fit at that cap
    assert all(planner.plan(w, h, f, ram_cap_gb=cap).ram_limited for w, h, f in named)


def test_check_hardware_uses_the_floor(monkeypatch):
    calls = []
    monkeypatch.setattr(installation, "memory_refusal", lambda total, on=None: calls.append(total) or "stop")
    monkeypatch.setattr(installation, "require_supported_platform", lambda: None)
    monkeypatch.setattr(installation.shutil, "which", lambda name: "nvidia-smi")

    class Done:
        stdout = "NVIDIA GeForce RTX 5090, 591.44, 32607\n"
    monkeypatch.setattr(installation.subprocess, "run", lambda *a, **k: Done())
    monkeypatch.setattr(installation, "evaluate_nvidia_driver", lambda v: {"errors": []})
    if installation.os.name != "nt":
        pytest.skip("the memory check reads Windows' GlobalMemoryStatusEx")
    with pytest.raises(SetupError) as error:
        installation.check_hardware()
    assert (str(error.value), error.value.code, len(calls)) == ("stop", "hardware", 1)

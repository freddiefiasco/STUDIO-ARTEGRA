"""The uninstaller's clean-up options: exact app-managed paths only; images, chosen folders and links are never touched."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from host import uninstall_cleanup as cleanup

ROOT = Path(__file__).resolve().parents[1]
MODELS = json.loads((ROOT / "models.manifest.json").read_text(encoding="utf-8-sig"))["models"]


def make_install(tmp_path, data=None, models_dir=None, runtime_dir=None):
    """A per-user layout like setup leaves it, with names that need care (spaces, accents)."""
    root = tmp_path / "Lokal Daten é" / "Studio Artegra" / "Artegra Enhancer"
    state = root / "production"
    state.mkdir(parents=True)
    data = data or root / "data"
    models = data / "models"
    for model in MODELS:
        folder = models / model["folder"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / model["filename"]).write_bytes(b"weights")
    first = MODELS[0]
    (models / first["folder"] / (first["filename"] + ".0123456789abcdef.part")).write_bytes(b"partial")
    (models / first["folder"] / (first["filename"] + ".damaged-1a2b3c4d")).write_bytes(b"set aside")
    (models / first["folder"] / "my-own-model.safetensors").write_bytes(b"not ours")
    engine = data / "engine-v1"
    (engine / "python").mkdir(parents=True)
    (engine / "python" / "python.exe").write_bytes(b"x")
    (engine / "runtime-receipt.json").write_text("{}")
    (engine / ".artegra-runtime.json").write_text("{}")
    pictures = tmp_path / "Pictures" / "Artegra Enhancer"
    pictures.mkdir(parents=True)
    (pictures / "result_cu2x.png").write_bytes(b"an image")
    choices = {"models_dir": str(models_dir or models), "runtime_dir": str(runtime_dir or engine), "output_dir": str(pictures)}
    (state / "folders.json").write_text(json.dumps(choices))
    (state / "installation-location.json").write_text(json.dumps({"data_directory": str(data)}))
    for name in ("host.log", "preferences.ini", "installation.json"):
        (state / name).write_text("x")
    (root / "demo" / "outputs").mkdir(parents=True)
    (root / "demo" / "outputs" / "demo_cu2x.png").write_bytes(b"demo image")
    return root, data, pictures


def run(root, *flags):
    return cleanup.main(["--state", str(root), "--app-root", str(ROOT), "--log", str(root.parent / "cleanup.log"), *flags])


def test_nothing_is_removed_without_an_option(tmp_path):
    root, data, pictures = make_install(tmp_path)
    before = sorted(p for p in tmp_path.rglob("*"))
    assert run(root) == 0
    after = sorted(p for p in tmp_path.rglob("*") if p.name != "cleanup.log")
    assert before == after


def test_the_files_option_removes_only_the_manifests_files_and_the_managed_engine(tmp_path):
    root, data, pictures = make_install(tmp_path)
    assert run(root, "--remove-files") == 0
    for model in MODELS:
        assert not (data / "models" / model["folder"] / model["filename"]).exists()
    first = MODELS[0]
    assert not list((data / "models" / first["folder"]).glob("*.part"))
    assert not list((data / "models" / first["folder"]).glob("*.damaged-*"))
    assert (data / "models" / first["folder"] / "my-own-model.safetensors").is_file()
    assert not (data / "engine-v1").exists()
    assert (pictures / "result_cu2x.png").is_file()
    assert (root / "production" / "folders.json").is_file()      # settings are a separate choice


def test_the_settings_option_removes_the_state_but_never_images(tmp_path):
    root, data, pictures = make_install(tmp_path)
    assert run(root, "--remove-settings") == 0
    assert not (root / "production").exists()
    assert (pictures / "result_cu2x.png").is_file()
    assert (data / "models").is_dir()


def test_images_saved_inside_a_state_folder_survive_the_settings_option(tmp_path):
    root, data, pictures = make_install(tmp_path)
    assert run(root, "--remove-settings") == 0
    assert (root / "demo" / "outputs" / "demo_cu2x.png").is_file()
    assert not (root / "demo" / "host.log").exists()


def test_both_options_leave_images_and_foreign_files(tmp_path):
    root, data, pictures = make_install(tmp_path)
    assert run(root, "--remove-files", "--remove-settings") == 0
    assert (pictures / "result_cu2x.png").is_file()
    assert (data / "models" / MODELS[0]["folder"] / "my-own-model.safetensors").is_file()


def test_a_models_folder_the_person_chose_is_never_touched(tmp_path):
    own = tmp_path / "My models"
    for model in MODELS:
        (own / model["folder"]).mkdir(parents=True, exist_ok=True)
        (own / model["folder"] / model["filename"]).write_bytes(b"theirs")
    root, data, pictures = make_install(tmp_path, models_dir=own)
    assert run(root, "--remove-files") == 0
    for model in MODELS:
        assert (own / model["folder"] / model["filename"]).is_file()


def test_an_engine_folder_without_setups_records_is_kept(tmp_path):
    root, data, pictures = make_install(tmp_path)
    (data / "engine-v1" / ".artegra-runtime.json").unlink()
    assert run(root, "--remove-files") == 0
    assert (data / "engine-v1" / "python" / "python.exe").is_file()


def test_an_output_folder_inside_the_data_folder_survives(tmp_path):
    root, data, pictures = make_install(tmp_path)
    inside = data / "my outputs"
    inside.mkdir()
    (inside / "kept_cu4x.png").write_bytes(b"image")
    assert run(root, "--remove-files", "--remove-settings") == 0
    assert (inside / "kept_cu4x.png").is_file()


def test_missing_records_remove_nothing_outside_the_default_layout(tmp_path):
    root = tmp_path / "Studio Artegra" / "Artegra Enhancer"
    root.mkdir(parents=True)
    stray = tmp_path / "other.txt"
    stray.write_text("x")
    assert run(root, "--remove-files", "--remove-settings") == 0
    assert stray.is_file()


@pytest.mark.skipif(os.name != "nt", reason="junctions are a Windows feature")
def test_a_junction_inside_the_engine_is_removed_but_never_followed(tmp_path):
    root, data, pictures = make_install(tmp_path)
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "keep.txt").write_text("keep")
    link = data / "engine-v1" / "linked"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(precious)], check=True, capture_output=True)
    assert run(root, "--remove-files") == 0
    assert (precious / "keep.txt").read_text() == "keep"
    assert not link.exists()


@pytest.mark.skipif(os.name != "nt", reason="junctions are a Windows feature")
def test_a_models_folder_that_is_a_junction_is_skipped(tmp_path):
    root, data, pictures = make_install(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    (data / "models").rename(elsewhere)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(data / "models"), str(elsewhere)], check=True, capture_output=True)
    assert run(root, "--remove-files") == 0
    assert (elsewhere / MODELS[0]["folder"] / MODELS[0]["filename"]).is_file()


def test_measure_reports_the_size_the_files_option_frees(tmp_path, capsys):
    root, data, pictures = make_install(tmp_path)
    out = tmp_path / "size.txt"
    assert run(root, "--measure", "--out", str(out)) == 0
    expected = len(MODELS) * len(b"weights") + len(b"partial") + len(b"set aside") + 1 + 2 + 2
    assert int(out.read_text()) == expected
    assert (data / "engine-v1").is_dir()


def test_every_action_is_logged(tmp_path):
    root, data, pictures = make_install(tmp_path)
    assert run(root, "--remove-files") == 0
    log = (root.parent / "cleanup.log").read_text(encoding="utf-8")
    assert "removed" in log and "cleanup finished" in log


def test_the_installer_runs_the_clean_up_only_as_chosen():
    text = (ROOT / "installer" / "ArtegraEnhancer.iss").read_text(encoding="utf-8")
    assert "FilesBox.Checked := False;" in text and "SettingsBox.Checked := False;" in text
    assert "Also remove downloaded enhancement files (" in text and "'Also remove settings and logs'" in text
    assert "RemoveFiles := HasParam('/REMOVEFILES=1');" in text and "RemoveSettings := HasParam('/REMOVESETTINGS=1');" in text
    usuninstall = text.index("CurUninstallStep = usUninstall")
    assert text.index("--uninstall-cleanup --state", usuninstall) > usuninstall
    mutex = text.index("CurUninstallStep = usAppMutexCheck")
    assert mutex < text.index("--quit-running --state", mutex) < usuninstall
    initialize = text[text.index("function InitializeUninstall()"):text.index("procedure CurUninstallStepChanged")]
    assert "Exec(" not in initialize and "MsgBox(" not in initialize       # nothing happens before the person confirms

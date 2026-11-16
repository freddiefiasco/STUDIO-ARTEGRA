"""The uninstaller's clean-up options: exact app-managed paths only; images, chosen folders and links are never touched."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from host import uninstall_cleanup as cleanup

ROOT = Path(__file__).resolve().parents[1]
MODELS = json.loads((ROOT / "models.manifest.json").read_text(encoding="utf-8-sig"))["models"]
SOURCE = json.loads((ROOT / "runtime" / "source-manifest.json").read_text(encoding="utf-8"))["files"]
# The pinned engine source's empty files (git's empty blob), so the tests can lay them down byte for byte.
EMPTY_SOURCE = sorted(k for k, v in SOURCE.items() if v["blob"] == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
PLACEHOLDER = "output/_output_images_will_be_put_here"


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    """Never touch this machine's own HKCU settings key: record the deletions the settings option asks for instead."""
    calls = []
    monkeypatch.setattr(cleanup, "_delete_key", lambda path, log, only_if_empty=False: calls.append((path, only_if_empty)))
    return calls


def fill_state(state):
    """Every entry the host and the service create in a state folder, with the app's own images inside its folders."""
    for name in ("jobs", "logs", "run", "notify"):
        (state / name).mkdir(parents=True, exist_ok=True)
    (state / "jobs" / "j0123456789ab.jsonl").write_text("{}\n")
    (state / "logs" / "app-20261117.jsonl").write_text("{}\n")
    (state / "run" / "host.json").write_text("{}")
    (state / "notify" / "toast-1-2-3.txt").write_text("x")
    (state / "media" / "m0123456789ab").mkdir(parents=True)
    for name in ("source.png", "thumb.jpg", "proxy.jpg"):
        (state / "media" / "m0123456789ab" / name).write_bytes(b"app copy")
    (state / "media" / "results" / "j0123456789ab_i001").mkdir(parents=True)
    (state / "media" / "results" / "j0123456789ab_i001" / "view.jpg").write_bytes(b"app view")
    (state / "work" / "j0123456789ab" / "i001").mkdir(parents=True)
    (state / "work" / "j0123456789ab" / "i001" / "stage0.png").write_bytes(b"pass")
    (state / "workers" / "gpu0" / "output").mkdir(parents=True)
    (state / "workers" / "gpu0" / "output" / "cu_j0123456789ab_i001_s0_00001_.png").write_bytes(b"engine file")
    for name in cleanup.OWNED_FILES:
        if not (state / name).exists():
            (state / name).write_text("{}" if name.endswith(".json") else "x")
    for name in ("session-0123456789abcdef.token", "folders.json.tmp", "settings.json.4242.a1b2c3.tmp",
                 "model-licence-acceptance.json." + "f" * 32 + ".tmp"):
        (state / name).write_text("x")


def fill_engine(engine):
    """The managed image engine as runtime setup leaves it: Python, the pinned ComfyUI source (its empty files, with
    the output folder's placeholder), the download cache and temporary folder, the log and lock, and the two records."""
    (engine / "python" / "Lib" / "site-packages").mkdir(parents=True)
    (engine / "python" / "python.exe").write_bytes(b"x")
    for relative in EMPTY_SOURCE:
        (engine / "ComfyUI" / relative).parent.mkdir(parents=True, exist_ok=True)
        (engine / "ComfyUI" / relative).write_bytes(b"")
    (engine / "ComfyUI" / "app" / "__pycache__").mkdir(parents=True, exist_ok=True)
    (engine / "ComfyUI" / "app" / "__pycache__" / "__init__.cpython-313.pyc").write_bytes(b"pyc")
    (engine / ".cache" / "assets").mkdir(parents=True)
    (engine / ".cache" / "assets" / "python-90b4e5b9898b72d7.zip").write_bytes(b"zip")
    (engine / ".tmp").mkdir()
    (engine / "setup-details.log").write_text("log")
    (engine / ".setup.lock").write_bytes(b"0")
    (engine / "runtime-receipt.json").write_text("{}")
    (engine / ".artegra-runtime.json").write_text("{}")


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
    fill_engine(engine)
    pictures = tmp_path / "Pictures" / "Artegra Enhancer"
    pictures.mkdir(parents=True)
    (pictures / "result_cu2x.png").write_bytes(b"an image")
    choices = {"models_dir": str(models_dir or models), "runtime_dir": str(runtime_dir or engine), "output_dir": str(pictures)}
    (state / "folders.json").write_text(json.dumps(choices))
    (state / "installation-location.json").write_text(json.dumps({"data_directory": str(data)}))
    fill_state(state)
    (root / "demo" / "outputs").mkdir(parents=True)
    (root / "demo" / "outputs" / "demo_cu2x.png").write_bytes(b"demo image")
    fill_state(root / "demo")
    (root / "cache" / "qmlcache").mkdir(parents=True)
    (root / "cache" / "qmlcache" / "Main.qmlc").write_bytes(b"compiled")
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


def test_the_settings_option_removes_the_state_but_never_images(tmp_path, registry):
    root, data, pictures = make_install(tmp_path)
    assert run(root, "--remove-settings") == 0
    assert not (root / "production").exists()       # every entry the app creates is on the list
    assert not (root / "cache").exists()
    assert (pictures / "result_cu2x.png").is_file()
    assert (data / "models").is_dir()
    if os.name == "nt":
        assert registry == [(cleanup.SETTINGS_KEY, False), ("Software\\Studio Artegra", True)]


def test_images_saved_inside_a_state_folder_survive_the_settings_option(tmp_path):
    root, data, pictures = make_install(tmp_path)
    assert run(root, "--remove-settings") == 0
    assert (root / "demo" / "outputs" / "demo_cu2x.png").is_file()
    assert not (root / "demo" / "host.log").exists()
    assert sorted(p.name for p in (root / "demo").iterdir()) == ["outputs"]


def write_job(state, job_id, output_dir, items=()):
    (state / "jobs").mkdir(exist_ok=True)
    (state / "jobs" / f"{job_id}.json").write_text(json.dumps({"id": job_id, "output_dir": str(output_dir),
                                                              "items": list(items)}), encoding="utf-8")


@pytest.mark.parametrize("state_name", ["production", "demo"])
def test_earlier_output_folders_inside_a_state_folder_survive(tmp_path, state_name):
    """The check's case: a job's output folder and the service's own output folder, both inside the state folder."""
    root, data, pictures = make_install(tmp_path)
    state = root / state_name
    job_out, tab_out = state / "client A", state / "my renders"
    for folder, image in ((job_out, "lobby_cu4x.png"), (tab_out, "facade_cu2x_bolt.png")):
        folder.mkdir()
        (folder / image).write_bytes(b"an image")
        (folder / image.replace(".png", ".json")).write_text("{}")
    write_job(state, "j000000000001", job_out)
    (state / "settings.json").write_text(json.dumps({"output_dir": str(tab_out)}), encoding="utf-8")
    assert cleanup.main(["--state", str(root), "--app-root", str(ROOT), "--log", str(tmp_path / "c.log"), "--remove-settings"]) == 0
    for path in (job_out / "lobby_cu4x.png", job_out / "lobby_cu4x.json", tab_out / "facade_cu2x_bolt.png",
                 tab_out / "facade_cu2x_bolt.json", pictures / "result_cu2x.png"):
        assert path.is_file(), path
    assert not (state / "host.log").exists() and not (state / "jobs").exists()
    log = (tmp_path / "c.log").read_text(encoding="utf-8")
    assert f"output folder kept: {job_out}" in log and f"output folder kept: {tab_out}" in log


def test_the_entry_point_keeps_output_folders_named_only_by_a_jobs_items(tmp_path):
    """Through ArtegraEnhancer --uninstall-cleanup (host.app's dispatch): a folder named by an item's result and recipe."""
    from host import app as host_app
    root, data, pictures = make_install(tmp_path)
    state = root / "production"
    # Inside the app's own folders, so only the records can keep them; plain names, so the result-name guard cannot.
    elsewhere, renamed = state / "media" / "exports", state / "work" / "saving"
    for folder in (elsewhere, renamed):
        folder.mkdir()
    (elsewhere / "hall.png").write_bytes(b"an image")
    (renamed / "atrium.png").write_bytes(b"an image")
    write_job(state, "j000000000002", pictures, items=[
        {"id": "i001", "output": str(elsewhere / "hall.png"), "sidecar": str(elsewhere / "hall.json")},
        {"id": "i002", "publishing": {"output": str(renamed / "atrium.png")}}])
    code = host_app.main(["--uninstall-cleanup", "--state", str(root), "--app-root", str(ROOT),
                          "--log", str(tmp_path / "c.log"), "--remove-settings", "--remove-files"])
    assert code == 0
    assert (elsewhere / "hall.png").is_file() and (renamed / "atrium.png").is_file()
    assert not (state / "logs").exists() and not (state / "jobs").exists() and not (state / "host.log").exists()
    assert not (data / "engine-v1").exists()


def test_a_folder_that_is_not_the_apps_own_is_kept_whatever_it_holds(tmp_path):
    root, data, pictures = make_install(tmp_path)
    state = root / "production"
    unrecorded = state / "old exports"
    unrecorded.mkdir()
    (unrecorded / "IMG_0042.png").write_bytes(b"an image")
    (state / "notes.txt").write_text("mine")
    (state / "jobs.bak").mkdir()
    assert run(root, "--remove-settings") == 0
    assert (unrecorded / "IMG_0042.png").is_file() and (state / "notes.txt").is_file() and (state / "jobs.bak").is_dir()
    assert sorted(p.name for p in state.iterdir()) == ["jobs.bak", "notes.txt", "old exports"]
    log = (root.parent / "cleanup.log").read_text(encoding="utf-8")
    assert "kept " + str(unrecorded) + " (not one of the app's own settings, logs or records)" in log


def test_an_output_folder_inside_an_app_folder_keeps_that_folder(tmp_path):
    root, data, pictures = make_install(tmp_path)
    state = root / "production"
    inside = state / "work" / "finals"
    inside.mkdir()
    (inside / "IMG_0042.png").write_bytes(b"an image")
    (state / "settings.json").write_text(json.dumps({"output_dir": str(inside)}), encoding="utf-8")
    assert run(root, "--remove-settings") == 0
    assert (inside / "IMG_0042.png").is_file()
    assert not (state / "media").exists() and not (state / "host.log").exists()


@pytest.mark.parametrize("where", ["media/m0123456789ab", "jobs", "cache"])
def test_an_unrecorded_result_inside_an_app_folder_keeps_that_folder(tmp_path, where):
    """No record names it (a job removed, a record unreadable): a file named like a result keeps its app folder."""
    root, data, pictures = make_install(tmp_path)
    base = root if where == "cache" else root / "production"
    folder = base / where
    (folder / "facade_cu2x.png").write_bytes(b"an image")
    (folder / "facade_cu2x.json").write_text("{}")
    assert run(root, "--remove-settings") == 0
    assert (folder / "facade_cu2x.png").is_file() and (folder / "facade_cu2x.json").is_file()
    if where != "jobs":
        assert not (root / "production" / "jobs").exists()


def test_a_state_folder_chosen_as_the_output_folder_keeps_everything_in_it(tmp_path):
    root, data, pictures = make_install(tmp_path)
    state = root / "production"
    (state / "lobby_cu2x.png").write_bytes(b"an image")
    (state / "lobby_cu2x.json").write_text("{}")
    folders = json.loads((state / "folders.json").read_text())
    (state / "folders.json").write_text(json.dumps(dict(folders, output_dir=str(state))))
    assert run(root, "--remove-settings") == 0
    assert (state / "lobby_cu2x.png").is_file() and (state / "lobby_cu2x.json").is_file()
    assert (state / "media" / "m0123456789ab" / "source.png").is_file()      # inside the output folder: kept too
    assert not (root / "demo" / "host.log").exists()                          # the other state is still cleaned


def test_an_output_folder_above_the_state_root_keeps_everything(tmp_path):
    root, data, pictures = make_install(tmp_path)
    (root / "production" / "settings.json").write_text(json.dumps({"output_dir": str(root.parent)}), encoding="utf-8")
    before = sorted(p for p in root.rglob("*"))
    assert run(root, "--remove-settings") == 0
    assert sorted(p for p in root.rglob("*")) == before


def test_a_long_history_resolves_each_folder_once(tmp_path, monkeypatch):
    """Many job records naming the same folders cost one lookup per folder, not one per record and entry."""
    root, data, pictures = make_install(tmp_path)
    for n in range(50):
        write_job(root / "production", f"j{n:012x}", pictures,
                  items=[{"id": f"i{k:03d}", "output": str(pictures / f"p{k}_cu2x.png")} for k in range(20)])
    calls = []
    real = os.path.realpath
    monkeypatch.setattr(cleanup.os.path, "realpath", lambda path, *a, **k: calls.append(str(path)) or real(path, *a, **k))
    assert run(root, "--remove-settings") == 0
    assert not (root / "production").exists() and (pictures / "result_cu2x.png").is_file()
    entries = 2 * (len(cleanup.OWNED_DIRS) + len(cleanup.OWNED_FILES) + 4) + 1
    assert len(calls) <= entries + 5, len(calls)
    log = (root.parent / "cleanup.log").read_text(encoding="utf-8")
    assert log.count(f"output folder kept: {pictures}") == 1


@pytest.mark.skipif(os.name != "nt", reason="drive letters are a Windows feature")
def test_an_output_folder_on_another_drive_is_never_resolved(tmp_path, monkeypatch):
    """Resolving a folder on an offline share can hang; one on another drive cannot be inside the state folder."""
    root, data, pictures = make_install(tmp_path)
    letter = next(c for c in "QRSTUVWXYZ" if not str(tmp_path).upper().startswith(c))
    other = letter + ":" + os.sep                             # a drive the state folder is not on
    write_job(root / "production", "j000000000003", other + "renders")
    calls = []
    real = os.path.realpath
    monkeypatch.setattr(cleanup.os.path, "realpath", lambda path, *a, **k: calls.append(str(path)) or real(path, *a, **k))
    assert run(root, "--remove-settings") == 0
    assert not any(c.upper().startswith(other[:2]) for c in calls)
    assert not (root / "production").exists()


def test_owned_names_are_exact(tmp_path):
    for name in ("settings.json", "host.log", "session-0123456789abcdef.token", "folders.json.tmp",
                 "settings.json.4242.a1b2c3.tmp", "installation.json." + "0" * 32 + ".tmp"):
        (tmp_path / name).write_text("x")
        assert cleanup._owned(tmp_path / name), name
    for name in ("facade_cu2x.json", "photo.json", "notes.log", "session-x.token", "image.png", "a.tmp",
                 "photo.png.tmp", "settings.json.backup", "jobs"):
        (tmp_path / name).write_text("x")                     # a file named like an app folder is not that folder
        assert not cleanup._owned(tmp_path / name), name
    for name in ("outputs", "settings.json.d", "Pictures"):
        (tmp_path / "dirs" / name).mkdir(parents=True)
        assert not cleanup._owned(tmp_path / "dirs" / name), name
    (tmp_path / "dirs" / "media").mkdir()
    assert cleanup._owned(tmp_path / "dirs" / "media")


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
def test_a_junction_in_the_engine_is_never_followed(tmp_path):
    """Setup never makes links. One beside setup's entries is kept; one inside setup's Python folder goes as a link."""
    root, data, pictures = make_install(tmp_path)
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "keep.txt").write_text("keep")
    beside, inside = data / "engine-v1" / "linked", data / "engine-v1" / "python" / "linked"
    for link in (beside, inside):
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(precious)], check=True, capture_output=True)
    assert run(root, "--remove-files") == 0
    assert (precious / "keep.txt").read_text() == "keep"
    assert (beside / "keep.txt").is_file() and not (data / "engine-v1" / "python").exists()
    assert sorted(p.name for p in (data / "engine-v1").iterdir()) == [".artegra-runtime.json", "linked", "runtime-receipt.json"]


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
    engine = len(b"x") + len(b"pyc") + len(b"zip") + len(b"log") + len(b"0") + 2 + 2
    expected = len(MODELS) * len(b"weights") + len(b"partial") + len(b"set aside") + engine
    assert int(out.read_text()) == expected
    assert (data / "engine-v1").is_dir()
    assert run(root, "--remove-files") == 0 and not (data / "engine-v1").exists()


def entry(root, *flags, app=ROOT, log=None):
    """Through ArtegraEnhancer --uninstall-cleanup (host.app's dispatch), as the uninstaller runs it."""
    from host import app as host_app
    return host_app.main(["--uninstall-cleanup", "--state", str(root), "--app-root", str(app),
                          "--log", str(log or root.parent / "cleanup.log"), *flags])


def tree_bytes(folder):
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file() and not p.is_symlink())


def record_output(root, how, folder, image=None):
    """Name `folder` as the output folder the way the app's records do: folders.json, the service's settings or a job."""
    state = root / "production"
    if how == "folders.json":
        choices = json.loads((state / "folders.json").read_text())
        (state / "folders.json").write_text(json.dumps(dict(choices, output_dir=str(folder))))
    elif how == "settings.json":
        (state / "settings.json").write_text(json.dumps({"output_dir": str(folder)}), encoding="utf-8")
    else:
        write_job(state, "j0000000000c1", folder, items=[{"id": "i001", "output": str(image or folder / "x_cu2x.png")}])


@pytest.mark.parametrize("flags", [("--remove-files",), ("--remove-files", "--remove-settings")])
@pytest.mark.parametrize("how", ["folders.json", "settings.json", "a job"])
@pytest.mark.parametrize("where", ["ComfyUI/output", "my exports"])
def test_an_output_folder_inside_the_engine_survives_the_files_option(tmp_path, where, how, flags):
    """The check's cases 9, 9b and 10: an output folder inside the managed engine folder, however it is recorded."""
    root, data, pictures = make_install(tmp_path)
    engine = data / "engine-v1"
    out = engine / where
    out.mkdir(exist_ok=True)
    images = [out / "tower_cu4x.png", out / "plain name.png", out / "tower_cu4x.json"]
    for image in images:
        image.write_bytes(b"an enhanced image")
    record_output(root, how, out, images[0])
    assert entry(root, *flags) == 0
    for image in images:
        assert image.read_bytes() == b"an enhanced image", image
    assert not (engine / "python").exists() and not (engine / ".cache").exists()
    assert not (engine / "ComfyUI" / "app").exists()                       # the rest of the engine source is gone
    assert (engine / "runtime-receipt.json").is_file() and (engine / ".artegra-runtime.json").is_file()
    assert not (data / "models" / MODELS[0]["folder"] / MODELS[0]["filename"]).exists()
    log = (root.parent / "cleanup.log").read_text(encoding="utf-8")
    assert f"output folder kept: {out}" in log and f"kept {out} (" in log and out.is_dir() and pictures.is_dir()
    if where == "ComfyUI/output":
        assert (engine / "ComfyUI" / PLACEHOLDER).is_file()                # a recorded output folder is never entered


def test_every_output_folder_the_log_keeps_still_exists_after_both_options(tmp_path):
    root, data, pictures = make_install(tmp_path)
    out = data / "engine-v1" / "ComfyUI" / "output"
    (out / "tower_cu4x.png").write_bytes(b"an image")
    record_output(root, "settings.json", out)
    before = {p for p in (out, pictures, root / "demo" / "outputs") if p.is_dir()}
    assert entry(root, "--remove-files", "--remove-settings") == 0
    log = (root.parent / "cleanup.log").read_text(encoding="utf-8")
    for folder in before:
        assert f"output folder kept: {folder}" in log and folder.is_dir(), folder
    assert (out / "tower_cu4x.png").is_file() and (out / PLACEHOLDER.split("/")[-1]).is_file()


@pytest.mark.parametrize("name", ["IMG_0042.png", "final for client.tif", "tower_cu4x.png"])
def test_an_unrecorded_image_in_the_engine_source_folder_is_kept(tmp_path, name):
    """No record names the folder any more and the image may be renamed: only setup's own source files go."""
    root, data, pictures = make_install(tmp_path)
    engine = data / "engine-v1"
    image = engine / "ComfyUI" / "output" / name
    image.write_bytes(b"an image")
    beside = engine / "old exports" / "plain.png"
    beside.parent.mkdir()
    beside.write_bytes(b"an image")
    assert entry(root, "--remove-files") == 0
    assert image.read_bytes() == b"an image" and beside.read_bytes() == b"an image"
    assert not (engine / "ComfyUI" / PLACEHOLDER).exists()                  # setup's placeholder is setup's
    assert not (engine / "ComfyUI" / "app").exists() and not (engine / "python").exists()
    assert (engine / "runtime-receipt.json").is_file()                      # the folder still holds the person's files
    log = (root.parent / "cleanup.log").read_text(encoding="utf-8")
    assert f"kept {image} (the engine setup did not put it there)" in log
    assert f"kept {beside.parent} (not one of the image engine's own files)" in log


@pytest.mark.parametrize("parent", ["engine", "data"])
def test_an_output_folder_above_the_engine_keeps_its_images_and_frees_the_engine(tmp_path, parent):
    """Results are saved straight into the output folder. One chosen at the engine or data folder keeps them, and
    setup's own folders below it still go."""
    root, data, pictures = make_install(tmp_path)
    engine = data / "engine-v1"
    out = engine if parent == "engine" else data
    (out / "lobby_cu2x.png").write_bytes(b"an image")
    (out / "lobby_cu2x.json").write_text("{}")
    record_output(root, "folders.json", out)
    assert entry(root, "--remove-files", "--remove-settings") == 0
    assert (out / "lobby_cu2x.png").is_file() and (out / "lobby_cu2x.json").is_file()
    assert not (engine / "python").exists() and not (engine / "ComfyUI").exists() and not (engine / ".cache").exists()
    assert not (data / "models" / MODELS[0]["folder"] / MODELS[0]["filename"]).exists()


def test_setups_python_folder_is_kept_when_it_holds_an_output_folder_or_a_result(tmp_path):
    root, data, pictures = make_install(tmp_path)
    engine = data / "engine-v1"
    (engine / "python" / "renders").mkdir()
    (engine / "python" / "renders" / "a.png").write_bytes(b"an image")
    record_output(root, "a job", engine / "python" / "renders")
    (engine / ".cache" / "facade_cu2x.png").write_bytes(b"an image")
    assert entry(root, "--remove-files") == 0
    assert (engine / "python" / "renders" / "a.png").is_file() and (engine / "python" / "python.exe").is_file()
    assert (engine / ".cache" / "facade_cu2x.png").is_file()
    assert not (engine / ".tmp").exists() and not (engine / "setup-details.log").exists()


@pytest.mark.parametrize("layout", ["normal", "images kept"])
def test_measure_is_exactly_what_the_files_option_frees(tmp_path, layout):
    root, data, pictures = make_install(tmp_path)
    engine = data / "engine-v1"
    if layout == "images kept":
        out = engine / "ComfyUI" / "output"
        (out / "tower_cu4x.png").write_bytes(b"x" * 5000)
        record_output(root, "settings.json", out)
        (engine / "my exports").mkdir()
        (engine / "my exports" / "plain.png").write_bytes(b"y" * 7000)
    size = tmp_path / "size.txt"
    assert entry(root, "--measure", "--out", str(size)) == 0
    before = tree_bytes(data)
    assert entry(root, "--remove-files") == 0
    assert int(size.read_text()) == before - (tree_bytes(data) if data.exists() else 0)
    if layout == "images kept":
        assert int(size.read_text()) < before - 12000


def fake_app(tmp_path, files):
    """An app folder with the real model manifest and a source manifest listing `files` ({relative path: bytes})."""
    app = tmp_path / "app"
    (app / "runtime").mkdir(parents=True)
    shutil.copy(ROOT / "models.manifest.json", app / "models.manifest.json")
    blob = lambda data: hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    (app / "runtime" / "source-manifest.json").write_text(json.dumps(
        {"commit": "0" * 40, "files": {rel: {"blob": blob(data), "mode": "100644"} for rel, data in files.items()}}))
    return app


def test_only_files_that_are_setups_source_byte_for_byte_are_removed(tmp_path):
    files = {"main.py": b"print('engine')\r\n", "input/example.png": b"\x89PNG example", "nodes.py": b"nodes\n",
             PLACEHOLDER: b""}
    app = fake_app(tmp_path, files)
    root, data, pictures = make_install(tmp_path)
    comfy = data / "engine-v1" / "ComfyUI"
    shutil.rmtree(comfy)
    for relative, content in files.items():
        (comfy / relative).parent.mkdir(parents=True, exist_ok=True)
        (comfy / relative).write_bytes(content)
    (comfy / "nodes.py").write_bytes(b"changed by someone\n")              # listed, but not what setup installed
    (comfy / "input" / "my photo.png").write_bytes(b"an image")              # not listed
    assert entry(root, "--remove-files", app=app) == 0
    assert not (comfy / "main.py").exists() and not (comfy / "input" / "example.png").exists()
    assert (comfy / "nodes.py").read_bytes() == b"changed by someone\n"
    assert (comfy / "input" / "my photo.png").is_file()
    assert not (comfy / "output").exists()                                   # emptied of setup's placeholder


def test_without_the_source_list_the_engine_source_folder_is_kept_whole(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    shutil.copy(ROOT / "models.manifest.json", app / "models.manifest.json")
    root, data, pictures = make_install(tmp_path)
    assert entry(root, "--remove-files", app=app) == 0
    engine = data / "engine-v1"
    assert (engine / "ComfyUI" / PLACEHOLDER).is_file() and not (engine / "python").exists()
    assert "the list of the engine's own files could not be read" in (root.parent / "cleanup.log").read_text(encoding="utf-8")


def test_the_engine_names_match_every_name_setup_writes():
    """Pin the lists to runtime setup's code, so a new setup file can't be left behind or a person's file taken for one."""
    text = (ROOT / "runtime" / "setup_runtime.py").read_text(encoding="utf-8")
    constants = dict(re.findall(r'^([A-Z_]+_FILE) = "([^"]+)"', text, re.MULTILINE))
    names = set(re.findall(r'destination / "([^"]+)"', text))
    names |= {constants[n] for n in re.findall(r"destination / ([A-Z_]+_FILE)\b", text)}
    names |= {constants["OWNER_FILE"] + ".tmp", "runtime-receipt.json.tmp"}       # _write_json's temporary files
    known = cleanup.ENGINE_TREES | cleanup.ENGINE_FILES | cleanup.ENGINE_RECORDS | {cleanup.ENGINE_SOURCE}
    assert {n.lower() for n in names} == known


@pytest.mark.parametrize("flags", [("--remove-files",), ("--remove-settings",), ("--measure",)])
def test_the_data_folders_drive_is_resolved_only_for_the_files_option(tmp_path, monkeypatch, flags):
    """The data folder can be on another drive than the state folder. The files option works there, so a record of a
    folder there is resolved (a short or linked name still matches); the settings option never looks a folder up on
    another drive than the state folder's, which can wait on an offline share."""
    root, data, pictures = make_install(tmp_path / "s", data=tmp_path / "d" / "data")
    out = data / "engine-v1" / "ComfyUI" / "output"
    record_output(root, "settings.json", out)
    monkeypatch.setattr(cleanup, "_drive", lambda path: "D:" if cleanup._norm(path).startswith(cleanup._norm(tmp_path / "d")) else "S:")
    assert cleanup.keep_for(root, files=True).is_one(out)
    calls = []
    real = os.path.realpath
    monkeypatch.setattr(cleanup.os.path, "realpath", lambda path, *a, **k: calls.append(cleanup._norm(path)) or real(path, *a, **k))
    extra = ["--out", str(tmp_path / "size.txt")] if flags == ("--measure",) else []
    assert entry(root, *flags, *extra) == 0
    assert (cleanup._norm(out) in calls) == (flags != ("--remove-settings",))
    assert (out / PLACEHOLDER.split("/")[-1]).is_file()


@pytest.mark.skipif(os.name != "nt", reason="8.3 short names are a Windows feature")
def test_an_engine_output_folder_recorded_by_its_short_name_is_kept(tmp_path):
    import ctypes
    root, data, pictures = make_install(tmp_path)
    out = data / "engine-v1" / "ComfyUI" / "Long Folder For Exports"
    out.mkdir()
    (out / "atrium.png").write_bytes(b"an image")
    buffer = ctypes.create_unicode_buffer(1024)
    ctypes.windll.kernel32.GetShortPathNameW(str(out), buffer, 1024)
    if not buffer.value or cleanup._norm(buffer.value) == cleanup._norm(out):
        pytest.skip("this volume has no short names")
    record_output(root, "settings.json", Path(buffer.value))
    assert entry(root, "--remove-files") == 0
    assert (out / "atrium.png").is_file()
    assert f"kept {out} (an output folder)" in (root.parent / "cleanup.log").read_text(encoding="utf-8")


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

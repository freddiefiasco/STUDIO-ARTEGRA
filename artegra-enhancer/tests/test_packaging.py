"""Release boundary checks that need neither a GPU nor network access."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

from runtime import setup_runtime
from tools.build_release import package_zip, setup_terms, sha256
from tools import build_release


def test_download_rejects_nonofficial_sources_before_network(tmp_path):
    for url in ("http://www.python.org/runtime.zip", "https://example.com/runtime.zip", "file:///runtime.zip"):
        with pytest.raises(ValueError, match="official HTTPS"):
            setup_runtime.download(url, "0" * 64, tmp_path / "payload")
    assert not (tmp_path / "payload").exists()


def test_extract_rejects_parent_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../escaped.txt", "no")
    with pytest.raises(ValueError, match="Unsafe archive"):
        setup_runtime.safe_extract(archive, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def test_extract_rejects_symlinks(tmp_path):
    archive = tmp_path / "bad.zip"
    item = zipfile.ZipInfo("link")
    item.external_attr = 0o120777 << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(item, "outside")
    with pytest.raises(ValueError, match="symlinks"):
        setup_runtime.safe_extract(archive, tmp_path / "out")


def test_setup_refuses_existing_runtime_without_modification(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("original runtime")
    with pytest.raises(FileExistsError):
        setup_runtime.install(tmp_path)
    assert sentinel.read_text() == "original runtime"
    assert list(tmp_path.iterdir()) == [sentinel]


def test_setup_is_explicit_and_inert_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_runtime, "install", lambda path: pytest.fail("Setup ran without explicit opt-in"))
    assert setup_runtime.main([]) == 0
    assert setup_runtime.main(["--directory", str(tmp_path / "runtime")]) == 0


def test_exact_blob_verification_rejects_changed_and_extra_files(tmp_path):
    data = b"pinned source\n"
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    path = tmp_path / "main.py"
    path.write_bytes(data)
    manifest = {"files": {"main.py": {"blob": blob, "mode": "100644"}}}
    setup_runtime.verify_source(tmp_path, manifest)
    path.write_bytes(data + b"modified")
    with pytest.raises(ValueError, match="checksum"):
        setup_runtime.verify_source(tmp_path, manifest)
    path.write_bytes(data)
    (tmp_path / "extra.py").write_text("")
    with pytest.raises(ValueError, match="file list"):
        setup_runtime.verify_source(tmp_path, manifest)


def test_pinned_sources_have_no_machine_specific_paths():
    root = Path(__file__).resolve().parents[1]
    files = [root / "runtime" / "requirements-win.lock", root / "runtime" / "source-manifest.json", root / "runtime" / "patches" / "0001-reference-runtime.patch"]
    for path in files:
        text = path.read_text().lower()
        assert "file:///" not in text
        assert ":/users/" not in text
        assert ":\\users\\" not in text
    assert sha256(files[2]) == setup_runtime.PATCH_SHA256
    manifest = json.loads(files[1].read_text())
    assert manifest["commit"] == setup_runtime.COMFY_COMMIT
    assert len(manifest["files"]) > 1000


def test_portable_archive_has_one_top_level_folder(tmp_path):
    folder = tmp_path / "ArtegraEnhancer"
    folder.mkdir()
    (folder / "app.exe").write_bytes(b"test")
    archive = tmp_path / "release.zip"
    package_zip(folder, archive)
    with zipfile.ZipFile(archive) as output:
        assert output.namelist() == ["ArtegraEnhancer/app.exe"]


def test_installer_owns_setup_and_preserves_user_data():
    text = (Path(__file__).resolve().parents[1] / "installer" / "ArtegraEnhancer.iss").read_text()
    assert "PrivilegesRequired=lowest" in text
    assert "[UninstallDelete]" not in text
    assert "ExecAndLogOutput(" in text
    assert "--accept-terms --cancel-file " in text
    assert "LicenseFile=TERMS.txt" in text
    assert "Check: PreparationSucceeded" in text
    assert "GetCustomSetupExitCode" in text
    # Upgrade removes the obsolete terminal-only helper instead of exposing it.
    assert 'Type: files; Name: "{app}\\SetupRuntime.exe"' in text
    assert 'Filename: "{app}\\SetupRuntime.exe"' not in text


def test_installer_terms_include_exact_required_model_notices_and_snapshots():
    root = Path(__file__).resolve().parents[1]
    text = setup_terms(root)
    catalogue = json.loads((root / "models.manifest.json").read_text(encoding="utf-8-sig"))
    for model in catalogue["models"]:
        required = model.get("required_for_standard") or model["id"] == "hyper-sdxl-8steps-cfg"
        if required:
            assert model["acceptance_notice"] in text
            assert model["model_card_url"] in text
            assert model["license_url"] in text
            assert (root / model["license_file"]).read_text(encoding="utf-8").strip() in text
    assert (root / "LICENSE.txt").read_text(encoding="utf-8").strip() in text
    assert (root / "installer" / "TERMS.txt").read_text(encoding="utf-8-sig") == text


def test_changed_terms_fail_build_before_consent_can_be_misrepresented(tmp_path):
    (tmp_path / "LICENSE.txt").write_text("Evaluation licence")
    (tmp_path / "terms.txt").write_text("changed terms")
    (tmp_path / "models.manifest.json").write_text(json.dumps({"models": [{
        "id": "example", "required_for_standard": True,
        "license_file": "terms.txt", "license_snapshot_sha256": "0" * 64,
    }]}))
    with pytest.raises(ValueError, match="saved terms do not match"):
        setup_terms(tmp_path)


def test_desktop_dependency_copy_checks_wheel_integrity_and_omits_entry_scripts(tmp_path, monkeypatch):
    import base64
    from importlib.metadata import FileHash, PackagePath
    from types import SimpleNamespace
    source, output = tmp_path / "site", tmp_path / "output"
    (source / "example").mkdir(parents=True)
    payload = b"verified package code\n"
    (source / "example/module.py").write_bytes(payload)
    item = PackagePath("example/module.py")
    item.hash = FileHash("sha256=" + base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode())
    ignored = PackagePath("../Scripts/example.exe")
    ignored.hash = None
    distribution = SimpleNamespace(version="1.0", files=[item, ignored], locate_file=lambda relative: source / str(relative))
    monkeypatch.setattr(build_release.importlib.metadata, "distribution", lambda name: distribution)
    receipt = build_release.copy_locked_distribution("example", output, "1.0")
    assert receipt["files"] == 1
    assert (output / "example/module.py").read_bytes() == payload
    (source / "example/module.py").write_bytes(b"unexpected edit")
    with pytest.raises(ValueError, match="differs from its wheel record"):
        build_release.copy_locked_distribution("example", output, "1.0")


def test_desktop_dependency_copy_rejects_wrong_version(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(build_release.importlib.metadata, "distribution", lambda name: SimpleNamespace(version="2.0"))
    with pytest.raises(RuntimeError, match="must be 1.0"):
        build_release.copy_locked_distribution("example", tmp_path, "1.0")


def test_packaging_replaces_only_its_generated_folder_and_preserves_previous_output(tmp_path, monkeypatch):
    monkeypatch.setattr(build_release, "ROOT", tmp_path)
    build = tmp_path / "build/release"
    staging = build / "new-package"
    staging.mkdir(parents=True)
    (staging / "new.txt").write_text("new")
    output = tmp_path / "dist/ArtegraEnhancer"
    output.mkdir(parents=True)
    (output / "old.txt").write_text("keep previous package")
    build_release.publish_staging(staging, output, build)
    assert (output / "new.txt").read_text() == "new"
    assert not (output / "old.txt").exists()
    assert next(build.glob("previous-output-*/old.txt")).read_text() == "keep previous package"
    with pytest.raises(ValueError, match="Unexpected release output"):
        build_release.publish_staging(output, tmp_path / "unrelated", build)


# --- 5.0.2: the packaged build channel is "release" (engine design section 3, G0g (d)) ------------------------------------

def channel_of(folder):
    namespace = {}
    exec((Path(folder) / "service" / "build_channel.py").read_text(encoding="utf-8"), namespace)
    return namespace["CHANNEL"], namespace["DEV_PROVEN_MP"]


def test_the_staged_package_is_the_release_channel(tmp_path):
    root = Path(__file__).resolve().parents[1]
    staging = tmp_path / "staging"
    staging.mkdir()
    build_release.stage_sources(staging)
    assert channel_of(staging) == ("release", None)
    assert (staging / "service" / "build_channel.py").read_bytes() == (root / "service" / "build_channel.py").read_bytes()
    assert not list(staging.rglob("__pycache__"))
    assert build_release.DATA_PATHS[:3] == ("host", "ui", "service")


def test_a_developer_tree_is_never_staged(tmp_path):
    from tools import make_dev_build
    dev = make_dev_build.make(tmp_path / "dev", proven={"ws128": 640.0})
    assert channel_of(dev) == ("dev", {"ws128": 640.0})
    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(RuntimeError, match="not the release channel"):
        build_release.stage_sources(staging, root=dev)
    with pytest.raises(RuntimeError, match="not the release channel"):
        build_release.check_release_channel(staging)


def test_the_installer_and_the_zip_are_made_from_the_checked_folder():
    root = Path(__file__).resolve().parents[1]
    iss = (root / "installer" / "ArtegraEnhancer.iss").read_text(encoding="utf-8")
    assert r'Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs' in iss
    source = (root / "tools" / "build_release.py").read_text(encoding="utf-8")
    body = source[source.index("def build(*"):]
    checked = body.index("check_release_channel(output)")
    assert body.index("check_release_channel()") < body.index("stage_sources(staging)") < body.index("publish_staging(")
    assert body.index("publish_staging(staging, output, build_dir)") < checked
    assert checked < body.index('f"/DSourceDir={output}"') and checked < body.index("package_zip(output, archive)")


def test_draft_release_text_is_never_packaged(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "RELEASE-NOTES.md").write_text("# Notes\n\nDone.\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Read me.\n", encoding="utf-8")
    build_release.check_release_text(tmp_path)
    (tmp_path / "docs" / "RELEASE-NOTES.md").write_text("# Notes\n\n<!-- release-draft: engines -->\nDraft.\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="docs/RELEASE-NOTES.md"):
        build_release.check_release_text(tmp_path)
    source = (Path(__file__).resolve().parents[1] / "tools" / "build_release.py").read_text(encoding="utf-8")
    assert "        check_release_text()\n" in source[source.index("if not allow_missing_docs:"):]

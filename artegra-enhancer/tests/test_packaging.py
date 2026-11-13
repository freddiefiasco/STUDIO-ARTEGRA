"""Release boundary checks that need neither a GPU nor network access."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

from runtime import setup_runtime
from tools.build_release import package_zip, sha256


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


def test_inno_recipe_never_installs_runtime_or_removes_user_data():
    text = (Path(__file__).resolve().parents[1] / "installer" / "ArtegraEnhancer.iss").read_text()
    assert "PrivilegesRequired=lowest" in text
    assert "[UninstallDelete]" not in text
    assert "--install" not in text

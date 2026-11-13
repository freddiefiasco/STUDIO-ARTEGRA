import hashlib
import pytest
from tools.verify_models import verify


def record(data=b"model"):
    return {"folder": "weights", "filename": "example.bin", "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def test_existing_model_is_verified_without_modification(tmp_path):
    path = tmp_path / "weights" / "example.bin"
    path.parent.mkdir()
    path.write_bytes(b"model")
    before = path.stat()
    assert verify(tmp_path, [record()]) == [{"file": "weights/example.bin", "ok": True}]
    assert path.read_bytes() == b"model" and path.stat().st_mtime_ns == before.st_mtime_ns


def test_corruption_and_missing_files_are_reported(tmp_path):
    assert verify(tmp_path, [record()])[0]["reason"] == "missing"
    path = tmp_path / "weights" / "example.bin"
    path.parent.mkdir()
    path.write_bytes(b"wrong")
    assert verify(tmp_path, [record()])[0]["reason"] == "hash differs from publisher"


def test_manifest_cannot_escape_model_directory(tmp_path):
    item = record()
    item["folder"] = ".."
    with pytest.raises(ValueError):
        verify(tmp_path, [item])

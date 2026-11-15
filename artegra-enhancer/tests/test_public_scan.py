import tools.public_scan as public_scan
from tools.public_scan import check_blob

# Placeholders stand in for the maintainer's untracked .local/private-terms.txt.
PRIVATE, PUBLISHER = "private-term-example", "publisher.example"


def test_public_installer_publisher_does_not_exempt_private_content(monkeypatch):
    monkeypatch.setattr(public_scan, "FORBIDDEN", (PRIVATE, PUBLISHER))
    line = b"AppPublisherURL=https://www." + PUBLISHER.encode() + b"\r\n"
    assert check_blob("installer/ArtegraEnhancer.iss", line) == []
    assert check_blob("installer/ArtegraEnhancer.iss", line + PRIVATE.encode())
    assert check_blob("notes.md", line)


def test_rejects_paths_tokens_and_weights():
    assert check_blob("notes.md", b"X:" + bytes([92]) + b"private")
    assert check_blob("key.txt", b"ghp_" + b"a" * 36)
    assert check_blob("model.safetensors", b"weight")


def test_accepts_portable_config_and_plain_docs():
    assert check_blob("settings.json", b'{"models_dir":"models"}') == []
    assert check_blob("README.md", b"Creative Upscaler uses local models.") == []


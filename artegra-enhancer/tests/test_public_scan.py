from tools.public_scan import check_blob


def test_rejects_paths_tokens_and_weights():
    assert check_blob("notes.md", b"X:" + bytes([92]) + b"private")
    assert check_blob("key.txt", b"ghp_" + b"a" * 36)
    assert check_blob("model.safetensors", b"weight")


def test_accepts_portable_config_and_plain_docs():
    assert check_blob("settings.json", b'{"models_dir":"models"}') == []
    assert check_blob("README.md", b"Creative Upscaler uses local models.") == []


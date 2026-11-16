import tools.public_scan as public_scan
from tools.public_scan import check_blob

# Placeholders stand in for the maintainer's untracked .local/private-terms.txt.
PRIVATE, PUBLISHER = "private-term-example", "publisher.example"
# A made-up two-word name stands in for another product's name.
FIRST, SECOND = b"quartz", b"lantern"


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



def test_rejects_another_products_name_however_its_words_are_joined(monkeypatch):
    name = (FIRST + b" " + SECOND).decode().title()
    monkeypatch.setattr(public_scan, "FORBIDDEN", (name,))
    monkeypatch.setattr(public_scan, "FORBIDDEN_PATTERNS", public_scan.joined_patterns((name,)))
    first, second = FIRST, SECOND
    for joiner in (b" ", b".", b"-", b"_", b"", b"__", b"\r\n", b"\t"):
        for word_one, word_two in ((first, second), (first.upper(), second.upper()), (first.capitalize(), second.capitalize())):
            text = b"def test_no_line_says_" + word_one + joiner + word_two + b"_or_n(self):"
            assert check_blob("tests/test_x.py", text), (joiner, word_one)
    assert check_blob("notes.md", b"a quartz check, then the lantern") == []
    assert check_blob("notes.md", b"quartzite lanterns") == []

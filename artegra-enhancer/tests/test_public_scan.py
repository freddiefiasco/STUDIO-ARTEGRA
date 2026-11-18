import hashlib
import subprocess
from pathlib import Path

import pytest

import tools.public_scan as public_scan
from tools.public_scan import check_blob, scan

ROOT = Path(__file__).resolve().parents[1]
LISTED = public_scan.load_private_terms()  # the maintainer's own list; empty in CI
BS = bytes([92])  # one backslash, so this file holds no network path itself
# Placeholders stand in for the maintainer's untracked .local/private-terms.txt.
PRIVATE, PUBLISHER = "private-term-example", "publisher.example"
# A made-up server name and folder name stand in for the studio's own.
SERVER, FOLDER = "fileserver-example", "ProjectFolderExample"
# A made-up two-word name stands in for another product's name.
FIRST, SECOND = b"quartz", b"lantern"


def test_rejects_network_paths_in_every_written_form():
    """QA1-01: a network path (server and share) fails in plain text, raw strings and escaped string literals."""
    share = b"server" + BS + b"projects" + BS + b"app"
    for text in (BS * 2 + share, b"PACKET = Path(r'" + BS * 2 + share + b"')",
                 b"p = '" + BS * 4 + b"server" + BS * 2 + b"projects'", b"see " + BS * 2 + b"nas01" + BS + b"c$",
                 b'{"dir": "' + BS * 4 + b"10_box" + BS * 2 + b'share"}'):
        assert any("network path" in issue for issue in check_blob("tests/test_x.py", text)), text


def test_accepts_escaped_backslashes_device_prefixes_and_urls():
    for text in (b'"Software' + BS * 2 + b"Studio Artegra" + BS * 2 + b'Artegra Enhancer"',
                 b"DefaultDirName={localappdata}" + BS * 2 + b"Programs" + BS * 2 + b"ArtegraEnhancer",
                 b"print('" + BS * 2 + b"u6f14" + BS * 2 + b"u793a')", b"'" + BS * 2 + b"shell" + BS * 2 + b"open'",
                 b"prefix = '" + BS * 4 + b"?" + BS * 2 + b"'", BS * 2 + b"." + BS + b"pipe" + BS + b"name",
                 b"https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases", b"a" + BS * 2 + b"b"):
        assert check_blob("notes.md", text) == [], text


def test_rejects_the_studio_server_and_internal_folder_names_in_any_case_and_form(monkeypatch):
    monkeypatch.setattr(public_scan, "FORBIDDEN", (SERVER, FOLDER))
    for word in (SERVER, FOLDER):
        for form in (word, word.upper(), word.lower(), "//" + word + "/share", "smb://" + word.lower()):
            assert any("private or excluded identifier" in issue for issue in check_blob("docs/x.md", form.encode())), form
        assert any("file name" in issue for issue in check_blob("docs/" + word + ".md", b"x = 1")), word


def test_the_history_scan_checks_every_blob(tmp_path, monkeypatch):
    monkeypatch.setattr(public_scan, "FORBIDDEN", (SERVER,))
    root = tmp_path / "repo"
    root.mkdir()
    git = lambda *a: subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    git("config", "core.autocrlf", "false")
    (root / "a.py").write_bytes(b"P = r'" + BS * 2 + SERVER.encode() + BS + b"s'\n")
    git("add", "a.py")
    git("commit", "-q", "-m", "one")
    issues = scan(Path(root), history=True)
    assert any("a.py: network path" in issue for issue in issues)
    assert any("a.py: private or excluded identifier" in issue for issue in issues)


def test_the_installer_exempts_only_the_exact_public_publisher_line(monkeypatch):
    """Pass 2's check D1: the exemption is that one line, not the same line form with any listed word."""
    line = b"AppPublisherURL=https://www." + PUBLISHER.encode()
    monkeypatch.setattr(public_scan, "FORBIDDEN", (PRIVATE, PUBLISHER))
    monkeypatch.setattr(public_scan, "PUBLISHER_LINE_SHA256", hashlib.sha256(line.lower()).hexdigest())
    iss = "installer/ArtegraEnhancer.iss"
    assert check_blob(iss, line + b"\r\n") == []
    assert check_blob(iss, b"AppName=Artegra Enhancer (Beta)\n" + line + b"\n") == []
    assert check_blob(iss, b"AppPublisherURL=https://www." + PRIVATE.encode() + b"\r\n")
    assert check_blob(iss, line + b"\r\n" + PRIVATE.encode())
    assert check_blob(iss, line + b"/about\r\n")
    assert check_blob(iss, b"AppSupportURL=https://www." + PUBLISHER.encode() + b"\r\n")
    assert check_blob("notes.md", line)


def test_the_publisher_constant_is_the_installer_scripts_publisher_line():
    lines = (ROOT / "installer" / "ArtegraEnhancer.iss").read_bytes().lower().splitlines()
    digests = [hashlib.sha256(line).hexdigest() for line in lines]
    assert digests.count(public_scan.PUBLISHER_LINE_SHA256) == 1
    assert lines[digests.index(public_scan.PUBLISHER_LINE_SHA256)].startswith(b"apppublisherurl=https://www.")


def test_the_local_list_is_read_with_or_without_a_bom_and_skips_comments(tmp_path):
    path = tmp_path / "private-terms.txt"
    assert public_scan.load_private_terms(path) == ()
    path.write_bytes("﻿# a comment\n\n  first-example  \n   # indented comment\nTwo Words\r\n".encode("utf-8"))
    assert public_scan.load_private_terms(path) == ("first-example", "Two Words")
    assert public_scan.PRIVATE_TERMS == ROOT / ".local" / "private-terms.txt"
    assert subprocess.run(["git", "check-ignore", "-q", ".local/private-terms.txt"], cwd=ROOT).returncode == 0


def test_without_the_local_list_only_the_generic_checks_run(monkeypatch):
    monkeypatch.setattr(public_scan, "FORBIDDEN", ())
    monkeypatch.setattr(public_scan, "FORBIDDEN_PATTERNS", ())
    assert check_blob("notes.md", b"any words at all, " + PRIVATE.encode()) == []
    assert any("network path" in issue for issue in check_blob("notes.md", BS * 2 + b"server" + BS + b"share"))
    assert check_blob("notes.md", b"X:" + BS + b"private")


@pytest.mark.skipif(not LISTED, reason="no .local/private-terms.txt: the listed words are checked where it is present")
def test_every_listed_word_is_refused_in_contents_and_file_names():
    for index, term in enumerate(LISTED):
        issues = check_blob("notes.md", ("see " + term + " here").encode("utf-8"))
        assert any("excluded identifier" in issue for issue in issues), f"listed word {index + 1}"
        issues = check_blob("docs/a" + term.replace("/", "_") + "b.md", b"x = 1")
        assert any("in the file name" in issue for issue in issues), f"listed word {index + 1}"


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


def test_rejects_the_name_with_any_short_joiner_and_in_file_names(monkeypatch):
    """A no-break space, a dash, a slash, a plus, a colon, a URL escape or a zero-width space between the two words is
    refused too, in contents and in file names (fix-round check C14)."""
    first, second = FIRST.decode(), SECOND.decode()
    name = first.title() + " " + second.title()
    monkeypatch.setattr(public_scan, "FORBIDDEN", (name,))
    monkeypatch.setattr(public_scan, "FORBIDDEN_PATTERNS", public_scan.joined_patterns((name,)))
    for joiner in (" ", "–", "—", "/", "+", ":", "%20", "​", ". ", " - ", "\r\n"):
        text = ("label: " + first.capitalize() + joiner + second.capitalize()).encode("utf-8")
        assert check_blob("notes.md", text), repr(joiner)
    for path in ("tests/" + first + "_" + second + "_test.py", "docs/" + first.upper() + second.capitalize() + ".md",
                 "assets/" + first + "%20" + second + ".txt"):
        assert any("file name" in issue for issue in check_blob(path, b"x = 1")), path
    assert check_blob("docs/quartz-check.md", b"x = 1") == []
    assert check_blob("notes.md", "a quartz check, then four more: the lantern".encode()) == []

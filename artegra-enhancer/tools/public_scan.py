"""Fail closed on private workstation data and accidental binary payloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Specific private identifiers are not kept in the repository. A maintainer keeps
# them, one per line, in the untracked .local/private-terms.txt (.local/ is ignored),
# the studio's file server and its internal project folders among them: each is
# refused in any case and in any form (a network path, a URL or text, a file name).
# Blank lines and lines starting with "#" are skipped. Without that file only the
# generic checks below run.
PRIVATE_TERMS = ROOT / ".local" / "private-terms.txt"


def load_private_terms(path: Path = PRIVATE_TERMS) -> tuple[str, ...]:
    if not path.is_file():
        return ()
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return tuple(line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#"))


def joined_patterns(terms: tuple[str, ...]) -> tuple[re.Pattern, ...]:
    """A listed name of two words (letters only, such as another product's name) fails in any case, with nothing or up
    to three joining characters between its two words: any character that is not a letter or digit (a space, no-break
    space, dot, hyphen, dash, underscore, slash, plus, colon, zero-width space, a line break) or a URL escape such as
    %20. So snake_case, kebab-case and CamelCase forms fail too. It is matched on the text (UTF-8) and on every file
    name."""
    found = []
    for term in terms:
        words = re.split(r"[^A-Za-z0-9]", term)
        if len(words) == 2 and all(word.isalpha() and len(word) >= 4 for word in words):
            found.append(re.escape(words[0].lower()) + r"(?:[^a-z0-9]|%[0-9a-f]{2}){0,3}" + re.escape(words[1].lower()))
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in dict.fromkeys(found))


FORBIDDEN = load_private_terms()
FORBIDDEN_PATTERNS = joined_patterns(FORBIDDEN)
DRIVE = re.compile(rb"(?i)(?<![a-z0-9])[a-z]:[\\/]")
# A Windows network path (two backslashes, a server name, a backslash and a share name) as plain text or a raw
# string, or escaped in a string literal (four backslashes, the server, two). Two backslashes on both sides of a
# name are an escaped single one, not a network path; the local device prefixes (a question mark or a dot after the
# two backslashes) are not matched either.
UNC = re.compile(rb"(?<![\\\w])(?:\\\\(?!\\)[A-Za-z0-9][A-Za-z0-9._-]*\\(?![\\\s])"
                 rb"|\\\\\\\\[A-Za-z0-9][A-Za-z0-9._-]*\\\\(?![\\\s]))[A-Za-z0-9$]")
SECRETS = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|hf_[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
ALLOWED_BINARY = {".ttf", ".png"}
REJECT_SUFFIXES = {".exe", ".dll", ".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".zip", ".7z", ".log"}
ASSETS = json.loads((ROOT / "asset-hashes.json").read_text()) if (ROOT / "asset-hashes.json").exists() else {}


def check_blob(name: str, data: bytes) -> list[str]:
    if name.startswith("artegra-enhancer/"):
        name = name[len("artegra-enhancer/"):]
    issues = []
    lower = data.lower()
    # The installer's public publisher link is intentionally disclosed. Review
    # only this exact metadata line; private identifiers elsewhere still fail.
    if name == "installer/ArtegraEnhancer.iss":
        publishers = {b"apppublisherurl=https://www." + value.lower().encode() for value in FORBIDDEN}
        lower = b"\n".join(line for line in lower.splitlines() if line not in publishers)
    if any(value.lower().encode() in lower for value in FORBIDDEN) \
            or any(p.search(lower.decode("utf-8", "ignore")) for p in FORBIDDEN_PATTERNS):
        issues.append(f"{name}: private or excluded identifier")
    if any(value.lower() in name.lower() for value in FORBIDDEN) or any(p.search(name) for p in FORBIDDEN_PATTERNS):
        issues.append(f"{name}: private or excluded identifier in the file name")
    if UNC.search(data):
        issues.append(f"{name}: network path")
    reviewed_asset = name.replace("\\", "/") in ASSETS and hashlib.sha256(data).hexdigest() == ASSETS[name.replace("\\", "/")]
    if DRIVE.search(data) and not reviewed_asset:
        issues.append(f"{name}: absolute drive path")
    if SECRETS.search(data):
        issues.append(f"{name}: credential pattern")
    suffix = Path(name).suffix.lower()
    if suffix in REJECT_SUFFIXES:
        issues.append(f"{name}: prohibited binary or runtime payload")
    elif b"\x00" in data and not reviewed_asset:
        issues.append(f"{name}: unreviewed binary type")
    return issues


def scan(root: Path, history: bool = False) -> list[str]:
    issues = []
    if history:
        # Inspect every historical blob, including deleted content, without printing it.
        objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=root, text=True)
        for line in objects.splitlines():
            sha, _, name = line.partition(" ")
            kind = subprocess.check_output(["git", "cat-file", "-t", sha], cwd=root, text=True).strip()
            if kind == "blob":
                data = subprocess.check_output(["git", "cat-file", "blob", sha], cwd=root)
                issues.extend(check_blob(name or sha, data))
            elif kind == "commit":
                data = subprocess.check_output(["git", "cat-file", "commit", sha], cwd=root)
                issues.extend(check_blob("commit " + sha, data))
    else:
        files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root)
        for raw in files.split(b"\0"):
            if not raw:
                continue
            name = raw.decode("utf-8")
            path = root / name
            if path.is_symlink():
                issues.append(f"{name}: symlink needs explicit review")
            elif path.is_file():
                issues.extend(check_blob(name, path.read_bytes()))
    return sorted(set(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    issues = scan(ROOT, args.history)
    print("\n".join(issues) if issues else "Public-content scan passed.")
    return bool(issues)


if __name__ == "__main__":
    raise SystemExit(main())

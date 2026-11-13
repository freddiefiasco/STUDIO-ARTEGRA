"""Fail closed on private workstation data and accidental binary payloads."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Encoded so the policy itself contains no matching private identifiers.
FORBIDDEN = tuple(bytes.fromhex(value).decode() for value in (
    "6d61786967", "415254454752415f", "4f6e654472697665", "52656e646572466c6f77",
    "31302e31302e", "73747564696f2d617274656772612e636f6d", "4d65727365726b",
    "56697375616c20456e68616e636572", "56697375616c2e456e68616e636572",
))
DRIVE = re.compile(rb"(?i)(?<![a-z0-9])[a-z]:[\\/]")
SECRETS = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|hf_[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
ALLOWED_BINARY = {".ttf", ".png"}
REJECT_SUFFIXES = {".exe", ".dll", ".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".zip", ".7z", ".log"}
ASSETS = json.loads((ROOT / "asset-hashes.json").read_text()) if (ROOT / "asset-hashes.json").exists() else {}


def check_blob(name: str, data: bytes) -> list[str]:
    if name.startswith("artegra-enhancer/"):
        name = name[len("artegra-enhancer/"):]
    issues = []
    lower = data.lower()
    for value in FORBIDDEN:
        if value.lower().encode() in lower:
            issues.append(f"{name}: private or excluded identifier")
            break
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

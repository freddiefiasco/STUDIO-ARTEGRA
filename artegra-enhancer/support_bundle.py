"""Write an explicitly requested, redacted diagnostic bundle. Never uploads."""
from __future__ import annotations

import json
from pathlib import Path
import platform
import re
import zipfile

PRIVATE_KEY = re.compile(r"token|password|secret|authorization|cookie|api.?key|(?:^|_)(?:user|email|hostname|computer|path|dir|filename|name)(?:$|_)", re.I)
URL = re.compile(r"(?:https?|file)://[^\s\"<>]+", re.I)
DRIVE = re.compile(r"(?<!\w)[a-z]:[\\/][^\r\n\"<>]*", re.I)
UNC = re.compile(r"\\\\[^\r\n\"<>]+")
POSIX = re.compile(r"(?<![\w:])/(?!/)[^\s\"<>]+")
BEARER = re.compile(r"\bBearer\s+[^\s\"<>,;]+", re.I)
SECRET_ASSIGNMENT = re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|token|password|secret|cookie)\s*[\"']?\s*[:=]\s*[\"']?[^\s\"',;}]+")
TOKEN = re.compile(r"\b(?:gh[pousr]_|github_pat_|hf_)[A-Za-z0-9_]+")
ADDRESS = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
IMAGE_NAME = re.compile(r"[\w .-]+\.(?:png|jpg|jpeg|tiff?|exr|webp|bmp)\b", re.I)


def sanitize(value, key=""):
    if PRIVATE_KEY.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        for pattern in (SECRET_ASSIGNMENT, BEARER, URL, DRIVE, UNC, POSIX, TOKEN, ADDRESS, IMAGE_NAME):
            value = pattern.sub("<redacted>", value)
    return value


def create_bundle(state_dir: Path, destination: Path, *, limit_bytes=8 * 1024 * 1024) -> dict:
    """Select only application logs/config; omit images, tokens and arbitrary files."""
    state = Path(state_dir).resolve()
    destination = Path(destination)
    candidates = [state / name for name in ("host.log", "host-service.log", "config.json")]
    candidates += sorted((state / "logs").glob("app-*.jsonl"), reverse=True)[:14]
    candidates += sorted((state / "workers").glob("*/comfy-*.log"), reverse=True)[:8]
    selected, total = [], 0
    for path in candidates:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(state):
            continue
        with path.open("rb") as stream:
            size = path.stat().st_size
            offset = max(0, size - 256 * 1024)
            stream.seek(offset)
            raw = stream.read(256 * 1024).decode("utf-8", errors="replace")
        if offset:
            raw = raw.partition("\n")[2]
        rows = []
        if path.suffix == ".json":
            try:
                raw = json.dumps(sanitize(json.loads(raw)))
            except ValueError:
                raw = "Unreadable configuration omitted."
        for row in raw.splitlines():
            try:
                rows.append(json.dumps(sanitize(json.loads(row)), ensure_ascii=False))
            except (ValueError, TypeError):
                rows.append(sanitize(row))
        content = ("\n".join(rows) + "\n").encode()
        if total + len(content) > limit_bytes:
            break
        # Numbering avoids exposing user-created directory or file names.
        selected.append((f"logs/{len(selected) + 1:02d}.txt", content))
        total += len(content)
    result = {"files": len(selected), "bytes": total, "uploaded": False,
              "platform": platform.system(), "python": platform.python_version()}
    with destination.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in selected:
                archive.writestr(name, content)
            archive.writestr("summary.json", json.dumps(result, indent=2))
    return result

"""Check for updates: one HTTPS request to the GitHub releases list, made only when the person asks.

Nothing is downloaded or installed. The request names the app and its version in the User-Agent and carries no
account, token, file name, folder or identifier.
"""
from __future__ import annotations

import http.client
import json
import re
import time
import urllib.error
import urllib.request

from host.config import DISPLAY_NAME, VERSION

REPOSITORY = "freddiefiasco/STUDIO-ARTEGRA"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=50"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases/tag/"
TAG_PREFIX = "artegra-enhancer-v"
TIMEOUT_S = 10.0
MAX_BYTES = 2 * 1024 * 1024
FAILED = "Couldn't reach GitHub. Check your connection and try again."
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$")
STAGES = {"alpha": 0, "beta": 1, "rc": 2}
STAGE_WORDS = {"alpha": "Alpha", "beta": "Beta", "rc": "Release candidate"}


class UpdateError(Exception):
    pass


def parse_version(text):
    """(major, minor, patch, stage, number) for '5.0.0' or '5.0.0-beta.2'; a final release sorts above its pre-releases."""
    m = VERSION_RE.match(str(text or ""))
    if not m:
        return None
    major, minor, patch, stage, number = m.groups()
    return (int(major), int(minor), int(patch)) + ((STAGES[stage], int(number)) if stage else (len(STAGES), 0))


def display_version(text):
    m = VERSION_RE.match(str(text or ""))
    if not m:
        return str(text or "")
    major, minor, patch, stage, number = m.groups()
    base = f"{major}.{minor}.{patch}"
    return f"{base} {STAGE_WORDS[stage]} {number}" if stage else base


def build_request():
    return urllib.request.Request(API_URL, method="GET", headers={
        "User-Agent": f"ArtegraEnhancer/{VERSION}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to another HTTPS address on api.github.com."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not str(newurl).startswith("https://api.github.com/"):
            raise UpdateError("redirect away from the releases API")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_opener():
    # The default handlers honour the system proxy and verify TLS with the system certificates. No cookie handler.
    return urllib.request.build_opener(_SameHostRedirect())


def _wait_at_most(response, seconds):
    """Let the next read of the answer's socket wait no longer than the time left (an answer that drips in slowly)."""
    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
    if sock is not None:
        try:
            sock.settimeout(max(0.05, seconds))
        except OSError:
            pass


def fetch(opener=None, timeout=TIMEOUT_S, clock=time.monotonic):
    """The raw answer of the releases API, at most MAX_BYTES, within `timeout` seconds overall. Each read returns what
    has arrived (read1) and waits at most the time left, so an answer that drips in slowly is cut off on time too."""
    opener = opener or default_opener()
    deadline = clock() + timeout
    with opener.open(build_request(), timeout=timeout) as response:
        if getattr(response, "status", 200) != 200:
            raise UpdateError(f"HTTP {response.status}")
        read = getattr(response, "read1", None) or response.read
        chunks, size = [], 0
        while True:
            left = deadline - clock()
            if left <= 0:
                raise TimeoutError("the releases API answered too slowly")
            _wait_at_most(response, left)
            chunk = read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise UpdateError("the answer is too large")
            chunks.append(chunk)
    return b"".join(chunks)


def newest_release(releases):
    """(version text, release page URL) of the newest non-draft artegra-enhancer release, pre-releases included."""
    if not isinstance(releases, list):
        raise UpdateError("not a release list")
    best = None
    for entry in releases:
        if not isinstance(entry, dict) or entry.get("draft") is not False:
            continue
        tag = entry.get("tag_name")
        if not isinstance(tag, str) or not tag.startswith(TAG_PREFIX):
            continue
        text = tag[len(TAG_PREFIX):]
        key = parse_version(text)
        if key is None:
            continue
        page = RELEASES_URL + tag
        url = entry.get("html_url") if entry.get("html_url") == page else page
        if best is None or key > best[0]:
            best = (key, text, url)
    if best is None:
        raise UpdateError("no Artegra Enhancer release in the list")
    return best[1], best[2]


def failed():
    return {"state": "failed", "message": FAILED, "latest": "", "url": ""}


def check(current=VERSION, opener=None, answer=None):
    """{state: current | available | failed, message, latest, url}. `answer`: recorded API bytes (tests, demo screens).
    Never raises: anything that goes wrong on the way (network, proxy, a cut-off or odd answer) is the plain failure."""
    try:
        data = answer if answer is not None else fetch(opener)
        releases = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
        latest, url = newest_release(releases)
        newer = parse_version(latest) > parse_version(current)
    except (OSError, ValueError, UpdateError, urllib.error.URLError, TimeoutError, http.client.HTTPException):
        return failed()
    except Exception:       # last resort: a check that cannot finish must still say so, never stay on "Checking"
        return failed()
    if newer:
        return {"state": "available", "message": f"{DISPLAY_NAME} {display_version(latest)} is available.",
                "latest": latest, "url": url}
    return {"state": "current", "message": f"{DISPLAY_NAME} {display_version(current)} is up to date.",
            "latest": latest, "url": url}

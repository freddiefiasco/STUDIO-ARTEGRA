"""The Check for updates button's bridge: it always comes back from "Checking for updates…" with a plain answer. No network."""
import http.client
import os
from pathlib import Path
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from host import updates, updates_qt
from host.updates_qt import UpdateBridge

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "github-releases"


@pytest.fixture(scope="module")
def qt():
    return QApplication.instance() or QApplication([])


def until(qt, condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.005)
    qt.processEvents()
    assert condition()


class Opener:
    def __init__(self, outcome):
        self.outcome = outcome

    def open(self, request, timeout=None):
        raise self.outcome


@pytest.mark.parametrize("outcome", [http.client.BadStatusLine("garbage"), http.client.IncompleteRead(b"["),
                                     http.client.LineTooLong("header line")], ids=lambda e: type(e).__name__)
def test_an_http_protocol_error_ends_the_check_with_the_plain_failure(qt, monkeypatch, outcome):
    monkeypatch.setattr(updates, "default_opener", lambda: Opener(outcome))
    bridge = UpdateBridge()
    bridge.check()
    assert bridge.state == "checking" and bridge.message == "Checking for updates…"
    until(qt, lambda: bridge.state != "checking")
    assert (bridge.state, bridge.message, bridge.downloadUrl) == ("failed", updates.FAILED, "")


def test_a_check_that_raises_still_answers_and_the_button_works_again(qt, monkeypatch):
    def broken(**kwargs):
        raise RuntimeError("an error nobody planned for")

    monkeypatch.setattr(updates, "check", broken)
    bridge = UpdateBridge()
    bridge.check()
    until(qt, lambda: bridge.state != "checking")
    assert (bridge.state, bridge.message) == ("failed", updates.FAILED)
    monkeypatch.undo()
    bridge.fixture = FIXTURES / "with-beta-2.json"
    bridge.check()                                   # accepted again: not stuck on "checking"
    until(qt, lambda: bridge.state != "checking")
    assert bridge.state == "available"
    assert bridge.message == "Artegra Enhancer (Beta) 5.0.1 Beta 2 is available."
    assert bridge.downloadUrl.startswith("https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/tag/")


def test_only_one_check_runs_at_a_time(qt, monkeypatch):
    started = []
    monkeypatch.setattr(updates, "check", lambda **kwargs: started.append(1) or updates.failed())
    bridge = UpdateBridge()
    bridge.check()
    bridge.check()
    until(qt, lambda: bridge.state != "checking")
    assert started == [1]


def test_a_missing_recorded_answer_and_an_odd_result_read_as_the_plain_failure(qt, tmp_path):
    bridge = UpdateBridge(fixture=tmp_path / "missing.json")
    bridge.check()
    until(qt, lambda: bridge.state != "checking")
    assert (bridge.state, bridge.message) == ("failed", updates.FAILED)
    bridge.apply(None)
    assert (bridge.state, bridge.message) == ("failed", updates.FAILED)


def test_the_download_button_opens_only_the_repositorys_pages(qt, monkeypatch):
    opened = []

    class Desktop:
        @staticmethod
        def openUrl(url):
            opened.append(url.toString())

    monkeypatch.setattr(updates_qt, "QDesktopServices", Desktop)
    bridge = UpdateBridge()
    bridge.apply({"state": "available", "message": "x", "latest": "9.0.0", "url": "https://example.invalid/x"})
    bridge.openDownload()
    good = "https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/tag/artegra-enhancer-v9.0.0"
    bridge.apply({"state": "available", "message": "x", "latest": "9.0.0", "url": good})
    bridge.openDownload()
    assert opened == [good]

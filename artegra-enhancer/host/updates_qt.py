"""Qt adapter for Check for updates (host/updates.py): one check at a time, only when the person asks."""
from __future__ import annotations

from pathlib import Path
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices

from host import updates

OPENABLE = ("https://github.com/freddiefiasco/STUDIO-ARTEGRA/",)


class UpdateBridge(QObject):
    changed = Signal()
    finished = Signal(object)

    def __init__(self, fixture=None, parent=None, *, openable=OPENABLE):
        super().__init__(parent)
        self._state, self._message, self._latest, self._url = "idle", "", "", ""
        self.fixture = fixture
        self.openable = tuple(openable)
        self.finished.connect(self.apply)

    @Property(str, notify=changed)
    def state(self): return self._state
    @Property(str, notify=changed)
    def message(self): return self._message
    @Property(str, notify=changed)
    def latestVersion(self): return self._latest
    @Property(str, notify=changed)
    def downloadUrl(self): return self._url

    @Slot()
    def check(self):
        if self._state == "checking":
            return
        self._state, self._message = "checking", "Checking for updates…"
        self.changed.emit()
        threading.Thread(target=self._work, args=(self.fixture,), daemon=True).start()

    def _work(self, fixture):
        # Exactly one result is always sent back, so the button never stays on "Checking for updates…".
        result = None
        try:
            answer = None
            if fixture is not None:
                try:
                    answer = Path(fixture).read_bytes()
                except OSError:
                    answer = b"not json"
            result = updates.check(answer=answer)
        except Exception:
            result = None
        finally:
            self.finished.emit(result if isinstance(result, dict) else updates.failed())

    @Slot(object)
    def apply(self, result):
        if not isinstance(result, dict):
            result = updates.failed()
        self._state = result.get("state", "failed")
        self._message = result.get("message", "")
        self._latest = result.get("latest", "")
        self._url = result.get("url", "") if self._state == "available" else ""
        self.changed.emit()

    @Slot()
    def openDownload(self):
        if self._url.startswith(self.openable):
            QDesktopServices.openUrl(QUrl(self._url))

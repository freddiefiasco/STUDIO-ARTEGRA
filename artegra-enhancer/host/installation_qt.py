"""Threaded Qt adapter for the complete installation, including recovery."""
from __future__ import annotations

from pathlib import Path
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices

from host.model_setup import SetupError


class InstallationBridge(QObject):
    changed = Signal()
    completed = Signal(object)
    closeReady = Signal()
    _event = Signal(object)
    _finished = Signal(str, str, object)

    def __init__(self, root, state, parent=None, *, enabled=True, factory=None):
        super().__init__(parent)
        self.root, self.state = Path(root), Path(state)
        self._factory = factory
        self._enabled = enabled
        self._busy = False
        self._complete = not enabled
        self._accepted = False
        self._needs_consent = enabled
        self._status = "We'll prepare everything you need to enhance your images."
        self._stage = "welcome"
        self._fraction = 0.0
        self._terms = []
        self._choices = {}
        self._thread = None
        self._cancel = threading.Event()
        self._closing = False
        self._event.connect(self._receive)
        self._finished.connect(self._finish)
        if enabled:
            try:
                installation = self._installation()
                self._choices = dict(installation.choices)
                self._terms = list(installation.terms)
                self._complete = installation.is_complete()
                accepted = getattr(installation, "terms_accepted", None)
                self._needs_consent = not (accepted() if callable(accepted) else self._complete)
                self._stage = "ready" if self._complete else "welcome"
            except (SetupError, OSError, ValueError) as exc:
                self._status = str(exc)
                self._stage = "error"

    def _installation(self):
        if self._factory is None:
            from host.installation import Installation
            self._factory = Installation
        return self._factory(self.root, self.state, progress=self._event.emit, cancel=self._cancel)

    @property
    def choices(self):
        return dict(self._choices)

    @Property(bool, notify=changed)
    def busy(self): return self._busy

    @Property(bool, notify=changed)
    def complete(self): return self._complete

    @Property(bool, notify=changed)
    def needsConsent(self): return self._needs_consent

    @Property(bool, notify=changed)
    def accepted(self): return self._accepted

    @Property(str, notify=changed)
    def status(self): return self._status

    @Property(str, notify=changed)
    def stage(self): return self._stage

    @Property(float, notify=changed)
    def fraction(self): return self._fraction

    @Property("QVariantList", notify=changed)
    def terms(self): return self._terms

    @Slot(bool)
    def setAccepted(self, accepted):
        if not self._busy:
            self._accepted = accepted
            self.changed.emit()

    @Slot()
    def start(self):
        if not self._enabled or self._busy or self._closing:
            return
        if self._needs_consent and not self._accepted:
            self._status = "Review and accept the terms to continue."
            self.changed.emit()
            return
        self._cancel.clear()
        self._busy = True
        self._complete = False
        self._stage = "checking"
        self._status = "Checking your installation…"
        self._fraction = 0.0
        self.changed.emit()

        def work():
            try:
                installation = self._installation()
                choices = installation.run(accept_terms=self._accepted)
                self._finished.emit("ready", "Everything is ready. Opening your workspace…", choices)
            except SetupError as exc:
                self._finished.emit("paused" if exc.code == "cancelled" else "error", str(exc), None)
            except Exception:
                self._finished.emit("error", "Setup couldn't finish. Check your connection and free space, then try again.", None)

        self._thread = threading.Thread(target=work, name="artegra-installation", daemon=False)
        self._thread.start()

    @Slot(object)
    def _receive(self, event):
        if not self._busy or self._cancel.is_set():
            return
        self._stage = str(event.get("stage", "installing"))
        self._status = str(event.get("message", "Preparing Artegra Enhancer…"))
        self._fraction = max(0.0, min(1.0, float(event.get("fraction", 0.0))))
        self.changed.emit()

    @Slot(str, str, object)
    def _finish(self, stage, message, choices):
        self._busy = False
        self._stage, self._status = stage, message
        self._complete = stage == "ready"
        if self._complete:
            self._choices = dict(choices)
            self._needs_consent = False
            self._fraction = 1.0
        self.changed.emit()
        if self._closing:
            self.closeReady.emit()
        elif self._complete:
            self.completed.emit(self.choices)

    @Slot()
    def pause(self):
        if self._busy:
            self._cancel.set()
            self._stage = "pausing"
            self._status = "Pausing safely… Your download progress will be saved."
            self.changed.emit()

    @Slot()
    def requestClose(self):
        self._closing = True
        if self._busy:
            self.pause()
        else:
            self.closeReady.emit()

    @Slot(str)
    def openTerms(self, identity):
        if identity == "application":
            path = self.root / "LICENSE.txt"
            url = QUrl.fromLocalFile(str(path))
        else:
            row = next((item for item in self._terms if item.get("id") == identity), None)
            if row is None or not str(row.get("license_url", "")).startswith("https://"):
                return
            url = QUrl(row["license_url"])
        if not QDesktopServices.openUrl(url):
            self._status = "The terms couldn't be opened. Try again or view the licences in the application folder."
            self.changed.emit()

    def close(self, timeout=15):
        """Request cancellation; report whether the worker has stopped within the bound."""
        self._closing = True
        self._cancel.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)
        return not (self._thread and self._thread.is_alive())

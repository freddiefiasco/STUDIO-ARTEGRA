"""Qt adapter for explicitly requested model setup; network work stays off the UI thread."""
from __future__ import annotations

from pathlib import Path
import hashlib
import threading
import time

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices

from host.model_setup import ModelSetup, SetupError


class ModelSetupBridge(QObject):
    changed = Signal()
    _event = Signal(object)
    _finished = Signal(str)

    def __init__(self, manifest, state, folder, available, parent=None):
        super().__init__(parent)
        self._folder = folder
        self._available = available
        self._busy = False
        self._status = "Select the models you need. Read each publisher's card and terms before accepting."
        self._fraction = 0.0
        self._cancel = threading.Event()
        self._thread = None
        self._states = {}
        self._selected = {}
        self._root = Path(manifest).resolve().parent
        try:
            self.store = ModelSetup(manifest, Path(state) / "model-licence-acceptance.json")
            self._selected = {key: bool(model.get("required_for_standard") or model.get("required_for_fast"))
                              for key, model in self.store.models.items()}
        except SetupError as exc:
            self.store = None
            self._status = str(exc)
        self._event.connect(self._receive)
        self._finished.connect(self._finish)

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(float, notify=changed)
    def fraction(self):
        return self._fraction

    @Property("QVariantList", notify=changed)
    def models(self):
        if not self.store:
            return []
        rows = []
        for key, model in self.store.models.items():
            purpose = "Standard" if model.get("required_for_standard") else "Fast" if model.get("required_for_fast") else "Optional preview"
            rows.append(dict(id=key, name=model.get("display_name", model["filename"]),
                             purpose=purpose, size=f'{model["size_bytes"]/1024**3:.2f} GiB',
                             license=model["license"], notice=model.get("acceptance_notice", "Read the publisher's terms."),
                             selected=self._selected[key], accepted=self.store.accepted(key),
                             state=self._states.get(key, "Not checked")))
        return rows

    @Property(bool, notify=changed)
    def canDownload(self):
        chosen = [key for key, selected in self._selected.items() if selected]
        return bool(self.store and chosen and not self._busy and all(self.store.accepted(key) for key in chosen))

    @Slot(str, bool)
    def setSelected(self, identity, value):
        if not self._busy and identity in self._selected:
            self._selected[identity] = value
            self.changed.emit()

    @Slot(str, bool)
    def setAccepted(self, identity, value):
        if self._busy or not self.store:
            return
        try:
            self.store.accept(identity, value)
        except SetupError as exc:
            self._status = str(exc)
        self.changed.emit()

    @Slot(str, str)
    def openPublisher(self, identity, kind):
        if not self.store or identity not in self.store.models:
            return
        model = self.store.models[identity]
        url = model["license_url" if kind == "terms" else "model_card_url"]
        if url.startswith("https://"):
            if not QDesktopServices.openUrl(QUrl(url)):
                self._status = "The browser could not open the publisher page. Read Saved terms for its text and source URL."
                self.changed.emit()

    @Slot(str)
    def openSavedTerms(self, identity):
        if not self.store or identity not in self.store.models:
            return
        relative = self.store.models[identity].get("license_file", "")
        path = (self._root / relative).resolve()
        if not relative or not path.is_relative_to(self._root / "licenses" / "models") or not path.is_file():
            self._status = "The saved terms file is missing. Use the publisher link or reinstall the application."
            self.changed.emit()
            return
        try:
            expected = self.store.models[identity].get("license_snapshot_sha256")
            if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                self._status = "The saved terms differ from the catalogue. Reinstall the app or use the publisher link."
                self.changed.emit()
            elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                self._status = "Your computer could not open the saved text. Use the publisher link to review the terms."
                self.changed.emit()
        except OSError:
            self._status = "The saved terms could not be read. Use the publisher link or reinstall the application."
            self.changed.emit()

    @Slot()
    def download(self):
        self._start(False)

    @Slot()
    def verify(self):
        self._start(True)

    def _start(self, verify_only):
        if self._busy or not self.store:
            return
        if not self._available():
            self._status = "Stop the image engine before setting up or verifying model files."
            self.changed.emit()
            return
        folder = self._folder().strip()
        chosen = [key for key, selected in self._selected.items() if selected]
        if not folder or not chosen:
            self._status = "Choose a model folder and select at least one model."
            self.changed.emit()
            return
        if not verify_only and not self.canDownload:
            self._status = "Read and accept the publisher terms for every selected model first."
            self.changed.emit()
            return
        self._busy = True
        self._fraction = 0.0
        self._cancel.clear()
        self._status = "Checking selected model files…"
        self.changed.emit()

        def work():
            last = [0.0]
            try:
                for number, identity in enumerate(chosen, 1):
                    def progress(event):
                        now = time.monotonic()
                        if now - last[0] > 0.12 or event["stage"] == "verified":
                            last[0] = now
                            self._event.emit(dict(event, number=number, count=len(chosen)))
                    result = (self.store.verify if verify_only else self.store.download)(
                        identity, folder, cancel=self._cancel, progress=progress)
                    self._event.emit(dict(result, number=number, count=len(chosen), result=True))
                self._finished.emit("Verification finished. Missing or different files are listed below." if verify_only
                                    else "Selected models are verified and ready. You can start the image engine.")
            except SetupError as exc:
                self._event.emit(dict(id=identity, status="paused" if exc.code == "cancelled" else "error", result=True))
                self._finished.emit(str(exc))
            except Exception:
                # Never surface signed URLs, proxy credentials, headers or raw server responses.
                self._finished.emit("Model setup could not finish. Check the folder and connection, then try again.")

        self._thread = threading.Thread(target=work, name="model-setup", daemon=False)
        self._thread.start()

    @Slot(object)
    def _receive(self, event):
        identity = event["id"]
        if event.get("result"):
            labels = {"verified": "Verified", "missing": "Missing", "different": "Different file — kept unchanged",
                      "paused": "Paused — download again to resume", "error": "Setup stopped — see message below"}
            label = labels.get(event["status"], event["status"])
            if event.get("variant") not in (None, "publisher"):
                label += " · " + event["variant"]
            self._states[identity] = label
        else:
            fraction = min(1.0, event["completed"] / max(1, event["total"]))
            self._fraction = fraction
            name = self.store.models[identity].get("display_name", identity)
            self._states[identity] = f'{event["stage"].capitalize()} · {fraction:.0%}'
            self._status = f'{event["number"]} of {event["count"]}: {name} — {event["stage"]}, {fraction:.0%}'
        self.changed.emit()

    @Slot(str)
    def _finish(self, message):
        self._busy = False
        self._fraction = 0.0
        self._status = message
        self.changed.emit()

    @Slot()
    def cancel(self):
        if self._busy:
            self._cancel.set()
            self._status = "Pausing model setup… The saved transfer can be resumed."
            self.changed.emit()

    def close(self):
        self._cancel.set()
        if self._thread and self._thread.is_alive():
            # Socket cancellation interrupts slow peers; wait for files and the OS
            # lock to close instead of leaving a daemon mutating data after quit.
            self._thread.join()

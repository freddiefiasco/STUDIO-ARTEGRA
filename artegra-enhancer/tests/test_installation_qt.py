"""The setup UI stays responsive and preserves progress through pause/close."""
import os
from pathlib import Path
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Property, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtWidgets import QApplication

from host.installation_qt import InstallationBridge
from host.model_setup import SetupError


@pytest.fixture(scope="module")
def qt():
    return QApplication.instance() or QApplication([])


def until(qt, condition, timeout=3):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.005)
    qt.processEvents()
    assert condition()


@pytest.fixture
def installer(tmp_path):
    class Installer:
        released = threading.Event()
        entered = threading.Event()
        calls = []
        approved = False
        def __init__(self, root, state, *, progress, cancel):
            self.progress, self.cancel = progress, cancel
            self.choices = {key: str(tmp_path / key) for key in ("models_dir", "runtime_dir", "output_dir")}
            self.terms = [{"id": "model", "name": "Image model", "notice": "Publisher terms apply.",
                           "license_url": "https://example.com/terms", "model_card_url": "https://example.com/model"}]
        def is_complete(self): return False
        def terms_accepted(self): return self.approved
        def run(self, *, accept_terms=False):
            self.calls.append((threading.get_ident(), accept_terms))
            self.entered.set()
            self.progress({"stage": "downloading", "message": "Downloading image tools…", "fraction": 0.4})
            while not self.released.wait(0.01):
                if self.cancel.is_set():
                    raise SetupError("Setup paused. Your progress is saved.", "cancelled")
            return self.choices
    return Installer


def test_consent_download_and_completion_are_marshaled_to_ui_thread(qt, installer, tmp_path):
    bridge = InstallationBridge(tmp_path, tmp_path, factory=installer)
    completions = []
    bridge.completed.connect(lambda value: completions.append((threading.get_ident(), value)))
    main_thread = threading.get_ident()
    try:
        bridge.start()
        assert not bridge.busy and not installer.calls
        bridge.setAccepted(True)
        bridge.start()
        assert bridge.busy
        until(qt, lambda: bridge.fraction == 0.4)
        assert installer.calls[0] == (bridge._thread.ident, True)
        assert installer.calls[0][0] != main_thread
        installer.released.set()
        until(qt, lambda: bridge.complete)
        assert not bridge.busy and not bridge.needsConsent
        assert completions == [(main_thread, bridge.choices)]
    finally:
        assert bridge.close()


def test_pause_and_resume_retains_the_same_installation_flow(qt, installer, tmp_path):
    bridge = InstallationBridge(tmp_path, tmp_path, factory=installer)
    try:
        bridge.setAccepted(True)
        bridge.start()
        until(qt, installer.entered.is_set)
        bridge.pause()
        until(qt, lambda: not bridge.busy)
        assert bridge.stage == "paused" and not bridge.complete
        bridge.start()
        installer.released.set()
        until(qt, lambda: bridge.complete)
        assert len(installer.calls) == 2
    finally:
        assert bridge.close()


def test_window_close_waits_for_cancellation_and_never_opens_workspace(qt, installer, tmp_path):
    bridge = InstallationBridge(tmp_path, tmp_path, factory=installer)
    completed, closed = [], []
    bridge.completed.connect(completed.append)
    bridge.closeReady.connect(lambda: closed.append(True))
    bridge.setAccepted(True)
    bridge.start()
    until(qt, installer.entered.is_set)
    bridge.requestClose()
    until(qt, lambda: bool(closed))
    assert bridge.close() and not bridge._thread.is_alive()
    assert not completed


def test_fresh_setup_screen_has_consent_and_direct_progress_controls(qt, installer, tmp_path):
    class Host(QObject):
        @Property(bool, constant=True)
        def busy(self): return False
        @Property(bool, constant=True)
        def demo(self): return False
        @Property(str, constant=True)
        def status(self): return "Welcome"
    host = Host()
    bridge = InstallationBridge(tmp_path, tmp_path, factory=installer)
    engine = QQmlEngine()
    warnings = []
    engine.warnings.connect(lambda items: warnings.extend(item.toString() for item in items))
    engine.rootContext().setContextProperty("installationBridge", bridge)
    engine.rootContext().setContextProperty("hostBridge", host)
    root = Path(__file__).resolve().parents[1]
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(root / "ui/qml/SetupView.qml")))
    view = component.create()
    assert view is not None, [error.toString() for error in component.errors()]
    try:
        view.setProperty("width", 960)
        view.setProperty("height", 540)
        qt.processEvents()
        action = view.findChild(QObject, "installOrResume")
        assert action is not None and not action.property("enabled")
        bridge.setAccepted(True)
        qt.processEvents()
        assert action.property("enabled")
        bridge.start()
        until(qt, lambda: bridge.fraction == 0.4)
        assert view.findChild(QObject, "pauseInstallation").property("visible")
        bridge.pause()
        until(qt, lambda: not bridge.busy)
        assert action.property("text") == "Resume setup"
        assert not warnings, warnings
    finally:
        bridge.close()
        view.deleteLater()
        qt.processEvents()

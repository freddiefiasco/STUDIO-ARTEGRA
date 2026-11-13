"""Qt Quick desktop host. Start with python -m host.app [--demo | --smoke]."""
from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
import urllib.request

from host.config import APP_NAME, ORGANIZATION, read_choices, service_configuration, validate_handshake, write_json

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


class OwnedService:
    def __init__(self, state: Path, configuration: dict, demo: bool):
        self.state = state
        self.process = None
        self.log_stream = None
        self.token = secrets.token_hex(32)
        self.token_path = state / ("session-" + secrets.token_hex(8) + ".token")
        state.mkdir(parents=True, exist_ok=True)
        write_json(state / "config.json", configuration)
        fd = os.open(self.token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as token_file:
            token_file.write(self.token)
        entry = [sys.executable, "--service"] if getattr(sys, "frozen", False) else [getattr(sys, "_base_executable", sys.executable), str(ROOT / "cu_service.py")]
        args = entry + ["--state", str(state), "--config", str(state / "config.json"),
                "--host-pid", str(os.getpid()), "--token-file", str(self.token_path), "--port", "18950"]
        if demo:
            args.append("--fake-engine")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        for name in list(env):
            if name.startswith(("CU_FAST", "CU_SPLIT")) or name in {"CU_TWO_CARD_PROOF", "CU_RUNTIME_PROOF"}:
                env.pop(name, None)
        if not getattr(sys, "frozen", False):
            env["CU_SITE_PACKAGES"] = sysconfig.get_path("purelib")
        try:
            if os.name == "nt":
                from service.windows_job import WindowsJobProcess
                self.process = WindowsJobProcess(args, cwd=str(ROOT), env=env,
                                                 log_path=state / "host-service.log", memory_limit_bytes=192 * 1024**3)
            else:
                self.log_stream = (state / "host-service.log").open("ab")
                self.process = subprocess.Popen(args, cwd=ROOT, env=env, stdout=self.log_stream,
                                                stderr=subprocess.STDOUT, start_new_session=True)
        except BaseException:
            self.close()
            raise

    @property
    def pid(self):
        return self.process.pid if self.process else 0

    def exited(self):
        if not self.process:
            return True
        return (self.process.poll_root() if os.name == "nt" else self.process.poll()) is not None

    def close(self):
        process, self.process = self.process, None
        if process:
            if os.name == "nt":
                process.close(timeout=5)
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        if self.log_stream:
            self.log_stream.close()
            self.log_stream = None
        self.token_path.unlink(missing_ok=True)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--service":
        from service.app import main as service_main
        return service_main(argv[1:])
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--demo", action="store_true", help="Use a separate fake-engine workspace; never use a GPU")
    parser.add_argument("--smoke", action="store_true", help="Offscreen fake-engine load check, then exit")
    parser.add_argument("--state", type=Path, help="Use an isolated application state folder")
    args = parser.parse_args(argv)
    if args.smoke:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["QT_QUICK_BACKEND"] = "software"
        os.environ["QSG_RHI_BACKEND"] = "software"
        os.environ["QSG_RENDER_LOOP"] = "basic"
        if os.name == "nt":
            os.environ["QT_QPA_FONTDIR"] = str(Path(os.environ["SystemRoot"]) / "Fonts")
    from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot, QCoreApplication, QStandardPaths, qInstallMessageHandler
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication, QFileDialog
    from host.model_setup_qt import ModelSetupBridge

    QCoreApplication.setOrganizationName(ORGANIZATION)
    QCoreApplication.setApplicationName(APP_NAME)
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(True)
    # Load font bytes synchronously: Qt's file font loader can lose Unicode path characters.
    for font_name in ("InstrumentSans-Regular.ttf", "InstrumentSans-Medium.ttf"):
        font_path = ROOT / "ui" / "qml" / "creative" / "fonts" / font_name
        if QFontDatabase.addApplicationFontFromData(font_path.read_bytes()) < 0:
            raise RuntimeError("A bundled application font could not be loaded.")
    demo = args.demo or args.smoke
    temporary = tempfile.TemporaryDirectory(prefix="artegra-smoke-") if args.smoke else None
    state = args.state or (Path(temporary.name) if temporary else Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)))
    state = state.resolve() / ("demo" if demo else "production")
    state.mkdir(parents=True, exist_ok=True)
    log_path = state / "host.log"
    warnings = []

    def qt_log(kind, context, message):
        message = re.sub(r"([?&]token=)[^&\s\"']+", r"\1[redacted]", message)
        message = re.sub(r"Bearer\s+[A-Za-z0-9_-]+", "Bearer [redacted]", message)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"{kind}: {message}\n")
        if int(kind) in (1, 2, 3):
            warnings.append(message)

    qInstallMessageHandler(qt_log)
    server_name = "artegra-enhancer-" + hashlib.sha256(str(state).encode()).hexdigest()[:24]
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(400):
        socket.write(b"activate")
        socket.waitForBytesWritten(400)
        socket.disconnectFromServer()
        return 0
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.UserAccessOption)
    if not server.listen(server_name):
        print("The application is already opening. Try again in a moment.", file=sys.stderr)
        return 1

    class Bridge(QObject):
        changed = Signal()
        healthResult = Signal(bool, str)

        def __init__(self):
            super().__init__()
            self.service = None
            self._endpoint = ""
            self._status = "Choose your folders to get started."
            self._ready = False
            self._busy = False
            self.started = 0.0
            self.checking = False
            try:
                self.choices = read_choices(state / "folders.json")
            except (OSError, ValueError) as exc:
                self.choices = {"models_dir": "", "output_dir": "", "runtime_dir": ""}
                self._status = str(exc)
            if demo:
                output = state / "outputs"
                output.mkdir(exist_ok=True)
                self.choices["output_dir"] = str(output)
            self.modelSetup = ModelSetupBridge(ROOT / "models.manifest.json", state,
                                               lambda: self.choices["models_dir"],
                                               lambda: not self._ready and not self._busy and not demo, self)
            self.timer = QTimer(self)
            self.timer.setInterval(250)
            self.timer.timeout.connect(self.poll)
            self.healthResult.connect(self.finish_health)

        @Property(str, notify=changed)
        def endpoint(self): return self._endpoint
        @Property(str, notify=changed)
        def token(self): return self.service.token if self.service else ""
        @Property(str, notify=changed)
        def status(self): return self._status
        @Property(bool, notify=changed)
        def ready(self): return self._ready
        @Property(bool, notify=changed)
        def busy(self): return self._busy
        @Property(bool, constant=True)
        def demo(self): return demo
        @Property(str, notify=changed)
        def modelsDir(self): return self.choices["models_dir"]
        @Property(str, notify=changed)
        def runtimeDir(self): return self.choices["runtime_dir"]
        @Property(str, notify=changed)
        def outputDir(self): return self.choices["output_dir"]
        @Property(str, constant=True)
        def logFolder(self): return str(state)

        def remember_folders(self):
            try:
                write_json(state / "folders.json", self.choices)
            except OSError:
                self._status = "The folder works for this session, but the selection could not be saved. Check the application settings folder."

        @Slot(str, result=str)
        def chooseFolder(self, key):
            if key not in self.choices or self._busy or self._ready or self.modelSetup.busy:
                return ""
            path = QFileDialog.getExistingDirectory(None, "Choose a folder", self.choices[key])
            if path:
                self.choices[key] = path
                self.remember_folders()
                self.changed.emit()
            return path

        @Slot(str, str)
        def setFolder(self, key, value):
            if key in self.choices and not self._busy and not self._ready and not self.modelSetup.busy:
                self.choices[key] = value.strip()
                self.remember_folders()
                self.changed.emit()

        @Slot()
        def start(self):
            if self._busy or self._ready or self.modelSetup.busy:
                return
            try:
                configuration = service_configuration(self.choices, demo=demo)
                write_json(state / "folders.json", self.choices)
                if self.service:
                    self.service.close()
                self.service = OwnedService(state, configuration, demo)
                self._busy = True
                self._status = "Starting the image engine…"
                self.started = time.monotonic()
                self.timer.start()
            except Exception as exc:
                self._status = str(exc)
                with log_path.open("a", encoding="utf-8") as log:
                    log.write(f"Start failed: {exc}\n")
            self.changed.emit()

        def poll(self):
            if not self.service:
                return
            if self.service.exited():
                self.timer.stop()
                self._busy = self._ready = False
                self._endpoint = ""
                self._status = "The image engine stopped. Open the logs for details, then try again."
                self.service.close()
                self.service = None
                self.changed.emit()
                return
            if self._ready or self.checking:
                return
            if time.monotonic() - self.started > 45:
                self.stop()
                self._status = "The image engine did not start in time. Open the logs for details, then try again."
                self.changed.emit()
                return
            try:
                data = json.loads((state / "service.json").read_text(encoding="utf-8"))
                port = validate_handshake(data, self.service.pid)
                if os.name == "nt" and not self.service.process.assert_listener_owned(port, root_only=True):
                    return
            except (OSError, ValueError):
                return
            endpoint, token = f"http://127.0.0.1:{port}", self.service.token
            self.checking = True

            def check_health():
                try:
                    request = urllib.request.Request(endpoint + "/health", headers={"Authorization": "Bearer " + token})
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with opener.open(request, timeout=2) as response:
                        health = json.loads(response.read())
                    good = isinstance(health, dict) and "engine" in health and "ok" in health
                except (OSError, ValueError):
                    good = False
                self.healthResult.emit(good, endpoint)

            threading.Thread(target=check_health, daemon=True).start()

        @Slot(bool, str)
        def finish_health(self, good, endpoint):
            self.checking = False
            if good and self.service and not self.service.exited():
                self._endpoint = endpoint
                self._ready, self._busy = True, False
                self._status = "Demo engine — no graphics card is used." if demo else "Experimental v5 engine — review results before delivery."
                self.changed.emit()

        @Slot()
        def stop(self):
            self.timer.stop()
            self._endpoint = ""
            self._ready = self._busy = False
            if self.service:
                self.service.close()
                self.service = None
            self.changed.emit()

        @Slot()
        def openLogs(self):
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(state)))

        @Slot()
        def saveDiagnosticBundle(self):
            path, _ = QFileDialog.getSaveFileName(None, "Save diagnostic bundle", "artegra-diagnostics.zip", "ZIP archive (*.zip)")
            if not path:
                return
            try:
                from support_bundle import create_bundle
                create_bundle(state, Path(path))
                self._status = "Diagnostic bundle saved. Review it before sharing."
            except Exception:
                self._status = "The diagnostic bundle could not be saved. Choose a writable folder and try again."
            self.changed.emit()

    bridge = Bridge()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("hostBridge", bridge)
    engine.rootContext().setContextProperty("modelSetupBridge", bridge.modelSetup)
    engine.rootContext().setContextProperty("cuPrefsLocation", str(state / "preferences.ini"))
    engine.load(QUrl.fromLocalFile(str(ROOT / "ui" / "qml" / "Main.qml")))
    if not engine.rootObjects():
        bridge.stop()
        print(f"The application window could not load. Details: {log_path}", file=sys.stderr)
        return 1
    window = engine.rootObjects()[0]

    def activate():
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            client.disconnectFromServer()
            client.deleteLater()
        window.showNormal()
        window.raise_()
        window.requestActivate()

    server.newConnection.connect(activate)
    app.aboutToQuit.connect(bridge.stop)
    app.aboutToQuit.connect(bridge.modelSetup.close)
    atexit.register(bridge.stop)
    if demo or all(bridge.choices.values()):
        QTimer.singleShot(0, bridge.start)
    if args.smoke:
        deadline = time.monotonic() + 35

        def smoke_check():
            if bridge.ready and window.property("tabConnected"):
                errors = list(warnings)
                if errors:
                    print("QML warnings: " + " | ".join(errors), file=sys.stderr)
                print(json.dumps({"smoke": not errors, "tab_loaded": True, "engine_connected": True,
                                  "fast_available": bool(window.property("fastAvailable")), "gpu_used": False}))
                app.exit(1 if errors else 0)
            elif time.monotonic() > deadline:
                print(f"Smoke check failed: {bridge.status}; details: {log_path}", file=sys.stderr)
                app.exit(1)
            else:
                QTimer.singleShot(250, smoke_check)

        QTimer.singleShot(1500, smoke_check)
    try:
        return app.exec()
    finally:
        bridge.modelSetup.close()
        bridge.stop()
        server.close()
        atexit.unregister(bridge.stop)
        qInstallMessageHandler(None)
        if temporary:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

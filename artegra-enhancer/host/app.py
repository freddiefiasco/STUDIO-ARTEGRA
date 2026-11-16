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

from host.config import (APP_ID, APP_NAME, DISPLAY_NAME, ORGANIZATION, VERSION, read_choices, service_configuration,
                         validate_handshake, write_json)

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def startup_health(health):
    """A live HTTP service is not necessarily ready to accept images."""
    if not isinstance(health, dict) or not isinstance(health.get("engine"), dict):
        return "checking", "Opening Artegra Enhancer…"
    if health["engine"].get("ready") is True:
        # Historical job/recovery warnings can make top-level ok false while the
        # engine is usable; those belong in the workspace, not a startup loop.
        return "ready", "Ready to enhance your images."
    if health.get("checking") is True:
        return "checking", "Checking your graphics card and image tools…"
    problems = health.get("problems")
    if isinstance(problems, list) and problems and isinstance(problems[0], str):
        return "blocked", problems[0]
    return "checking", "Preparing your image workspace…"


def service_command():
    """Launch the service with the app's interpreter and explicit text settings."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--service"]
    python = Path(getattr(sys, "_base_executable", sys.executable))
    if python.name.lower() == "pythonw.exe":
        console = python.with_name("python.exe")
        if console.is_file():
            python = console
    # The owned Windows Job hides the console. cu_service.py adds only the
    # application root and explicitly selected site-packages to the import path.
    return [str(python), "-I", "-X", "utf8", "-S", "-B", "-u", str(ROOT / "cu_service.py")]


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
        args = service_command() + ["--state", str(state), "--config", str(state / "config.json"),
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


RELEASES_PAGE = "https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/tag/artegra-enhancer-v" + VERSION
SOURCE_PAGE = "https://github.com/freddiefiasco/STUDIO-ARTEGRA/tree/main/artegra-enhancer"
OPENABLE = ("https://github.com/freddiefiasco/STUDIO-ARTEGRA/",)


def installed_uninstaller():
    """The registered uninstaller of this installed copy, or "" (portable zip, source runs, another copy)."""
    if os.name != "nt":
        return ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" + APP_ID + "_is1") as key:
            command = str(winreg.QueryValueEx(key, "UninstallString")[0])
    except OSError:
        return ""
    target = Path(command.strip().strip('"'))
    if not target.name.lower().startswith("unins") or target.suffix.lower() != ".exe" or not target.is_file():
        return ""
    if os.path.normcase(str(target.parent.resolve())) != os.path.normcase(str(ROOT.resolve())):
        return ""
    return str(target)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--service":
        from service.app import main as service_main
        return service_main(argv[1:])
    if argv and argv[0] == "--quit-running":
        from host.run_record import main as quit_main
        return quit_main(argv[1:])
    if argv and argv[0] == "--uninstall-cleanup":
        from host.uninstall_cleanup import main as cleanup_main
        return cleanup_main(argv[1:])
    parser = argparse.ArgumentParser(description=DISPLAY_NAME)
    parser.add_argument("--demo", action="store_true", help="Use a separate fake-engine workspace; never use a GPU")
    parser.add_argument("--smoke", action="store_true", help="Offscreen fake-engine load check, then exit")
    parser.add_argument("--software-rendering", action="store_true", help="Draw the interface with the CPU; image processing still uses the NVIDIA GPU")
    parser.add_argument("--state", type=Path, help="Use an isolated application state folder")
    parser.add_argument("--update-fixture", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.update_fixture and not (args.smoke or args.demo):
        parser.error("--update-fixture is only for demo and smoke runs")
    if not (args.smoke or args.demo):
        from runtime.compatibility import require_supported_platform
        try:
            require_supported_platform()
        except ValueError as exc:
            if os.name == "nt":
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, str(exc), APP_NAME, 0x10)
            print(str(exc), file=sys.stderr)
            return 1
    if args.software_rendering:
        os.environ["QT_QUICK_BACKEND"] = "software"
        os.environ["QSG_RENDER_LOOP"] = "basic"
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
    from host.installation_qt import InstallationBridge

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

    class UpdateBridge(QObject):
        """Check for updates, only when the person asks (host/updates.py). One check at a time."""
        changed = Signal()
        finished = Signal(object)

        def __init__(self, fixture=None):
            super().__init__()
            self._state, self._message, self._latest, self._url = "idle", "", "", ""
            self.fixture = fixture
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
            self._state, self._message = "checking", "Checking for updates\u2026"
            self.changed.emit()
            fixture = self.fixture

            def work():
                from host import updates
                answer = None
                if fixture is not None:
                    try:
                        answer = Path(fixture).read_bytes()
                    except OSError:
                        answer = b"not json"
                self.finished.emit(updates.check(answer=answer))

            threading.Thread(target=work, daemon=True).start()

        @Slot(object)
        def apply(self, result):
            self._state = result.get("state", "failed")
            self._message = result.get("message", "")
            self._latest = result.get("latest", "")
            self._url = result.get("url", "") if self._state == "available" else ""
            self.changed.emit()

        @Slot()
        def openDownload(self):
            from PySide6.QtGui import QDesktopServices
            if self._url.startswith(OPENABLE):
                QDesktopServices.openUrl(QUrl(self._url))

    class Bridge(QObject):
        changed = Signal()
        healthResult = Signal(object, str, int)

        def __init__(self):
            super().__init__()
            self.service = None
            self._endpoint = ""
            self._status = "Welcome to Artegra Enhancer (Beta)."
            self._ready = False
            self._busy = False
            self.started = 0.0
            self.checking = False
            self.generation = 0
            try:
                self.choices = read_choices(state / "folders.json")
            except (OSError, ValueError) as exc:
                self.choices = {"models_dir": "", "output_dir": "", "runtime_dir": ""}
                self._status = str(exc)
            if demo:
                output = state / "outputs"
                output.mkdir(exist_ok=True)
                self.choices["output_dir"] = str(output)
            self.uninstaller = "" if demo else installed_uninstaller()
            self.installation = InstallationBridge(ROOT, state, self, enabled=not demo)
            if not demo and self.installation.choices:
                self.choices = self.installation.choices
            self.installation.completed.connect(self.setup_finished)
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
        @Property(str, constant=True)
        def displayName(self): return DISPLAY_NAME
        @Property(str, constant=True)
        def version(self): return VERSION
        @Property(str, constant=True)
        def versionText(self):
            from host.updates import display_version
            return display_version(VERSION)
        @Property(bool, notify=changed)
        def uninstallAvailable(self): return bool(self.uninstaller)

        @Slot(str)
        def openPage(self, which):
            from PySide6.QtGui import QDesktopServices
            url = {"release": RELEASES_PAGE, "source": SOURCE_PAGE}.get(which)
            if url:
                QDesktopServices.openUrl(QUrl(url))
            elif which == "licences":
                folder = ROOT / "licenses"
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder if folder.is_dir() else ROOT)))

        @Slot(result=bool)
        def startUninstall(self):
            """Start this copy's registered uninstaller (it asks the person itself); the window then closes."""
            target = installed_uninstaller()
            if not target or demo:
                self._status = "Uninstall works in an installed copy. Use Installed apps in Windows Settings."
                self.changed.emit()
                return False
            try:
                flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                # The person confirmed in the app, so the uninstaller asks only for the options (installer/ArtegraEnhancer.iss).
                subprocess.Popen([target, "/SILENT", "/ASKOPTIONS=1"], cwd=str(Path(target).parent), close_fds=True,
                                 creationflags=flags)
            except OSError:
                self._status = "The uninstaller could not start. Use Installed apps in Windows Settings to remove the app."
                self.changed.emit()
                return False
            return True

        def remember_folders(self):
            try:
                write_json(state / "folders.json", self.choices)
            except OSError:
                self._status = "The folder works for this session, but the selection could not be saved. Check the application settings folder."

        @Slot(str)
        def rememberOutput(self, value):
            if value and self._ready and Path(value).is_dir():
                self.choices["output_dir"] = value
                self.remember_folders()
                self.changed.emit()

        @Slot(object)
        def setup_finished(self, choices):
            self.choices = dict(choices)
            self.start()

        @Slot()
        def repair(self):
            if demo or self.installation.busy or self._busy:
                return
            self.stop()
            self.installation.start()

        @Slot()
        def start(self):
            if self._busy or self._ready or self.installation.busy:
                return
            try:
                configuration = service_configuration(self.choices, demo=demo)
                write_json(state / "folders.json", self.choices)
                if self.service:
                    self.service.close()
                self.service = OwnedService(state, configuration, demo)
                self.generation += 1
                self.checking = False
                self._busy = True
                self._status = "Opening your image workspace…"
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
                # Invalidate any in-flight health probe before Retry can replace
                # this service; its late result must not strand the next startup.
                self.stop()
                self._status = "Artegra Enhancer stopped unexpectedly. Choose Try again to reopen your workspace."
                self.changed.emit()
                return
            if self._ready or self.checking:
                return
            if time.monotonic() - self.started > 180:
                self.stop()
                self._status = "Opening the workspace took too long. Try again, or choose Repair installation."
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
            generation = self.generation
            self.checking = True

            def check_health():
                try:
                    request = urllib.request.Request(endpoint + "/health", headers={"Authorization": "Bearer " + token})
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with opener.open(request, timeout=5) as response:
                        health = json.loads(response.read())
                except (OSError, ValueError):
                    health = None
                self.healthResult.emit(health, endpoint, generation)

            threading.Thread(target=check_health, daemon=True).start()

        @Slot(object, str, int)
        def finish_health(self, health, endpoint, generation):
            if generation != self.generation:
                return
            self.checking = False
            result, message = startup_health(health)
            if result == "ready" and self.service and not self.service.exited():
                self._endpoint = endpoint
                self._ready, self._busy = True, False
                self._status = "Demo — no graphics card is used." if demo else message
                self.changed.emit()
            elif result == "blocked":
                self.stop()
                self._status = message
                self.changed.emit()
            elif self._busy and self._status != message:
                self._status = message
                self.changed.emit()

        @Slot()
        def stop(self):
            self.timer.stop()
            self.generation += 1
            self.checking = False
            self._endpoint = ""
            self._ready = self._busy = False
            if self.service:
                self.service.close()
                self.service = None
            self.changed.emit()

        @Slot()
        def openSetupGuide(self):
            from PySide6.QtGui import QDesktopServices
            guide = ROOT / "INSTALL.md"
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide))):
                self._status = "Open INSTALL.md in the application folder for setup instructions."
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
    updater = UpdateBridge(args.update_fixture)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("hostBridge", bridge)
    engine.rootContext().setContextProperty("updateBridge", updater)
    engine.rootContext().setContextProperty("installationBridge", bridge.installation)
    engine.rootContext().setContextProperty("cuPrefsLocation", str(state / "preferences.ini"))
    engine.load(QUrl.fromLocalFile(str(ROOT / "ui" / "qml" / "Main.qml")))
    if not engine.rootObjects():
        bridge.stop()
        print(f"The application window could not load. Details: {log_path}", file=sys.stderr)
        return 1
    window = engine.rootObjects()[0]
    from host import run_record
    try:
        run_record.write(state, ROOT, os.environ.get("ENHANCER_LAUNCHER_PID"))
    except OSError:
        pass

    def activate():
        quit_asked = False
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            if client.bytesAvailable() or client.waitForReadyRead(300):
                quit_asked = quit_asked or bytes(client.readAll()).strip() == run_record.QUIT_MESSAGE
            client.disconnectFromServer()
            client.deleteLater()
        if quit_asked:
            # The uninstaller asked: stop and close. The engine ends with the window; unfinished images resume later.
            from PySide6.QtCore import QMetaObject
            QTimer.singleShot(0, lambda: QMetaObject.invokeMethod(window, "quitForUninstall"))
            return
        window.showNormal()
        window.raise_()
        window.requestActivate()

    server.newConnection.connect(activate)
    app.aboutToQuit.connect(bridge.stop)
    app.aboutToQuit.connect(bridge.installation.close)
    atexit.register(bridge.stop)
    if demo or bridge.installation.complete:
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
        bridge.installation.close()
        bridge.stop()
        server.close()
        atexit.unregister(bridge.stop)
        try:
            run_record.remove(state)
        except Exception:
            pass
        qInstallMessageHandler(None)
        if temporary:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

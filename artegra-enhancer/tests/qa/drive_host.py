"""Drive the real host window (demo engine, offscreen) through one scenario and print its findings as JSON.

Used by tests/test_host_states.py, each scenario in its own process: python -B tests/qa/drive_host.py <scenario> <state>.
The window, the tab and the service are the real ones; only the engine is the fake one and nothing is on screen.
Keys are sent to the window as key events, so they go through the same shortcut map as a person's key presses.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SCENARIO, STATE = sys.argv[1], Path(sys.argv[2])
STATE.mkdir(parents=True, exist_ok=True)

from PySide6 import QtQml, QtWidgets                      # noqa: E402
from PySide6.QtCore import QObject, Qt, QTimer            # noqa: E402
from PySide6.QtQml import QQmlExpression                  # noqa: E402
from PySide6.QtTest import QTest                          # noqa: E402

from host import app as host                              # noqa: E402

engines = []
found = {}


class CapturedEngine(QtQml.QQmlApplicationEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        engines.append(self)


def window():
    return engines[0].rootObjects()[0]


def js(code):
    expr = QQmlExpression(QtQml.QQmlEngine.contextForObject(window()), window(), code)
    value = expr.evaluate()
    if isinstance(value, tuple):               # PySide6 returns (value, value is undefined)
        value = None if value[1] else value[0]
    if expr.hasError():
        raise RuntimeError(f"{code[:70]}: {expr.error().toString()}")
    return value


def child(name):
    return window().findChild(QObject, name)


def bridge():
    return engines[0].rootContext().contextProperty("hostBridge")


def key(k, mod=Qt.NoModifier):
    QTest.keyClick(window(), k, mod)


def picture(name):
    """A small synthetic picture (no private images)."""
    from PIL import Image
    path = STATE / name
    img = Image.new("RGB", (320, 240))
    img.putdata([((x * 7) % 256, (y * 5) % 256, ((x // 16 + y // 16) % 2) * 160 + 40) for y in range(240) for x in range(320)])
    img.save(path)
    return str(path).replace("\\", "/")


def setup_text():
    out = {}
    for name in ("setupHeading", "setupLead", "setupWelcome", "setupSteps", "installationProgress", "setupCloseNote",
                 "retryWorkspace", "installationStatus"):
        item = child(name)
        if item is None:
            out[name] = None
            continue
        out[name] = {"visible": bool(item.property("visible")),
                     "text": item.property("text") if item.property("text") is not None else ""}
    return out


def _effectively_visible(item):
    # An item's visible property reads false when any of its parents is hidden.
    return item is not None and bool(item.property("visible"))


def connected():
    return bool(js("window.tabConnected"))


# ---------------------------------------------------------------------------------------------------------- scenarios
def modal_pages():
    """With Settings, About or setup up, no key reaches the workspace; with them gone, keys work again."""
    yield ("wait", connected, 60)
    js("window.minimumWidth = 0; window.minimumHeight = 0; window.width = 1280; window.height = 800")
    window().requestActivate()
    yield ("sleep", 0.5)
    js(f"window.tabItem.setMode('standard'); window.tabItem.addPaths({json.dumps([picture('facade.png'), picture('court.png')])})")
    yield ("wait", lambda: js("window.tabItem.selectedRow !== null && window.tabItem.selectedRow.kind === 'input'"), 20)
    yield ("sleep", 0.5)

    def snapshot():
        return {"batch_active": bool(js("window.tabItem.batch.active")),
                "inputs": int(js("window.tabItem.inputs ? window.tabItem.inputs.length : -1")),
                "mask": bool(js("window.tabItem.maskVisible")),
                "panels": bool(js("window.panelsShown")),
                "activity": bool(js("window.tabItem.activityOpen")),
                "shortcuts": bool(js("window.tabItem.shortcutsOpen === true")),
                "results": bool(js("window.tabItem.resultsOpen === true")),
                "zoom": float(js("window.tabItem.viewerItem.zoom")),
                "split": str(js("window.tabItem.viewerItem.viewMode !== undefined ? window.tabItem.viewerItem.viewMode : ''"))}

    keys = [(Qt.Key_Return, Qt.ControlModifier), (Qt.Key_Enter, Qt.ControlModifier), (Qt.Key_Delete, Qt.NoModifier),
            (Qt.Key_B, Qt.NoModifier), (Qt.Key_M, Qt.NoModifier), (Qt.Key_0, Qt.NoModifier), (Qt.Key_1, Qt.NoModifier),
            (Qt.Key_F6, Qt.NoModifier), (Qt.Key_Question, Qt.ShiftModifier), (Qt.Key_Period, Qt.ControlModifier)]
    for page in ("settingsShown", "aboutShown"):
        before = snapshot()
        js(f"window.{page} = true")
        yield ("sleep", 0.4)
        found[page + "_workspace_visible"] = bool(child("creativeUpscalerView").property("visible"))
        found[page + "_keys_active"] = bool(js("window.tabItem.keysActive"))
        for k, mod in keys:
            key(k, mod)
            yield ("sleep", 0.05)
        for _ in range(12):
            key(Qt.Key_Tab)
            inside = bool(js("(function() { for (var p = window.activeFocusItem; p; p = p.parent)"
                             " if (p.objectName === 'creativeUpscalerView') return true; return false })()"))
            found.setdefault(page + "_tab_entered_workspace", False)
            found[page + "_tab_entered_workspace"] = found[page + "_tab_entered_workspace"] or inside
            yield ("sleep", 0.02)
        yield ("sleep", 1.5)
        after = snapshot()
        found[page + "_changed"] = {k: [before[k], after[k]] for k in before if before[k] != after[k]}
        key(Qt.Key_Escape)
        yield ("sleep", 0.4)
        found[page + "_closed_by_escape"] = not bool(js(f"window.{page}"))
        js("window.settingsShown = false; window.aboutShown = false")
        yield ("sleep", 0.6)
    # The uninstall question opened from Settings still takes Esc while the workspace is hidden.
    js("window.settingsShown = true")
    yield ("sleep", 0.3)
    js("window.tabItem.confirmDialog.ask('Question', 'Body', 'Go', 'Keep', function() {}, 'danger')")
    yield ("sleep", 0.5)
    found["dialog_opened_over_settings"] = bool(js("window.tabItem.confirmDialog.opened"))
    key(Qt.Key_Escape)
    yield ("sleep", 0.5)
    found["dialog_closed_by_escape"] = not bool(js("window.tabItem.confirmDialog.opened"))
    found["settings_still_open_after_dialog"] = bool(js("window.settingsShown"))
    js("window.settingsShown = false")
    yield ("sleep", 0.6)
    # Not vacuous: with the pages closed the same key starts the batch.
    found["focus_back_in_workspace"] = bool(js("window.tabItem.focusInside()"))
    key(Qt.Key_Return, Qt.ControlModifier)
    yield ("wait", lambda: js("window.tabItem.batch.active"), 15)
    found["ctrl_enter_starts_after_close"] = bool(js("window.tabItem.batch.active"))
    js("window.tabItem.cancelBatch()")
    yield ("wait", lambda: not js("window.tabItem.batch.active"), 30)


def opening_and_engine_stopped():
    """Launch shows an opening state (not setup); an engine crash shows an engine state (not '1 Install')."""
    seen = set()

    def watch():
        s = setup_text()
        if s["setupHeading"] and s["setupHeading"]["visible"] and _effectively_visible(child("setupHeading")):
            seen.add(json.dumps({k: (v["visible"] if v else None) for k, v in s.items()} | {"heading": s["setupHeading"]["text"]},
                                sort_keys=True))
        return connected()

    yield ("wait", watch, 60)
    found["opening_states"] = sorted(json.loads(x) for x in seen)
    js("window.minimumWidth = 0; window.minimumHeight = 0; window.width = 1280; window.height = 800")
    js(f"window.tabItem.setMode('standard'); window.tabItem.addPaths({json.dumps([picture('facade.png')])})")
    yield ("wait", lambda: js("window.tabItem.selectedRow !== null && window.tabItem.selectedRow.kind === 'input'"), 20)
    js("window.tabItem.startUpscale()")
    yield ("wait", lambda: js("window.tabItem.batch.active && window.tabItem.batch.working.length > 0"), 30)
    yield ("sleep", 1.0)
    # A second picture waits, selected, so Delete and Ctrl+Enter would have something to act on.
    js(f"window.tabItem.addPaths({json.dumps([picture('court.png')])})")
    yield ("wait", lambda: js("window.tabItem.inputs.length === 1"), 20)
    js("for (var k in window.tabItem.rowsByKey) if (window.tabItem.rowsByKey[k].kind === 'input') window.tabItem.selectKey(k)")
    yield ("sleep", 0.5)

    def snapshot():
        return {"inputs": int(js("window.tabItem.inputs.length")), "mask": bool(js("window.tabItem.maskVisible")),
                "zoom": float(js("window.tabItem.viewerItem.zoom")), "panels": bool(js("window.panelsShown"))}

    before = snapshot()
    # End the app's own engine process, as a crash would.
    pid = json.loads((STATE / "demo" / "service.json").read_text(encoding="utf-8"))["pid"]
    os.kill(pid, 9)
    yield ("wait", lambda: child("retryWorkspace") is not None and child("retryWorkspace").property("visible"), 15)
    yield ("sleep", 0.4)
    # Keys behind the setup page change nothing, and Tab stays out of the hidden workspace.
    window().requestActivate()
    for k, mod in ((Qt.Key_Return, Qt.ControlModifier), (Qt.Key_Delete, Qt.NoModifier), (Qt.Key_M, Qt.NoModifier),
                   (Qt.Key_0, Qt.NoModifier), (Qt.Key_1, Qt.NoModifier), (Qt.Key_B, Qt.NoModifier)):
        key(k, mod)
        yield ("sleep", 0.05)
    entered = False
    for _ in range(12):
        key(Qt.Key_Tab)
        entered = entered or bool(js("(function() { for (var p = window.activeFocusItem; p; p = p.parent)"
                                     " if (p.objectName === 'creativeUpscalerView') return true; return false })()"))
        yield ("sleep", 0.02)
    yield ("sleep", 1.0)
    after = snapshot()
    found["behind_setup_changed"] = {k: [before[k], after[k]] for k in before if before[k] != after[k]}
    found["behind_setup_tab_entered_workspace"] = entered
    found["after_crash"] = setup_text()
    found["after_crash_workspace_visible"] = bool(child("creativeUpscalerView").property("visible"))
    found["status"] = str(bridge().status)
    bridge().start()
    yield ("wait", connected, 60)
    yield ("wait", lambda: js("window.tabItem.batch.last !== null && window.tabItem.batch.last !== undefined"
                              " && !window.tabItem.batch.active && window.tabItem.batch.last.done > 0"), 120)
    found["resumed_and_finished"] = bool(js("window.tabItem.batch.last.done > 0"))


def out_of_memory():
    """An out-of-memory failure offers Save GPU memory, asks first, then runs the image again with it."""
    yield ("wait", connected, 60)
    js("window.minimumWidth = 0; window.minimumHeight = 0; window.width = 1280; window.height = 800")
    yield ("wait", lambda: js("window.tabItem.settingsLoaded"), 20)
    found["profile_before"] = str(js("window.tabItem.memoryProfile"))
    js(f"window.tabItem.setMode('standard'); window.tabItem.addPaths({json.dumps([picture('facade.png')])})")
    yield ("wait", lambda: js("window.tabItem.selectedRow !== null && window.tabItem.selectedRow.kind === 'input'"), 20)
    js("window.tabItem.startUpscale()")
    yield ("wait", lambda: js("window.tabItem.batch.active"), 30)
    yield ("wait", lambda: not js("window.tabItem.batch.active"), 120)
    yield ("sleep", 1.0)
    found["failed_text"] = str(js("window.tabItem.selectedRow ? window.tabItem.selectedRow.errorText : ''"))
    retry = child("viewerRetry")
    found["retry_label"] = retry.property("text") if retry is not None else None
    found["retry_visible"] = bool(retry is not None and retry.property("visible"))
    js("window.tabItem.retryWithLessMemory(window.tabItem.selectedRow)")
    yield ("sleep", 0.6)
    found["asked"] = bool(js("window.tabItem.confirmDialog.opened"))
    found["question"] = str(js("window.tabItem.confirmDialog.title"))
    found["profile_while_asking"] = str(js("window.tabItem.memoryProfile"))
    js("window.tabItem.confirmDialog.chosen('go')")
    yield ("wait", lambda: js("window.tabItem.memoryProfile === 'balanced'"), 15)
    found["profile_after"] = str(js("window.tabItem.memoryProfile"))
    yield ("wait", lambda: js("window.tabItem.batch.active"), 30)
    yield ("wait", lambda: not js("window.tabItem.batch.active"), 120)
    found["second_run_done"] = int(js("window.tabItem.batch.last ? window.tabItem.batch.last.done : -1"))


def close_prompt():
    """The close prompt goes away when the batch it asks about ends."""
    yield ("wait", connected, 60)
    js(f"window.tabItem.setMode('standard'); window.tabItem.addPaths({json.dumps([picture('facade.png')])})")
    yield ("wait", lambda: js("window.tabItem.selectedRow !== null && window.tabItem.selectedRow.kind === 'input'"), 20)
    js("window.tabItem.startUpscale()")
    yield ("wait", lambda: js("window.tabItem.batch.active"), 30)
    found["held"] = bool(js("window.tabItem.holdAppClose(function() {})"))
    yield ("sleep", 0.5)
    found["prompt_open"] = bool(js("window.tabItem.closePromptOpen"))
    yield ("wait", lambda: not js("window.tabItem.batch.active"), 120)
    yield ("sleep", 0.8)
    found["prompt_open_after_end"] = bool(js("window.tabItem.closePromptOpen"))
    found["window_still_open"] = bool(js("window.visible"))


def shortcuts_sheet():
    """The Shortcuts sheet lists only keys this window has."""
    yield ("wait", connected, 60)
    js("window.tabItem.shortcuts.openAt('shortcuts')")
    yield ("sleep", 0.5)
    found["keys"] = json.loads(js("JSON.stringify(window.tabItem.shortcuts.shownKeys.map(function(k) { return k.keys + ': ' + k.d }))"))


def preferences():
    """The tab's remembered choices are kept in this state folder's preferences.ini, not shared with other copies."""
    yield ("wait", connected, 60)
    yield ("wait", lambda: js("window.tabItem.settingsLoaded"), 20)
    found["scale_at_start"] = int(js("window.tabItem.scale"))
    js("window.tabItem.setScale(4)")
    yield ("sleep", 1.0)
    ini = STATE / "demo" / "preferences.ini"
    found["ini_exists"] = ini.is_file()
    found["ini_has_scale"] = ini.is_file() and '\\"scale\\":4' in ini.read_text(encoding="utf-8", errors="replace")


def seeded_preferences():
    """A preferences.ini written by the one-time move from the registry is read by the tab: it opens at 4x."""
    yield ("wait", connected, 60)
    yield ("wait", lambda: js("window.tabItem.settingsLoaded"), 20)
    yield ("sleep", 0.5)
    found["scale"] = int(js("window.tabItem.scale"))
    found["protect"] = json.loads(js("JSON.stringify(window.tabItem.protect)"))


def reduced_motion():
    """With Windows' Animation effects off, the tab's motion takes its reduced path."""
    yield ("wait", connected, 60)
    found["bridge"] = bool(js("hostBridge.reduceMotion"))
    found["tokens"] = bool(js("Tokens.reduceMotion"))


SCENARIOS = {"modal": modal_pages, "states": opening_and_engine_stopped, "oom": out_of_memory, "close": close_prompt,
             "sheet": shortcuts_sheet, "motion": reduced_motion, "prefs": preferences, "prefs_seeded": seeded_preferences}


def run(gen):
    state = {"until": 0.0, "pred": None, "deadline": 0.0}

    def tick():
        try:
            now = time.monotonic()
            if now < state["until"]:
                QTimer.singleShot(30, tick)
                return
            if state["pred"] is not None:
                if not state["pred"]():
                    if now > state["deadline"]:
                        raise TimeoutError("timed out waiting")
                    QTimer.singleShot(50, tick)
                    return
                state["pred"] = None
            step = next(gen)
            if step[0] == "sleep":
                state["until"] = now + step[1]
            elif step[0] == "wait":
                state["pred"], state["deadline"] = step[1], now + step[2]
            QTimer.singleShot(10, tick)
        except StopIteration:
            print("FOUND " + json.dumps(found, default=str), flush=True)
            QtWidgets.QApplication.instance().exit(0)
        except Exception as exc:                                  # report, then let the host close normally
            import traceback
            traceback.print_exc()
            print("FOUND " + json.dumps(found, default=str), flush=True)
            print("FAILED " + repr(exc), flush=True)
            QtWidgets.QApplication.instance().exit(2)

    QTimer.singleShot(200, tick)


class DrivenApplication(QtWidgets.QApplication):
    def exec(self):
        run(SCENARIOS[SCENARIO]())
        return super().exec()


if SCENARIO == "prefs_seeded":
    # Write the state's preferences.ini exactly as the one-time move from the registry does, from a stand-in source.
    from PySide6.QtCore import QSettings
    from host.app import migrate_tab_preferences
    source = QSettings(str(STATE / "registry-stand-in.ini"), QSettings.Format.IniFormat)
    source.setValue("CreativeUpscalerTab/settings", json.dumps({"preset": "Default", "custom": False, "creativity": 50,
                    "resemblance": 60, "restoration": 35, "scale": 4, "protect": ["people", "vehicles"], "quickProtect": "",
                    "outputFormat": "png8"}, separators=(",", ":")))
    source.setValue("CreativeUpscalerTab/schema", "1")
    source.sync()
    (STATE / "demo").mkdir(parents=True, exist_ok=True)
    assert migrate_tab_preferences(STATE / "demo" / "preferences.ini", source) == 2
if SCENARIO == "motion":
    host.windows_reduces_motion = lambda: True          # as Windows reports with Animation effects turned off
QtQml.QQmlApplicationEngine = CapturedEngine
QtWidgets.QApplication = DrivenApplication
code = host.main(["--demo", "--state", str(STATE)])
print("EXIT", code, flush=True)
raise SystemExit(code)

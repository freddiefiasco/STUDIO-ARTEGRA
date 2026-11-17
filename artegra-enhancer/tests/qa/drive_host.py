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
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QTimer  # noqa: E402
from PySide6.QtQml import QQmlExpression                  # noqa: E402
from PySide6.QtQuick import QQuickItem                    # noqa: E402
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


def _items_under(root):
    """Every item of the visual tree under root. Delegates of lists and repeaters, and the contents of popups (in the
    window's overlay), are found this way; they are not QObject children of the window."""
    stack = list(root.childItems()) if root is not None else []
    while stack:
        item = stack.pop(0)
        stack.extend(item.childItems())
        yield item


def shown(name):
    """The first item of this name that is on screen (effectively visible, with a size), or None."""
    for item in _items_under(window().contentItem()):
        if item.objectName() == name and item.isVisible() and item.width() > 0 and item.height() > 0:
            return item
    return None


def named(name):
    """The first item of this name, on screen or not, or None."""
    return next((item for item in _items_under(window().contentItem()) if item.objectName() == name), None)


def click(item, fx=0.5, fy=0.5):
    """A real left click on the window at a point of the item (a person's click: press and release events)."""
    point = item.mapToScene(QPointF(item.width() * fx, item.height() * fy))
    QTest.mouseClick(window(), Qt.LeftButton, Qt.NoModifier, QPoint(int(point.x()), int(point.y())))


def list_row(wanted):
    """The body of a row of the image list (not the pinned working row) whose (kind, status) passes `wanted`, or None.
    List rows are delegates, found through the visual tree (they are not QObject children of the window)."""
    for item in _items_under(shown("queueList")):
        if item.objectName() != "rowBody" or not (item.isVisible() and item.width() > 0 and item.height() > 0):
            continue
        row = item.parentItem()
        while row is not None and row.property("inList") is None:
            row = row.parentItem()
        if row is not None and row.property("inList") and wanted(row.property("kind"), row.property("status")):
            return item
    return None


FOCUS_IN_WORKSPACE = ("(function() { for (var p = window.activeFocusItem; p; p = p.parent)"
                      " if (p.objectName === 'creativeUpscalerView') return true; return false })()")
FOCUS_PATH = ("(function() { var out = []; for (var p = window.activeFocusItem; p; p = p.parent)"
              " if (p.objectName) out.push(p.objectName); return out.join('<') })()")


def focus():
    return {"path": str(js(FOCUS_PATH)), "in_workspace": bool(js(FOCUS_IN_WORKSPACE)),
            "visible": bool(js("window.activeFocusItem ? window.activeFocusItem.visible : false"))}


def controls():
    """What the keys under test could change: the settings every waiting image takes, the selection, the dialog."""
    t = "window.tabItem"
    return {"mode": str(js(t + ".mode")), "scale": int(js(t + ".scale")), "preset": str(js(t + ".preset")),
            "creativity": float(js(t + ".creativity")), "selected": str(js(t + ".selectedKey")),
            "inputs": int(js(t + ".inputs ? " + t + ".inputs.length : -1")),
            "dialog": str(js(t + ".confirmDialog.opened ? " + t + ".confirmDialog.title : ''"))}


# Keys a person might press on a page, which act on a focused Mode, Scale or Look control or on the image list.
PAGE_KEYS = [Qt.Key_Right, Qt.Key_End, Qt.Key_Down, Qt.Key_Space, Qt.Key_Return, Qt.Key_Delete]


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


def clicked_control_behind_pages():
    """AUD-02 with the mouse, as a person works: a click on Mode, Scale, Look or a row of the image list gives that control
    the keyboard; a click on the header's Settings or About button does not move it. Keys pressed on the page must not
    reach the control behind it, and the uninstall question over Settings hands the keys back to Settings."""
    yield ("wait", connected, 60)
    js("window.minimumWidth = 0; window.minimumHeight = 0; window.width = 1280; window.height = 800")
    window().requestActivate()
    yield ("sleep", 0.5)
    js(f"window.tabItem.setMode('standard'); window.tabItem.addPaths({json.dumps([picture('facade.png'), picture('court.png'), picture('lane.png')])})")
    yield ("wait", lambda: js("window.tabItem.inputs.length === 3 && window.tabItem.selectedRow !== null"), 20)
    yield ("sleep", 0.6)
    # The white Upscale block at rest, to compare with the first frame after a page closes.
    white = shown("primaryAction")
    spot = white.mapToScene(QPointF(white.width() * 0.08, white.height() * 0.5))
    spot = (int(spot.x()), int(spot.y()))
    found["white_at_rest"] = window().grabWindow().pixelColor(*spot).name()
    cases = []
    for target, fx in (("modeControl", 0.25), ("scaleControl", 0.1), ("presetControl", 0.5), ("queueList", 0.3)):
        for page, button in (("settingsShown", "headerSettings"), ("aboutShown", "headerAbout")):
            js("window.tabItem.setMode('standard'); window.tabItem.setScale(2); window.tabItem.applyPreset('Default')")
            yield ("sleep", 0.4)
            click(list_row(lambda kind, status: kind == "input") if target == "queueList" else shown(target), fx)
            yield ("sleep", 0.4)
            case = {"target": target, "page": page, "focus_on_click": focus()}
            before = controls()
            click(shown(button))
            yield ("sleep", 0.5)
            case["page_shown"] = bool(js("window." + page))
            case["focus_on_page"] = focus()
            for k in PAGE_KEYS:
                key(k)
                yield ("sleep", 0.08)
            yield ("sleep", 0.8)
            case["changed"] = {k: [before[k], v] for k, v in controls().items() if before[k] != v}
            if js("window.tabItem.confirmDialog.opened"):
                js("window.tabItem.confirmDialog.close()")
                yield ("sleep", 0.4)
            key(Qt.Key_Escape)
            case["white_first_frame"] = window().grabWindow().pixelColor(*spot).name()
            yield ("sleep", 0.5)
            case["closed_by_escape"] = not bool(js("window." + page))
            js("window.settingsShown = false; window.aboutShown = false")
            yield ("sleep", 0.6)
            case["focus_after_close"] = focus()
            cases.append(case)
    found["cases"] = cases
    # No time for a deferred hand-over: a key straight after the click on the header button.
    js("window.tabItem.setMode('standard')")
    yield ("sleep", 0.3)
    click(shown("modeControl"), 0.25)
    yield ("sleep", 0.3)
    found["at_once_focus_on_click"] = focus()
    before = controls()
    click(shown("headerSettings"))
    key(Qt.Key_Right)
    key(Qt.Key_End)
    yield ("sleep", 0.6)
    found["at_once_changed"] = {k: [before[k], v] for k, v in controls().items() if before[k] != v}
    # Focus moved into the hidden workspace by code (as a sheet or a question handing focus back would) goes to the page,
    # and keys sent at once change nothing.
    hidden_mode = named("modeControl")
    hidden_mode.forceActiveFocus()
    found["forced_focus"] = focus()
    key(Qt.Key_Right)
    key(Qt.Key_End)
    key(Qt.Key_Delete)
    yield ("sleep", 0.6)
    found["forced_changed"] = {k: [before[k], v] for k, v in controls().items() if before[k] != v}
    js("window.settingsShown = false")
    yield ("sleep", 0.6)
    # The uninstall question, asked over Settings as its button asks it: Esc hands the keys back to the Settings page
    # (on screen), not to the hidden workspace; the question also answers to the mouse.
    click(shown("headerSettings"))
    yield ("sleep", 0.5)
    js("window.askUninstall()")
    yield ("sleep", 0.6)
    found["question_open"] = bool(js("window.tabItem.confirmDialog.opened"))
    found["question_enabled"] = bool(js("window.tabItem.confirmDialog.enabled"))
    found["focus_in_question"] = focus()
    walk = []
    for _ in range(4):
        key(Qt.Key_Tab)
        yield ("sleep", 0.05)
        walk.append(focus()["path"].split("<")[0])
    found["question_tab_walk"] = walk
    key(Qt.Key_Escape)
    yield ("sleep", 0.6)
    found["question_closed_by_escape"] = not bool(js("window.tabItem.confirmDialog.opened"))
    found["settings_after_question"] = bool(js("window.settingsShown"))
    found["focus_after_question"] = focus()
    js("window.askUninstall()")
    yield ("sleep", 0.6)
    keep = shown("confirmKeep")
    found["keep_found"] = keep is not None
    if keep is not None:
        click(keep)
    yield ("sleep", 0.6)
    found["question_closed_by_click"] = not bool(js("window.tabItem.confirmDialog.opened"))
    found["focus_after_click"] = focus()
    key(Qt.Key_Escape)
    yield ("sleep", 0.5)
    found["settings_closed"] = not bool(js("window.settingsShown"))
    yield ("sleep", 0.3)
    found["focus_after_settings"] = focus()


def clicked_control_behind_setup():
    """AUD-02 behind the engine-stopped page: the person had clicked Mode, or a waiting row of the image list, when the
    app's own engine stopped. Keys pressed on that page must not reach the control. Try again (a click) carries on."""
    yield ("wait", connected, 60)
    js("window.minimumWidth = 0; window.minimumHeight = 0; window.width = 1280; window.height = 800")
    window().requestActivate()
    yield ("sleep", 0.5)
    js(f"window.tabItem.setMode('standard'); window.tabItem.addPaths({json.dumps([picture('facade.png'), picture('court.png'), picture('lane.png')])})")
    yield ("wait", lambda: js("window.tabItem.inputs.length === 3"), 20)
    js("window.tabItem.startUpscale()")
    yield ("wait", lambda: js("window.tabItem.batch.active && window.tabItem.batch.working.length > 0"), 30)
    yield ("sleep", 1.0)
    # Delete on its own behind Settings, with a waiting image of the batch clicked in the list (the last of three, so it
    # is still waiting while the keys are sent).
    queued = list_row(lambda kind, status: kind == "job" and status == "queued")
    found["delete_row_found"] = queued is not None
    if queued is not None:
        click(queued, 0.3)
        yield ("sleep", 0.4)
        found["delete_focus_on_click"] = focus()
        # The click gave the list the keyboard; make sure the last, unfinished image of the batch is the selected row (the
        # selection can follow the batch as an image finishes; Delete acts on any unfinished state). Selecting does not
        # move focus.
        js("(function(){ var t = window.tabItem; var active = ['queued', 'preparing', 'running', 'finishing', 'interrupted'];"
           " for (var k in t.rowsByKey) { var r = t.rowsByKey[k];"
           " if (r.kind === 'job' && r.name === 'lane.png' && active.indexOf(r.status) >= 0) { t.selectKey(k); return } } })()")
        yield ("sleep", 0.2)
        sel = "window.tabItem.selectedRow"
        found["delete_selected"] = json.loads(js(f"JSON.stringify({sel} ? {{kind: {sel}.kind, status: {sel}.status, name: {sel}.name}} : null)"))
        found["delete_focus_before"] = focus()
        before = controls()
        click(shown("headerSettings"))
        yield ("sleep", 0.5)
        found["delete_settings_shown"] = bool(js("window.settingsShown"))
        key(Qt.Key_Delete)
        yield ("sleep", 0.8)
        found["delete_changed"] = {k: [before[k], v] for k, v in controls().items() if before[k] != v}
        if js("window.tabItem.confirmDialog.opened"):
            js("window.tabItem.confirmDialog.close()")
            yield ("sleep", 0.4)
        js("window.settingsShown = false")
        yield ("sleep", 0.6)
    js(f"window.tabItem.addPaths({json.dumps([picture('yard.png')])})")
    yield ("wait", lambda: js("window.tabItem.inputs.length === 1"), 20)
    yield ("sleep", 0.6)
    cases = []
    for target, fx in (("modeControl", 0.25), ("queueList", 0.3)):
        waiting = (list_row(lambda kind, status: kind == "job" and status == "queued")
                   or list_row(lambda kind, status: kind == "input"))
        click(waiting if target == "queueList" else shown(target), fx)
        yield ("sleep", 0.4)
        case = {"target": target, "focus_on_click": focus(),
                "selected_on_click": json.loads(js("JSON.stringify(window.tabItem.selectedRow ? {kind: window.tabItem.selectedRow.kind,"
                                                   " status: window.tabItem.selectedRow.status} : null)"))}
        before = controls()
        pid = json.loads((STATE / "demo" / "service.json").read_text(encoding="utf-8"))["pid"]
        os.kill(pid, 9)                                   # the app's own engine ends, as a crash would
        yield ("wait", lambda: shown("retryWorkspace") is not None, 20)
        yield ("sleep", 0.5)
        case["focus_on_setup"] = focus()
        for k in PAGE_KEYS:
            key(k)
            yield ("sleep", 0.08)
        yield ("sleep", 0.8)
        case["changed"] = {k: [before[k], v] for k, v in controls().items() if before[k] != v}
        if js("window.tabItem.confirmDialog.opened"):
            js("window.tabItem.confirmDialog.close()")
            yield ("sleep", 0.4)
        click(shown("retryWorkspace"))
        yield ("wait", connected, 60)
        yield ("wait", lambda: js("window.workspaceShown"), 30)
        yield ("sleep", 0.8)
        case["focus_after_retry"] = focus()
        cases.append(case)
    found["cases"] = cases
    # A question the workspace asked is not left open over the stopped page (its answer would act behind it).
    sel = "window.tabItem.selectedRow"
    found["dialog_selected"] = json.loads(js(f"JSON.stringify({sel} ? {{kind: {sel}.kind, status: {sel}.status}} : null)"))
    js("window.tabItem.confirmDialog.ask('Question', 'Body', 'Go', 'Keep', function() {}, 'danger')")
    yield ("sleep", 0.6)
    found["dialog_open_before_stop"] = bool(js("window.tabItem.confirmDialog.opened"))
    pid = json.loads((STATE / "demo" / "service.json").read_text(encoding="utf-8"))["pid"]
    os.kill(pid, 9)
    yield ("wait", lambda: shown("retryWorkspace") is not None, 20)
    yield ("sleep", 0.8)
    found["dialog_open_over_setup"] = bool(js("window.tabItem.confirmDialog.opened"))
    found["focus_on_setup_after_dialog"] = focus()
    if found["dialog_open_over_setup"]:
        js("window.tabItem.confirmDialog.close()")
        yield ("sleep", 0.4)
    click(shown("retryWorkspace"))
    yield ("wait", connected, 60)
    yield ("wait", lambda: js("window.tabItem.batch.last !== null && window.tabItem.batch.last !== undefined"
                              " && !window.tabItem.batch.active"), 180)
    found["last_batch"] = json.loads(js("JSON.stringify({done: window.tabItem.batch.last.done, failed: window.tabItem.batch.last.failed,"
                                        " total: window.tabItem.batch.last.total})"))
    found["inputs_after"] = int(js("window.tabItem.inputs.length"))


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


def mode_fit():
    """A Look, fine-tuning or a factor Bolt cannot make, chosen while the form is in Bolt, puts the form in Redux and says
    so (the final v5's form fix of 17 November, synced into the Beta)."""
    yield ("wait", connected, 60)
    yield ("wait", lambda: js("window.tabItem.settingsLoaded"), 20)
    yield ("wait", lambda: js("window.tabItem.fastAvailable"), 30)
    cases = []
    for label, action in (("look", "window.tabItem.applyPreset('Strong')"), ("scale", "window.tabItem.setScale(4)"),
                          ("fine-tune", "window.tabItem.setSlider('creativity', 77)")):
        js("window.tabItem.applyPreset('Default'); window.tabItem.setScale(2); window.tabItem.setMode('fast')")
        yield ("sleep", 0.5)
        before = str(js("window.tabItem.mode"))
        js(action)
        yield ("sleep", 0.8)
        last = js("(function() { var m = window.tabItem.toasts; var t = m.count > 0 ? m.get(m.count - 1) : null;"
                  " return t ? t.title + ' | ' + t.body : '' })()")
        cases.append({"case": label, "mode_before": before, "mode_after": str(js("window.tabItem.mode")), "toast": str(last)})
    found["cases"] = cases


SCENARIOS = {"modal": modal_pages, "clicked_pages": clicked_control_behind_pages, "clicked_setup": clicked_control_behind_setup,
             "states": opening_and_engine_stopped, "oom": out_of_memory, "close": close_prompt,
             "sheet": shortcuts_sheet, "motion": reduced_motion, "prefs": preferences, "prefs_seeded": seeded_preferences,
             "mode_fit": mode_fit}


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

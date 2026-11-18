"""Make the images of the README and the guides in docs/assets: the banner, the two mode marks and the app screens.

Everything is drawn offscreen with Qt's offscreen platform, so no window opens. The screens come from the real app in
demo mode: the demo engine uses no graphics card, and the pictures it enhances are synthetic test images drawn by this
script. The output folder shown in the screens is a neutral label, so no screen shows a user name, a folder of this
computer or a client image. The banner and the marks are SVG sources (text turned into outlines) with PNG copies.

Run from the artegra-enhancer folder with the project's environment:

    python -B docs/assets/make_assets.py              # everything
    python -B docs/assets/make_assets.py graphics     # the banner and the mode marks
    python -B docs/assets/make_assets.py screens      # the app screens

--texts DIR saves the words each screen shows, for a privacy review before publishing. Every PNG is saved without
metadata and pinned in asset-hashes.json, which tools/public_scan.py requires. The screens take about three minutes.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BRAND = ROOT / "ui" / "qml" / "creative" / "assets" / "brand"
FONTS = ROOT / "ui" / "qml" / "creative" / "fonts"
ICONS = ROOT / "ui" / "qml" / "creative" / "CuIcon.qml"
PINS = ROOT / "asset-hashes.json"
SCREENS = HERE / "screens"

# The app's tokens (ui/qml/creative/Tokens.qml): monochrome, ink ground.
INK, TEXT1, TEXT3, TEXT4, GREY = "#181818", "#EDEDED", "#999999", "#6E6E6E", "#828385"
# Shown in place of the real output folder, which holds the Windows user name.
NEUTRAL_OUTPUT = "Pictures\\Artegra Enhancer"
SCALE = 2


# ---------------------------------------------------------------------------------------------------------------
# Graphics: the banner and the mode marks
# ---------------------------------------------------------------------------------------------------------------

def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    families = []
    for name in ("InstrumentSans-Regular.ttf", "InstrumentSans-Medium.ttf"):
        font_id = QFontDatabase.addApplicationFontFromData((FONTS / name).read_bytes())
        if font_id < 0:
            raise RuntimeError(f"The font {name} could not be loaded.")
        families += QFontDatabase.applicationFontFamilies(font_id)
    return app, families[0]


def svg_number(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def path_data(path, dx: float = 0.0, dy: float = 0.0) -> str:
    """SVG path data of a QPainterPath (moves, lines and cubic curves)."""
    from PySide6.QtGui import QPainterPath
    out, i, n = [], 0, path.elementCount()
    while i < n:
        e = path.elementAt(i)
        x, y = svg_number(e.x + dx), svg_number(e.y + dy)
        if e.type == QPainterPath.ElementType.MoveToElement:
            out.append(f"M{x} {y}")
        elif e.type == QPainterPath.ElementType.LineToElement:
            out.append(f"L{x} {y}")
        elif e.type == QPainterPath.ElementType.CurveToElement:
            c2, end = path.elementAt(i + 1), path.elementAt(i + 2)
            out.append(f"C{x} {y} {svg_number(c2.x + dx)} {svg_number(c2.y + dy)} {svg_number(end.x + dx)} {svg_number(end.y + dy)}")
            i += 2
        i += 1
    return "".join(out) + "Z"


def text_outline(family: str, text: str, px: float, weight: int, tracking: float = 0.0):
    """(path, advance width) of a line of text set in the bundled Instrument Sans, baseline at y = 0."""
    from PySide6.QtGui import QFont, QFontMetricsF, QPainterPath
    font = QFont(family)
    font.setPixelSize(round(px))
    font.setWeight(QFont.Weight(weight))
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    font.setKerning(True)
    if tracking:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    return path, QFontMetricsF(font).horizontalAdvance(text)


def brand_path(name: str) -> tuple[str, str]:
    """(viewBox, path data) of a brand-kit SVG with one path, as kept in the app."""
    source = (BRAND / name).read_text(encoding="utf-8")
    box = re.search(r'viewBox="([^"]+)"', source).group(1)
    return box, re.search(r'<path[^>]* d="([^"]+)"', source).group(1)


def render_svg(svg: str, width: int, height: int) -> bytes:
    """PNG bytes of an SVG drawn at width x height pixels, through Qt's SVG renderer."""
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise RuntimeError("Qt could not read the SVG it was given.")
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, width, height))
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def banner(family: str) -> str:
    """The README banner: the brandmark built from tiles that get finer from left to right, and the name."""
    w, h = 1280, 400
    unit = 88                                    # the brandmark's grid unit; the mark is 3 x 3 units
    mx, my = w - 112 - 3 * unit, (h - 3 * unit) / 2
    parts = [f'<rect width="{w}" height="{h}" fill="{INK}"/>']
    # The brandmark's three blocks (brand kit: a left leg, a top-centre keystone and a right leg on a 3 x 3 grid),
    # each cut into finer tiles: 1, then 2 x 2 per unit, then 4 x 4 per unit.
    gaps = {1: 0.0, 2: 4.0, 4: 3.0}
    tiles = []
    for col, row, cols, rows, n in ((0, 1, 1, 2, 1), (1, 0, 1, 1, 2), (2, 1, 1, 2, 4)):
        size, gap = unit / n, gaps[n]
        for i in range(cols * n):
            for j in range(rows * n):
                x0 = mx + col * unit + i * size + (gap / 2 if i else 0)
                y0 = my + row * unit + j * size + (gap / 2 if j else 0)
                x1 = mx + col * unit + (i + 1) * size - (gap / 2 if i < cols * n - 1 else 0)
                y1 = my + row * unit + (j + 1) * size - (gap / 2 if j < rows * n - 1 else 0)
                tiles.append(f"M{svg_number(x0)} {svg_number(y0)}H{svg_number(x1)}V{svg_number(y1)}H{svg_number(x0)}Z")
    parts.append(f'<path fill="{TEXT1}" d="{"".join(tiles)}"/>')
    # The name, the line under it and the studio's wordmark, as outlines (no font is needed to show the SVG).
    left = 96
    title_px = 54
    title, title_w = text_outline(family, "Artegra Enhancer (Beta)", title_px, 500, -0.9)
    while title_w > mx - left - 64 and title_px > 40:
        title_px -= 1
        title, title_w = text_outline(family, "Artegra Enhancer (Beta)", title_px, 500, -0.9)
    line, _ = text_outline(family, "Upscale architectural renders on your own computer.", 21, 400, 0.1)
    parts.append(f'<path fill="{TEXT1}" d="{path_data(title, left, 196)}"/>')
    parts.append(f'<path fill="{TEXT3}" d="{path_data(line, left, 238)}"/>')
    box, logo = brand_path("SA_LOGO-03.svg")
    lw = 150.0
    k = lw / float(box.split()[2])
    parts.append(f'<path fill="{GREY}" transform="translate({left} {svg_number(my + 3 * unit - k * float(box.split()[3]))}) '
                 f'scale({k:.6f})" d="{logo}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<title>Artegra Enhancer (Beta)</title>' + "".join(parts) + "</svg>\n")


def mode_strokes() -> dict[str, list[list[float]]]:
    """The two mode marks as the app draws them: CuIcon.qml's stroke lists on a 16-unit grid."""
    source = ICONS.read_text(encoding="utf-8")
    marks = {}
    for name in ("modeRedux", "modeBolt"):
        found = re.search(r'"%s":\s*(\[\[.*?\]\])\s*,?\s*$' % name, source, re.M)
        if not found:
            raise RuntimeError(f"CuIcon.qml has no stroke list for {name}.")
        marks[name] = json.loads(found.group(1))
    return marks


def mode_mark(strokes: list[list[float]]) -> str:
    """A mode mark on its own ink tile, so it reads the same on GitHub's light and dark pages."""
    size, pad = 32, 6.0
    k = (size - 2 * pad) / 16.0
    lines = []
    for stroke in strokes:
        points = [(pad + stroke[i] * k, pad + stroke[i + 1] * k) for i in range(0, len(stroke) - 1, 2)]
        lines.append("M" + " L".join(f"{svg_number(x)} {svg_number(y)}" for x, y in points))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<rect width="{size}" height="{size}" rx="5" fill="{INK}"/>'
            f'<path d="{" ".join(lines)}" fill="none" stroke="{TEXT1}" stroke-width="{svg_number(1.5 * k)}" '
            f'stroke-linecap="square" stroke-linejoin="miter"/></svg>\n')


def make_graphics():
    _app, family = qt_app()
    hero = banner(family)
    write_text(HERE / "hero.svg", hero)
    save_png(render_svg(hero, 1280 * SCALE, 400 * SCALE), HERE / "hero.png")
    marks = mode_strokes()
    for key, name in (("modeRedux", "mode-redux"), ("modeBolt", "mode-bolt")):
        write_text(HERE / f"{name}.svg", mode_mark(marks[key]))


# ---------------------------------------------------------------------------------------------------------------
# Synthetic test pictures (the screens never show a real render)
# ---------------------------------------------------------------------------------------------------------------

def study(path: Path, width: int, height: int, *, dusk: bool, bays: int, floors: int, seed: int):
    """A simple facade elevation drawn from rectangles and gradients: a neutral picture for the demo engine."""
    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, height)[:, None]
    x = np.linspace(0, 1, width)[None, :]
    if dusk:
        sky_top, sky_low, wall, glass, lit = (52, 60, 78), (150, 140, 138), (126, 122, 118), (40, 46, 56), (232, 196, 140)
    else:
        sky_top, sky_low, wall, glass, lit = (176, 188, 199), (226, 224, 219), (190, 184, 174), (70, 82, 94), (150, 166, 180)
    img = np.empty((height, width, 3), np.float32)
    for c in range(3):
        img[..., c] = sky_top[c] + (sky_low[c] - sky_top[c]) * np.clip(y / 0.8, 0, 1)
    ground = int(height * 0.84)
    img[ground:] = np.array(wall, np.float32) * (0.62 if dusk else 0.78)
    img[ground:ground + 3] *= 0.7
    for jx in range(0, width, max(24, width // 40)):
        img[ground:, jx:jx + 1] *= 0.9
    left, right, top = int(width * 0.1), int(width * 0.9), int(height * 0.2)
    shade = 1.0 - 0.12 * (y - 0.2)
    block = np.array(wall, np.float32)[None, None, :] * shade[..., None]
    img[top:ground, left:right] = block[top:ground] * np.ones((1, right - left, 1), np.float32)
    img[top - 14:top, left - 30:right + 30] = np.array(wall, np.float32) * 0.86
    img[top:top + 10, left:right] *= 0.82
    bay_w = (right - left) / bays
    floor_h = (ground - top - 24) / floors
    for i in range(bays):
        for j in range(floors):
            wx0 = int(left + i * bay_w + bay_w * 0.16)
            wx1 = int(left + (i + 1) * bay_w - bay_w * 0.16)
            wy0 = int(top + 24 + j * floor_h + floor_h * 0.16)
            wy1 = int(top + 24 + (j + 1) * floor_h - floor_h * 0.08)
            entrance = j == floors - 1 and i == bays // 2
            if entrance:
                wy1 = ground
            frame = np.array(wall, np.float32) * 0.55
            img[wy0 - 6:wy1, wx0 - 6:wx1 + 6] = frame
            gy = np.linspace(0, 1, wy1 - wy0)[:, None, None]
            on = dusk and rng.random() < 0.55
            tone = np.array(lit if on else glass, np.float32)
            pane = tone * (0.85 + 0.25 * gy) if not on else tone * (1.0 - 0.18 * gy)
            img[wy0:wy1, wx0:wx1] = pane * np.ones((1, wx1 - wx0, 1), np.float32)
            img[wy0:wy0 + 8, wx0:wx1] *= 0.72
            mid = (wx0 + wx1) // 2
            img[wy0:wy1, mid - 2:mid + 2] = frame
        fin = int(left + i * bay_w)
        img[top + 10:ground, fin:fin + 8] = np.array(wall, np.float32) * 1.05
        img[top + 10:ground, fin + 8:fin + 20] *= 0.86
    img[ground - 18:ground, left:right] *= 0.9
    img = np.clip(np.round(img), 0, 255).astype(np.uint8)
    Image.fromarray(img, "RGB").save(path)


# ---------------------------------------------------------------------------------------------------------------
# Screens of the real app (demo mode), driven in a child process
# ---------------------------------------------------------------------------------------------------------------

VISIBLE_TEXTS = """(function() {
    var out = [];
    function walk(it) {
        if (!it || it.visible === false) return;
        if (typeof it.text === "string" && it.text !== "") out.push(it.text);
        if (typeof it.placeholderText === "string" && it.placeholderText !== "") out.push(it.placeholderText);
        var ch = it.children || [];
        for (var i = 0; i < ch.length; ++i) walk(ch[i]);
    }
    walk(window.contentItem);
    return JSON.stringify(out);
})()"""


def child_env(work: Path) -> dict:
    env = dict(os.environ)
    env.update({
        "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software", "QT_SCALE_FACTOR": str(SCALE),
        "QML_DISABLE_DISK_CACHE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
        "CU_FAKE_STAGE_SECONDS": "6", "CU_FAKE_GPUS": "1", "CU_LIVE_PREVIEW": "off",
    })
    env.pop("CU_FAKE_FAULT", None)
    if os.name == "nt":
        env["QT_QPA_FONTDIR"] = str(Path(os.environ["SystemRoot"]) / "Fonts")
    return env


def drive_host(out: Path, texts_dir: Path | None, work: Path):
    """Runs inside the child process: opens the app in demo mode and takes the screens in order."""
    sys.path.insert(0, str(ROOT))
    import PySide6.QtQml as QtQml
    from PySide6.QtCore import QObject, QPointF, QTimer
    from PySide6.QtQml import QQmlExpression
    from PySide6.QtQuick import QQuickItem

    inputs = work / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    study(inputs / "facade-study.png", 1600, 1000, dusk=False, bays=6, floors=4, seed=5)
    study(inputs / "courtyard-dusk.png", 1500, 1000, dusk=True, bays=5, floors=4, seed=11)
    study(inputs / "terrace-study.png", 1400, 1000, dusk=False, bays=4, floors=3, seed=23)
    fixture = work / "releases.json"
    fixture.write_text(json.dumps([
        {"tag_name": "artegra-enhancer-v5.0.0-beta.1", "draft": False, "prerelease": True,
         "html_url": "https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/tag/artegra-enhancer-v5.0.0-beta.1"},
        {"tag_name": "artegra-enhancer-v0.1.0-alpha.4", "draft": False, "prerelease": True,
         "html_url": "https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/tag/artegra-enhancer-v0.1.0-alpha.4"},
    ]), encoding="utf-8")

    state = {"engine": None, "window": None, "i": 0, "wait_until": 0.0, "real_out": None}
    texts, crops, steps = {}, {}, []

    class Engine(QtQml.QQmlApplicationEngine):
        def load(self, url):
            super().load(url)
            state["engine"] = self
            QTimer.singleShot(480000, give_up)
            QTimer.singleShot(0, drive)

    QtQml.QQmlApplicationEngine = Engine

    def js(code):
        window = state["window"]
        expr = QQmlExpression(QtQml.QQmlEngine.contextForObject(window), window, code)
        value = expr.evaluate()
        if isinstance(value, tuple):
            value = None if value[1] else value[0]
        if expr.hasError():
            print("JS error:", code[:80], expr.error().toString(), flush=True)
            return None
        return value

    def bridge(name):
        return state["engine"].rootContext().contextProperty(name)

    def item(name):
        return state["window"].findChild(QQuickItem, name)

    def visible_item(name):
        stack = list(state["window"].contentItem().childItems())
        while stack:
            it = stack.pop(0)
            stack.extend(it.childItems())
            if it.objectName() == name and it.isVisible() and it.width() > 0:
                return it
        return None

    def shot(name, crop_item=None, pad=14, pad_y=6):
        path = out / f"{name}.png"

        def begin():
            if path.exists():
                path.unlink()
            state["overrode"] = False
            if js("window.tabItem !== null && window.tabItem !== undefined"):
                real = js("window.tabItem.outputDir")
                if real and real != NEUTRAL_OUTPUT:
                    state["real_out"] = real
                    js("window.tabItem.outputDir = %s" % json.dumps(NEUTRAL_OUTPUT))
                    state["overrode"] = True

        def grab():
            texts[name] = json.loads(js(VISIBLE_TEXTS) or "[]")
            if crop_item:
                it = visible_item(crop_item)
                if it is not None:
                    p = it.mapToScene(QPointF(0, 0))
                    # A little air at the sides; less above and below, where the next line of text starts.
                    crops[name] = [(p.x() - pad) * SCALE, (p.y() - pad_y) * SCALE,
                                   (p.x() + it.width() + pad) * SCALE, (p.y() + it.height() + pad_y) * SCALE]
            js("var it = window.contentItem; it.grabToImage(function(r) { r.saveToFile(%s) }, Qt.size(it.width, it.height))"
               % json.dumps(path.as_posix()))

        def end():
            if state["overrode"]:
                js("window.tabItem.outputDir = %s" % json.dumps(state["real_out"]))
            print("saved", name, flush=True)

        return [("do", begin), ("pause", 0.3), ("do", grab), ("wait", lambda: path.exists() and path.stat().st_size > 0, 15),
                ("pause", 0.1), ("do", end)]

    def scroll_settings_to(name):
        flick, target = item("settingsScroll"), item(name)
        if flick is None or target is None:
            print("Settings item not found:", name, flush=True)
            return
        y = target.mapToItem(flick.property("contentItem"), QPointF(0, 0)).y() - 28
        limit = max(0.0, float(flick.property("contentHeight")) - flick.height())
        flick.setProperty("contentY", max(0.0, min(y, limit)))

    def select_row(fragment):
        rows = js("JSON.stringify((function(m){var o=[];for(var i=0;i<m.count;++i){var r=m.get(i);o.push([r.key||'',r.name||'',r.group||''])}return o})(window.tabItem.queue))")
        for key, name, _group in json.loads(rows or "[]"):
            if fragment in name and key:
                js("window.tabItem.selectKey(%s)" % json.dumps(key))
                return
        print("No row for", fragment, flush=True)

    def show_repair():
        # Repair installation is hidden in demo mode; an installed copy shows it, so the screen does too.
        stack = list(state["window"].contentItem().childItems())
        while stack:
            it = stack.pop(0)
            stack.extend(it.childItems())
            if it.property("text") == "Repair installation":
                it.setVisible(True)

    facade, dusk, terrace = ([(inputs / n).as_posix()] for n in ("facade-study.png", "courtyard-dusk.png", "terrace-study.png"))

    def plan():
        return [
            ("do", lambda: js("window.minimumWidth = 0; window.minimumHeight = 0; window.width = 1280; window.height = 800")),
            ("wait", lambda: bool(js("window.tabConnected")), 90),
            ("pause", 1.5),
            ("do", lambda: js("window.tabItem.setMode('standard')")),
            ("do", lambda: js("window.tabItem.setScale(2)")),
            ("do", lambda: js("window.tabItem.applyPreset('Default')")),
            ("do", lambda: js("window.tabItem.addPaths(%s)" % json.dumps(dusk + facade))),
            ("pause", 3.0),
            ("do", lambda: select_row("courtyard-dusk")),
            ("pause", 1.0),
            *shot("screen-queued", crop_item="modeControl"),
            ("do", lambda: js("window.tabItem.startUpscale()")),
            ("pause", 4.0),
            *shot("screen-running"),
            ("wait", lambda: not js("window.tabItem.batch.active"), 240),
            ("pause", 1.0),
            ("do", lambda: js("window.tabItem.setMode('fast')")),
            ("pause", 0.6),
            ("do", lambda: js("window.tabItem.addPaths(%s)" % json.dumps(terrace))),
            ("pause", 2.0),
            ("do", lambda: js("window.tabItem.startUpscale()")),
            ("pause", 2.0),
            ("wait", lambda: not js("window.tabItem.batch.active"), 240),
            ("pause", 2.0),
            ("do", lambda: js("window.tabItem.toasts.clear()")),
            ("do", lambda: js("window.tabItem.earlierOpen = true")),
            ("do", lambda: select_row("terrace-study")),
            ("pause", 1.0),
            # The demo engine's result is the original enlarged with a warm tint (so testers can tell them apart),
            # which is not what an enhanced image looks like; the screen shows the original (Before) instead.
            ("do", lambda: js("window.tabItem.viewerItem.viewMode = 'before'")),
            ("pause", 1.0),
            ("do", lambda: js("window.tabItem.toasts.clear()")),
            *shot("screen-results", crop_item="modeControl"),
            ("do", lambda: js("window.settingsShown = true")),
            ("do", lambda: setattr(bridge("hostBridge"), "uninstaller", "screens")),
            ("do", lambda: bridge("hostBridge").changed.emit()),
            ("pause", 0.8),
            ("do", lambda: bridge("updateBridge").check()),
            ("pause", 2.5),
            ("do", lambda: scroll_settings_to("memorySettings")),
            ("do", show_repair),
            ("pause", 0.8),
            *shot("screen-settings"),
            ("do", lambda: js("window.askUninstall()")),
            ("pause", 0.8),
            *shot("screen-uninstall"),
            ("do", lambda: js("window.tabItem.confirmDialog.close(); window.settingsShown = false")),
            ("pause", 0.6),
            ("quit", None),
        ]

    def drive():
        try:
            step()
        except Exception:
            import traceback
            traceback.print_exc()
            state["i"] += 1
            QTimer.singleShot(100, drive)

    def finish(code):
        if texts_dir:
            texts_dir.mkdir(parents=True, exist_ok=True)
            (texts_dir / "screens-host-texts.json").write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")
        (work / "crops.json").write_text(json.dumps(crops), encoding="utf-8")
        from PySide6.QtWidgets import QApplication
        QApplication.instance().exit(code)

    def give_up():
        print("The screens took too long; giving up.", flush=True)
        finish(3)

    def step():
        if state["window"] is None:
            roots = state["engine"].rootObjects()
            if not roots:
                QTimer.singleShot(20, drive)
                return
            state["window"] = roots[0]
            steps.extend(plan())
        now = time.monotonic()
        if now < state["wait_until"]:
            QTimer.singleShot(30, drive)
            return
        if state["i"] >= len(steps):
            return
        kind, *rest = steps[state["i"]]
        if kind == "wait":
            predicate, limit = rest
            try:
                ok = predicate()
            except Exception:
                ok = False
            if not ok:
                state.setdefault("since", now)
                if now - state["since"] > limit:
                    print("Timed out at step", state["i"], flush=True)
                    state.pop("since", None)
                    state["i"] += 1
                QTimer.singleShot(50, drive)
                return
            state.pop("since", None)
        elif kind == "do":
            rest[0]()
        elif kind == "pause":
            state["wait_until"] = now + rest[0]
        elif kind == "quit":
            finish(0)
            return
        state["i"] += 1
        QTimer.singleShot(10, drive)

    from host import app as host_app
    return host_app.main(["--demo", "--state", str(work / "state"), "--update-fixture", str(fixture)])


def drive_setup(out: Path, texts_dir: Path | None, work: Path):
    """Runs inside the child process: the setup page (SetupView.qml) with a stand-in for the installation, whose terms
    are the real required models and whose progress line uses the real wording of host/installation.py."""
    sys.path.insert(0, str(ROOT))
    import threading
    from PySide6.QtCore import QObject, Property, QUrl, Slot
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtQuick import QQuickView
    from PySide6.QtWidgets import QApplication
    from host.installation_qt import InstallationBridge
    from host.model_setup import SetupError

    app = QApplication.instance() or QApplication([sys.argv[0]])
    for name in ("InstrumentSans-Regular.ttf", "InstrumentSans-Medium.ttf"):
        QFontDatabase.addApplicationFontFromData((FONTS / name).read_bytes())
    manifest = json.loads((ROOT / "models.manifest.json").read_text(encoding="utf-8"))
    models = manifest["models"] if isinstance(manifest.get("models"), dict) else {m["id"]: m for m in manifest["models"]}
    required = [key for key, m in models.items() if m.get("required_for_standard") or m.get("required_for_fast")]
    gib = 1024 ** 3
    total = sum(models[key]["size_bytes"] for key in required)
    first = models[required[0]]
    done = first["size_bytes"] * 0.38
    progress_line = (f"Downloading enhancement files 1 of {len(required)} · "
                     f"{done / gib:.1f} of {first['size_bytes'] / gib:.1f} GB")
    progress_fraction = .4 + .54 * done / total

    class StandIn:
        def __init__(self, root, state, *, progress, cancel):
            self.progress, self.cancel = progress, cancel
            self.choices = {key: str(work / key) for key in ("models_dir", "output_dir", "runtime_dir")}
            self.terms = [dict(id=key, name=models[key].get("display_name", key), notice=models[key].get("acceptance_notice", ""),
                               license_url=models[key]["license_url"], model_card_url=models[key]["model_card_url"]) for key in required]

        def is_complete(self):
            return False

        def terms_accepted(self):
            return False

        def run(self, *, accept_terms=False):
            self.progress({"stage": "models", "message": progress_line, "fraction": progress_fraction})
            while not self.cancel.wait(0.02):
                pass
            raise SetupError("Setup is paused. Open Artegra Enhancer or run the installer again to resume.", "cancelled")

    class Host(QObject):
        @Property(bool, constant=True)
        def busy(self): return False
        @Property(bool, constant=True)
        def ready(self): return False
        @Property(bool, constant=True)
        def demo(self): return False
        @Property(bool, constant=True)
        def engineStarted(self): return False
        @Property(str, constant=True)
        def status(self): return ""
        @Slot()
        def start(self): pass
        @Slot()
        def repair(self): pass
        @Slot()
        def saveDiagnosticBundle(self): pass

    host = Host()
    installation = InstallationBridge(ROOT, work / "state", factory=StandIn)
    view = QQuickView()
    view.rootContext().setContextProperty("installationBridge", installation)
    view.rootContext().setContextProperty("hostBridge", host)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setSource(QUrl.fromLocalFile(str(ROOT / "ui" / "qml" / "SetupView.qml")))
    if view.status() != QQuickView.Status.Ready:
        print([e.toString() for e in view.errors()], flush=True)
        return 2
    view.resize(960, 520)
    view.show()
    texts = {}

    def settle(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)

    def words():
        found = []

        def walk(it):
            if not it.isVisible():
                return
            for prop in ("text", "placeholderText"):
                value = it.property(prop)
                if isinstance(value, str) and value:
                    found.append(value)
            for c in it.childItems():
                walk(c)
        walk(view.rootObject())
        return found

    def grab(name):
        settle(0.6)
        texts[name] = words()
        image = view.grabWindow()
        image.save(str(out / f"{name}.png"))
        print("saved", name, flush=True)

    settle(0.5)
    installation.setAccepted(True)
    grab("screen-setup")
    installation.start()
    view.resize(960, 440)
    settle(1.0)
    grab("screen-setup-progress")
    installation.close() if hasattr(installation, "close") else None
    settle(0.5)
    if texts_dir:
        texts_dir.mkdir(parents=True, exist_ok=True)
        (texts_dir / "screens-setup-texts.json").write_text(json.dumps(texts, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


def make_screens(texts_dir: Path | None):
    from PIL import Image
    SCREENS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="artegra-screens-") as temp:
        work = Path(temp)
        raw = work / "raw"
        raw.mkdir()
        env = child_env(work)
        for kind in ("host", "setup"):
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--child", kind, "--raw", str(raw), "--work", str(work)]
            if texts_dir:
                command += ["--texts", str(texts_dir)]
            code = subprocess.run(command, cwd=str(ROOT), env=env, timeout=900).returncode
            if code != 0:
                raise SystemExit(f"The {kind} screens stopped with exit code {code}.")
        crops = json.loads((work / "crops.json").read_text(encoding="utf-8")) if (work / "crops.json").exists() else {}
        for path in sorted(raw.glob("*.png")):
            with Image.open(path) as image:
                picture = image.convert("RGB")
            save_image(picture, SCREENS / path.name)
            if path.stem in crops:
                box = [round(v) for v in crops[path.stem]]
                save_image(picture.crop(tuple(box)), SCREENS / f"{path.stem}-mode.png")


# ---------------------------------------------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------------------------------------------

def write_text(path: Path, text: str):
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
    print(path.relative_to(ROOT).as_posix())


def save_image(image, path: Path):
    """Save a PIL image as an optimised PNG with no metadata (no text chunks, no time, no colour profile)."""
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    path.write_bytes(buffer.getvalue())
    print(path.relative_to(ROOT).as_posix())


def save_png(data: bytes, path: Path):
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        save_image(image.convert("RGB"), path)


def pin_pngs():
    """Pin every PNG under docs/assets in asset-hashes.json (and drop pins of PNGs that are gone)."""
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    prefix = HERE.relative_to(ROOT).as_posix() + "/"
    pins = {k: v for k, v in pins.items() if not k.startswith(prefix)}
    for path in sorted(HERE.rglob("*.png")):
        pins[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    PINS.write_bytes((json.dumps(pins, indent=2) + "\n").replace("\n", "\r\n").encode("ascii"))
    print(PINS.relative_to(ROOT).as_posix())


def below_normal_priority():
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("what", nargs="?", choices=("all", "graphics", "screens"), default="all")
    parser.add_argument("--texts", type=Path, help="save the words each screen shows in this folder")
    parser.add_argument("--child", choices=("host", "setup"), help=argparse.SUPPRESS)
    parser.add_argument("--raw", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--work", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child == "host":
        return drive_host(args.raw, args.texts, args.work)
    if args.child == "setup":
        return drive_setup(args.raw, args.texts, args.work)
    below_normal_priority()
    if args.what in ("all", "graphics"):
        make_graphics()
    if args.what in ("all", "screens"):
        make_screens(args.texts)
    pin_pngs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""5.0.2: the engine named in the app (engine design 2.10, D3) and the viewer's zoom path for a Large-image result.

- format.js reads the engine from a plan (no engine key = classic) and says the service's own words.
- The queue row tags its size with "Classic" or "Large-image"; the caption names the engine of a result and, for a waiting
  image (the plan card), the plan's engine line.
- The zoom path asks only for proxies and regions of at most 4096 x 4096 px, never for the saved file.

Qt runs in a child process (offscreen), so this file never shares a Q*Application with other tests; where PySide6 is
missing, the static checks of the bindings still run."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from service import media

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / 'ui' / 'qml' / 'creative'


def text(name):
    return (QML / name).read_text(encoding='utf-8')


def run_qt(script):
    pytest.importorskip('PySide6')
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', PYTHONIOENCODING='utf-8')
    r = subprocess.run([sys.executable, '-B', '-c', script], cwd=ROOT, env=env, capture_output=True, text=True,
                       encoding='utf-8', timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


FORMAT_JS = r'''
import json, sys
LARGE = 'Engine: Large-image (this size is beyond the Classic engine on this computer)'
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine
app = QCoreApplication([])
eng = QJSEngine()
src = Path('ui/qml/creative/format.js').read_text(encoding='utf-8').replace('.pragma library', '', 1)
r = eng.evaluate(src)
assert not r.isError(), r.toString()
def ev(expr):
    v = eng.evaluate(expr)
    assert not v.isError(), (expr, v.toString())
    return v.toVariant()
out = {
 'classic': ev('engineOf({ok: true, output_size: [7000, 4376]})'),
 'none': ev('engineOf(null)'),
 'banded': ev('engineOf({engine: "banded"})'),
 'answer': ev('engineOf({executor: "large-image"})'),
 'tags': [ev('engineTag({engine: "banded"})'), ev('engineTag({})'), ev('engineTagOf("large-image")'), ev('engineTagOf("")')],
 'line_classic': ev('engineLine({ok: true, text: {summary: "x"}})'),
 'line_text': ev('engineLine({ok: true, text: {engine: "Engine: Large-image (developer comparison run)"}})'),
 'line_banded': ev('engineLine({ok: true, engine: "banded"})'),
 'line_refused': ev('engineLine({ok: false, engine: "banded"})'),
 'consts': [ev('ENGINE_CLASSIC_LINE'), ev('ENGINE_LARGE_LINE')],
 'item_banded': ev('normalizeItem({id: "i001", plan: {engine: "banded", output_size: [28000, 17504], stages: [1, 2, 3]}}, {id: "j1"}).engine'),
 'item_classic': ev('normalizeItem({id: "i001", plan: {output_size: [7000, 4376], stages: [1]}}, {id: "j1"}).engine'),
 'item_noplan': ev('normalizeItem({id: "i001"}, {id: "j1"}).engine'),
 'scales': ev('engineOf(planFromScales({"8": {ok: true, output_size: [28000, 17504], passes: 3, executor: "large-image"}}, 8))'),
 'scales_line': ev('engineLine(planFromScales({"8": {ok: true, output_size: [28000, 17504], passes: 3, executor: "large-image", text: {engine: "Engine: Large-image (this size is beyond the Classic engine on this computer)"}}}, 8))'),
 'scales_old': ev('engineOf(planFromScales({"2": {ok: true, output_size: [7000, 4376], passes: 1}}, 2))'),
 'card_large': ev('planCard(planFromScales({"8": {ok: true, output_size: [28000, 17504], passes: 3, executor: "large-image", '
                  'text: {engine: "%s", disk: "about 55 GB free disk space for the work files", memory_class: "Memory class: 64 GB PC"}}}, 8))'
                  % LARGE),
 'card_classic': ev('planCard({ok: true, text: {engine: "Engine: Classic", disk: "ignored for a classic plan"}})'),
 'card_refused': ev('planCard({ok: false, engine: "banded", text: {disk: "x"}})'),
 'caption_note': ev('withPlanCard("Uses a lighter setting to fit this computer\'s memory.", "Engine: Classic")'),
 'caption_facts': ev('withPlanCard(facts(["3,500 \u00d7 2,188 px", "PNG", ""]), "Engine: Classic")'),
 'caption_nocard': ev('withPlanCard(facts(["3,500 \u00d7 2,188 px", "PNG"]), "")'),
 'caption_onlycard': ev('withPlanCard("", "Engine: Classic")'),
}
print(json.dumps(out))
'''

TRAY = r'''
import json
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
app = QGuiApplication([])
eng = QQmlEngine()
comp = QQmlComponent(eng, QUrl.fromLocalFile(str(Path('ui/qml/creative/CuTrayStatus.qml').resolve())))
assert comp.status() == QQmlComponent.Ready, [e.toString() for e in comp.errors()]
def make(**props):
    o = comp.create()
    for k, v in props.items():
        o.setProperty(k, v)
    return {'full': o.property('full'), 'short': o.property('shortText'), 'shorter': o.property('shorterText'),
            'size': o.property('becomesSize')}
out = {
 'input_large': make(kind='input', state='ready', outW=28000, outH=17504, engineTag='Large-image'),
 'input_classic': make(kind='input', state='ready', outW=7000, outH=4376, engineTag='Classic'),
 'input_none': make(kind='input', state='ready', outW=7000, outH=4376),
 'done_large': make(kind='job', state='done', outW=28000, outH=17504, tookS=7200, engineTag='Large-image'),
 'done_inview': make(kind='job', state='done', outW=28000, outH=17504, tookS=7200, engineTag='Large-image', inView=True),
 'working': make(kind='job', state='running', outW=28000, outH=17504, gpu=0, engineTag='Large-image'),
 'refused': make(kind='input', state='refused', maxFactor=4, engineTag='Classic'),
}
print(json.dumps(out))
'''


def test_format_js_reads_the_engine_from_the_plan():
    out = run_qt(FORMAT_JS)
    assert (out['classic'], out['none'], out['banded'], out['answer']) == ('classic', 'classic', 'large-image', 'large-image')
    assert out['tags'] == ['Large-image', 'Classic', 'Large-image', 'Classic']
    assert out['line_classic'] == media.ENGINE_CLASSIC
    assert out['line_text'] == media.ENGINE_LARGE_FORCED
    assert out['line_banded'] == media.ENGINE_LARGE
    assert out['line_refused'] == ''
    assert out['consts'] == [media.ENGINE_CLASSIC, media.ENGINE_LARGE]
    assert (out['item_banded'], out['item_classic'], out['item_noplan']) == ('large-image', 'classic', 'classic')
    assert (out['scales'], out['scales_old']) == ('large-image', 'classic')
    assert out['scales_line'] == media.ENGINE_LARGE
    assert out['card_large'] == (media.ENGINE_LARGE + ' \u00b7 about 55 GB free disk space for the work files'
                                 ' \u00b7 Memory class: 64 GB PC')
    assert out['card_classic'] == media.ENGINE_CLASSIC
    assert out['card_refused'] == ''
    assert out['caption_note'] == "Uses a lighter setting to fit this computer's memory. \u00b7 Engine: Classic"
    assert out['caption_facts'] == '3,500 \u00d7 2,188 px, PNG \u00b7 Engine: Classic'
    assert out['caption_nocard'] == '3,500 \u00d7 2,188 px, PNG'
    assert out['caption_onlycard'] == 'Engine: Classic'


def test_the_queue_row_tags_the_size_with_the_engine():
    out = run_qt(TRAY)
    big, small = out['input_large']['size'], out['input_classic']['size']
    assert big.startswith('28,000') and big.endswith('17,504 px')
    assert out['input_large']['full'] == f'Becomes {big}, Large-image'
    assert out['input_large']['short'] == f'→ {big}, Large-image'
    assert out['input_classic']['full'] == f'Becomes {small}, Classic'
    assert out['input_none']['full'] == f'Becomes {small}'                                 # no tag given: as before
    assert out['done_large']['full'].replace(' ', ' ') == 'Took 2 h 0 min, Large-image'
    assert out['done_inview']['full'].replace(' ', ' ') == 'Took 2 h 0 min'                                 # the caption says it there
    assert 'Large-image' not in out['working']['full']
    assert out['refused']['full'] == 'Fits at 4×'


# --- static checks of the bindings (they run without Qt) -----------------------------------------------------------------

def test_the_constants_are_the_services_words():
    js = text('format.js')
    assert f'var ENGINE_CLASSIC_LINE = "{media.ENGINE_CLASSIC}"' in js
    assert f'var ENGINE_LARGE_LINE = "{media.ENGINE_LARGE}"' in js
    assert 'halo' not in js.lower()                       # HALO-FIX.md reads "STATUS: NOT FIXED": no halo line in the app


def test_every_row_carries_the_engine_and_the_row_reads_it_softly():
    model = text('CuQueueModel.qml')
    assert re.search(r'function blank\(\) \{[^}]*\bengine: ""', model, re.S)
    row = text('CuQueueRow.qml')
    assert 'engineTag: row.isImage && String(row.role("engine", "")) !== ""' in row
    assert 'required property string engine' not in row          # heading, cleared and removed rows have none
    tab = text('CreativeUpscalerTab.qml')
    assert 'engine: it.engine || "classic", planCard: ""' in tab                                       # job rows
    assert 'engine: gone ? "" : F.engineOf(plan), planCard: gone || reason !== "" ? "" : F.planCard(plan)' in tab
    assert tab.count('engine: "", planCard: ""') == 1                                                  # the cleared row


def test_the_caption_names_the_engine():
    viewer = text('CuViewer.qml')
    assert 'F.engineTagOf(String(row.engine)) + " engine"' in viewer
    assert '"with transparency" : "", engineWords])' in viewer
    assert 'return F.withPlanCard(F.captionNotes(row.notes), planCardLine)' in viewer   # small cards, round 3
    assert 'return F.withPlanCard(F.facts([F.size(row.srcW, row.srcH), formatOf(row.name), transparencyWords]), planCardLine)' in viewer
    assert 'String(row.planCard || "")' in viewer


def test_the_zoom_path_uses_proxies_and_regions_only():
    """CuViewer and its region image ask for a Large-image result only through /proxy (at most the drawn size) and
    /region (at most 4096 x 4096 px); nothing in the viewer asks for the saved file or a whole decode."""
    viewer, pane, region = text('CuViewer.qml'), text('CuViewerPane.qml'), text('CuRegionImage.qml')
    assert '"/proxy?kind=result&job="' in viewer
    assert 'if (w < 8 || h < 8 || w > 4096 || h > 4096) { clear(); return }' in region
    assert '"/region?kind=result&job="' in region
    for src in (viewer, pane, region):
        assert 'row.output)' not in src.replace('F.basename(String(row.output))', '').replace('formatOf(row.output', '')
        assert 'view.jpg' not in src and 'file:' not in src
    assert re.search(r'id: resFull[^}]*source: pane\.loadResult \? pane\.viewer\.resultUrl : ""', pane, re.S)


COMPILE = r'''
import json
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
app = QGuiApplication([])
eng = QQmlEngine()
out = {}
for n in ('CuTrayStatus', 'CuQueueModel', 'CuQueueRow', 'CuViewer', 'CuViewerPane', 'CuRegionImage', 'CreativeUpscalerTab',
          'CuViewerCaption', 'CuPassRuler'):
    c = QQmlComponent(eng, QUrl.fromLocalFile(str(Path('ui/qml/creative/' + n + '.qml').resolve())))
    out[n] = [e.toString() for e in c.errors()] if c.status() != QQmlComponent.Ready else []
print(json.dumps(out))
'''


def test_the_changed_components_compile():
    assert run_qt(COMPILE) == {n: [] for n in ('CuTrayStatus', 'CuQueueModel', 'CuQueueRow', 'CuViewer', 'CuViewerPane',
                                              'CuRegionImage', 'CreativeUpscalerTab', 'CuViewerCaption', 'CuPassRuler')}


# --- V6 (build wave 2): the queue row's engine tag from a service item, through the model and the row, in Qt ---------------

ROW_PATH = r'''
import json
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
app = QGuiApplication([])
eng = QQmlEngine()
here = Path('ui/qml/creative').resolve()
probe = b"""
import QtQuick
import "format.js" as F
Item {
    id: root
    width: 900; height: 600
    property var out: ({})
    CuQueueModel { id: qm }
    ListView { id: lv; anchors.fill: parent; model: qm.list; delegate: CuQueueRow { width: lv.width } }
    function item(plan, state) {
        var it = F.normalizeItem({id: "i001", name: "card.png", size: [3500, 2188], plan: plan, state: state,
                                  timings: {started: "2026-11-21T00:00:00Z", finished: "2026-11-21T02:00:00Z"}},
                                 {id: "j0123456789ab"})
        // the queue tab's job row (CreativeUpscalerTab.jobRows), with the engine as the tab passes it
        return {key: "j:" + state + ":" + it.engine, kind: "job", group: state === "done" ? "done" : "next",
                name: it.name, srcW: it.width, srcH: it.height, outW: it.outW, outH: it.outH, factor: 8,
                status: it.state, tookS: it.tookS, engine: it.engine || "classic"}
    }
    function run() {
        var banded = {ok: true, engine: "banded", output_size: [28000, 17504], stages: [{}, {}, {}]}
        var classic = {ok: true, output_size: [7000, 4376], stages: [{}]}
        var rows = [item(banded, "done"), item(classic, "done"), item(banded, "queued"), item(classic, "queued")]
        var o = {entries: [], meta: []}
        for (var i = 0; i < rows.length; ++i) {
            var e = qm.rowEntry(rows[i], rows[i].group)
            o.entries.push(e.engine)
            qm.list.append(e)
        }
        lv.forceLayout()
        for (var j = 0; j < rows.length; ++j) {
            var d = lv.itemAtIndex(j)
            o.meta.push(d ? String(d.metaText) : null)
        }
        out = o
    }
}
"""
c = QQmlComponent(eng)
c.setData(probe, QUrl.fromLocalFile(str(here / '_engine_tag_probe.qml')))
obj = c.create()
if obj is None:
    print(json.dumps({'errors': [e.toString() for e in c.errors()]}))
else:
    from PySide6.QtCore import QMetaObject
    QMetaObject.invokeMethod(obj, 'run')
    app.processEvents()
    print(json.dumps(obj.property('out').toVariant() if hasattr(obj.property('out'), 'toVariant') else obj.property('out')))
'''


def test_the_queue_rows_engine_tag_from_a_service_item_in_qt():
    """V6: a service item through format.js normalizeItem, the tab's job row, CuQueueModel.rowEntry (the ListModel role)
    and CuQueueRow into CuTrayStatus: a Large-image item's row ends with ', Large-image', a classic one's with ', Classic'.
    A renamed role or a key dropped from blank() would leave the tag empty and fail here."""
    out = run_qt(ROW_PATH)
    assert 'errors' not in out, out
    assert out['entries'] == ['large-image', 'classic', 'large-image', 'classic']
    meta = [m.replace('\u202f', ' ').replace('\xa0', ' ') for m in out['meta']]          # the row's no-break spaces
    took, becomes = meta[:2], meta[2:]
    assert took[0].endswith(', Large-image') and took[0].startswith('Took 2 h 0 min'), took
    assert took[1].endswith(', Classic'), took
    assert becomes[0].endswith('28,000 × 17,504 px, Large-image'), becomes
    assert becomes[1].endswith('7,000 × 4,376 px, Classic'), becomes


def test_the_queue_rows_engine_binding_without_qt():
    """Where PySide6 is missing, the same path as a binding check: the tab gives every job row the item's engine, the model
    keeps the key, and the row turns it into the tag."""
    tab, model, row = text('CreativeUpscalerTab.qml'), text('CuQueueModel.qml'), text('CuQueueRow.qml')
    js = text('format.js')
    assert re.search(r'function normalizeItem\(it, job\) \{.*?\bengine: engineOf\(plan\),', js, re.S)
    assert 'engine: it.engine || "classic"' in tab
    assert re.search(r'function blank\(\) \{.*?\bengine: "".*?\}\s*\}', model, re.S)
    assert re.search(r'function rowEntry\(r, g\) \{\s*var e = blank\(\)\s*for \(var k in e\)', model)
    assert 'engineTag: row.isImage && String(row.role("engine", "")) !== "" ? F.engineTagOf(String(row.role("engine", ""))) : ""' in row


# --- Small cards, round 2: the time warning of a Classic image that needs more graphics memory than its card has -----------
# (service/runner.py VRAM_SPILL_NOTE). The service carries it on the plan cards (scales of /api/inputs and /api/plan, as
# vram_note {on, off}: with and without protected areas) and on the image (item notes); the window draws it on the caption
# of a waiting image (with its plan card) and of a queued one.

def spill_notes():
    from service.runner import VRAM_SPILL_NOTE
    on = VRAM_SPILL_NOTE.format(gb=10, who='this card has', card=8)
    off = VRAM_SPILL_NOTE.format(gb=9, who='this card has', card=8)
    return on, off


SPILL_JS = r"""
import json
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine
app = QCoreApplication([])
eng = QJSEngine()
src = Path('ui/qml/creative/format.js').read_text(encoding='utf-8').replace('.pragma library', '', 1)
r = eng.evaluate(src)
assert not r.isError(), r.toString()
eng.globalObject().setProperty('ON', @ON@)
eng.globalObject().setProperty('OFF', @OFF@)
def ev(expr):
    v = eng.evaluate(expr)
    assert not v.isError(), (expr, v.toString())
    return v.toVariant()
ev('var SC = {"6": {ok: true, output_size: [9120, 10572], passes: 2, vram_note: {on: ON, off: OFF}}, '
   '"2": {ok: true, output_size: [3040, 3524], passes: 1}}')
out = {
 'kept': ev('planFromScales(SC, 6).vram_note'),
 'on': ev('spillNote(planFromScales(SC, 6), true)'),
 'off': ev('spillNote(planFromScales(SC, 6), false)'),
 'none': [ev('spillNote(planFromScales(SC, 2), true)'), ev('spillNote(null, true)'),
          ev('spillNote({ok: true, vram_note: {on: ON, off: null}}, false)')],
 'answer': ev('spillNote({ok: true, text: {notes: ["x", ON]}, vram_note: {on: ON, off: OFF}}, true)'),
 'is': [ev('isSpillNote(ON)'), ev('isSpillNote("JPEG has no transparency: the transparent areas are filled.")'),
        ev('isSpillNote("")')],
 'in_text': ev('spillNoteIn(notesText(["JPEG has no transparency: the transparent areas are filled.", OFF]))'),
 'in_list': ev('spillNoteIn(["a", ON])'),
 'in_none': [ev('spillNoteIn("")'), ev('spillNoteIn(null)'), ev('spillNoteIn("Uses a lighter setting.")')],
 'item': ev('spillNoteIn(normalizeItem({id: "i001", notes: ["JPEG has no transparency: x.", ON]}, {id: "j1"}).notes)'),
 'input': ev('inputNotes(ON, "Uses a lighter setting to fit this computer\'s memory.", "own note")'),
 'input_none': ev('inputNotes("", "", "")'),
 'input_own': ev('inputNotes("", "", "own note")'),
}
print(json.dumps(out))
"""


def test_format_js_reads_the_spill_note():
    on, off = spill_notes()
    out = run_qt(SPILL_JS.replace('@ON@', json.dumps(on)).replace('@OFF@', json.dumps(off)))
    assert out['kept'] == {'on': on, 'off': off}
    assert (out['on'], out['off']) == (on, off)
    assert out['none'] == ['', '', '']
    assert out['answer'] == on
    assert out['is'] == [True, False, False]
    assert (out['in_text'], out['in_list'], out['item']) == (off, on, on)
    assert out['in_none'] == ['', '', '']
    assert out['input'] == on + "\nUses a lighter setting to fit this computer's memory.\nown note"   # the warning first
    assert (out['input_none'], out['input_own']) == ('', 'own note')


CAPTION = r"""
import json
from pathlib import Path
from PySide6.QtCore import QUrl, QMetaObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
app = QGuiApplication([])
eng = QQmlEngine()
here = Path('ui/qml/creative').resolve()
probe = (b'''
import QtQuick
import "format.js" as F
Item {
    id: root
    width: 1400; height: 800
    property var out: ({})
    property string on: @ON@
    property string off: @OFF@
    QtObject { id: fakeTab; property var selectedRow: null; property int scale: 6 }
    CuViewer { id: viewer; width: 1300; height: 600; tab: fakeTab }
    CuViewerCaption { id: cap; width: 1300; height: 60; viewer: viewer }
    function inputRow(protectOn) {
        // the waiting row as CreativeUpscalerTab.rebuildQueueNow builds it: the plan from the image's scales
        var plan = F.planFromScales({"6": {ok: true, output_size: [9120, 10572], passes: 2, vram_note: {on: on, off: off}}}, 6)
        return {key: "in:m1", kind: "input", group: "ready", name: "card.png", srcW: 1520, srcH: 1762, outW: 9120,
                outH: 10572, factor: 6, status: "ready", planCard: F.planCard(plan),
                notes: F.inputNotes(F.spillNote(plan, protectOn), "", ""), mediaId: "m1", jobId: "", itemId: "",
                errorText: "", message: "", output: "", mode: "standard", engine: F.engineOf(plan)}
    }
    function jobRow(state) {
        var it = F.normalizeItem({id: "i001", name: "card.png", size: [1520, 1762], state: state,
                                  notes: ["JPEG has no transparency: the transparent areas are filled.", on],
                                  plan: {ok: true, output_size: [9120, 10572], stages: [{}, {}], minutes: 40}},
                                 {id: "j0123456789ab"})
        // CreativeUpscalerTab.jobRows: `notes: it.notes`
        return {key: "j:" + state, kind: "job", group: "next", name: it.name, srcW: it.width, srcH: it.height,
                outW: it.outW, outH: it.outH, factor: 6, status: it.state, tookS: it.tookS, engine: it.engine || "classic",
                notes: it.notes, message: it.message, minutes: 40, errorText: "", mediaId: "m1", jobId: "j0123456789ab",
                itemId: "i001", progress: 0, stage: 0, stages: 2, output: state === "done" ? "card_cu6x.png" : "",
                mode: "standard", resultReady: true}
    }
    function show(r) {
        fakeTab.selectedRow = r
        return {kind: String(cap.l2Kind), text: String(cap.l2Text), shown: String(cap.l2Shown), note: String(viewer.noteText),
                ruler: String(viewer.spillRunning)}
    }
    function run() {
        out = {input_on: show(inputRow(true)), input_off: show(inputRow(false)), queued: show(jobRow("queued")),
               running: show(jobRow("running")), done: show(jobRow("done"))}
    }
}
''').replace(b'@ON@', json.dumps(@ONR@).encode()).replace(b'@OFF@', json.dumps(@OFFR@).encode())
c = QQmlComponent(eng)
c.setData(probe, QUrl.fromLocalFile(str(here / '_spill_caption_probe.qml')))
obj = c.create()
if obj is None:
    print(json.dumps({'errors': [e.toString() for e in c.errors()]}))
else:
    QMetaObject.invokeMethod(obj, 'run')
    app.processEvents()
    v = obj.property('out')
    print(json.dumps(v.toVariant() if hasattr(v, 'toVariant') else v))
"""


def test_the_caption_draws_the_spill_note_of_a_waiting_and_a_queued_image():
    """In Qt (offscreen): what CuViewerCaption draws on its second line. A waiting image shows the note of the protect
    choice in force, with its plan card; a queued image shows its item's note; a running one shows its pass, with the note
    under the pass ruler's tip (and in Activity at its start); a finished one shows its result."""
    on, off = spill_notes()
    out = run_qt(CAPTION.replace('@ONR@', repr(on)).replace('@OFFR@', repr(off)))
    assert 'errors' not in out, out
    assert out['input_on']['kind'] == 'facts' and out['input_on']['text'] == on + ' · Engine: Classic', out
    assert out['input_off']['text'] == off + ' · Engine: Classic'
    assert out['input_on']['shown'].startswith('May run slowly: '), out          # a cut keeps the warning first
    assert out['queued']['kind'] == 'facts' and out['queued']['text'] == on, out
    assert out['queued']['note'] == on and out['input_on']['note'] == on
    assert out['running']['kind'] == 'state' and on not in out['running']['text']
    assert out['running']['ruler'] == on                                         # under the pass ruler's tip
    assert out['queued']['ruler'] == '' and out['input_on']['ruler'] == ''
    assert on not in out['done']['text'] and out['done']['note'] == '' and out['done']['ruler'] == ''


def test_the_pass_rulers_tip_carries_the_running_images_note():
    assert 'tipDetail: caption.viewer ? caption.viewer.spillRunning : ""' in text('CuViewerCaption.qml')
    assert 'detail: ruler.tipDetail' in text('CuPassRuler.qml')


def test_the_tab_gives_the_waiting_row_the_note_and_plans_again_when_the_cards_change():
    tab = text('CreativeUpscalerTab.qml')
    assert 'var spill = gone ? "" : F.spillNote(plan, protectOn)' in tab
    assert re.search(r'readonly property bool protectOn: effectiveProtect\.length > 0\s+onProtectOnChanged: rebuildQueue\(\)', tab)
    assert 'notes: gone ? "" : F.inputNotes(spill, lighter, String(inp.notes || "")),' in tab
    assert re.search(r'onCardBasisChanged: \{[^}]*refreshInputPlans\(\)', tab, re.S)
    js = text('format.js')
    assert 'vram_note: v.vram_note || null' in js                   # planFromScales keeps the service's key


# --- Small cards, round 3: a waiting image's other notes stay readable beside the time warning ---------------------------
# The caption draws the first of a waiting image's notes, and the warning comes first (F.inputNotes). 5.0.1 draws the
# lighter-setting note first on such an image, so the caption now keeps every note after the warning on the same line (the
# whole line shows on hover when it is cut), and a row without the warning is drawn as before.

LIGHTER = "Uses a lighter setting to fit this computer's memory."


def test_the_caption_keeps_the_other_notes_of_a_warned_waiting_image():
    on, off = spill_notes()
    probe = CAPTION.replace('notes: F.inputNotes(F.spillNote(plan, protectOn), "", ""),',
                            'notes: F.inputNotes(F.spillNote(plan, protectOn), protectOn ? "@L@" : "", "own note"),'
                            .replace('@L@', LIGHTER.replace("'", "\'")))
    assert probe != CAPTION
    out = run_qt(probe.replace('@ONR@', repr(on)).replace('@OFFR@', repr(off)))
    assert 'errors' not in out, out
    assert out['input_on']['text'] == on + ' · ' + LIGHTER + ' · own note · Engine: Classic', out
    assert out['input_on']['note'] == on + ' · ' + LIGHTER + ' · own note', out
    assert out['input_on']['shown'].startswith(on), out                    # the warning is never cut (no ", " in it)
    assert out['input_off']['text'] == off + ' · own note · Engine: Classic', out


def test_a_waiting_image_without_the_warning_draws_its_first_note_as_before():
    plain = 'captionNotes(%s)' % json.dumps(LIGHTER + '\nown note')
    out = run_qt(SPILL_JS.replace('@ON@', json.dumps('x')).replace('@OFF@', json.dumps('y'))
                 .replace('print(json.dumps(out))',
                          'out = {"plain": ev(%r), "none": ev(%r)}\nprint(json.dumps(out))' % (plain, 'captionNotes("")')))
    assert out == {'plain': LIGHTER, 'none': ''}, out

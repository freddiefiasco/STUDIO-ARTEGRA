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
    assert 'return F.withPlanCard(String(row.notes).split("\\n")[0], planCardLine)' in viewer
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
for n in ('CuTrayStatus', 'CuQueueModel', 'CuQueueRow', 'CuViewer', 'CuViewerPane', 'CuRegionImage', 'CreativeUpscalerTab'):
    c = QQmlComponent(eng, QUrl.fromLocalFile(str(Path('ui/qml/creative/' + n + '.qml').resolve())))
    out[n] = [e.toString() for e in c.errors()] if c.status() != QQmlComponent.Ready else []
print(json.dumps(out))
'''


def test_the_changed_components_compile():
    assert run_qt(COMPILE) == {n: [] for n in ('CuTrayStatus', 'CuQueueModel', 'CuQueueRow', 'CuViewer', 'CuViewerPane',
                                              'CuRegionImage', 'CreativeUpscalerTab')}

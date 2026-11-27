"""Zooming in past the 2048 px preview: the viewer's full-resolution detail (CuRegionImage) asks the service for /region
tiles of the visible area. The service takes the session token of an image route from the query (service/api.py _guard),
and only service.mediaUrl(...) adds it. From 5.0.0 to 5.0.2 Beta 1 the tile URL was built with service.url(...), so the
service refused every tile with 401 and the viewer showed the preview stretched. These tests pin the token on every tile
request, in the QML text, in Qt, and at the service."""
import json
import re
import urllib.parse
from pathlib import Path

from tests.service.helpers import gradient, write_image
from tests.service.test_integration import Base
from tests.test_views_qml import run_qt

ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / 'ui' / 'qml'
UNTOKENED = re.compile(r'\b(?:service|api)\.url\(')


def test_the_detail_tiles_are_requested_with_the_session_token():
    region = (QML_ROOT / 'creative' / 'CuRegionImage.qml').read_text(encoding='utf-8')
    assert 'source = pane.tab.service.mediaUrl(base + (base.indexOf("?") >= 0 ? "&" : "?") + xywh)' in region
    assert not UNTOKENED.search(region)


def test_no_image_in_the_qml_is_asked_for_without_the_session_token():
    """service.url(...) gives the address without the token, which the service refuses for every image route
    (thumb, proxy, region, mask, the live pictures). Nothing outside CuApi itself uses it."""
    found = []
    for path in sorted(QML_ROOT.rglob('*.qml')):
        if path.name == 'CuApi.qml':
            continue
        for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if UNTOKENED.search(line):
                found.append(f'{path.relative_to(ROOT).as_posix()}:{n}')
    assert found == []


TILE_URLS = r'''
import json
from pathlib import Path
from PySide6.QtCore import QMetaObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
app = QGuiApplication([])
eng = QQmlEngine()
here = Path('ui/qml/creative').resolve()
probe = b"""
import QtQuick
Item {
    id: root
    property var out: ({})
    CuApi { id: api; hostEndpoint: "http://127.0.0.1:18950"; hostToken: "t0ken-of-this-session" }
    QtObject {
        id: tabStub
        property bool connected: true
        property var service: api
        function log(level, event, message, data) {}
    }
    QtObject { id: proxyStub; property int status: Image.Ready; property real implicitWidth: 500 }
    QtObject {
        id: paneStub
        property bool hasRow: true
        property var tab: tabStub
        property real paneW: 800
        property real paneH: 600
        property real picX: -1000
        property real picY: -1000
        property var row: ({ mediaId: "m0123456789ab", jobId: "j0123456789ab", itemId: "i0123456789ab", resultRegionUrl: "" })
    }
    CuRegionImage { id: src; pane: paneStub; kind: "source"; proxy: proxyStub; layerWidth: 2000; layerHeight: 2000; drawnWidth: 8000 }
    CuRegionImage { id: res; pane: paneStub; kind: "result"; proxy: proxyStub; layerWidth: 2000; layerHeight: 2000; drawnWidth: 8000 }
    CuRegionImage {
        id: live; pane: paneStub; kind: "result"; proxy: proxyStub; layerWidth: 2000; layerHeight: 2000; drawnWidth: 8000
        baseUrl: "/api/jobs/j0123456789ab/items/i0123456789ab/live-region.jpg?seq=3"
    }
    function run() {
        src.update(); res.update(); live.update()
        out = { source: String(src.source), result: String(res.source), live: String(live.source) }
    }
}
"""
c = QQmlComponent(eng)
c.setData(probe, QUrl.fromLocalFile(str(here / '_tile_token_probe.qml')))
obj = c.create()
if obj is None:
    print(json.dumps({'errors': [e.toString() for e in c.errors()]}))
else:
    QMetaObject.invokeMethod(obj, 'run')
    app.processEvents()
    out = obj.property('out')
    print(json.dumps(out.toVariant() if hasattr(out, 'toVariant') else out))
'''


def test_each_tile_url_the_viewer_makes_in_qt_carries_the_token_once():
    """The source, result and live detail images of a zoomed-in view, through CuApi as the tab has it."""
    out = run_qt(TILE_URLS)
    assert 'errors' not in out, out
    paths = {'source': '/api/media/m0123456789ab/region', 'result': '/api/media/m0123456789ab/region',
             'live': '/api/jobs/j0123456789ab/items/i0123456789ab/live-region.jpg'}
    for kind, path in paths.items():
        url = urllib.parse.urlsplit(out[kind])
        query = urllib.parse.parse_qs(url.query)
        assert (url.scheme, url.netloc, url.path) == ('http', '127.0.0.1:18950', path), (kind, out[kind])
        assert query.get('token') == ['t0ken-of-this-session'], (kind, out[kind])
        assert all(len(query.get(k, [])) == 1 for k in ('x', 'y', 'w', 'h')), (kind, out[kind])
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(out['source']).query)['kind'] == ['source']
    assert urllib.parse.parse_qs(urllib.parse.urlsplit(out['result']).query)['kind'] == ['result']


class TheServiceAndTheTileToken(Base):
    def test_a_tile_with_the_token_in_its_query_is_served_and_one_without_is_refused(self):
        svc = self.service()
        code, res, _ = svc.post('/api/inputs', {'paths': [str(write_image(self.d / 'a.png', gradient(96, 80, 1)))]})
        self.assertEqual(code, 200, res)
        mid = res['items'][0]['id']
        path = f'/api/media/{mid}/region?kind=source&x=0&y=0&w=32&h=24'
        code, png, hdr = svc.get(path + '&token=' + svc.token, raw=True, auth=False)
        self.assertEqual((code, hdr['Content-Type'], hdr['X-Region']), (200, 'image/png', '0,0,32,24'))
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        for refused in (path, path + '&token=' + 'f' * len(svc.token)):
            code, body, _ = svc.get(refused, auth=False)
            self.assertEqual((code, body['error']['code'], body['error']['message']),
                             (401, 'unauthorized', 'This request does not belong to the current app session.'))

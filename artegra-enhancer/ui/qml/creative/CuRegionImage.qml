import QtQuick

Image {
    id: region

    property var pane: null
    property string kind: "source"
    property var proxy: null
    property real layerWidth: 0
    property real layerHeight: 0
    property real drawnWidth: 0
    property string baseUrl: ""
    property string stamp: ""
    property var shownGeom: null
    property var pendingGeom: null
    property var plateView: null
    property real layerScale: 1
    readonly property real density: layerWidth > 0 ? drawnWidth / layerWidth : 1

    asynchronous: true
    cache: false
    retainWhileLoading: true
    smooth: density < 2
    mipmap: false
    fillMode: Image.Stretch
    visible: shownGeom !== null && status === Image.Ready
    x: shownGeom ? Math.round(shownGeom.x * density) : 0
    y: shownGeom ? Math.round(shownGeom.y * density) : 0
    width: shownGeom ? Math.round((shownGeom.x + shownGeom.w) * density) - x : 0
    height: shownGeom ? Math.round((shownGeom.y + shownGeom.h) * density) - y : 0

    onStatusChanged: {
        if (status === Image.Ready && pendingGeom) { shownGeom = pendingGeom; pendingGeom = null }
        else if (status === Image.Error) {
            pendingGeom = null
            shownGeom = null
            if (pane && pane.tab && typeof pane.tab.log === "function")
                pane.tab.log("warning", "region_failed", "Could not load full-resolution detail for the " + kind + " image.", { source: String(source) })
        }
    }

    function clear() {
        source = ""
        shownGeom = null
        pendingGeom = null
    }

    function update() {
        if (!pane || !pane.hasRow || !pane.tab || !pane.tab.connected || layerWidth <= 0 || layerHeight <= 0 || !proxy
                || proxy.status !== Image.Ready || !region.visibleWanted) { clear(); return }
        var proxyDensity = proxy.implicitWidth / layerWidth
        if (density <= proxyDensity * 1.15) { clear(); return }
        var pad = 0.1
        var vw = pane.paneW, vh = pane.paneH
        var x0 = Math.max(0, Math.floor((-pane.picX - vw * pad) / density))
        var y0 = Math.max(0, Math.floor((-pane.picY - vh * pad) / density))
        var x1 = Math.min(layerWidth, Math.ceil((vw * (1 + pad) - pane.picX) / density))
        var y1 = Math.min(layerHeight, Math.ceil((vh * (1 + pad) - pane.picY) / density))
        var w = Math.round(x1 - x0), h = Math.round(y1 - y0)
        if (w < 8 || h < 8 || w > 4096 || h > 4096) { clear(); return }
        var g = { x: x0, y: y0, w: w, h: h, stamp: region.stamp }
        if (shownGeom && shownGeom.x === g.x && shownGeom.y === g.y && shownGeom.w === g.w && shownGeom.h === g.h
                && shownGeom.stamp === g.stamp) return
        if (pendingGeom && pendingGeom.x === g.x && pendingGeom.y === g.y && pendingGeom.w === g.w && pendingGeom.h === g.h
                && pendingGeom.stamp === g.stamp) return
        var row = pane.row
        var xywh = "x=" + g.x + "&y=" + g.y + "&w=" + g.w + "&h=" + g.h
        var base
        if (region.baseUrl !== "") base = region.baseUrl
        else if (kind === "result" && row.resultRegionUrl) base = row.resultRegionUrl
        else if (kind === "result") base = "/api/media/" + encodeURIComponent(row.mediaId) + "/region?kind=result&job=" + encodeURIComponent(row.jobId) + "&item=" + encodeURIComponent(row.itemId)
        else base = "/api/media/" + encodeURIComponent(row.mediaId) + "/region?kind=source"
        pendingGeom = g
        source = pane.tab.service.url(base + (base.indexOf("?") >= 0 ? "&" : "?") + xywh)
    }
    property bool visibleWanted: true

    Connections {
        target: region.pane
        ignoreUnknownSignals: true
        function onRowKeyChanged() { region.clear() }
    }
    Connections {
        target: region.proxy
        ignoreUnknownSignals: true
        function onStatusChanged() { if (region.proxy && region.proxy.status === Image.Ready) region.update() }
    }
}

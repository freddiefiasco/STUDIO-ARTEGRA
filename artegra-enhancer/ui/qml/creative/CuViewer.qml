import QtQuick
import QtQuick.Window
import "format.js" as F

Item {
    id: viewer
    property var tab: null
    property real reserveBottom: 0
    property bool dropping: false
    property string dropState: ""
    property int dropCount: 0
    property bool dropFolder: false
    property string dropWords: ""
    readonly property bool recessDrop: dropState === "recess" || (dropState === "" && dropping)

    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1

    property bool focusLayout: tab !== null && tab !== undefined
                               && (tab.panelsHidden !== undefined ? tab.panelsHidden === true : tab.traysAway === true)
    readonly property string span: tab && typeof tab.hiddenSpan === "string" && tab.hiddenSpan !== "" ? tab.hiddenSpan : Tokens.hiddenSpan
    readonly property bool windowSpan: focusLayout && span === "window"
    readonly property real hostWidth: parent ? parent.width : width
    readonly property real hostHs: parent ? Tokens.snap(parent.height, dpr) : height
    property real lineLeft: !focusLayout ? Tokens.openingInset : (windowSpan ? Tokens.openingInset - x : 0)
    property real lineRight: !focusLayout ? width - Tokens.openingInset : (windowSpan ? hostWidth - x - Tokens.openingInset : width)
    readonly property real availH: Math.max(0, height - reserveBottom)
    readonly property int toolH: Tokens.hToolLine
    readonly property int capSlot: Tokens.capSlot
    readonly property int blockAir: Tokens.blockAirMin
    readonly property int sideGap: Tokens.sp16
    readonly property int captionMin: Tokens.captionMin
    readonly property real textInset: lineLeft
    readonly property rect shellBlockRect: tab && tab.pictureBlockRect !== undefined && tab.pictureBlockRect !== null
                                           ? tab.pictureBlockRect : Qt.rect(0, 0, 0, 0)
    readonly property bool shellRect: shellBlockRect.width > 0 && shellBlockRect.height > 0
    readonly property real allowTop: shellRect ? Math.max(toolH, shellBlockRect.y - y) : toolH
    readonly property real windowFoot: windowSpan ? hostHs - y - 80 : 1e9
    readonly property real allowBottom: shellRect ? Math.min(availH, shellBlockRect.y + shellBlockRect.height - y)
                                                  : Math.min(availH, windowFoot)
    readonly property real allowH: Math.max(0, allowBottom - allowTop)

    readonly property var row: tab ? tab.selectedRow : null
    readonly property bool hasRow: row !== null && row !== undefined
    readonly property string rowKey: hasRow ? String(row.key || "") : ""
    readonly property string status: hasRow ? String(row.status || "") : ""
    readonly property bool isJob: hasRow && row.kind === "job"
    readonly property bool hasResult: isJob && status === "done" && row.resultReady !== false
    readonly property bool busy: isJob && F.contains(F.BUSY_ITEM_STATES, status)
    readonly property bool halted: isJob && (status === "stopped" || status === "cancelled" || status === "failed")
    readonly property bool batchActive: tab !== null && tab.batch !== undefined && tab.batch.active === true
    readonly property bool layoutInResult: isJob && status !== "queued" && status !== "interrupted" && (row.outW > 0 || hasResult)
    readonly property real pw: !hasRow ? 0 : layoutInResult ? (row.outW > 0 ? row.outW : row.srcW * Math.max(1, row.factor)) : row.srcW
    readonly property real ph: !hasRow ? 0 : layoutInResult ? (row.outH > 0 ? row.outH : row.srcH * Math.max(1, row.factor)) : row.srcH
    readonly property real layerFactor: hasRow && row.srcW > 0 ? pw / row.srcW : 1
    readonly property var inputRecord: hasRow && tab && typeof tab.inputFor === "function" ? tab.inputFor(row.mediaId) : null
    readonly property bool hasAlpha: hasRow && (row.alpha === true || (inputRecord !== null && inputRecord.alpha === true))
    readonly property var mask: hasRow && tab && typeof tab.maskFor === "function" ? tab.maskFor(row.mediaId) : null
    readonly property bool maskShown: mask !== null && tab.maskVisible === true
    readonly property bool maskStale: mask !== null && mask.signature !== tab.protectSignature
    readonly property bool problem: tab !== null && tab.engineState === "problem"
    readonly property string sourcePath: !hasRow ? "" : row.proxyUrl ? String(row.proxyUrl) : "/api/media/" + encodeURIComponent(row.mediaId) + "/proxy"
    readonly property string resultPath: !hasResult ? "" : row.resultProxyUrl ? String(row.resultProxyUrl)
        : "/api/media/" + encodeURIComponent(row.mediaId) + "/proxy?kind=result&job=" + encodeURIComponent(row.jobId) + "&item=" + encodeURIComponent(row.itemId)
    readonly property string sourceUrl: sourcePath !== "" && tab && tab.everConnected ? tab.service.mediaUrl(sourcePath) : ""
    readonly property string resultUrl: resultPath !== "" && tab && tab.everConnected ? tab.service.mediaUrl(resultPath) : ""
    readonly property bool sizedCopies: features !== null && features.sized_proxy === true
    function sizedUrl(path, w, h) {
        if (path === "" || !(w > 0 && h > 0) || !tab || !tab.everConnected) return ""
        return tab.service.mediaUrl(path + (path.indexOf("?") >= 0 ? "&" : "?") + "w=" + Math.round(w) + "&h=" + Math.round(h))
    }
    function sourceProxyUrl() { return sourceUrl }
    function resultProxyUrl() { return resultUrl }

    CuLiveFeed {
        id: feed
        tab: viewer.tab
        busy: viewer.batchActive
        wantedQuiet: viewer.tab !== null && viewer.tab.visible === true
                     && (viewer.halted || viewer.tab.wantsLastFrames === true)
    }
    property alias liveFeed: feed
    readonly property var liveItem: hasRow && isJob && (busy || status === "stopped" || status === "failed") ? feed.itemFor(row) : null
    readonly property string liveState: liveItem ? String(liveItem.state || "") : ""
    readonly property var passOrder: liveItem && liveItem.pass_order && liveItem.pass_order.length === 2
                                     ? liveItem.pass_order : ["structure", "detail"]
    readonly property bool creativeFirst: passOrder[0] === "detail"
    readonly property var earlierPass: liveItem && liveItem.earlier_pass && liveItem.earlier_pass.url ? liveItem.earlier_pass : null
    readonly property bool earlierShown: creativeFirst && earlierPass !== null
    readonly property string liveUrlNow: !liveItem || !tab || !tab.service ? ""
                                         : earlierShown ? tab.service.mediaUrl(earlierPass.url) : feed.canvasUrl(liveItem)
    property string lastLiveUrl: ""
    onLiveUrlNowChanged: {
        if (liveUrlNow === "") return
        var cu = earlierShown && liveItem ? String(feed.canvasUrl(liveItem) || "") : ""
        lastLiveUrl = cu !== "" ? cu : liveUrlNow
    }
    readonly property string liveUrl: liveUrlNow !== "" ? liveUrlNow : (landing ? lastLiveUrl : "")
    readonly property var liveSize: earlierShown && earlierPass.size ? earlierPass.size : (liveItem && liveItem.canvas_size ? liveItem.canvas_size : null)
    readonly property real liveNaturalW: liveSize ? Number(liveSize[0]) : 0
    readonly property real liveNaturalH: liveSize ? Number(liveSize[1]) : 0
    readonly property var liveRects: liveItem && liveState === "sampling" && liveItem.rects ? liveItem.rects : []
    readonly property bool liveFrameAvailable: liveUrlNow !== "" && (busy || halted)
    readonly property bool liveFrameServed: liveFrameAvailable && !(tilePending && pendingKind === "queue")
    readonly property string liveRegionBase: liveItem && liveItem.region_url && !earlierShown ? String(liveItem.region_url) : ""
    readonly property string liveSeq: liveItem && liveItem.image_seq !== undefined ? String(liveItem.image_seq) : ""
    onLiveSeqChanged: { if (pastFit && liveRegionBase !== "" && !liveRegionTimer.running) liveRegionTimer.start() }
    Timer { id: liveRegionTimer; interval: 1000; onTriggered: viewer.regionsNow() }
    readonly property bool roughPreview: liveItem !== null && (liveItem.preview === "rough" || liveItem.fallback === true)
    readonly property real liveMagnification: liveNaturalW > 0 && picDW > 0 ? picDW / liveNaturalW : 1
    readonly property bool liveRegionsOn: liveRegionBase !== "" && pastFit && !hasAlpha
    readonly property real liveRegionScale: liveItem && Number(liveItem.region_scale) > 0 ? Number(liveItem.region_scale) : 1
    readonly property real liveRegionMagnification: pw > 0 && picDW > 0 ? picDW / (pw * liveRegionScale) : 1
    readonly property bool liveEnlarged: afterKind === "live" && busy
                                         && (liveRegionsOn ? liveRegionMagnification : liveMagnification) > 1.5
    readonly property string previewName: roughPreview ? "Live, rough preview" : "Live, detailed preview"
    readonly property string liveTip: previewName + (liveEnlarged ? ", enlarged" : "") + ". Hold Space for the original."
    readonly property bool liveMissing: busy && (!feed.featureOn || !feed.supported)

    property string viewMode: "after"
    property bool sideBySide: false
    property bool holdBefore: false
    property bool loupeOn: false
    readonly property bool secondAvailable: hasResult || liveFrameAvailable
    readonly property bool compareAvailable: hasResult || liveFrameAvailable
    readonly property bool sideAvailable: hasResult
    readonly property string secondLabel: hasResult ? "After" : (busy ? "Live" : (halted ? "Last frame" : "After"))
    readonly property string effectiveView: holdBefore || !secondAvailable ? "before"
                                            : (viewMode === "split" && !compareAvailable ? "after" : viewMode)
    readonly property string viewCell: effectiveView
    readonly property string compareLayout: effectiveView === "split" ? (sideBySide && sideAvailable ? "side" : "split") : "single"
    readonly property bool splitActive: compareLayout === "split"
    readonly property string afterKind: hasResult ? "result" : (liveFrameAvailable ? "live" : "none")
    readonly property bool compare: effectiveView === "split"
    readonly property bool beforeOnly: effectiveView === "before"
    property bool showBefore: false
    property real splitPos: 0.5

    function chooseView(value) {
        if (value === "split" && !compareAvailable) return
        if (value === "split" && viewMode === "split") { if (sideAvailable) sideBySide = !sideBySide; return }
        viewMode = value
    }
    function toggleBeforeAfter() {
        if (!secondAvailable) return
        viewMode = effectiveView === "before" ? "after" : "before"
    }
    function toggleCompare() {
        if (!compareAvailable) return
        viewMode = effectiveView === "split" ? "after" : "split"
    }
    function toggleSplit() {
        if (!compareAvailable) return
        if (effectiveView === "split" && compareLayout === "split") viewMode = "after"
        else { viewMode = "split"; sideBySide = false }
    }
    function toggleSideBySide() {
        if (!sideAvailable) return
        if (effectiveView === "split" && sideBySide) { sideBySide = false; viewMode = "after" }
        else { viewMode = "split"; sideBySide = true }
    }

    readonly property real boxW: Math.max(0, lineRight - lineLeft)
    readonly property real boxH: Math.max(0, allowH - 2 * blockAir - capSlot)
    readonly property real paneBoxW: compareLayout === "side" ? Tokens.snap((boxW - sideGap) / 2, dpr) : boxW
    readonly property real aspect: hasRow && row.srcW > 0 && row.srcH > 0 ? row.srcW / row.srcH : (pw > 0 && ph > 0 ? pw / ph : 1.6)
    readonly property bool fitWide: boxH <= 0 || aspect >= paneBoxW / boxH
    readonly property real fitLW: !hasRow || pw <= 0 ? 0 : Math.max(Tokens.px(1, dpr), fitWide ? Tokens.snap(paneBoxW, dpr) : Tokens.snap(boxH * aspect, dpr))
    readonly property real fitLH: !hasRow || pw <= 0 ? 0 : Math.max(Tokens.px(1, dpr), fitWide ? Tokens.snap(paneBoxW / aspect, dpr) : Tokens.snap(boxH, dpr))
    readonly property real fitScale: pw > 0 ? fitLW / pw : 1
    readonly property real fitZoom: fitScale * dpr
    readonly property real minZoom: Math.min(fitZoom, 0.02)
    readonly property real maxZoom: 8

    property string zoomMode: "fit"
    property real zoom: 1
    property real offX: 0
    property real offY: 0
    readonly property bool pastFit: hasRow && zoomMode === "manual" && zoom > fitZoom * 1.0005
    readonly property bool freeZoom: hasRow && zoomMode === "manual" && Math.abs(zoom - 1) >= 0.001
    readonly property string fitFigure: pw > 0 ? F.percent(Math.max(1, Math.round(fitZoom * 100))) : ""
    readonly property string zoomFigure: F.percent(Math.round(zoom * 100))
    onFitZoomChanged: { if (zoomMode === "fit") zoom = fitZoom }

    readonly property real drawScale: zoomMode === "fit" ? fitScale : zoom / dpr
    readonly property real picLW: !hasRow || pw <= 0 ? 0 : zoomMode === "fit" ? fitLW : Math.max(Tokens.px(2, dpr), Tokens.snap(pw * drawScale, dpr))
    readonly property real picLH: !hasRow || ph <= 0 ? 0 : zoomMode === "fit" ? fitLH : Math.max(Tokens.px(2, dpr), Tokens.snap(ph * drawScale, dpr))
    readonly property real blockTop: Math.max(allowTop, Tokens.snap(allowTop + (allowH - picLH - capSlot) / 2, dpr))
    readonly property real fitLX: Tokens.snap(lineLeft + (paneBoxW - picLW) / 2, dpr)
    readonly property real fitRightLX: Tokens.snap(lineLeft + paneBoxW + sideGap + (paneBoxW - picLW) / 2, dpr)

    readonly property real capPastY: Tokens.snap(Math.max(allowTop + 40, allowBottom - blockAir - capSlot), dpr)
    readonly property int vpDX: Math.round(lineLeft * dpr)
    readonly property int vpDX1: Math.round(lineRight * dpr)
    readonly property int vpDY: Math.round(allowTop * dpr)
    readonly property int vpDY1: Math.round(capPastY * dpr)
    readonly property int vpDW: Math.max(0, vpDX1 - vpDX)
    readonly property int vpDH: Math.max(0, vpDY1 - vpDY)
    readonly property int sideGapD: Math.round(sideGap * dpr)
    readonly property int leftDW: compareLayout === "side" ? Math.floor((vpDW - sideGapD) / 2) : vpDW
    readonly property int rightDX: vpDX + leftDW + sideGapD
    readonly property int rightDW: Math.max(0, vpDW - leftDW - sideGapD)
    readonly property int pastDW: Math.round(pw * zoom)
    readonly property int pastDH: Math.round(ph * zoom)
    function clampOff(o, pic, view) { return pic <= view ? Math.round((view - pic) / 2) : Math.max(view - pic, Math.min(0, Math.round(o))) }
    readonly property int offXc: clampOff(offX, pastDW, leftDW)
    readonly property int offYc: clampOff(offY, pastDH, vpDH)
    property int _lastLeftDW: 0
    property int _lastVpDH: 0
    onLeftDWChanged: { if (pastFit && _lastLeftDW > 0) offX = offXc + Math.round((leftDW - _lastLeftDW) / 2); _lastLeftDW = leftDW }
    onVpDHChanged: { if (pastFit && _lastVpDH > 0) offY = offYc + Math.round((vpDH - _lastVpDH) / 2); _lastVpDH = vpDH }

    readonly property int mainDevX: pastFit ? vpDX : Math.round(fitLX * dpr)
    readonly property int mainDevY: pastFit ? vpDY : Math.round(blockTop * dpr)
    readonly property int mainDevW: pastFit ? leftDW : Math.round(picLW * dpr)
    readonly property int mainDevH: pastFit ? vpDH : Math.round(picLH * dpr)
    readonly property int mainPicDX: pastFit ? vpDX + offXc : mainDevX
    readonly property int mainPicDY: pastFit ? vpDY + offYc : mainDevY
    readonly property int picDW: pastFit ? pastDW : mainDevW
    readonly property int picDH: pastFit ? pastDH : mainDevH
    readonly property int rightDevX: pastFit ? rightDX : Math.round(fitRightLX * dpr)
    readonly property int rightDevW: pastFit ? rightDW : mainDevW
    readonly property int rightPicDX: pastFit ? rightDX + offXc : rightDevX

    function visRect(paneX, paneY, paneW, paneH, px, py, pwd, phd) {
        var x0 = Math.max(paneX, px), y0 = Math.max(paneY, py)
        var x1 = Math.min(paneX + paneW, px + pwd), y1 = Math.min(paneY + paneH, py + phd)
        if (x1 <= x0 || y1 <= y0) return Qt.rect(0, 0, 0, 0)
        return Qt.rect(x0 / dpr, y0 / dpr, (x1 - x0) / dpr, (y1 - y0) / dpr)
    }
    readonly property rect mainVis: hasRow && pw > 0 ? visRect(mainDevX, mainDevY, mainDevW, mainDevH, mainPicDX, mainPicDY, picDW, picDH) : Qt.rect(0, 0, 0, 0)
    readonly property rect rightVis: hasRow && pw > 0 && compareLayout === "side"
                                     ? visRect(rightDevX, mainDevY, rightDevW, mainDevH, rightPicDX, mainPicDY, picDW, picDH) : Qt.rect(0, 0, 0, 0)
    readonly property rect pictureRect: {
        if (rightVis.width <= 0) return mainVis
        var x0 = Math.min(mainVis.x, rightVis.x), y0 = Math.min(mainVis.y, rightVis.y)
        return Qt.rect(x0, y0, Math.max(mainVis.x + mainVis.width, rightVis.x + rightVis.width) - x0,
                       Math.max(mainVis.y + mainVis.height, rightVis.y + rightVis.height) - y0)
    }
    readonly property real picSpanX: fitLX
    readonly property real picSpanW: compareLayout === "side" ? fitRightLX + picLW - fitLX : picLW
    readonly property real capX: pastFit ? lineLeft
                                 : (picSpanW >= captionMin ? picSpanX
                                    : Tokens.snap(Math.max(lineLeft, picSpanX + (picSpanW - captionMin) / 2), dpr))
    readonly property real capW: pastFit ? boxW : Math.min(boxW, Math.max(picSpanW, captionMin))
    readonly property real capY: pastFit ? capPastY : blockTop + picLH
    readonly property real barX: pastFit ? 0 : picSpanX - capX
    readonly property real barW: pastFit ? capW : picSpanW
    readonly property rect captionRect: hasRow ? Qt.rect(capX, capY, capW, capSlot) : Qt.rect(0, 0, 0, 0)
    readonly property rect toolLineRect: Qt.rect(lineLeft, 0, Math.max(0, lineRight - lineLeft), toolH)
    readonly property bool recessWide: boxH <= 0 || 1.6 >= boxW / boxH
    readonly property real recessW: recessWide ? Tokens.snap(boxW, dpr) : Tokens.snap(boxH * 1.6, dpr)
    readonly property real recessH: recessWide ? Tokens.snap(boxW / 1.6, dpr) : Tokens.snap(boxH, dpr)
    readonly property real recessX: Tokens.snap(lineLeft + (boxW - recessW) / 2, dpr)
    readonly property real recessY: Math.max(allowTop, Tokens.snap(allowTop + (allowH - recessH - capSlot) / 2, dpr))
    readonly property rect recessRect: hasRow ? Qt.rect(0, 0, 0, 0) : Qt.rect(recessX, recessY, recessW, recessH)
    readonly property real portWidth: pastFit ? vpDW / dpr : boxW
    readonly property real portHeight: pastFit ? vpDH / dpr : boxH
    readonly property int seamDX: splitActive && mainVis.width > 0 ? Math.round(mainVis.x * dpr + splitPos * mainVis.width * dpr) : -1
    readonly property rect splitSpan: mainVis
    readonly property bool seamLit: seamHandle.lit
    readonly property rect viewFraction: pastFit && pastDW > 0 && pastDH > 0
        ? Qt.rect(Math.max(0, -offXc / pastDW), Math.max(0, -offYc / pastDH), Math.min(1, leftDW / pastDW), Math.min(1, vpDH / pastDH))
        : Qt.rect(0, 0, 1, 1)
    readonly property bool navigatorShown: pastFit && hasRow
    readonly property string navigatorUrl: hasResult ? resultUrl : sourceUrl
    readonly property bool pictureShown: hasRow && mainPane.anyReady
    readonly property string navigatorPlace: tab && typeof tab.navigatorPlace === "string" && tab.navigatorPlace !== ""
                                             ? tab.navigatorPlace : (!focusLayout ? "leg" : (windowSpan ? "floating" : "stack"))

    function tipKeepClearRects() {
        var out = []
        if (pictureRect.width > 0 && pictureRect.height > 0) out.push(pictureRect)
        if (loupeShown) out.push(Qt.rect(loupeLX, loupeLY, loupeSize, loupeSize))
        if (floatingNav.visible) out.push(Qt.rect(floatingNav.x, floatingNav.y, floatingNav.width, floatingNav.height))
        return out
    }

    function currentPic(paneIndex) {
        var x = paneIndex === 1 ? rightPicDX : mainPicDX
        return { x: x, y: mainPicDY, w: picDW, h: picDH }
    }
    function paneAt(cx) { return compareLayout === "side" && cx * dpr >= rightDevX - sideGapD / 2 ? 1 : 0 }
    function zoomAround(newZoom, cx, cy) {
        if (!hasRow || pw <= 0) return
        var z = Math.max(minZoom, Math.min(maxZoom, newZoom))
        var pi = paneAt(cx)
        var cur = currentPic(pi)
        var cxd = cx * dpr, cyd = cy * dpr
        var u = Math.max(0, Math.min(pw, (cxd - cur.x) * pw / Math.max(1, cur.w)))
        var v = Math.max(0, Math.min(ph, (cyd - cur.y) * ph / Math.max(1, cur.h)))
        if (Math.abs(z - fitZoom) < fitZoom * 0.0005) { fit(); return }
        zoomMode = "manual"
        zoom = z
        if (z > fitZoom) {
            offX = cxd - u * z - (pi === 1 ? rightDX : vpDX)
            offY = cyd - v * z - vpDY
        }
        regionTimer.restart()
    }
    function zoomBy(f) {
        var c = mainVis.width > 0 ? Qt.point(mainVis.x + mainVis.width / 2, mainVis.y + mainVis.height / 2)
                                  : Qt.point(width / 2, availH / 2)
        zoomAround(zoom * f, c.x, c.y)
    }
    function actualSize() {
        if (!hasRow || pw <= 0) return
        var u = pw / 2, v = ph / 2
        if (pastFit) {
            u = (leftDW / 2 - offXc) / zoom
            v = (vpDH / 2 - offYc) / zoom
        }
        zoomMode = "manual"
        zoom = 1
        offX = leftDW / 2 - u
        offY = vpDH / 2 - v
        if (Math.abs(1 - fitZoom) < 0.0005) zoomMode = "fit"
        regionTimer.restart()
    }
    function fit() {
        zoomMode = "fit"
        zoom = fitZoom
        regionTimer.restart()
    }
    function panBy(dx, dy) {
        if (!pastFit) return false
        offX = (Math.abs(offX - offXc) < 1 ? offX : offXc) + dx * dpr
        offY = (Math.abs(offY - offYc) < 1 ? offY : offYc) + dy * dpr
        regionTimer.restart()
        return true
    }
    function centreOn(fx, fy) {
        if (!pastFit) return
        offX = leftDW / 2 - fx * pastDW
        offY = vpDH / 2 - fy * pastDH
        regionTimer.restart()
    }
    property real _lastPw: 0
    onPwChanged: {
        if (zoomMode === "manual" && _lastPw > 0 && pw > 0) zoom = zoom * _lastPw / pw
        _lastPw = pw
        regionTimer.restart()
    }
    function holdFor(item) {}

    Keys.onPressed: (event) => {
        var step = (event.modifiers & Qt.ShiftModifier) ? 240 : 48
        var moved = false
        if (event.key === Qt.Key_Left) moved = panBy(step, 0)
        else if (event.key === Qt.Key_Right) moved = panBy(-step, 0)
        else if (event.key === Qt.Key_Up) moved = panBy(0, step)
        else if (event.key === Qt.Key_Down) moved = panBy(0, -step)
        if (moved) event.accepted = true
    }

    property bool landing: false
    property real liveOpacity: 1
    property string _shownKey: ""
    property bool _wasBusy: false
    onRowChanged: {
        var r = viewer.row
        var key = r ? String(r.key || "") : ""
        var nowBusy = !!r && r.kind === "job" && F.contains(F.BUSY_ITEM_STATES, String(r.status))
        var nowDone = !!r && r.kind === "job" && r.status === "done" && r.resultReady !== false
        if (key !== _shownKey) {
            _shownKey = key
            landing = false
            landAnim.stop()
            liveOpacity = 1
            lastLiveUrl = ""
        } else if (_wasBusy && nowDone && lastLiveUrl !== "") {
            landing = true
            landCheck.restart()
        }
        _wasBusy = nowBusy
        regionTimer.restart()
    }
    Timer {
        id: landCheck
        interval: 50
        repeat: true
        property int ticks: 0
        onRunningChanged: if (running) ticks = 0
        onTriggered: {
            ticks += 1
            if (!viewer.landing) { stop(); return }
            if (mainPane.resultReady || rightPane.resultReady) { stop(); viewer.resultLoaded() }
            else if (ticks > 60) { stop(); viewer.landing = false }
        }
    }
    function resultLoaded() {
        if (!landing || landAnim.running) return
        if (Tokens.durReveal <= 0) { landing = false; return }
        landAnim.restart()
    }
    NumberAnimation {
        id: landAnim
        target: viewer
        property: "liveOpacity"
        from: 1
        to: 0
        duration: Tokens.durReveal
        easing.type: Easing.OutCubic
        onFinished: { viewer.landing = false; viewer.liveOpacity = 1 }
    }

    function formatOf(name) {
        var m = /\.([A-Za-z0-9]+)$/.exec(String(name || ""))
        if (!m) return ""
        var e = m[1].toLowerCase()
        return e === "jpg" || e === "jpeg" ? "JPEG" : e === "png" ? "PNG" : (e === "tif" || e === "tiff") ? "TIFF"
             : e === "webp" ? "WebP" : e === "bmp" ? "BMP" : e.toUpperCase()
    }
    function bytesText(n) { return F.bytesText(n) }
    readonly property string transparency: {
        if (!hasRow || !hasAlpha) return "none"
        var t = row.transparency !== undefined ? String(row.transparency) : ""
        if (t === "kept" || t === "not_kept") return t
        var fmt = tab && tab.outputFormat !== undefined ? String(tab.outputFormat) : "png8"
        return /jpe?g/i.test(fmt) ? "not_kept" : "kept"
    }
    readonly property string transparencyWords: transparency === "kept" ? "with transparency"
                                                : transparency === "not_kept" ? "transparency not kept in JPEG" : ""
    readonly property bool failedShown: isJob && status === "failed"
    readonly property bool doneActionsShown: hasResult
    readonly property bool useSettingsSupported: tab !== null && typeof tab.useSettingsFrom === "function"
    readonly property string captionName: hasResult && String(row.output || "") !== "" ? F.basename(String(row.output))
                                          : (hasRow ? String(row.name || "") : "")
    readonly property string captionFact: {
        if (!busy || savedWaiting) return ""
        return F.facts([F.sizePair(row.srcW, row.srcH, row.outW, row.outH), transparencyWords])
    }
    readonly property string captionFacts: {
        if (!hasRow || busy || halted || refusedInput !== null) return ""
        if (hasResult) {
            var b = Number(row.outputBytes || 0)
            return F.facts([F.sizePair(row.srcW, row.srcH, pw, ph), formatOf(row.output || ""), b > 0 ? F.bytesText(b) : "",
                            hasAlpha && transparency === "kept" ? "with transparency" : ""])
        }
        if (row.kind === "input" && String(row.notes || "") !== "") return String(row.notes).split("\n")[0]
        return F.facts([F.size(row.srcW, row.srcH), formatOf(row.name), transparencyWords])
    }
    readonly property string captionSizes: captionFact !== "" ? captionFact : captionFacts
    readonly property bool savedWaiting: isJob && status === "finishing" && F.waitingWords(row.message) === "Waiting for the output folder"
    function passName(p) { return p === "structure" ? "Structure pass" : p === "detail" ? "Detail pass" : "" }
    function passWord(p) { return p === "structure" ? "structure pass" : p === "detail" ? "detail pass" : "" }
    readonly property var feedPass: {
        if (!busy) return { pass: "", step: 0 }
        var sp = Math.max(0, Math.min(1, Number(row.stageProgress) || 0))
        if (sp < 0.5) return { pass: "structure", step: Math.max(1, Math.min(30, Math.floor(sp * 60) + 1)) }
        return { pass: "detail", step: Math.max(1, Math.min(30, Math.floor((sp - 0.5) * 60) + 1)) }
    }
    readonly property bool liveSays: liveItem !== null && liveItem !== undefined && liveState !== ""
    readonly property int stageCount: liveItem ? Number(liveItem.stages || 1) : Number(row ? row.stages || 1 : 1)
    readonly property int stageNow: (liveItem ? Number(liveItem.stage || 0) : Number(row ? row.stage || 0 : 0)) + 1
    readonly property string stageWords: stageCount > 1 ? "stage " + stageNow + " of " + stageCount : ""
    readonly property string readingA: {
        if (!hasRow || (tab && tab.reconnecting)) return ""
        if (savedWaiting) return "Finished, waiting to be saved"
        if (!busy) return ""
        if (status === "preparing" || liveState === "preparing") return "Preparing"
        if (status === "finishing" || liveState === "finishing") return "Finishing"
        if (liveSays && liveItem && liveState === "between") {
            var ended = Number(liveItem.step || 0) >= Number(liveItem.steps || 30)
            var nextPass = ended ? (passOrder[0] === String(liveItem.pass) ? passOrder[1] : passOrder[0]) : String(liveItem.pass || passOrder[0])
            return passName(nextPass)
        }
        if (liveSays && liveItem && liveItem.pass) return passName(String(liveItem.pass))
        return passName(feedPass.pass)
    }
    readonly property string readingB: {
        if (!hasRow || !busy || readingA === "" || savedWaiting) return ""
        if (readingA === "Preparing") return String(row.message || "") === "Starting the engine" ? "Models load once, about 3 min" : ""
        if (readingA === "Finishing") return ""
        if (liveSays && liveItem && liveState === "between") return "starting"
        if (liveSays && liveItem && liveItem.step) return F.stepOf(liveItem.step, liveItem.steps || 30)
        return F.stepOf(feedPass.step, 30)
    }
    readonly property bool readingBQuiet: readingA === "Preparing" && readingB !== ""
    readonly property string stateLine: {
        if (readingA === "") return ""
        if (readingBQuiet || readingB === "") return readingA
        return F.facts([readingA, readingB, stageWords])
    }
    function atWords(at) {
        if (!at || !at.pass) return ""
        return "in the " + passWord(String(at.pass)) + (Number(at.step) > 0 ? ", " + F.stepOf(at.step, at.steps || 30) : "")
    }
    readonly property string failText: !failedShown ? "" : String(row.errorText || "").replace(/\s+in pass \d+ of \d+/, "").replace(/\s+$/, "")
    readonly property string failCause: {
        if (!failedShown) return ""
        var t = failText
        var m = /^(.*?[.!?])(\s|$)/.exec(t)
        if (m && m[1].length < t.length) t = m[1]
        return t === "" ? "The engine stopped on this image." : t
    }
    readonly property string haltLine: {
        if (!halted) return ""
        var at = row.at || null
        if (status === "failed") {
            var pw = at && at.pass ? passWord(String(at.pass)) : ""
            if (pw === "") return failCause
            var oom = /^GPU (\d+) ran out of memory[^.]*\.$/.exec(failCause)
            if (oom) return "The " + pw + " ran out of memory on GPU " + oom[1] + "."
            if (/^The graphics card ran out of memory[^.]*\.$/.test(failCause)) return "The " + pw + " ran out of memory."
            return "In the " + pw + ": " + failCause
        }
        var lead = status === "cancelled" ? "Cancelled" : "Stopped"
        var aw = atWords(at)
        return aw !== "" ? lead + " " + aw : lead + " before it started"
    }
    readonly property bool captionSaysState: stateLine !== "" || haltLine !== ""
    readonly property bool rulerShown: busy && !savedWaiting && status !== "preparing" && liveState !== "preparing"
    readonly property var barSegments: [1, 1]
    readonly property real barValue: {
        if (!rulerShown) return 0
        if (status === "finishing" || liveState === "finishing") return 1
        if (liveSays && liveItem && liveItem.pass) {
            var idx = Math.max(0, passOrder.indexOf(String(liveItem.pass)))
            var steps = Math.max(1, Number(liveItem.steps || 30))
            var st = Number(liveItem.step || 0)
            if (liveState === "between") return (idx + (st >= steps ? 1 : 0)) / 2
            var sp = liveItem.step_progress !== undefined && liveItem.step_progress !== null ? Number(liveItem.step_progress) : 0
            return Math.max(0, Math.min(1, (idx + Math.max(0, st - 1 + sp) / steps) / 2))
        }
        return Math.max(0, Math.min(1, Number(row.stageProgress) || 0))
    }
    readonly property string rulerPass: rulerShown && liveSays && liveItem && liveItem.pass ? String(liveItem.pass) : (rulerShown ? feedPass.pass : "")
    readonly property int rulerStep: rulerShown ? (liveSays && liveItem && liveItem.step ? Number(liveItem.step) : feedPass.step) : 0
    readonly property int rulerTotal: liveSays && liveItem && liveItem.steps ? Number(liveItem.steps) : 30
    readonly property string rulerTip: {
        if (!rulerShown) return ""
        var t = stateLine
        var s = liveItem && liveItem.timing && liveItem.timing.step_s ? Number(liveItem.timing.step_s) : 0
        if (s > 0 && liveState === "sampling") t += ", " + Math.round(s) + " s a step"
        if (stageWords !== "" && t.indexOf("stage") < 0) t += ", " + stageWords
        return t
    }
    readonly property var features: tab && tab.health && tab.health.features ? tab.health.features : null
    readonly property bool stopSupported: tab !== null && (tab.stopImageSupported !== undefined ? tab.stopImageSupported === true
                                                           : (typeof tab.stopImage === "function" || (features !== null && features.stop_image === true)))
    readonly property bool requeueSupported: tab !== null && (typeof tab.queueAgain === "function" || typeof tab.requeueImage === "function"
                                                              || (features !== null && features.requeue === true))
    readonly property bool settingsChanged: hasRow && (row.settingsChanged === true || row.settings_changed === true)
    readonly property var refusedInput: hasRow && row.kind === "input" && row.status === "refused" && tab ? tab.inputFor(row.mediaId) : null
    readonly property int refusedFallback: refusedInput !== null && typeof tab.largestFactor === "function" ? tab.largestFactor(refusedInput) : 0
    readonly property string refusalLine: refusedInput !== null && typeof tab.refusalText === "function"
                                          ? tab.refusalText(tab.planForInput(refusedInput, tab.scale), tab.scale) : ""
    readonly property int retrySmaller: failedShown && tab && tab.controlsInfo ? F.smallerScale(row.factor, tab.controlsInfo.scales) : 0
    property bool actionBusy: false
    property string pendingKey: ""
    property string pendingKind: ""
    property string pendingStatus: ""
    readonly property bool tilePending: pendingKey !== "" && pendingKey === rowKey
                                        && (pendingKind === "stop" ? busy && status !== "finishing" : status === pendingStatus)
    function markPending(kind) { pendingKey = rowKey; pendingKind = kind; pendingStatus = status; pendingTimer.restart() }
    function clearPending() { pendingKey = ""; pendingTimer.stop() }
    Timer { id: pendingTimer; interval: 15000; onTriggered: viewer.pendingKey = "" }
    onStatusChanged: {
        if (pendingKey !== "" && pendingKey === rowKey
                && (pendingKind === "stop" ? !busy : status !== pendingStatus)) clearPending()
    }
    readonly property string tileKind: {
        if (!hasRow || (tab && tab.reconnecting)) return ""
        if (busy && status !== "finishing" && stopSupported) return "stop"
        if ((status === "stopped" || status === "cancelled") && requeueSupported) return "queue"
        if (refusedInput !== null && refusedFallback > 0) return "smaller"
        return ""
    }
    readonly property string tileLabel: tileKind === "stop" ? (tilePending ? "Stopping…" : "Stop this image")
        : tileKind === "queue" ? (settingsChanged ? "Queue again with these settings" : "Queue again")
        : tileKind === "smaller" ? (tab && typeof tab.useFactorFor === "function" ? "Use " + F.factor(refusedFallback)
                                                                                 : "Upscale this one at " + F.factor(refusedFallback))
        : ""
    readonly property string tileTip: tilePending ? ""
        : tileKind === "stop" ? Tokens.keyTip("Stops this image now. The rest of the batch carries on.", "Ctrl+Shift+.")
        : tileKind === "queue" ? (settingsChanged ? "First in line, with the changed settings" : "First in line, with the settings it ran with")
        : tileKind === "smaller" ? "Upscales this image at " + F.factor(refusedFallback) + ". The others keep " + F.factor(tab.scale) + "."
        : ""
    readonly property bool tileMenu: tileKind === "queue" && settingsChanged
    readonly property string asBeforeLabel: "Queue again as before"
    readonly property string noteText: failedShown ? haltLine : (refusedInput !== null ? refusalLine
                                       : (hasRow && row.kind === "input" && String(row.notes || "") !== "" ? String(row.notes).split("\n")[0] : ""))
    readonly property bool noteQuiet: !failedShown && refusedInput === null

    property double tileQuietUntil: 0
    property string _tileKindWas: ""
    property string _tileRowWas: ""
    onTileKindChanged: {
        if (_tileKindWas !== "" && tileKind !== "" && _tileKindWas !== tileKind && _tileRowWas === rowKey)
            tileQuietUntil = Date.now() + 700
        _tileKindWas = tileKind
        _tileRowWas = rowKey
    }
    onRowKeyChanged: { _tileKindWas = tileKind; _tileRowWas = rowKey }
    function tileClicked() {
        if (Date.now() < tileQuietUntil) return
        tileQuietUntil = Date.now() + 700
        if (tileKind === "stop") stopThisImage()
        else if (tileKind === "queue") queueAgain(false)
        else if (tileKind === "smaller") {
            if (typeof tab.useFactorFor === "function") tab.useFactorFor([row], refusedFallback)
            else tab.startInputAt(row.mediaId, refusedFallback)
        }
    }
    function stopThisImage() {
        if (!hasRow || !busy || actionBusy || tilePending) return
        var r = row
        markPending("stop")
        if (typeof tab.stopImage === "function") { tab.stopImage(r); return }
        actionBusy = true
        tab.service.post("/api/cancel?image=" + encodeURIComponent(r.mediaId) + "&job=" + encodeURIComponent(r.jobId)
                         + "&item=" + encodeURIComponent(r.itemId), {}, function(err, data) {
            viewer.actionBusy = false
            if (err) {
                viewer.clearPending()
                if (typeof viewer.tab.showError === "function") viewer.tab.showError("This image did not stop", err.message, err.log_ref || "", err.detail || "")
                return
            }
            viewer.tab.log("info", "image_stopped", "Stopped " + r.name, { job: r.jobId, item: r.itemId })
            if (typeof viewer.tab.refreshJob === "function") viewer.tab.refreshJob(r.jobId)
        })
    }
    function queueAgain(asBefore) {
        if (!hasRow || actionBusy || tilePending) return
        var r = row
        markPending("queue")
        if (typeof tab.queueAgain === "function") {
            var k = String(r.key || "")
            tab.queueAgain([r], asBefore === true, function(taken) {
                if (!taken && viewer.pendingKey !== "" && viewer.pendingKey === k) viewer.clearPending()
            })
            return
        }
        if (typeof tab.requeueImage === "function") { tab.requeueImage(r, asBefore === true); return }
        actionBusy = true
        tab.service.post("/api/jobs/" + encodeURIComponent(r.jobId) + "/items/" + encodeURIComponent(r.itemId) + "/requeue",
                         asBefore === true ? { as_before: true, front: true } : { front: true }, function(err, data) {
            viewer.actionBusy = false
            if (err) {
                viewer.clearPending()
                if (typeof viewer.tab.showError === "function") viewer.tab.showError("This image was not queued again", err.message, err.log_ref || "", err.detail || "")
                return
            }
            viewer.tab.log("info", "image_requeued", "Queued " + r.name + " again" + (asBefore === true ? " as before" : ""), { job: r.jobId, item: r.itemId })
            if (typeof viewer.tab.refreshJob === "function") viewer.tab.refreshJob(r.jobId)
        })
    }
    function useTheseSettings() { if (hasResult && useSettingsSupported) tab.useSettingsFrom(row) }

    readonly property bool keysOn: visible && tab !== null && tab.keysActive === true
    Shortcut { sequence: "S"; enabled: viewer.keysOn && viewer.compareAvailable; onActivated: viewer.toggleSplit() }
    Shortcut { sequence: "Y"; enabled: viewer.keysOn && viewer.sideAvailable; onActivated: viewer.toggleSideBySide() }
    Shortcut { sequence: "L"; enabled: viewer.keysOn && viewer.hasRow; onActivated: viewer.loupeOn = !viewer.loupeOn }
    Shortcut {
        sequences: ["Ctrl+Shift+.", "Ctrl+>"]
        enabled: viewer.keysOn && viewer.tileKind === "stop"
        onActivated: viewer.stopThisImage()
    }

    Accessible.role: Accessible.Pane
    Accessible.name: "Image viewer"

    readonly property bool surroundMid: (tab !== null && String(tab.pictureSurround || "").toLowerCase() === "midgrey")
                                        || Tokens.surroundMidGrey === true
    Rectangle {
        objectName: "viewerSurround"
        visible: viewer.hasRow && viewer.surroundMid && viewer.pictureShown
        x: viewer.pastFit ? viewer.vpDX / viewer.dpr : 0
        y: viewer.allowTop
        width: viewer.pastFit ? viewer.vpDW / viewer.dpr : viewer.width
        height: Math.max(0, (viewer.pastFit ? viewer.vpDY1 / viewer.dpr : viewer.blockTop + viewer.picLH) - viewer.allowTop)
        color: Tokens.surroundMid
    }

    CuViewerEmpty {
        id: empty
        viewer: viewer
        anchors.fill: parent
        dragging: viewer.recessDrop
    }

    property point pointer: Qt.point(-1, -1)
    MouseArea {
        id: panArea
        objectName: "viewerPanArea"
        x: viewer.pastFit ? viewer.vpDX / viewer.dpr : 0
        y: viewer.allowTop
        width: viewer.pastFit ? viewer.vpDW / viewer.dpr : viewer.width
        height: Math.max(0, (viewer.pastFit ? viewer.vpDY1 / viewer.dpr : viewer.capY) - viewer.allowTop)
        enabled: viewer.hasRow
        hoverEnabled: viewer.loupeOn
        acceptedButtons: Qt.LeftButton
        readonly property bool overPicture: {
            var p = Qt.point(mouseX + x, mouseY + y)
            var a = viewer.mainVis, b = viewer.rightVis
            return (p.x >= a.x && p.x < a.x + a.width && p.y >= a.y && p.y < a.y + a.height)
                || (p.x >= b.x && p.x < b.x + b.width && p.y >= b.y && p.y < b.y + b.height)
        }
        cursorShape: viewer.pastFit ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor)
                                    : (viewer.splitActive && overPicture ? Qt.SplitHCursor : Qt.ArrowCursor)
        property real lastX: 0
        property real lastY: 0
        property real startX: 0
        property bool seamDrag: false
        onPressed: (mouse) => {
            lastX = mouse.x; lastY = mouse.y; startX = mouse.x; seamDrag = false
            viewer.forceActiveFocus(Qt.MouseFocusReason)
        }
        onPositionChanged: (mouse) => {
            if (viewer.loupeOn) viewer.pointer = Qt.point(mouse.x + x, mouse.y + y)
            if (!pressed) return
            if (viewer.pastFit) {
                viewer.panBy(mouse.x - lastX, mouse.y - lastY)
            } else if (viewer.splitActive && (seamDrag || Math.abs(mouse.x - startX) >= 8)) {
                seamDrag = true
                var r = viewer.splitSpan
                viewer.splitPos = Math.max(0, Math.min(1, (mouse.x + x - r.x) / Math.max(1, r.width)))
            }
            lastX = mouse.x
            lastY = mouse.y
        }
        onExited: viewer.pointer = Qt.point(-1, -1)
        onDoubleClicked: (mouse) => {
            if (viewer.pastFit) viewer.fit()
            else if (overPicture) viewer.zoomAround(1, mouse.x + x, mouse.y + y)
        }
        onWheel: (wheel) => {
            var steps = wheel.angleDelta.y / 120
            if (steps === 0) return
            viewer.zoomAround(viewer.zoom * Math.pow(1.15, steps), wheel.x + x, wheel.y + y)
        }
    }

    Item {
        id: devLayer
        objectName: "viewerPlate"
        scale: 1 / viewer.dpr
        transformOrigin: Item.TopLeft
        width: Math.round(viewer.width * viewer.dpr)
        height: Math.round(viewer.height * viewer.dpr)
        visible: viewer.hasRow
        CuViewerPane {
            id: mainPane
            objectName: "viewerMainPane"
            viewer: viewer
            keepBoth: true
            devX: viewer.mainDevX
            devY: viewer.mainDevY
            devW: viewer.mainDevW
            devH: viewer.mainDevH
            picDX: viewer.mainPicDX
            picDY: viewer.mainPicDY
            picDW: viewer.picDW
            picDH: viewer.picDH
            drawBefore: viewer.effectiveView === "before" || viewer.compareLayout !== "single"
            drawAfter: viewer.effectiveView === "after" || viewer.compareLayout === "split"
            afterKind: viewer.afterKind
            seamDX: viewer.seamDX
            decodeAtDrawn: !viewer.pastFit
            decodeDevice: Qt.size(viewer.mainDevW, viewer.mainDevH)
            liveOpacity: viewer.liveOpacity
            keepLive: viewer.landing
        }
        CuViewerPane {
            id: rightPane
            objectName: "viewerRightPane"
            visible: viewer.compareLayout === "side"
            active: viewer.compareLayout === "side"
            viewer: viewer
            devX: viewer.rightDevX
            devY: viewer.mainDevY
            devW: viewer.rightDevW
            devH: viewer.mainDevH
            picDX: viewer.rightPicDX
            picDY: viewer.mainPicDY
            picDW: viewer.picDW
            picDH: viewer.picDH
            drawBefore: false
            drawAfter: viewer.compareLayout === "side"
            afterKind: viewer.afterKind
            decodeAtDrawn: !viewer.pastFit
            decodeDevice: Qt.size(viewer.mainDevW, viewer.mainDevH)
            liveOpacity: viewer.liveOpacity
            keepLive: viewer.landing
        }
    }
    Timer {
        id: regionTimer
        interval: 250
        onTriggered: viewer.regionsNow()
    }
    function regionsNow() { mainPane.updateRegions(); if (rightPane.visible) rightPane.updateRegions() }
    onZoomChanged: regionTimer.restart()
    onOffXChanged: regionTimer.restart()
    onOffYChanged: regionTimer.restart()
    onPastFitChanged: regionTimer.restart()
    onCompareLayoutChanged: regionTimer.restart()
    onWidthChanged: regionTimer.restart()
    onHeightChanged: regionTimer.restart()

    CuPlateLabel {
        id: tagA
        objectName: "viewerBeforeLabel"
        text: "Before"
        readonly property rect vis: viewer.mainVis
        readonly property real room: viewer.splitActive ? viewer.seamDX / viewer.dpr - vis.x : vis.width
        visible: viewer.hasRow && viewer.compareLayout !== "single" && vis.width > 0 && room >= width + 2 * Tokens.sp8
                 && vis.height >= 2 * Tokens.hTag && viewer.pictureShown
        x: Tokens.snap(vis.x + Tokens.sp8, viewer.dpr)
        y: Tokens.snap(vis.y + vis.height - Tokens.sp8 - height, viewer.dpr)
    }
    CuPlateLabel {
        id: tagB
        objectName: "viewerAfterLabel"
        text: "After"
        readonly property rect vis: viewer.compareLayout === "side" ? viewer.rightVis : viewer.mainVis
        readonly property real startX: viewer.splitActive ? viewer.seamDX / viewer.dpr : vis.x
        readonly property real room: vis.x + vis.width - startX
        visible: viewer.hasRow && viewer.compareLayout !== "single" && vis.width > 0 && room >= width + 2 * Tokens.sp8
                 && vis.height >= 2 * Tokens.hTag && viewer.pictureShown
        x: Tokens.snap(startX + Tokens.sp8, viewer.dpr)
        y: Tokens.snap(vis.y + vis.height - Tokens.sp8 - height, viewer.dpr)
    }

    CuViewerSeam {
        id: seamHandle
        viewer: viewer
        visible: viewer.splitActive && viewer.mainVis.width > 0
        x: viewer.seamDX / viewer.dpr - width / 2
        y: viewer.mainVis.y
        height: viewer.mainVis.height
    }

    readonly property int loupeSize: Tokens.loupeSize
    readonly property bool pointerOnPicture: {
        var p = pointer, a = mainVis, b = rightVis
        return p.x >= 0 && ((p.x >= a.x && p.x < a.x + a.width && p.y >= a.y && p.y < a.y + a.height)
                            || (p.x >= b.x && p.x < b.x + b.width && p.y >= b.y && p.y < b.y + b.height))
    }
    readonly property bool loupeShown: loupeOn && !pastFit && hasRow && pictureShown && pointerOnPicture
    readonly property real loupeLX: Tokens.snap(Math.max(lineLeft, Math.min(lineRight - loupeSize, pointer.x - loupeSize / 2)), dpr)
    readonly property real loupeLY: Tokens.snap(Math.max(allowTop, Math.min(allowBottom - loupeSize, pointer.y - loupeSize / 2)), dpr)
    readonly property int loupePane: paneAt(pointer.x)
    readonly property real loupeU: { var c = currentPic(loupePane); return (pointer.x * dpr - c.x) * pw / Math.max(1, c.w) }
    readonly property real loupeV: { var c = currentPic(loupePane); return (pointer.y * dpr - c.y) * ph / Math.max(1, c.h) }
    readonly property bool loupeBefore: compareLayout === "side" ? loupePane === 0
                                        : compareLayout === "split" ? pointer.x * dpr < seamDX : effectiveView === "before"
    CuPlate {
        id: loupeFrame
        objectName: "viewerLoupe"
        visible: viewer.loupeShown
        x: viewer.loupeLX - edgeWidth
        y: viewer.loupeLY - edgeWidth
        width: viewer.loupeSize + 2 * edgeWidth
        height: viewer.loupeSize + 2 * edgeWidth
    }
    Item {
        id: loupeLayer
        scale: 1 / viewer.dpr
        transformOrigin: Item.TopLeft
        visible: viewer.loupeShown
        CuViewerPane {
            id: loupePaneItem
            objectName: "viewerLoupePane"
            viewer: viewer
            active: viewer.loupeShown
            readonly property int size: Math.round(viewer.loupeSize * viewer.dpr)
            devX: Math.round(viewer.loupeLX * viewer.dpr)
            devY: Math.round(viewer.loupeLY * viewer.dpr)
            devW: size
            devH: size
            picDW: Math.round(viewer.pw)
            picDH: Math.round(viewer.ph)
            picDX: devX + Math.round(size / 2 - viewer.loupeU)
            picDY: devY + Math.round(size / 2 - viewer.loupeV)
            drawBefore: viewer.loupeBefore
            drawAfter: !viewer.loupeBefore
            afterKind: viewer.afterKind
            decodeAtDrawn: false
            showSeam: false
            showOutline: false
            showRing: false
        }
    }
    Timer {
        id: loupeRegion
        interval: 80
        onTriggered: { if (viewer.loupeShown) loupePaneItem.updateRegions() }
    }
    onLoupeUChanged: { if (loupeShown) loupeRegion.restart() }
    onLoupeVChanged: { if (loupeShown) loupeRegion.restart() }
    onLoupeShownChanged: { if (loupeShown) loupeRegion.restart() }

    CuViewerTools {
        id: tools
        objectName: "viewerHeader"
        viewer: viewer
        visible: viewer.hasRow
        x: viewer.lineLeft
        y: 0
        width: Math.max(0, viewer.lineRight - viewer.lineLeft)
    }
    property alias toolLine: tools

    CuViewerCaption {
        id: caption
        viewer: viewer
        visible: viewer.hasRow
        x: viewer.capX
        y: viewer.capY
        width: viewer.capW
        height: viewer.capSlot
    }
    property alias captionItem: caption

    readonly property bool ownNavigator: navigatorShown && (navigatorPlace === "floating" || navigatorPlace === "stack")
    CuNavigator {
        id: floatingNav
        objectName: viewer.navigatorPlace === "floating" ? "viewerNavigatorFloating" : "viewerNavigatorStack"
        viewer: viewer
        floating: viewer.navigatorPlace === "floating"
        visible: viewer.ownNavigator
        readonly property real legW: Tokens.legWidth(viewer.hostWidth)
        width: floating ? legW - 2 * Tokens.legInset + 2 * Tokens.sp8 : legW
        height: implicitHeight
        x: floating ? Tokens.snap(viewer.lineLeft + Tokens.sp16, viewer.dpr) : -viewer.x
        y: floating ? Tokens.snap(viewer.capPastY - Tokens.sp16 - height, viewer.dpr)
                    : Tokens.snap(viewer.hostHs - viewer.y - height, viewer.dpr)
    }

    CuText {
        id: reconnecting
        objectName: "viewerReconnecting"
        visible: viewer.hasRow && viewer.tab !== null && viewer.tab.reconnecting === true && !viewer.pictureShown
        x: Tokens.snap(viewer.fitLX + (viewer.picLW - width) / 2, viewer.dpr)
        y: Tokens.snap(viewer.blockTop + (viewer.picLH - lineBox) / 2, viewer.dpr)
        role: "body"
        color: Tokens.text2
        text: "Reconnecting to the engine…"
    }
}

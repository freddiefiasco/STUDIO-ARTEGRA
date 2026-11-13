import QtQuick

Item {
    id: pane

    property var viewer: null
    readonly property var tab: viewer ? viewer.tab : null
    readonly property var row: viewer ? viewer.row : null
    readonly property bool hasRow: viewer !== null && viewer.hasRow
    readonly property string rowKey: viewer ? viewer.rowKey : ""
    readonly property real dpr: viewer ? viewer.dpr : 1

    property int devX: 0
    property int devY: 0
    property int devW: 0
    property int devH: 0
    property int picDX: 0
    property int picDY: 0
    property int picDW: 0
    property int picDH: 0
    property bool drawBefore: true
    property bool drawAfter: false
    property string afterKind: "result"
    property int seamDX: -1
    property bool decodeAtDrawn: true
    property bool showOutline: true
    property bool showRing: true
    property bool showSeam: true
    property real liveOpacity: 1
    property bool keepLive: false
    property bool active: true
    property bool keepBoth: false

    readonly property int picX: picDX - devX
    readonly property int picY: picDY - devY
    readonly property int paneW: devW
    readonly property int paneH: devH
    readonly property int seamX: seamDX >= 0 ? Math.max(0, Math.min(devW, seamDX - devX)) : -1
    readonly property bool splitOn: seamDX >= 0 && drawBefore && drawAfter
    readonly property int visX0: Math.max(0, picX)
    readonly property int visY0: Math.max(0, picY)
    readonly property int visX1: Math.min(devW, picX + picDW)
    readonly property int visY1: Math.min(devH, picY + picDH)

    property size decodeDevice: Qt.size(0, 0)
    property size settled: Qt.size(0, 0)
    readonly property bool covered: tab !== null && tab.resultsOpen === true
    onCoveredChanged: { if (!covered) settleNow() }
    readonly property bool settling: settleTimer.running || (!covered && decodeAtDrawn && decodeDevice.width > 0
                                     && (settled.width !== decodeDevice.width || settled.height !== decodeDevice.height))
    onDecodeDeviceChanged: settleTimer.restart()
    Component.onCompleted: settled = decodeDevice
    function settleNow() {
        if (!pane.decodeAtDrawn || pane.covered) return
        var s = pane.decodeDevice
        if (pane.settled.width !== s.width || pane.settled.height !== s.height) pane.settled = Qt.size(s.width, s.height)
    }
    Timer {
        id: settleTimer
        interval: 150
        onTriggered: pane.settleNow()
    }
    function sameShape(a, b) {
        return a.width > 0 && a.height > 0 && b.width > 0 && b.height > 0
               && Math.abs(a.width * b.height - a.height * b.width) <= 0.02 * a.height * b.width
    }
    function twice(nw, nh) {
        if (!(settled.width > 0 && settled.height > 0)) return undefined
        var w = 2 * settled.width, h = 2 * settled.height
        if (nw > 0 && nh > 0 && (w > nw + 0.5 || h > nh + 0.5)) return undefined
        return Qt.size(w, h)
    }
    function proxyNatural(w, h, lw, lh) {
        if (lw > 0 && lh > 0) return Qt.size(lw, lh)
        var k = Math.min(1, 2048 / Math.max(1, w, h))
        return Qt.size(Math.round(w * k), Math.round(h * k))
    }
    readonly property size srcNatural: proxyNatural(row ? row.srcW : 0, row ? row.srcH : 0, srcFull.implicitWidth, srcFull.implicitHeight)
    readonly property size resNatural: proxyNatural(viewer ? viewer.pw : 0, viewer ? viewer.ph : 0, resFull.implicitWidth, resFull.implicitHeight)
    readonly property var srcDecode: twice(srcNatural.width, srcNatural.height)
    readonly property var resDecode: twice(resNatural.width, resNatural.height)
    readonly property bool settledOk: decodeAtDrawn && settled.width > 0 && settled.height > 0
    readonly property bool settledShape: sameShape(settled, decodeDevice)
    readonly property bool sized: viewer !== null && viewer.sizedCopies
    readonly property bool srcAtFit: settledOk && (sized ? settledShape : srcDecode !== undefined)
    readonly property bool resAtFit: settledOk && (sized ? settledShape : resDecode !== undefined)

    function holdsThisShape(img) {
        var iw = img.implicitWidth, ih = img.implicitHeight
        if (!(iw > 0 && ih > 0 && picDW > 0 && picDH > 0)) return false
        return Math.abs(iw * picDH - ih * picDW) <= 0.02 * ih * picDW
    }
    function usable(img) {
        return img.status === Image.Ready || (img.status === Image.Loading && holdsThisShape(img))
    }
    readonly property bool afterOnScreen: afterKind === "live" ? liveCanvas.ready : (resFull.visible || resSized.visible)
    readonly property bool sourceUnder: drawAfter && !drawBefore && afterKind !== "none" && !afterOnScreen
    readonly property bool sourceWanted: drawBefore || sourceUnder
    readonly property bool loadSource: active && hasRow && (sourceWanted || keepBoth)
    readonly property bool loadResult: active && hasRow && afterKind === "result" && (drawAfter || keepBoth)
    readonly property bool loadLive: active && hasRow && (afterKind === "live" || keepLive)

    x: devX
    y: devY
    width: devW
    height: devH
    clip: true

    function updateRegions() {
        srcRegion.update()
        resRegion.update()
        liveRegion.update()
    }

    Image {
        objectName: "viewerChecker"
        visible: pane.hasRow && pane.viewer.hasAlpha && pane.viewer.pictureShown
        x: pane.picX
        y: pane.picY
        width: pane.picDW
        height: pane.picDH
        source: Tokens.checkerTile
        sourceSize: Qt.size(Math.round(2 * Tokens.checkerSize * pane.dpr), Math.round(2 * Tokens.checkerSize * pane.dpr))
        fillMode: Image.Tile
        smooth: false
        mipmap: false
    }

    Item {
        id: beforeClip
        visible: pane.sourceWanted
        width: pane.splitOn ? pane.seamX : pane.devW
        height: pane.devH
        clip: pane.splitOn
        Item {
            id: beforePic
            objectName: "viewerPicture"
            x: pane.picX
            y: pane.picY
            width: pane.picDW
            height: pane.picDH
            Image {
                id: srcFull
                objectName: "viewerSourceProxy"
                anchors.fill: parent
                visible: !srcSized.visible && pane.usable(srcFull)
                asynchronous: true
                cache: true
                retainWhileLoading: true
                smooth: true
                mipmap: false
                fillMode: Image.Stretch
                source: pane.loadSource ? pane.viewer.sourceUrl : ""
            }
            Image {
                id: srcSized
                objectName: "viewerSourceAtFit"
                property bool everReady: false
                readonly property bool shown: everReady && pane.srcAtFit && source.toString() !== ""
                anchors.fill: parent
                visible: shown && pane.usable(srcSized)
                asynchronous: true
                cache: true
                retainWhileLoading: true
                smooth: true
                mipmap: false
                fillMode: Image.Stretch
                sourceSize: pane.sized ? undefined : pane.srcDecode
                source: !(pane.loadSource && pane.srcAtFit) ? ""
                        : pane.sized ? pane.viewer.sizedUrl(pane.viewer.sourcePath, pane.settled.width, pane.settled.height)
                                     : pane.viewer.sourceUrl
                onSourceChanged: { if (source.toString() === "") everReady = false }
                onStatusChanged: { if (status === Image.Ready) everReady = true }
            }
            CuRegionImage {
                id: srcRegion
                pane: pane
                kind: "source"
                proxy: srcFull
                visibleWanted: pane.loadSource && !pane.decodeAtDrawn
                layerWidth: pane.row ? pane.row.srcW : 0
                layerHeight: pane.row ? pane.row.srcH : 0
                drawnWidth: pane.picDW
            }
            CuMaskOverlay {
                anchors.fill: parent
                visible: pane.viewer !== null && pane.viewer.maskShown
                maskUrl: pane.viewer && pane.viewer.mask ? pane.viewer.mask.url : ""
            }
        }
    }

    Item {
        id: afterClip
        visible: pane.drawAfter && pane.afterKind !== "none"
        x: pane.splitOn ? pane.seamX : 0
        width: Math.max(0, pane.devW - x)
        height: pane.devH
        clip: true
        Item {
            id: afterPic
            objectName: "viewerAfterPicture"
            x: pane.picX - afterClip.x
            y: pane.picY
            width: pane.picDW
            height: pane.picDH
            Image {
                id: resFull
                objectName: "viewerResultProxy"
                anchors.fill: parent
                visible: pane.afterKind === "result" && !resSized.visible && pane.usable(resFull)
                asynchronous: true
                cache: true
                retainWhileLoading: true
                smooth: true
                mipmap: false
                fillMode: Image.Stretch
                source: pane.loadResult ? pane.viewer.resultUrl : ""
                onStatusChanged: { if (status === Image.Ready && pane.viewer) pane.viewer.resultLoaded() }
            }
            Image {
                id: resSized
                objectName: "viewerResultAtFit"
                property bool everReady: false
                readonly property bool shown: everReady && pane.resAtFit && source.toString() !== ""
                anchors.fill: parent
                visible: pane.afterKind === "result" && shown && pane.usable(resSized)
                asynchronous: true
                cache: true
                retainWhileLoading: true
                smooth: true
                mipmap: false
                fillMode: Image.Stretch
                sourceSize: pane.sized ? undefined : pane.resDecode
                source: !(pane.loadResult && pane.resAtFit) ? ""
                        : pane.sized ? pane.viewer.sizedUrl(pane.viewer.resultPath, pane.settled.width, pane.settled.height)
                                     : pane.viewer.resultUrl
                onSourceChanged: { if (source.toString() === "") everReady = false }
                onStatusChanged: { if (status === Image.Ready) { everReady = true; if (pane.viewer) pane.viewer.resultLoaded() } }
            }
            CuRegionImage {
                id: resRegion
                pane: pane
                kind: "result"
                proxy: resFull
                visibleWanted: pane.loadResult && !pane.decodeAtDrawn
                layerWidth: pane.viewer ? pane.viewer.pw : 0
                layerHeight: pane.viewer ? pane.viewer.ph : 0
                drawnWidth: pane.picDW
            }
            CuLiveCanvas {
                id: liveCanvas
                objectName: "viewerLiveCanvas"
                anchors.fill: parent
                visible: pane.drawAfter && (pane.afterKind === "live" || pane.keepLive) && url !== ""
                opacity: pane.afterKind === "live" ? 1 : pane.liveOpacity
                url: pane.loadLive ? pane.viewer.liveUrl : ""
                naturalW: pane.viewer ? pane.viewer.liveNaturalW : 0
                naturalH: pane.viewer ? pane.viewer.liveNaturalH : 0
                decodeSize: pane.settledOk ? pane.settled : Qt.size(0, 0)
                current: pane.viewer !== null && pane.viewer.liveFrameServed
                alphaUrl: pane.viewer && pane.viewer.hasAlpha ? pane.viewer.sourceUrl : ""
            }
            CuRegionImage {
                id: liveRegion
                pane: pane
                kind: "live"
                proxy: liveCanvas.frontImage
                baseUrl: pane.viewer ? pane.viewer.liveRegionBase : ""
                stamp: pane.viewer ? pane.viewer.liveSeq : ""
                visibleWanted: pane.loadLive && pane.afterKind === "live" && (pane.drawAfter || pane.keepBoth) && !pane.decodeAtDrawn
                               && baseUrl !== "" && !pane.viewer.hasAlpha
                layerWidth: pane.viewer ? pane.viewer.pw : 0
                layerHeight: pane.viewer ? pane.viewer.ph : 0
                drawnWidth: pane.picDW
            }
            CuMaskOverlay {
                anchors.fill: parent
                visible: pane.viewer !== null && pane.viewer.maskShown && pane.afterKind !== "none"
                maskUrl: pane.viewer && pane.viewer.mask ? pane.viewer.mask.url : ""
            }
            CuLiveOutline {
                anchors.fill: parent
                visible: pane.showOutline && pane.afterKind === "live" && liveCanvas.ready
                rects: pane.viewer ? pane.viewer.liveRects : []
                dpr: pane.dpr
            }
        }
    }
    readonly property bool liveReady: liveCanvas.ready
    readonly property bool resultReady: resFull.status === Image.Ready || resSized.everReady
    readonly property bool anyReady: srcFull.visible || srcSized.visible || resFull.visible || resSized.visible
                                     || (liveCanvas.visible && liveCanvas.ready)

    CuPrintEdge {
        visible: pane.showRing && pane.hasRow && pane.viewer.pictureShown
        x: pane.picX
        y: pane.picY
        width: pane.picDW
        height: pane.picDH
        portWidth: pane.devW
        portHeight: pane.devH
    }

    Item {
        id: seam
        objectName: "viewerSplitLine"
        visible: pane.splitOn && pane.showSeam && pane.visY1 > pane.visY0
        readonly property int sx: pane.seamX
        readonly property int gw: Math.max(3, Math.round(Tokens.gripWidth * pane.dpr))
        readonly property int gh: Math.round(Tokens.gripHeight * pane.dpr)
        Rectangle { x: seam.sx - 1; y: pane.visY0; width: 3; height: pane.visY1 - pane.visY0; color: Tokens.seamHalo }
        Rectangle { x: seam.sx; y: pane.visY0; width: 1; height: pane.visY1 - pane.visY0; color: Tokens.seamLine }
        Rectangle {
            objectName: "viewerSplitGrip"
            x: seam.sx - Math.floor(seam.gw / 2) - 1
            y: Math.round((pane.visY0 + pane.visY1 - seam.gh) / 2) - 1
            width: seam.gw + 2
            height: seam.gh + 2
            color: "transparent"
            border.width: 1
            border.color: Tokens.liveOutlineHalo
            Rectangle {
                x: 1
                y: 1
                width: seam.gw
                height: seam.gh
                color: pane.viewer && pane.viewer.seamLit ? Tokens.whiteHover : Tokens.text1
            }
        }
    }
}

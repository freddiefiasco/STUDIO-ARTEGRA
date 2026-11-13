import QtQuick
import QtQuick.Templates as T

T.ToolTip {
    id: tip
    delay: Tokens.tipDelay()
    timeout: -1
    margins: Tokens.sp8

    property string placement: "above"
    property Item avoidItem: null
    property rect avoidRect: Qt.rect(0, 0, 0, 0)
    property url picture: ""
    property real pictureAspect: 0
    property bool pictureAlpha: false
    property int pictureSize: Tokens.tipPicture
    property string detail: ""
    property real cardWidth: 0
    property real boundWidth: 0
    readonly property bool hasPicture: picture.toString() !== ""
    property string side: placement
    readonly property bool below: side === "below"
    property bool blocked: false
    property string closedBecause: ""
    function dismiss() {
        if (!visible) return
        closedBecause = "escape"
        close()
    }
    Shortcut {
        sequence: "Escape"
        context: Qt.WindowShortcut
        enabled: tip.visible && Tokens.tipsOpen > 0 && Tokens.tipsShown[Tokens.tipsOpen - 1] === tip
        onActivated: Tokens.dismissTips()
        onActivatedAmbiguously: Tokens.dismissTips()
    }

    readonly property var keyParts: Tokens.keyTipParts(text)
    leftPadding: Tokens.sp8
    rightPadding: Tokens.sp8
    topPadding: Tokens.sp8
    bottomPadding: Tokens.sp8

    function meet(a, c) {
        var x1 = Math.max(a.x, c.x), y1 = Math.max(a.y, c.y)
        var x2 = Math.min(a.x + a.width, c.x + c.width), y2 = Math.min(a.y + a.height, c.y + c.height)
        return Qt.rect(x1, y1, Math.max(0, x2 - x1), Math.max(0, y2 - y1))
    }
    function tabItem() {
        for (var p = parent; p; p = p.parent)
            if (p.objectName === "creativeUpscalerTab") return p
        return null
    }
    function rootItem() {
        var top = parent
        while (top && top.parent) top = top.parent
        return top
    }
    function trayRect() {
        for (var p = parent; p; p = p.parent) {
            if (p.tipBounds === true)
                return parent.mapFromItem(p, Tokens.sp8, 0, Math.max(0, p.width - 2 * Tokens.sp8), Math.max(0, p.height - Tokens.sp8))
        }
        return null
    }
    function canvasRect() {
        for (var p = parent; p; p = p.parent) {
            if (typeof p.tipCanvasRect === "function") {
                var r = p.tipCanvasRect()
                if (!r || r.width <= 0 || r.height <= 0) return null
                return parent.mapFromItem(p, r.x, r.y, r.width, r.height)
            }
        }
        return null
    }
    function boundsRect() {
        var top = rootItem()
        var win = top ? parent.mapFromItem(top, Tokens.sp8, Tokens.sp8, Math.max(0, top.width - 2 * Tokens.sp8),
                                           Math.max(0, top.height - 2 * Tokens.sp8))
                      : Qt.rect(-1e6, -1e6, 2e6, 2e6)
        var r = win
        var tab = tabItem()
        if (tab) r = meet(r, parent.mapFromItem(tab, 0, 0, tab.width, tab.height))
        var tray = trayRect()
        if (tray) return meet(r, tray)
        var canvas = canvasRect()
        return canvas ? meet(r, canvas) : r
    }
    function keepClear() {
        var x1 = 0, y1 = 0, x2 = parent.width, y2 = parent.height
        if (avoidItem) {
            var r = (avoidRect.width > 0 && avoidRect.height > 0) ? avoidRect : Qt.rect(0, 0, avoidItem.width, avoidItem.height)
            var m = parent.mapFromItem(avoidItem, r.x, r.y, r.width, r.height)
            x1 = Math.min(x1, m.x); y1 = Math.min(y1, m.y)
            x2 = Math.max(x2, m.x + m.width); y2 = Math.max(y2, m.y + m.height)
        }
        return { x1: x1, y1: y1, x2: x2, y2: y2 }
    }
    function keepOffSource() {
        for (var p = parent; p; p = p.parent) {
            if (typeof p.tipKeepClearRects === "function") return { item: p, rects: p.tipKeepClearRects() || [] }
            if (typeof p.tipKeepClearRect === "function") {
                var r = p.tipKeepClearRect()
                return { item: p, rects: r ? [r] : [] }
            }
        }
        return null
    }
    function keepOffRects() {
        var src = keepOffSource()
        if (!src) return []
        var out = []
        for (var i = 0; i < src.rects.length; ++i) {
            var r = src.rects[i]
            if (r && r.width > 0 && r.height > 0) out.push(parent.mapFromItem(src.item, r.x, r.y, r.width, r.height))
        }
        return out
    }
    function keepOffSignature() {
        var src = keepOffSource()
        if (!src) return ""
        var s = []
        for (var i = 0; i < src.rects.length; ++i) {
            var r = src.rects[i]
            if (r) s.push(Math.round(r.x) + "," + Math.round(r.y) + "," + Math.round(r.width) + "," + Math.round(r.height))
        }
        return s.join(";")
    }
    function liesOver(c, w, h, off) {
        return off !== null && c.x < off.x + off.width - 0.5 && off.x < c.x + w - 0.5
               && c.y < off.y + off.height - 0.5 && off.y < c.y + h - 0.5
    }
    function liesOverAny(c, w, h, list) {
        for (var i = 0; i < list.length; ++i) if (liesOver(c, w, h, list[i])) return true
        return false
    }
    function clampTo(v, lo, hi) { return hi < lo ? lo : Math.max(lo, Math.min(hi, v)) }
    function candidate(s, w, h, k, b, align) {
        var x, y, fits
        if (s === "above" || s === "below") {
            y = s === "above" ? k.y1 - h - Tokens.tipGap : k.y2 + Tokens.tipGap
            x = Math.round((parent.width - w) / 2)
            fits = y >= b.y && y + h <= b.y + b.height
            x = clampTo(x, b.x, b.x + b.width - w)
            y = clampTo(y, b.y, b.y + b.height - h)
        } else {
            x = s === "right" ? k.x2 + Tokens.tipGapSide : k.x1 - w - Tokens.tipGapSide
            y = align === "centre" ? Math.round((parent.height - h) / 2) : 0
            fits = x >= b.x && x + w <= b.x + b.width
            x = clampTo(x, b.x, b.x + b.width - w)
            y = clampTo(y, b.y, b.y + b.height - h)
        }
        return { x: Math.round(x), y: Math.round(y), fits: fits }
    }
    function place() {
        if (!parent) return false
        var b = boundsRect(), k = keepClear()
        var tray = trayRect()
        var bw = tray ? Math.floor(b.width) : 0
        if (boundWidth !== bw) boundWidth = bw
        var w = width > 0 ? width : implicitWidth, h = height > 0 ? height : implicitHeight
        var order = { "above": ["above", "below", "right", "left"], "below": ["below", "above", "right", "left"],
                      "right": ["right", "left", "below", "above"], "left": ["left", "right", "below", "above"] }[placement]
                    || ["above", "below", "right", "left"]
        var off = keepOffRects()
        var own = Qt.rect(0, 0, parent.width, parent.height)
        var offAll = off.concat([own])
        if (!tray && off.length > 0 && (order[0] === "above" || order[0] === "below")) {
            var roomL = k.x1 - b.x, roomR = b.x + b.width - k.x2
            order = [order[0], order[1]].concat(roomL > roomR ? ["left", "right"] : ["right", "left"])
        }
        var chosen = null
        var aligns = function(sd) { return sd === "left" || sd === "right" ? ["top", "centre"] : ["top"] }
        for (var i = 0; i < order.length && !chosen; ++i) {
            var al = aligns(order[i])
            for (var a = 0; a < al.length && !chosen; ++a) {
                var c = candidate(order[i], w, h, k, b, al[a])
                if (c.fits && !liesOverAny(c, w, h, off)) { chosen = c; side = order[i] }
            }
        }
        for (var j = 0; j < order.length && !chosen; ++j) {
            var al2 = aligns(order[j])
            for (var a2 = 0; a2 < al2.length && !chosen; ++a2) {
                var d = candidate(order[j], w, h, k, b, al2[a2])
                if (!liesOverAny(d, w, h, offAll)) { chosen = d; side = order[j] }
            }
        }
        if (!chosen) return false
        x = chosen.x
        y = chosen.y
        return true
    }
    function placeOrClose(reason) {
        if (!tip.visible) return
        if (tip.place()) { tip.blocked = false; tip.anchorAt = tip.scenePos(); return }
        tip.blocked = true
        tip.closedBecause = reason
        tip.close()
    }

    property point anchorAt: Qt.point(0, 0)
    property double resizedAt: 0
    function scenePos() {
        var top = rootItem()
        return parent && top ? parent.mapToItem(top, 0, 0) : Qt.point(0, 0)
    }
    property var watched: []
    property bool pendingMove: false
    property string pendingReason: ""
    property bool pendingClose: false
    property int pendingAgain: 0
    Timer {
        id: later
        interval: 0
        onTriggered: tip.runPending()
    }
    function defer() { later.restart() }
    function runPending() {
        if (pendingClose) { pendingClose = false; close(); return }
        if (pendingMove) { pendingMove = false; checkMoved() }
        if (pendingReason !== "") { var r = pendingReason; pendingReason = ""; placeOrClose(r) }
        if (pendingAgain > 0) { pendingAgain = 0; placeAgain() }
    }
    function sceneMoved() { tip.pendingMove = true; tip.defer() }
    function checkMoved() {
        if (!tip.visible || !tip.parent) return
        var p = tip.scenePos()
        if (Math.abs(p.x - tip.anchorAt.x) < 0.5 && Math.abs(p.y - tip.anchorAt.y) < 0.5) return
        if (Date.now() - tip.resizedAt < 400) { tip.placeOrClose("no room"); return }
        tip.closedBecause = "control moved"
        tip.close()
    }
    function watchScene() {
        unwatchScene()
        var list = []
        for (var p = parent; p; p = p.parent) {
            p.xChanged.connect(tip.sceneMoved)
            p.yChanged.connect(tip.sceneMoved)
            list.push(p)
        }
        watched = list
    }
    function unwatchScene() {
        for (var i = 0; i < watched.length; ++i) {
            try { watched[i].xChanged.disconnect(tip.sceneMoved); watched[i].yChanged.disconnect(tip.sceneMoved) } catch (e) {}
        }
        watched = []
    }
    readonly property string keepOffNow: visible ? keepOffSignature() : ""
    onKeepOffNowChanged: if (visible) { pendingReason = "keep-off changed"; defer() }

    onAboutToShow: {
        closedBecause = ""
        if (!place()) {
            blocked = true
            closedBecause = "no room"
            pendingClose = true
            defer()
            return
        }
        blocked = false
        anchorAt = scenePos()
        watchScene()
    }
    onAboutToHide: unwatchScene()
    onWidthChanged: if (visible) placeOrClose("no room")
    onHeightChanged: if (visible) placeOrClose("no room")
    function placeAgain() { if (tip.visible) tip.placeOrClose("no room") }
    Connections {
        target: tip.parent && tip.parent.Window ? tip.parent.Window.window : null
        ignoreUnknownSignals: true
        function onWidthChanged() { tip.resizedAt = Date.now(); tip.placeAgain(); tip.pendingAgain = 1; tip.defer() }
        function onHeightChanged() { tip.resizedAt = Date.now(); tip.placeAgain(); tip.pendingAgain = 1; tip.defer() }
    }

    enabled: false
    opacity: blocked ? 0 : 1
    function breakPaths(s) { return s.indexOf("\\") >= 0 ? s.split("\\").join("\\" + String.fromCharCode(0x200B)) : s }
    readonly property int maxWidth: (text + detail).indexOf("\\") >= 0 ? 2 * Tokens.tooltipMaxWidth : Tokens.tooltipMaxWidth
    implicitWidth: {
        if (cardWidth > 0) return boundWidth > 0 ? Math.min(cardWidth, boundWidth) : cardWidth
        var limit = boundWidth > 0 ? Math.min(maxWidth, boundWidth) : maxWidth
        return Math.min(limit, Math.ceil(contentItem.implicitWidth) + leftPadding + rightPadding)
    }
    implicitHeight: Math.ceil(contentItem.implicitHeight) + topPadding + bottomPadding
    closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent | T.Popup.CloseOnReleaseOutsideParent

    contentItem: Item {
        id: body
        FontMetrics { id: tipMetrics; font: Tokens.fontFor("meta", false) }
        readonly property int keyGap: Math.ceil(tipMetrics.advanceWidth("  "))
        readonly property int keyWidth: tip.keyParts ? Math.ceil(keyText.implicitWidth) + keyGap : 0
        readonly property int pictureBlock: tip.hasPicture ? miniature.height + Tokens.sp8 : 0
        readonly property int textWidth: Math.max(0, tip.maxWidth - tip.leftPadding - tip.rightPadding)
        readonly property bool keyOnOwnLine: tip.keyParts !== null
                                             && Math.ceil(tipMetrics.advanceWidth(tip.keyParts.words)) + keyWidth > textWidth
        implicitWidth: Math.max(tip.hasPicture ? miniature.width : 0,
                                Math.min(textWidth, Math.max(Math.ceil(words.implicitWidth) + keyWidth,
                                                             detailText.visible ? Math.ceil(detailText.implicitWidth) : 0)))
        implicitHeight: pictureBlock + words.height + (keyOnOwnLine ? keyText.lineBox : 0)
                        + (detailText.visible ? detailText.height : 0)
        CuMiniature {
            id: miniature
            objectName: "tooltipPicture"
            visible: tip.hasPicture
            hug: true
            source: tip.picture
            aspect: tip.pictureAspect
            hasAlpha: tip.pictureAlpha
            maxWidth: tip.pictureSize
            maxHeight: tip.pictureSize
            horizontalAlignment: Qt.AlignLeft
            surface: Tokens.float
        }
        CuText {
            id: words
            objectName: "tooltipWords"
            x: 0
            y: body.pictureBlock
            width: Math.min(Math.ceil(implicitWidth), Math.max(0, body.textWidth - (body.keyOnOwnLine ? 0 : body.keyWidth)))
            text: tip.keyParts ? tip.keyParts.words : tip.breakPaths(tip.text)
            role: "meta"
            color: Tokens.text1
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            maximumLineCount: Tokens.tooltipMaxLines
            elide: Text.ElideRight
        }
        CuText {
            id: keyText
            objectName: "tooltipKey"
            visible: tip.keyParts !== null
            x: body.keyOnOwnLine ? 0 : words.width + body.keyGap
            y: body.keyOnOwnLine ? words.y + words.height : words.y
            text: tip.keyParts ? tip.keyParts.key : ""
            role: "meta"
            color: Tokens.text2
        }
        CuText {
            id: detailText
            objectName: "tooltipDetail"
            visible: tip.detail !== ""
            x: 0
            y: words.y + words.height + (body.keyOnOwnLine ? keyText.lineBox : 0)
            width: Math.min(Math.ceil(implicitWidth), body.textWidth)
            text: tip.breakPaths(tip.detail)
            role: "meta"
            color: Tokens.text2
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            maximumLineCount: Tokens.tooltipMaxLines
            elide: Text.ElideRight
        }
    }
    background: CuPlate {
        objectName: "tooltipPlate"
    }
    property bool wasOpen: false
    onOpened: { wasOpen = true; Tokens.tipShown(tip) }
    onClosed: { if (closedBecause !== "control moved") Tokens.tipClosedAt = Date.now(); unwatchScene(); Tokens.tipGone(tip) }
    Component.onDestruction: {
        unwatchScene()
        if (wasOpen && closedBecause !== "control moved") Tokens.tipClosedAt = Date.now()
        Tokens.tipGone(tip)
    }
}

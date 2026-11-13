import QtQuick
import QtQuick.Window

Item {
    id: zone
    property var tab: null
    property Item labelArea: null
    readonly property bool usable: tab !== null && (tab.canAddImages !== undefined ? tab.canAddImages === true
                                                    : tab.connected && !(tab.engineState === "problem" && tab.problemKind !== "output"))
    readonly property bool dragging: drop.containsDrag && accepting
    property bool accepting: false
    property int dragCount: 0
    readonly property bool dropFolder: dragCount < 0
    readonly property int dropCount: Math.max(0, dragCount)
    readonly property Item rail: tab !== null && tab.railItem !== undefined ? tab.railItem : null
    readonly property Item viewer: labelArea !== null ? labelArea : (tab !== null && tab.viewerItem !== undefined ? tab.viewerItem : null)
    readonly property bool listEmpty: tab === null || tab.queue === undefined || tab.queue === null || tab.queue.count === 0
    readonly property string dropState: !dragging ? "" : (listEmpty ? "recess" : "list")
    readonly property string words: dropFolder ? "Drop to add images"
                                   : "Drop to add " + (dropCount === 1 ? "1 image" : dropCount + " images")
    readonly property var imageExtensions: [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"]
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1

    function countImages(urls) {
        var n = 0
        for (var i = 0; i < urls.length; ++i) {
            var s = decodeURIComponent(String(urls[i])).replace(/\\/g, "/").replace(/\/+$/, "")
            var last = s.substring(s.lastIndexOf("/") + 1).toLowerCase()
            var dot = last.lastIndexOf(".")
            if (dot <= 0) return -1
            if (imageExtensions.indexOf(last.substring(dot)) >= 0) n += 1
        }
        return n
    }

    readonly property var refusal: {
        if (tab === null) return { title: "", body: "" }
        if (tab.engineState === "problem")
            return { title: "Images cannot be added while the engine has a problem.", body: "Solve the problem shown, then drop them again." }
        if (tab.reconnecting === true)
            return { title: "The engine is reconnecting.", body: "Drop the images again once it is back." }
        return { title: "The engine is still starting.", body: "Drop the images again once it is ready." }
    }
    property real refusedAt: 0
    function sayRefused() {
        var now = Date.now()
        if (now - refusedAt < 6000 || tab === null || typeof tab.showToast !== "function") return
        refusedAt = now
        tab.showToast("notice", refusal.title, refusal.body)
        if (typeof tab.announce === "function") tab.announce(refusal.title)
    }

    DropArea {
        id: drop
        anchors.fill: parent
        onEntered: (drag) => {
            if (!drag.hasUrls) { drag.accepted = false; zone.accepting = false; return }
            if (!zone.usable) { drag.accepted = false; zone.accepting = false; zone.sayRefused(); return }
            zone.accepting = true
            zone.dragCount = zone.countImages(drag.urls)
        }
        onExited: { zone.dragCount = 0; zone.accepting = false }
        onDropped: (event) => {
            zone.dragCount = 0
            zone.accepting = false
            if (event.hasUrls && zone.usable) {
                zone.tab.addUrls(event.urls)
                event.acceptProposedAction()
            }
        }
    }

    readonly property Item railTarget: rail !== null && rail.dropState !== undefined ? rail : null
    readonly property Item viewerTarget: viewer !== null && viewer.dropState !== undefined ? viewer : null
    readonly property Item viewerCountTarget: viewer !== null && viewer.dropCount !== undefined ? viewer : null
    readonly property Item viewerFolderTarget: viewer !== null && viewer.dropFolder !== undefined ? viewer : null
    readonly property Item viewerWordsTarget: viewer !== null && viewer.dropWords !== undefined ? viewer : null
    Binding { target: zone.railTarget; property: "dropState"; value: zone.dropState === "list" ? "list" : "" }
    Binding { target: zone.railTarget; property: "dropWords"; value: zone.words }
    Binding { target: zone.viewerTarget; property: "dropState"; value: zone.dropState }
    Binding { when: zone.dragging; target: zone.viewerCountTarget; property: "dropCount"; value: zone.dropCount }
    Binding { when: zone.dragging; target: zone.viewerFolderTarget; property: "dropFolder"; value: zone.dropFolder }
    Binding { target: zone.viewerWordsTarget; property: "dropWords"; value: zone.words }

    readonly property bool viewerDraws: viewer !== null && viewer.dropState !== undefined
    readonly property rect litRect: {
        zone.dragging; zone.width; zone.height
        var a = zone.viewer
        if (a === null) return Qt.rect(0, 0, 0, 0)
        a.x; a.y; a.width; a.height
        var r = a.recessRect !== undefined && a.recessRect.width > 0 ? a.recessRect : Qt.rect(0, 0, 0, 0)
        if (r.width <= 0 || r.height <= 0) return Qt.rect(0, 0, 0, 0)
        var p = zone.mapFromItem(a, r.x, r.y)
        return Qt.rect(p.x, p.y, r.width, r.height)
    }
    Item {
        id: overlay
        objectName: "dropOverlay"
        anchors.fill: parent
        visible: zone.dropState === "recess" && !zone.viewerDraws && zone.litRect.width > 0
        Item {
            id: edge
            objectName: "dropEdge"
            readonly property int t: Tokens.devPx("bar", zone.dpr)
            readonly property int x0: Math.round(zone.litRect.x * zone.dpr)
            readonly property int y0: Math.round(zone.litRect.y * zone.dpr)
            readonly property int x1: Math.round((zone.litRect.x + zone.litRect.width) * zone.dpr)
            readonly property int y1: Math.round((zone.litRect.y + zone.litRect.height) * zone.dpr)
            scale: 1 / zone.dpr
            transformOrigin: Item.TopLeft
            Rectangle { x: edge.x0; y: edge.y0; width: edge.x1 - edge.x0; height: edge.t; color: Tokens.text1; antialiasing: false }
            Rectangle { x: edge.x0; y: edge.y1 - edge.t; width: edge.x1 - edge.x0; height: edge.t; color: Tokens.text1; antialiasing: false }
            Rectangle { x: edge.x0; y: edge.y0; width: edge.t; height: edge.y1 - edge.y0; color: Tokens.text1; antialiasing: false }
            Rectangle { x: edge.x1 - edge.t; y: edge.y0; width: edge.t; height: edge.y1 - edge.y0; color: Tokens.text1; antialiasing: false }
        }
    }
}

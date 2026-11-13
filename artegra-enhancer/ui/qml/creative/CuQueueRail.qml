import QtQuick
import QtQuick.Templates as T
import QtQuick.Window
import "format.js" as F

Rectangle {
    id: leg
    property var tab: null
    property real footReserve: 0
    property real stackTop: tab !== null && tab.stackTop !== undefined && tab.stackEmpty === false ? Number(tab.stackTop) - y : -1
    property bool batchRunning: tab !== null && tab.batchRunning !== undefined ? tab.batchRunning === true : qm.running
    property string inViewKey: tab !== null && tab.inViewKey !== undefined ? String(tab.inViewKey)
                               : (tab !== null && tab.readingKey !== undefined ? String(tab.readingKey) : "")
    property string dropState: ""
    property string dropWords: ""
    readonly property int inset: Tokens.legInset
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    function near(v) { return Tokens.snap(v + 0.5 / dpr, dpr) }
    readonly property bool empty: tab === null || tab.queue.count === 0
    readonly property int imageCount: tab !== null && tab.imageCount !== undefined ? tab.imageCount : qm.images
    readonly property bool running: qm.running
    readonly property bool usable: {
        if (tab === null) return false
        if (tab.canAddImages !== undefined) return tab.canAddImages === true
        return tab.connected && !(tab.engineState === "problem" && tab.problemKind !== "output")
    }
    readonly property var skipped: tab !== null && tab.rejected ? tab.rejected : []
    readonly property bool noteShown: skipped.length > 0
    readonly property bool attention: legHover.hovered || list.activeFocus
    readonly property bool tipBounds: true
    readonly property bool totalShown: !empty && imageCount > 0 && !qm.resultsOpen && !batchRunning
    readonly property bool clearShown: {
        if (empty || running) return false
        var g = qm.groupsShown
        var any = false
        for (var i = 0; i < g.length; ++i) {
            if (["done", "failed", "stopped", "earlier"].indexOf(g[i]) >= 0) any = true
            else if (g[i] !== "cleared") return false
        }
        return any
    }

    color: Tokens.ink
    clip: true

    Accessible.role: Accessible.Pane
    Accessible.name: "Images"

    HoverHandler { id: legHover }

    readonly property real nameRoom: Math.max(0, width - inset - Tokens.miniBoxWidth - Tokens.sp12 - inset)
    CuQueueModel {
        id: qm
        tab: leg.tab
        nameRoom: leg.nameRoom
        bodyHeight: Math.max(0, leg.listBottom - Tokens.hBand)
        held: bar.pressed && list.visible
    }
    property alias model: qm

    function groupRows(g) {
        var out = []
        if (tab === null) return out
        for (var i = 0; i < tab.queue.count; ++i) {
            var r = tab.rowsByKey[tab.queue.get(i).key]
            if (r && (r.kind === "input" || r.kind === "job") && qm.groupOf(r) === g) out.push(r)
        }
        return out
    }
    function smallestMax(rows) {
        var f = 0
        for (var i = 0; i < rows.length; ++i) {
            var m = Number(rows[i].maxFactor) || 0
            if (m <= 0) return 0
            f = f === 0 ? m : Math.min(f, m)
        }
        return f
    }
    function groupAction(g) {
        if (tab === null) return
        if (g === "skipped") { tab.rejected = []; return }
        var rows = groupRows(g)
        if (g === "cleared") { tab.undoClearFinished(); return }
        if (rows.length === 0) return
        if (g === "stopped") {
            if (typeof tab.queueAgain === "function") tab.queueAgain(rows, false)
            else if (typeof tab.confirmAgain === "function") tab.confirmAgain(rows)
            return
        }
        if (g === "refused") {
            var f = smallestMax(rows)
            if (f <= 0) return
            if (typeof tab.useFactorFor === "function") tab.useFactorFor(rows, f)
            else for (var i = 0; i < rows.length; ++i) tab.startInputAt(rows[i].mediaId, f)
            return
        }
        if (g === "later") {
            if (typeof tab.queueLater === "function") tab.queueLater(rows)
            else tab.startUpscale()
        }
    }
    function openTailWhenRoom() {
        if (qm.openGroups.nextTail !== undefined || !list.visible || list.height <= 0) return
        for (var i = 0; i < qm.list.count; ++i) {
            var e = qm.list.get(i)
            if (e.kind !== "fold" || e.group !== "nextTail") continue
            var n = parseInt(String(e.title), 10)
            if (!(n > 0)) return
            if (list.contentHeight - Tokens.hGroupHead + n * Tokens.hRowMedia <= list.height + 0.5) {
                var o = Object.assign({}, qm.openGroups)
                o.nextTail = true
                qm.openGroups = o
            }
            return
        }
    }
    Connections {
        target: qm
        function onSynced() { Qt.callLater(leg.openTailWhenRoom) }
    }
    onListBottomChanged: Qt.callLater(openTailWhenRoom)
    function toggleGroup(g) {
        if (tab === null) return
        if (g === "earlier" && !qm.resultsOpen && qm.openGroups.earlier === undefined) {
            tab.earlierOpen = !tab.earlierOpen
            return
        }
        var o = Object.assign({}, qm.openGroups)
        o[g] = qm.folded(g)
        qm.openGroups = o
    }

    readonly property string addBlockedTip: {
        if (tab === null || usable) return ""
        if (tab.engineState === "problem") return "Images can be added once the engine's problem is solved."
        if (tab.reconnecting === true) return "Images can be added once the engine is back."
        return "Images can be added once the engine has started."
    }
    Item {
        id: header
        width: parent.width
        height: Tokens.hBand

        CuButton {
            id: addBtn
            objectName: "railAddImages"
            x: Tokens.snap(header.width - leg.inset - width, leg.dpr)
            y: Tokens.snap((header.height - height) / 2, leg.dpr)
            variant: "tile"
            ground: "ink"
            iconName: "add"
            text: "Add"
            enabled: leg.usable
            menuModel: [{ label: "Add images…", value: "images" }, { label: "Add a folder…", value: "folder" }]
            tooltip: Tokens.keyTip("Add images", "Ctrl+O")
            accessibleDescription: "Opens the file picker. You can also drop images or folders anywhere on the tab."
            onClicked: leg.tab.openFileDialog()
            onMenuChosen: (value) => {
                if (value === "folder" && typeof leg.tab.openFolderDialog === "function") leg.tab.openFolderDialog()
                else leg.tab.openFileDialog()
            }
        }
        Item {
            x: addBtn.x
            y: addBtn.y
            width: addBtn.width
            height: addBtn.height
            visible: !addBtn.enabled && leg.addBlockedTip !== ""
            HoverHandler { id: addOffHover }
            CuHoverTip { shown: addOffHover.hovered; text: leg.addBlockedTip; placement: "below" }
        }
        CuText {
            id: title
            objectName: "railTitle"
            x: leg.inset
            y: leg.near(addBtn.y + addBtn.labelItem.y + addBtn.labelItem.baselineOffset - baselineOffset)
            text: "Images"
            role: "title"
            color: Tokens.text1
            Accessible.role: Accessible.Heading
            Accessible.name: leg.imageCount === 0 ? text : text + ", " + F.plural(leg.imageCount, "image", "images")
        }
        CuText {
            id: count
            objectName: "railCount"
            visible: leg.totalShown && (!clearBtn.visible
                                        || clearBtn.x + Tokens.textBleed - (x + Math.ceil(implicitWidth)) >= Tokens.sp16)
            x: Tokens.snap(title.x + Math.ceil(title.implicitWidth) + Tokens.sp8, leg.dpr)
            y: leg.near(title.y + title.baselineOffset - baselineOffset)
            text: leg.totalShown ? String(leg.imageCount) : ""
            role: "body"
            color: Tokens.text3
            tabular: true
            Accessible.ignored: true
        }
        CuButton {
            id: clearBtn
            objectName: "railClearFinished"
            visible: leg.clearShown
            x: Tokens.snap(addBtn.x - Tokens.sp8 - Tokens.textBleed - width, leg.dpr)
            y: leg.near(title.y + title.baselineOffset - (labelItem.y + labelItem.baselineOffset))
            variant: "text"
            ground: "ink"
            text: "Clear"
            tooltip: "Clear finished images from this list. Their files stay in the output folder."
            accessibleDescription: tooltip
            onClicked: leg.tab.clearFinished()
        }
    }

    readonly property real bodyTop: header.height
    readonly property real listBottom: {
        if (stackTop >= 0 && stackTop < height - 0.5) return Math.max(bodyTop, Tokens.snap(stackTop - Tokens.sp8, dpr))
        if (footReserve > 0) return Math.max(bodyTop, Tokens.snap(height - footReserve, dpr))
        return height
    }
    readonly property real bodyBottom: listBottom

    Column {
        id: pinnedColumn
        objectName: "queuePinned"
        y: leg.bodyTop
        width: leg.width
        visible: !leg.empty
        Repeater {
            id: pinnedRepeater
            model: qm.pinned
            delegate: CuQueueRow {
                tab: leg.tab
                rail: leg
                view: list
                listFocused: list.keyboardFocus
            }
        }
    }

    readonly property string dropGroup: running ? "later" : "next"
    readonly property var dropSpot: {
        if (dropState !== "list") return null
        qm.list.count
        var g = dropGroup
        var order = qm.order
        var last = -1
        for (var i = 0; i < qm.list.count; ++i) {
            var e = qm.list.get(i)
            if (e.group === g || (g === "next" && e.group === "nextTail")) last = i
        }
        if (last >= 0) return { key: qm.list.get(last).key, after: true }
        var at = order.indexOf(g)
        for (var j = 0; j < qm.list.count; ++j) {
            var f = qm.list.get(j)
            var k = order.indexOf(f.group)
            if (k > at) return { key: f.key, after: false }
        }
        if (qm.list.count > 0) return { key: qm.list.get(qm.list.count - 1).key, after: true }
        return { key: "", after: true }
    }
    onDropSpotChanged: {
        if (dropSpot === null || dropSpot.key === "") return
        var k = dropSpot.key
        Qt.callLater(function() { list.reveal(list.listIndexOfKey(k)) })
    }

    Item {
        id: body
        y: leg.bodyTop + pinnedColumn.height
        width: leg.width
        height: Math.max(0, leg.listBottom - y)
        visible: !leg.empty || leg.noteShown

        CuQueueDropRow {
            objectName: "queueDropRowAlone"
            visible: leg.dropSpot !== null && leg.dropSpot.key === ""
            width: parent.width
            height: Tokens.hRowMedia
            inset: leg.inset
            words: leg.dropWords
        }

        ListView {
            id: list
            objectName: "queueList"
            y: leg.dropSpot !== null && leg.dropSpot.key === "" ? Tokens.hRowMedia : 0
            width: parent.width
            readonly property real room: Math.max(0, body.height - y)
            property bool atRest: true
            function syncRest() { var t = contentY <= originY + 0.5; if (t !== atRest) atRest = t }
            property real restCut: -1
            height: atRest && restCut > 0 ? restCut : room
            function measureCut() {
                if (contentHeight <= room + 0.5) { if (restCut !== -1) restCut = -1; return }
                var best = -1
                for (var i = 0; i < count; ++i) {
                    var it = itemAtIndex(i)
                    if (!it || !it.visible || it.height <= 0) continue
                    var b = it.y - originY + it.height
                    if (b <= room + 0.5 && b > best) best = b
                }
                var cut = best > 0 ? Tokens.snap(best, leg.dpr) : -1
                if (cut !== restCut) restCut = cut
            }
            Timer { id: restCutTimer; interval: 0; onTriggered: list.measureCut() }
            onRoomChanged: restCutTimer.restart()
            onContentHeightChanged: restCutTimer.restart()
            onCountChanged: restCutTimer.restart()
            property bool selectedWasInView: false
            onHeightChanged: {
                if (contentY > maxY + 0.5) contentY = maxY
                var i = listIndexOfKey(leg.tab ? leg.tab.selectedKey : "")
                if (i >= 0 && selectedWasInView && !inView(i)) Qt.callLater(function() { list.reveal(i) })
                selectedWasInView = i >= 0 && inView(i)
            }
            function noteSelectedInView() { var i = listIndexOfKey(leg.tab ? leg.tab.selectedKey : ""); selectedWasInView = i >= 0 && inView(i) }
            clip: true
            spacing: 0
            interactive: false
            boundsBehavior: Flickable.StopAtBounds
            model: qm.list
            reuseItems: true
            cacheBuffer: 2400
            activeFocusOnTab: true
            keyNavigationEnabled: false
            currentIndex: -1
            highlightFollowsCurrentItem: false
            readonly property real maxY: Math.max(originY, originY + contentHeight - height)
            readonly property bool scrolled: contentY > originY + 0.5
            readonly property bool moreBelow: contentHeight > height + 0.5 && contentY < maxY - 0.5

            CuWheelScroll { }

            property bool keyNav: false
            property bool fromPointer: false
            readonly property bool keyboardFocus: activeFocus && keyNav
            function takePointerFocus() {
                keyNav = false
                if (!activeFocus) {
                    fromPointer = true
                    forceActiveFocus(Qt.MouseFocusReason)
                }
            }
            onActiveFocusChanged: {
                keyNav = activeFocus && !fromPointer
                fromPointer = false
            }

            function sequence() {
                var out = []
                for (var p = 0; p < qm.pinned.count; ++p) {
                    var e = qm.pinned.get(p)
                    if (e.kind === "input" || e.kind === "job") out.push({ pinned: true, index: p, key: e.key })
                }
                for (var i = 0; i < qm.list.count; ++i) {
                    var l = qm.list.get(i)
                    if (l.kind === "input" || l.kind === "job") out.push({ pinned: false, index: i, key: l.key })
                }
                return out
            }
            function listIndexOfKey(k) {
                for (var i = 0; i < qm.list.count; ++i) if (qm.list.get(i).key === k) return i
                return -1
            }
            function reveal(i) {
                if (i < 0) return
                var item = itemAtIndex(i)
                if (!item) {
                    positionViewAtIndex(i, ListView.Contain)
                    item = itemAtIndex(i)
                    if (!item) return
                }
                var lo = originY
                var hi = Math.max(lo, originY + contentHeight - height)
                var y = contentY
                var band = sticky.bandHeight
                if (item.y < y + (y > lo + 0.5 ? band : 0)) y = item.y - band
                else if (item.y + item.height > y + height) y = item.y + item.height - height
                y = Math.round(Math.max(lo, Math.min(hi, y)))
                if (y <= lo + band) y = item.y + item.height <= lo + height ? lo : y
                if (y !== contentY) contentY = y
            }
            function inView(i) {
                var item = itemAtIndex(i)
                return item !== null && item.y >= contentY + (contentY > originY + 0.5 ? sticky.bandHeight : 0)
                       && item.y + item.height <= contentY + height
            }

            Keys.onPressed: (event) => {
                var k = event.key
                if (k === Qt.Key_Down || k === Qt.Key_Up || k === Qt.Key_Home || k === Qt.Key_End) {
                    keyNav = true
                    event.accepted = true
                    var seq = sequence()
                    if (seq.length === 0) return
                    var at = -1
                    for (var s = 0; s < seq.length; ++s) if (seq[s].key === leg.tab.selectedKey) at = s
                    var to = k === Qt.Key_Home ? 0 : k === Qt.Key_End ? seq.length - 1
                           : k === Qt.Key_Down ? (at < 0 ? 0 : Math.min(seq.length - 1, at + 1))
                           : (at < 0 ? seq.length - 1 : Math.max(0, at - 1))
                    revealedKey = seq[to].key
                    leg.tab.selectKey(revealedKey)
                    if (!seq[to].pinned) Qt.callLater(function() { list.reveal(list.listIndexOfKey(leg.tab.selectedKey)) })
                } else if (k === Qt.Key_Delete && leg.tab.selectedKey !== "") {
                    var r = leg.tab.rowsByKey[leg.tab.selectedKey]
                    if (r && r.kind === "job" && F.contains(F.ACTIVE_ITEM_STATES, r.status)) {
                        leg.tab.requestCancelItem(r)
                        event.accepted = true
                    }
                }
            }

            property string revealedKey: ""
            Connections {
                target: leg.tab
                function onSelectedKeyChanged() {
                    var k = leg.tab.selectedKey
                    if (k === "" || k === list.revealedKey) return
                    list.revealedKey = k
                    Qt.callLater(function() {
                        var i = list.listIndexOfKey(k)
                        if (i >= 0 && !list.inView(i)) list.reveal(i)
                        list.selectedWasInView = i >= 0 && list.inView(i)
                    })
                }
                function onQueueAboutToChange() { list.anchor = bar.pressed ? null : list.rowsOnScreen() }
            }
            Connections {
                target: qm
                function onSynced() { list.keepRowsOnScreen() }
                function onReleasing() { list.anchor = list.rowsOnScreen() }
            }
            property var anchor: null
            function rowsOnScreen() {
                if (!visible || qm.list.count === 0) return null
                if (contentY <= originY + 0.5) return { top: true, rows: [], cy: contentY }
                var out = []
                for (var i = 0; i < qm.list.count; ++i) {
                    var it = itemAtIndex(i)
                    if (!it || it.height <= 0 || it.y + it.height <= contentY + 0.5) continue
                    if (it.y >= contentY + height) break
                    var r = qm.list.get(i)
                    if (r.kind !== "input" && r.kind !== "job" && r.kind !== "removed") continue
                    out.push({ key: r.key, group: r.group, y: it.y })
                }
                return out.length > 0 ? { top: false, rows: out, cy: contentY } : null
            }
            function keepRowsOnScreen() {
                var a = anchor
                anchor = null
                if (!a) return
                forceLayout()
                var lo = originY
                var hi = Math.max(lo, originY + contentHeight - height)
                var y = lo
                if (!a.top) {
                    var shift = null
                    for (var j = 0; shift === null && j < a.rows.length; ++j) {
                        var i = listIndexOfKey(a.rows[j].key)
                        if (i < 0 || qm.list.get(i).group !== a.rows[j].group) continue
                        var it = itemAtIndex(i)
                        if (!it || it.height <= 0) continue
                        shift = Math.abs(it.y - a.rows[j].y) < 0.5 ? 0 : it.y - a.rows[j].y
                    }
                    if (shift === null) return
                    y = Math.max(lo, Math.min(hi, a.cy + shift))
                }
                if (Math.abs(y - contentY) > 0.001) contentY = y
            }
            onContentYChanged: { leg.closePlate(); noteSelectedInView(); Qt.callLater(syncRest) }

            Accessible.role: Accessible.List
            Accessible.name: "Image queue"

            T.ScrollBar.vertical: CuScrollBar { id: bar; objectName: "queueScrollBar"; regionHovered: legHover.hovered }

            delegate: CuQueueRow {
                tab: leg.tab
                rail: leg
                view: list
                listFocused: list.keyboardFocus
            }

            footer: Column {
                id: skippedGroup
                objectName: "rejectedNotice"
                width: list.width
                visible: leg.noteShown
                height: visible ? implicitHeight : 0
                Accessible.role: Accessible.AlertMessage
                Accessible.name: F.plural(leg.skipped.length, "file", "files") + " skipped"
                CuTrayGroupHeading {
                    width: parent.width
                    height: Tokens.hGroupHead
                    rail: leg
                    tab: leg.tab
                    group: "skipped"
                    title: "Skipped"
                    action: "Dismiss"
                    actionTip: "Hides the list of files that were not added"
                }
                Repeater {
                    model: leg.noteShown ? leg.skipped.slice(0, 4) : []
                    CuListRow {
                        id: skipRow
                        required property var modelData
                        readonly property string reason: String(modelData.reason || "")
                        width: skippedGroup.width
                        kind: "media"
                        ground: "ink"
                        hoverEnabled: false
                        inset: leg.inset
                        text: Tokens.elideName(String(modelData.name || ""), Math.max(0, width - textX - inset), skipFm, false)
                        meta: leg.shortReason(reason, Math.max(0, width - textX - inset))
                        Accessible.name: String(modelData.name || "") + ", " + reason
                        HoverHandler { id: skipHover }
                        CuHoverTip { shown: skipHover.hovered && skipRow.meta !== skipRow.reason.replace(/\.$/, ""); text: skipRow.reason }
                    }
                }
                CuText {
                    visible: leg.skipped.length > 4
                    x: leg.inset + Tokens.miniBoxWidth + Tokens.sp12
                    width: Math.max(0, parent.width - x - leg.inset)
                    height: visible ? Tokens.hRow : 0
                    topPadding: Tokens.sp12
                    elide: Text.ElideRight
                    role: "meta"
                    color: Tokens.text3
                    text: "and " + (leg.skipped.length - 4) + " more, listed in Activity"
                }
            }
        }

        Item {
            id: sticky
            objectName: "queueSticky"
            readonly property int bandHeight: Tokens.hGroupHead
            readonly property var state_: {
                list.contentY; list.originY; list.count; qm.list.count
                var view = list.contentY
                var cur = null, next = null
                for (var i = 0; i < qm.list.count; ++i) {
                    var e = qm.list.get(i)
                    if (e.kind !== "heading") continue
                    var it = list.itemAtIndex(i)
                    if (!it) continue
                    var top = it.y + (it.bodyTop !== undefined ? it.bodyTop : 0)
                    if (top - view <= 0) cur = { title: e.title, group: e.group, danger: e.danger }
                    else { next = top - view; break }
                }
                return { cur: cur, shift: cur !== null && next !== null ? Math.min(0, next - Tokens.hGroupHead) : 0 }
            }
            readonly property bool showing: state_.cur !== null && list.scrolled
            y: list.y + state_.shift
            width: list.width
            height: bandHeight
            visible: showing
            Rectangle { anchors.fill: parent; color: Tokens.ink }
            CuText {
                x: leg.inset
                y: Tokens.sp16
                width: Math.max(0, parent.width - 2 * leg.inset)
                elide: Text.ElideRight
                role: "bodyStrong"
                color: sticky.state_.cur && sticky.state_.cur.danger ? Tokens.danger : Tokens.text2
                text: sticky.state_.cur ? sticky.state_.cur.title : ""
            }
            CuSettingsRule {
                objectName: "queueStickyRule"
                ground: "ink"
                y: parent.height
                width: parent.width
            }
        }
        CuSettingsRule {
            objectName: "queueTopRule"
            visible: list.scrolled && !sticky.showing
            ground: "ink"
            y: list.y
            width: list.width
        }
        CuSettingsRule {
            objectName: "queueEndRule"
            visible: list.moreBelow
            ground: "ink"
            y: Tokens.snap(list.y + list.height - 1 / leg.dpr, leg.dpr)
            width: list.width
        }
    }

    FontMetrics { id: skipFm; font: Tokens.fontFor("body") }
    FontMetrics { id: reasonFm; font: Tokens.fontFor("meta") }
    function shortReason(r, room) {
        var t = String(r || "").replace(/\.$/, "")
        if (reasonFm.advanceWidth(t) <= room) return t
        var first = t.split(/;\s|\.\s/)[0]
        return first
    }

    CuQueueHoverThumb {
        id: plate
        rail: leg
        z: 40
    }
    function openPlate(row) { plate.openFor(row) }
    function closePlate(row) { if (row === undefined || plate.row === row) plate.close() }
    onWidthChanged: closePlate()
    onHeightChanged: closePlate()
    readonly property real plateTop: bodyTop
    readonly property real plateBottom: body.y + list.y + list.height
}

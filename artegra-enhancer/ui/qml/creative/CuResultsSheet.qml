import QtQuick
import QtQuick.Window
import QtQuick.Templates as T
import "format.js" as F

Rectangle {
    id: sheet
    objectName: "resultsSheet"
    property var tab: null
    property bool shown: false
    signal closeRequested()
    visible: shown
    color: Tokens.stage
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    function near(v) { return Tokens.snap(v + 0.5 / dpr, dpr) }
    readonly property int inset: Tokens.openingInset
    readonly property real aw: Math.max(0, width - 2 * inset)

    readonly property var last: tab && tab.batch ? tab.batch.last : null
    readonly property var runJobs: {
        var out = []
        if (!last || !tab) return out
        var ids = last.ids && last.ids.length ? last.ids : [last.id]
        for (var i = 0; i < ids.length; ++i) {
            var j = tab.jobFor(ids[i])
            if (j) out.push(j)
        }
        return out
    }
    readonly property var job: runJobs.length > 0 ? runJobs[0] : null
    readonly property var cells: {
        var out = []
        if (!job || !tab) return out
        for (var r = 0; r < runJobs.length; ++r) {
            for (var q = 0; q < runJobs[r].items.length; ++q) {
                var it = runJobs[r].items[q]
                var key = tab.itemKey(runJobs[r].id, it.itemId)
                var row = tab.rowsByKey[key] || null
                var w = it.width > 0 ? it.width : 4, h = it.height > 0 ? it.height : 3
                var eff = it.effective || runJobs[r].effective || null
                var fct = eff && eff.scale ? Number(eff.scale) : 2
                var ow = it.outW > 0 ? it.outW : w * fct, oh = it.outH > 0 ? it.outH : h * fct
                var stopped = it.state === "stopped" || it.state === "cancelled"
                var lastFrame = it.state !== "done" && row !== null && !!row.lastFrameUrl
                var src = it.state === "done" && it.resultProxyUrl !== "" ? it.resultProxyUrl
                        : (lastFrame ? row.lastFrameUrl : it.proxyUrl)
                out.push({ key: key, name: it.name, aspect: w / h, state: it.state, failed: it.state === "failed",
                           stopped: stopped, outW: ow, outH: oh, errorText: it.errorText || "", at: it.at || null,
                           gpu: it.gpu, tookS: it.tookS,
                           url: src !== "" && tab.service ? tab.service.mediaUrl(src) : "" })
            }
        }
        return out
    }
    readonly property int doneCount: { var n = 0; for (var i = 0; i < cells.length; ++i) if (cells[i].state === "done") n += 1; return n }
    property var opened: ({})
    function noteOpened() {
        if (!tab) return
        var k = tab.selectedKey
        if (k === "" || opened[k]) return
        var row = tab.rowsByKey ? tab.rowsByKey[k] : null
        if (!row || row.kind !== "job" || row.status !== "done") return
        var o = Object.assign({}, opened)
        o[k] = true
        opened = o
    }
    Connections {
        target: sheet.tab
        function onSelectedKeyChanged() { sheet.noteOpened() }
        function onRowsByKeyChanged() { sheet.noteOpened() }
    }
    Component.onCompleted: noteOpened()
    readonly property int openedCount: { var n = 0; for (var i = 0; i < cells.length; ++i) if (opened[cells[i].key]) n += 1; return n }
    readonly property string headline: {
        if (!job) return ""
        var n = cells.length
        var factors = []
        for (var r = 0; r < runJobs.length; ++r) {
            for (var q = 0; q < runJobs[r].items.length; ++q) {
                var e = runJobs[r].items[q].effective || runJobs[r].effective
                var f = e && e.scale ? Number(e.scale) : 0
                if (f > 0 && factors.indexOf(f) < 0) factors.push(f)
            }
        }
        var at = factors.length === 1 ? " at " + F.scaleLabel(factors[0]) : ""
        return (doneCount === n ? F.plural(n, "image", "images") : F.doneOf(doneCount, n)) + at
    }
    function causeOf(c) {
        if (c.stopped) {
            var p = c.at && c.at.pass ? String(c.at.pass) : ""
            return p === "structure" ? "Stopped in the structure pass" : p === "detail" ? "Stopped in the detail pass" : "Stopped"
        }
        var t = String(c.errorText || "")
        var m = /\b(GPU \d+) ran out of memory/i.exec(t)
        if (m) return "Out of memory on " + m[1]
        if (/out of memory/i.test(t)) return "Out of memory"
        var first = t.split(/\.\s/)[0].replace(/\.$/, "").trim()
        return first !== "" && first.length <= 40 ? first : "Did not finish"
    }

    readonly property int gap: Tokens.sp16
    readonly property int minCell: 240
    readonly property int columns: Math.max(1, Math.floor((aw + gap) / (minCell + gap)))
    readonly property real cellWidth: Math.max(0, Math.floor((aw - gap * (columns - 1)) / columns * dpr) / dpr)
    readonly property real boxHeight: Tokens.snap(cellWidth * 10 / 16, dpr)
    readonly property real nameLine: Tokens.type.body.line
    readonly property real sizeLine: Tokens.type.meta.line
    readonly property real cellHeight: boxHeight + Tokens.sp8 + nameLine + sizeLine
    readonly property real pitchX: cellWidth + gap
    readonly property real pitchY: Tokens.snap(cellHeight + gap, dpr)
    readonly property int rows: Math.ceil(cells.length / columns)

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: (wheel) => { wheel.accepted = true } }

    property int kbIndex: -1
    property bool kbNav: false
    function indexOfKey(k) { for (var i = 0; i < cells.length; ++i) if (cells[i].key === k) return i; return -1 }
    property Item returnFocus: null
    onShownChanged: {
        if (shown) {
            var w = Window.window
            returnFocus = w ? w.activeFocusItem : null
            kbNav = false
            kbIndex = tab ? indexOfKey(tab.selectedKey) : -1
            sheet.forceActiveFocus()
        } else {
            var back = returnFocus !== null && returnFocus.visible ? returnFocus : tab
            returnFocus = null
            if (back && typeof back.forceActiveFocus === "function") back.forceActiveFocus()
        }
    }
    function openCell(i) {
        if (i < 0 || i >= cells.length || !tab) return
        tab.selectKey(cells[i].key)
        sheet.closeRequested()
    }
    function moveTo(i) {
        if (cells.length === 0) return
        kbNav = true
        kbIndex = Math.max(0, Math.min(cells.length - 1, i))
        var item = repeater.itemAt(kbIndex)
        if (item) scroll.reveal(item)
    }
    Keys.onShortcutOverride: (event) => { if (event.key === Qt.Key_Escape && sheet.shown && Tokens.tipsOpen === 0) event.accepted = true }
    Keys.onEscapePressed: (event) => { sheet.closeRequested(); event.accepted = true }
    Keys.onPressed: (event) => {
        var k = event.key
        var at = kbIndex < 0 ? -1 : kbIndex
        if (k === Qt.Key_Right) moveTo(at + 1)
        else if (k === Qt.Key_Left) moveTo(at < 0 ? 0 : at - 1)
        else if (k === Qt.Key_Down) moveTo(at < 0 ? 0 : at + columns)
        else if (k === Qt.Key_Up) moveTo(at < 0 ? 0 : at - columns)
        else if (k === Qt.Key_Home) moveTo(0)
        else if (k === Qt.Key_End) moveTo(cells.length - 1)
        else if ((k === Qt.Key_Return || k === Qt.Key_Enter || k === Qt.Key_Space) && kbIndex >= 0) openCell(kbIndex)
        else return
        event.accepted = true
    }

    Item {
        id: toolLine
        objectName: "resultsToolLine"
        x: sheet.inset
        y: 0
        width: sheet.aw
        height: Tokens.hBand
        CuButton {
            id: closeBtn
            objectName: "resultsClose"
            x: Tokens.snap(toolLine.width - width, sheet.dpr)
            y: sheet.near(openBtn.y + openBtn.labelItem.y + openBtn.labelItem.baselineOffset - (labelItem.y + labelItem.baselineOffset))
            variant: "text"
            ground: "stage"
            text: "Close"
            tooltip: "Close the results"
            keyCap: "Esc"
            onClicked: sheet.closeRequested()
        }
        CuButton {
            id: openBtn
            objectName: "resultsOpenFolder"
            x: Tokens.snap(closeBtn.x - Tokens.textBleed - Tokens.sp8 - width, sheet.dpr)
            y: Tokens.snap((toolLine.height - height) / 2, sheet.dpr)
            variant: "tile"
            ground: "stage"
            iconName: "folder"
            text: "Open folder"
            tooltip: sheet.job ? (sheet.job.outputDir || sheet.tab.outputDir) : ""
            onClicked: sheet.tab.openPath(sheet.job ? (sheet.job.outputDir || sheet.tab.outputDir) : sheet.tab.outputDir, "output folder")
        }
        CuText {
            id: sheetTitle
            objectName: "resultsTitle"
            y: sheet.near(openBtn.y + openBtn.labelItem.y + openBtn.labelItem.baselineOffset - baselineOffset)
            text: "Results"
            role: "title"
            color: Tokens.text1
            Accessible.role: Accessible.Heading
            Accessible.name: text + ", " + sheet.headline
        }
        CuText {
            objectName: "resultsHeadline"
            x: Tokens.snap(Math.ceil(sheetTitle.implicitWidth) + Tokens.sp8, sheet.dpr)
            y: sheet.near(sheetTitle.y + sheetTitle.baselineOffset - baselineOffset)
            width: Math.max(0, openBtn.x - Tokens.sp16 - x)
            elide: Text.ElideRight
            text: sheet.headline
            role: "body"
            tabular: true
            color: Tokens.text3
            Accessible.ignored: true
        }
    }

    CuScrollArea {
        id: scroll
        objectName: "resultsScroll"
        x: 0
        y: toolLine.height + Tokens.sp24 - Tokens.sp8
        width: sheet.width
        height: Math.max(0, sheet.height - y - Tokens.sp24 + Tokens.sp8)
        ground: "stage"
        surface: Tokens.stage
        regionHovered: sheetHover.hovered
        Item {
            id: grid
            x: sheet.inset
            y: Tokens.sp8
            width: sheet.aw
            height: sheet.rows > 0 ? sheet.rows * sheet.pitchY - sheet.gap + 2 * Tokens.sp8 : 0
            Repeater {
                id: repeater
                model: sheet.cells.length
                Item {
                    id: cell
                    required property int index
                    readonly property var c: sheet.cells[index] || { key: "", name: "", url: "", state: "", failed: false, stopped: false, aspect: 1.6, outW: 0, outH: 0 }
                    readonly property bool done: c.state === "done"
                    readonly property bool seen: sheet.opened[c.key] === true
                    readonly property bool chosen: sheet.kbIndex === index
                    objectName: "resultCell"
                    x: Tokens.snap((index % sheet.columns) * sheet.pitchX, sheet.dpr)
                    y: Tokens.snap(Math.floor(index / sheet.columns) * sheet.pitchY, sheet.dpr)
                    width: sheet.cellWidth
                    height: sheet.cellHeight
                    Accessible.role: Accessible.Button
                    Accessible.name: c.name + ", " + sizeText.text
                    Accessible.onPressAction: sheet.openCell(index)

                    CuListRow {
                        id: body
                        objectName: "resultBody"
                        kind: "cell"
                        ground: "stage"
                        x: -Tokens.sp8
                        y: -Tokens.sp8
                        width: cell.width + 2 * Tokens.sp8
                        height: cell.height + 2 * Tokens.sp8
                        selected: cell.chosen
                        Accessible.ignored: true
                        onClicked: sheet.openCell(cell.index)
                    }
                    CuFocusRing {
                        target: body
                        inset: true
                        shown: cell.chosen && sheet.kbNav && sheet.activeFocus
                        targetRadius: 0
                    }
                    Rectangle {
                        id: box
                        objectName: "resultBox"
                        width: cell.width
                        height: sheet.boxHeight
                        color: Tokens.wellStage
                    }
                    readonly property real picW: c.aspect >= cell.width / Math.max(1, sheet.boxHeight) ? cell.width : Tokens.snap(sheet.boxHeight * c.aspect, sheet.dpr)
                    readonly property real picH: c.aspect >= cell.width / Math.max(1, sheet.boxHeight) ? Tokens.snap(cell.width / c.aspect, sheet.dpr) : sheet.boxHeight
                    readonly property size wanted: Qt.size(Math.round(cell.picW * sheet.dpr), Math.round(cell.picH * sheet.dpr))
                    property size decodeAt: Qt.size(0, 0)
                    onWantedChanged: { if (decodeAt.width <= 0) decodeAt = wanted; else settle.restart() }
                    Component.onCompleted: decodeAt = wanted
                    Timer { id: settle; interval: 250; onTriggered: cell.decodeAt = cell.wanted }
                    Image {
                        id: pic
                        objectName: "resultPicture"
                        x: Tokens.snap((cell.width - cell.picW) / 2, sheet.dpr)
                        y: Tokens.snap((sheet.boxHeight - cell.picH) / 2, sheet.dpr)
                        width: cell.picW
                        height: cell.picH
                        source: cell.decodeAt.width > 0 ? cell.c.url : ""
                        asynchronous: true
                        cache: false
                        retainWhileLoading: true
                        fillMode: Image.PreserveAspectCrop
                        mipmap: false
                        sourceSize: cell.decodeAt
                    }
                    CuName {
                        id: nameText
                        objectName: "resultName"
                        y: sheet.boxHeight + Tokens.sp8
                        name: cell.c.name
                        maxWidth: cell.width
                        role: cell.done && !cell.seen ? "bodyStrong" : "body"
                        color: cell.done && !cell.seen ? Tokens.text1 : body.stepTone(Tokens.text2)
                    }
                    CuText {
                        id: sizeText
                        objectName: "resultSize"
                        y: nameText.y + sheet.nameLine
                        width: cell.width
                        elide: Text.ElideRight
                        role: "meta"
                        tabular: true
                        color: body.stepTone(Tokens.text3)
                        text: cell.done ? F.size(cell.c.outW, cell.c.outH) : sheet.causeOf(cell.c)
                    }
                }
            }
        }
    }
    HoverHandler { id: sheetHover }
}

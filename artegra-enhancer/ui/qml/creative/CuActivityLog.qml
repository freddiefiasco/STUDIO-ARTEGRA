import QtQuick
import QtQuick.Window
import QtQuick.Templates as T
import "format.js" as F

Item {
    id: drawer
    property var tab: null
    property bool live: true
    property bool problemsOnly: false
    property bool followLatest: true

    function tsValue(ts) {
        if (typeof ts === "number") return ts > 1e12 ? ts : ts * 1000
        var v = Date.parse(ts)
        return isNaN(v) ? 0 : v
    }

    readonly property var hiddenEvents: ["inputs_added", "job_created", "job_state", "stage_progress", "item_progress", "progress"]
    function readable(l) {
        if (hiddenEvents.indexOf(l.event || "") >= 0) return false
        var m = l.msg || "", n = m.length, i = n - 2
        if (l.event === "item_started" && n > 0 && m.charCodeAt(n - 1) === 41 && m.indexOf(", from pass") < 0) return false
        if (n < 4 || m.charCodeAt(n - 1) !== 37) return true
        while (i >= 0 && m.charCodeAt(i) >= 48 && m.charCodeAt(i) <= 57) --i
        return !(i < n - 2 && i >= 1 && m.charCodeAt(i) === 32 && m.charCodeAt(i - 1) === 44)
    }
    function levelOf(l) { var v = l.level || "info"; return v === "warn" ? "warning" : v === "exception" ? "error" : v }

    property var svcPrev: []
    property var svcSeqs: []
    property int svcSeq: 0
    function sameLine(a, b) {
        return a.ts === b.ts && a.msg === b.msg && a.event === b.event && a.level === b.level && a.job === b.job
               && a.item === b.item && a.log_ref === b.log_ref
    }
    function numberEngineLines(svc) {
        if (svc === svcPrev) return svcSeqs
        var old = svcPrev, oldSeqs = svcSeqs, n0 = old.length, from = n0, keep = 0
        if (n0 > 0 && svc.length > 0) {
            for (var e = Math.min(svc.length, n0) - 1; e >= 0; --e) {
                if (!sameLine(old[n0 - 1], svc[e])) continue
                var k = n0 - 1 - e
                var ok = true
                for (var j = 0; ok && j < e; ++j) ok = sameLine(old[k + j], svc[j])
                if (ok) { from = k; keep = e + 1; break }
            }
        }
        var seqs = new Array(svc.length)
        var next = svcSeq
        for (var i = 0; i < svc.length; ++i) seqs[i] = i < keep ? oldSeqs[from + i] : ++next
        svcSeq = next
        svcPrev = svc
        svcSeqs = seqs
        return seqs
    }

    function mergedKeys(svc, seqs, own) {
        var keys = [], codes = []
        var ia = 0, ib = 0
        while (ia < svc.length && !readable(svc[ia])) ++ia
        while (ia < svc.length || ib < own.length) {
            var fromEngine = ib >= own.length || (ia < svc.length && tsValue(svc[ia].ts) <= own[ib].ts)
            if (fromEngine) {
                if (!problemsOnly || levelOf(svc[ia]) === "warning" || levelOf(svc[ia]) === "error") {
                    keys.push(seqs[ia])
                    codes.push(ia)
                }
                ++ia
                while (ia < svc.length && !readable(svc[ia])) ++ia
            } else {
                var o = own[ib]
                if (!problemsOnly || o.level === "warning" || o.level === "error") {
                    keys.push(-(o.seq !== undefined ? o.seq : ib + 1))
                    codes.push(-(ib + 1))
                }
                ++ib
            }
        }
        var cut = Math.max(0, keys.length - 200)
        var k2 = cut > 0 ? keys.slice(cut) : keys, c2 = cut > 0 ? codes.slice(cut) : codes
        return { keys: k2.slice().reverse(), codes: c2.slice().reverse() }
    }
    function lineRow(key, code, svc, own) {
        if (code >= 0) {
            var l = svc[code]
            return { key: key, t: tsValue(l.ts), level: String(levelOf(l)).toLowerCase(), msg: String(l.msg || l.message || l.event || ""),
                     job: l.job ? String(l.job) : "", source: "engine", ref: l.log_ref ? String(l.log_ref) : "" }
        }
        var o = own[-code - 1]
        return { key: key, t: Number(o.ts), level: String(o.level || "info"), msg: String(o.msg || ""), job: o.job ? String(o.job) : "",
                 source: "tab", ref: "" }
    }
    function lineTexts() {
        var out = []
        for (var i = 0; i < lineModel.count; ++i) out.push(lineModel.get(i).msg)
        return out
    }

    property var lineKeys: []
    property int linesBuilt: 0
    property bool pending: false
    ListModel { id: lineModel }

    function sync() {
        if (!live || !tab) return
        if (sb.pressed) { pending = true; return }
        pending = false
        var svc = tab.serviceLog || []
        var own = tab.tabLog || []
        var m = mergedKeys(svc, numberEngineLines(svc), own)
        var next = m.keys
        var keys = lineKeys
        var same = next.length === keys.length
        for (var s = 0; same && s < next.length; ++s) same = next[s] === keys[s]
        if (same) return
        keys = keys.slice()
        var anchor = followLatest ? null : firstOnScreen()
        var cy0 = list.contentY
        selfMoving = true
        for (var r = keys.length - 1; r >= 0; ) {
            if (next.indexOf(keys[r]) >= 0) { --r; continue }
            var end = r
            while (r >= 0 && next.indexOf(keys[r]) < 0) --r
            lineModel.remove(r + 1, end - r)
            keys.splice(r + 1, end - r)
        }
        for (var k = 0; k < next.length; ++k) {
            var key = next[k]
            if (k < keys.length && keys[k] === key) continue
            if (keys.indexOf(key, k) >= 0) {
                var from = keys.indexOf(key, k)
                lineModel.move(from, k, 1)
                keys.splice(from, 1)
                keys.splice(k, 0, key)
                continue
            }
            if (k === keys.length) {
                var add = []
                for (var a = k; a < next.length; ++a) add.push(lineRow(next[a], m.codes[a], svc, own))
                lineModel.append(add)
                for (var p = k; p < next.length; ++p) keys.push(next[p])
                break
            }
            lineModel.insert(k, lineRow(key, m.codes[k], svc, own))
            keys.splice(k, 0, key)
        }
        lineKeys = keys
        list.forceLayout()
        if (!followLatest) keepOnScreen(anchor, cy0)
        selfMoving = false
        if (followLatest) Qt.callLater(drawer.toEnd)
    }
    function firstOnScreen() {
        if (list.contentY <= list.originY - list.topMargin + 0.5) return null
        for (var i = 0; i < lineModel.count; ++i) {
            var it = list.itemAtIndex(i)
            if (!it || it.y + it.height <= list.contentY + 0.5) continue
            if (it.y >= list.contentY + list.height) break
            return { key: lineKeys[i], y: it.y }
        }
        return null
    }
    function keepOnScreen(anchor, cy0) {
        var shift = 0
        if (anchor) {
            var i = lineKeys.indexOf(anchor.key)
            var it = i >= 0 ? list.itemAtIndex(i) : null
            if (it && Math.abs(it.y - anchor.y) >= 0.5) shift = it.y - anchor.y
        }
        var lo = list.originY - list.topMargin
        var hi = Math.max(lo, list.originY + list.contentHeight + list.bottomMargin - list.height)
        var y = Math.max(lo, Math.min(hi, cy0 + shift))
        if (Math.abs(y - list.contentY) > 0.001) list.contentY = y
    }
    Connections {
        target: drawer.tab
        function onServiceLogChanged() { drawer.sync() }
        function onTabLogChanged() { drawer.sync() }
    }
    onProblemsOnlyChanged: sync()
    onLiveChanged: { if (live) sync() }
    Component.onCompleted: sync()

    property bool selfMoving: false
    function atEnd() {
        if (list.count === 0 || list.contentHeight + list.topMargin + list.bottomMargin <= list.height + 0.5) return true
        return list.contentY <= list.originY - list.topMargin + 1
    }
    function toEnd() {
        if (sb.pressed) return
        var lo = Math.round(list.originY - list.topMargin)
        if (Math.abs(list.contentY - lo) < 1) return
        selfMoving = true
        list.contentY = lo
        selfMoving = false
    }

    readonly property int inset: Tokens.legInset
    readonly property alias sheetItem: sheet
    readonly property alias copyButton: sheet.secondButton
    readonly property alias closeButton: sheet.closeButton
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    signal closeRequested()
    function focusFirst() { if (sheet.secondButton.visible) sheet.secondButton.forceActiveFocus(); else sheet.closeButton.forceActiveFocus() }

    CuSheet {
        id: sheet
        objectName: "activitySheet"
        anchors.fill: parent
        title: "Activity"
        ground: "ink"
        onCloseRequested: drawer.closeRequested()
        secondText: "Copy"
        secondTip: "Copy every line, with the batch numbers"
        onSecondClicked: drawer.copyLines()
    }

    readonly property real wordsWidth: Math.max(0, width - 2 * inset - timeWidth - Tokens.sp12)
    readonly property real nameMin: Tokens.sp64
    FontMetrics { id: lineMetrics; font: Tokens.fontFor("body") }
    FontMetrics { id: timeMetrics; font: Tokens.fontFor("body", true) }
    readonly property real timeWidth: Math.ceil(timeMetrics.advanceWidth("00:00"))
    readonly property real nameKeep: 160
    function addedWords(msg) {
        var m = /^Started (.+) \(\d+ pass(?:es)?\), (Fast mode|matching earlier results|sped up)$/.exec(msg)
        if (!m) return msg
        return m[1] + (m[2] === "Fast mode" ? " runs in Fast mode" : m[2] === "sped up" ? " runs sped up" : " matches earlier results")
    }
    function shortNames(msg) {
        msg = addedWords(msg)
        var pm = /^(.*?)((?:[A-Za-z]:|\\\\[^\\]+)\\.+)$/.exec(msg)
        if (pm && Math.ceil(lineMetrics.advanceWidth(msg)) > drawer.wordsWidth) {
            var segs = pm[2].split("\\")
            if (segs.length > 2) msg = pm[1] + segs[0] + "\\\u2026\\" + segs[segs.length - 1]
        }
        var pm2 = /^(.*?)((?:[A-Za-z]:|\\\\[^\\]+)\\.+)$/.exec(msg)
        if (pm2) msg = pm2[1] + pm2[2].replace(/ /g, "\u00a0")
        if (msg.indexOf(".") < 0) return msg
        var re = /[^\s"'()\\\/:,;]+\.(?:png|jpe?g|tiff?|webp|bmp)(?![A-Za-z0-9])/gi
        var names = msg.match(re) || []
        if (names.length === 0) return msg
        var rest = msg
        for (var i = 0; i < names.length; ++i) rest = rest.replace(names[i], "")
        var room = Math.max(drawer.nameMin, (drawer.wordsWidth - Math.ceil(lineMetrics.advanceWidth(rest))) / names.length - 2)
        if (room < drawer.nameKeep) room = Math.max(room, drawer.wordsWidth - 2)
        return msg.replace(re, function(name) { return Tokens.elideName(name, room, lineMetrics, false).replace(/…/g, "⁠…⁠") })
    }
    function hhmm(t) {
        var d = new Date(t)
        if (!isFinite(d.getTime())) return ""
        return (d.getHours() < 10 ? "0" : "") + d.getHours() + ":" + (d.getMinutes() < 10 ? "0" : "") + d.getMinutes()
    }
    function copyLines() {
        var t = []
        for (var i = 0; i < lineModel.count; ++i) {
            var l = lineModel.get(i)
            t.push(F.clockFromTs(l.t) + " " + l.level.toUpperCase() + " " + (l.source === "tab" ? "[tab] " : "") + l.msg
                   + (l.job ? " (batch " + l.job + ")" : "") + (l.ref ? " (log " + l.ref + ")" : ""))
        }
        drawer.tab.copyText(t.join("\n"))
    }

    CuCheckBox {
        id: problemsBox
        objectName: "activityProblemsOnly"
        x: drawer.inset
        y: Tokens.hBand
        width: Math.max(0, drawer.width - 2 * drawer.inset)
        ground: "ink"
        text: "Problems only"
        checked: drawer.problemsOnly
        onToggled: (on) => { drawer.problemsOnly = on }
    }
    CuText {
        id: warnLine
        objectName: "activitySummary"
        visible: drawer.tab !== null && drawer.tab.logsError !== ""
        x: drawer.inset
        y: problemsBox.y + problemsBox.height + Tokens.sp4
        width: Math.max(0, drawer.width - 2 * drawer.inset)
        text: drawer.tab ? drawer.tab.logsError : ""
        role: "meta"
        color: Tokens.text3
        elide: Text.ElideRight
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    readonly property real listTop: Tokens.hBand + Tokens.hCheckRow + Tokens.sp8 + (warnLine.visible ? Tokens.lineOf("meta") + Tokens.sp4 : 0)

    ListView {
        id: list
        objectName: "activityList"
        x: 0
        y: drawer.listTop
        width: drawer.width
        height: Math.max(0, drawer.height - y)
        topMargin: 0
        bottomMargin: Tokens.sp16
        clip: true
        interactive: false
        boundsBehavior: Flickable.StopAtBounds
        model: lineModel
        cacheBuffer: 12000
        onContentYChanged: { if (!drawer.selfMoving && drawer.live && list.height > 0) drawer.followLatest = drawer.atEnd() }
        Accessible.role: Accessible.List
        Accessible.name: "Activity log"
        activeFocusOnTab: count > 0
        Keys.onPressed: (event) => {
            var step = 0
            if (event.key === Qt.Key_Down) step = 24
            else if (event.key === Qt.Key_Up) step = -24
            else if (event.key === Qt.Key_PageDown) step = Math.max(48, list.height - 48)
            else if (event.key === Qt.Key_PageUp) step = -Math.max(48, list.height - 48)
            else if (event.key === Qt.Key_Home) { drawer.followLatest = true; drawer.toEnd(); event.accepted = true; return }
            else if (event.key === Qt.Key_End) step = 1e9
            if (step === 0) return
            var lo = list.originY - list.topMargin
            var hi = Math.max(lo, list.originY + list.contentHeight + list.bottomMargin - list.height)
            list.contentY = Math.round(Math.max(lo, Math.min(hi, list.contentY + step)))
            event.accepted = true
        }

        CuWheelScroll { }
        T.ScrollBar.vertical: CuScrollBar {
            id: sb
            objectName: "activityScrollBar"
            regionHovered: sheetHover.hovered
            onPressedChanged: { if (!pressed && drawer.pending) drawer.sync() }
        }

        delegate: Item {
            id: line
            required property string level
            required property string msg
            required property real t
            required property string ref
            width: list.width
            height: Math.max(Tokens.lineOf("body"), msgText.height) + 6
            readonly property bool problem: level === "error"
            readonly property string shown: drawer.shortNames(line.msg) + (line.ref ? " (log " + line.ref + ")" : "")
            Component.onCompleted: drawer.linesBuilt += 1
            Accessible.role: Accessible.ListItem
            Accessible.name: (problem ? "Problem: " : "") + line.msg
            CuText {
                id: time
                objectName: "activityLineTime"
                x: drawer.inset
                y: 0
                text: drawer.hhmm(line.t)
                role: "body"
                tabular: true
                color: Tokens.text3
            }
            CuText {
                id: msgText
                objectName: "activityLineWords"
                x: drawer.inset + drawer.timeWidth + Tokens.sp12
                y: 0
                width: Math.max(0, line.width - x - drawer.inset)
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                text: line.shown
                role: "body"
                color: line.problem ? Tokens.danger : Tokens.text2
            }
        }

        CuText {
            x: drawer.inset
            y: 0
            visible: list.count === 0
            text: drawer.problemsOnly ? "No problems this session." : "Nothing logged yet."
            role: "body"
            color: Tokens.text3
        }
    }
    HoverHandler { id: sheetHover }
    CuSettingsRule {
        objectName: "activityTopEdge"
        visible: list.contentY > list.originY - list.topMargin + 0.5
        x: drawer.inset
        y: Tokens.snap(list.y, drawer.dpr)
        width: Math.max(0, drawer.width - 2 * drawer.inset)
        ground: "ink"
    }
    CuFocusRing {
        target: list
        shown: list.activeFocus && (list.focusReason === undefined
                                    || list.focusReason === Qt.TabFocusReason || list.focusReason === Qt.BacktabFocusReason)
        inset: true
    }
}

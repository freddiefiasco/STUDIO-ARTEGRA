import QtQuick
import "format.js" as F

QtObject {
    id: qm
    property var tab: null
    property real bodyHeight: 0
    property var openGroups: ({})

    readonly property bool running: tab !== null && tab.batch !== undefined && tab.batch !== null && tab.batch.active === true
    readonly property bool resultsOpen: tab !== null && tab.resultsOpen === true
    readonly property string selectedKey: tab !== null ? tab.selectedKey : ""

    property ListModel pinned: ListModel { }
    property ListModel list: ListModel { }
    property int groupCount: 0
    property int images: 0
    property var groupsShown: []
    property var counts: ({})
    signal synced()

    readonly property var order: ["working", "failed", "stopped", "refused", "next", "later", "done", "cleared", "earlier"]

    function groupOf(r) {
        var g = String(r.group || "")
        if (r.kind === "job" && (r.status === "stopped" || r.status === "cancelled") && g !== "earlier"
                && !(g === "last" && running))
            return "stopped"
        switch (g) {
        case "working": case "failed": case "next": case "done": case "refused": case "earlier": case "cleared":
        case "stopped": case "later":
            return g
        case "now": return "working"
        case "cancelled": return "stopped"
        case "ready": return running ? "later" : "next"
        case "last":
            if (running) return "earlier"
            return r.status === "failed" ? "failed" : (r.status === "cancelled" || r.status === "stopped") ? "stopped" : "done"
        }
        return "next"
    }

    function isImage(r) { return r.kind === "input" || r.kind === "job" }

    readonly property int nextHead: 8
    function folded(g) {
        if (openGroups[g] !== undefined) return !openGroups[g]
        if (g === "nextTail") return true
        if (g === "earlier") return !(tab && tab.earlierOpen === true)
        if (resultsOpen) return g !== "cleared"
        if (running && (g === "done" || g === "later")) return true
        return false
    }
    function foldable(g) {
        return g === "earlier" || resultsOpen || (running && (g === "done" || g === "later"))
    }

    function actionFor(g, rows) {
        var imgs = rows.filter(isImage)
        if (g === "stopped" && imgs.length > 0 && !running && tab && tab.footerMode === "cancelled") return ""
        if (g === "stopped" && imgs.length > 0) return running ? "Queue again" : "Upscale again"
        if (g === "refused") {
            var f = 0
            for (var i = 0; i < imgs.length; ++i) {
                var m = Number(imgs[i].maxFactor) || 0
                if (m <= 0) { f = 0; break }
                f = f === 0 ? m : Math.min(f, m)
            }
            return f > 0 ? "Use " + F.scaleLabel(f) : ""
        }
        if (g === "later" && imgs.length > 0) return "Queue at " + F.scaleLabel(tab && tab.scale ? tab.scale : 2)
        if (g === "cleared") return "Undo"
        return ""
    }

    function title(g) {
        if (g === "working") return "Working"
        if (g === "failed") return "Failed"
        if (g === "stopped") return "Stopped"
        if (g === "refused") return "Too large for " + F.scaleLabel(tab && tab.scale ? tab.scale : 2)
        if (g === "next") return "Next"
        if (g === "later") return "Added later"
        if (g === "done") return "Done"
        if (g === "earlier") return "Earlier"
        if (g === "cleared") {
            var n = tab && tab.clearedLine ? tab.clearedLine.count : 0
            return F.plural(n, "finished image", "finished images") + " cleared"
        }
        return g
    }

    function blank() {
        return { key: "", kind: "", group: "", place: 0, mediaId: "", jobId: "", itemId: "", name: "", path: "",
                 srcW: 0, srcH: 0, outW: 0, outH: 0, factor: 2, status: "", progress: 0, stage: 0, stages: 0,
                 message: "", errorText: "", thumbUrl: "", proxyUrl: "", liveThumbUrl: "", output: "", duplicate: false,
                 alpha: false, refusedReason: "", maxFactor: 0, removedState: "", removedText: "", tookS: -1, gpu: -1,
                 atPass: "", atStep: -1, atSteps: 0, ownFactor: false, bytes: 0, cardsText: "", format: "",
                 livePass: "", mode: "",
                 title: "", figure: -1, action: "",
                 first: false, foldable: false, folded: false, peek: false, danger: false }
    }
    function rowEntry(r, g) {
        var e = blank()
        for (var k in e) {
            if (r[k] === undefined || r[k] === null) continue
            if (typeof e[k] === "number") e[k] = Number(r[k])
            else if (typeof e[k] === "boolean") e[k] = !!r[k]
            else e[k] = String(r[k])
        }
        if (r.gpu !== undefined && r.gpu !== null && isFinite(r.gpu)) e.gpu = Number(r.gpu)
        else if (r.cards && r.cards.length > 0) e.gpu = Number(r.cards[0])
        if (r.at && typeof r.at === "object") {
            e.atPass = r.at.pass ? String(r.at.pass) : ""
            e.atStep = r.at.step !== undefined && r.at.step !== null ? Number(r.at.step) : -1
            e.atSteps = r.at.steps ? Number(r.at.steps) : 0
        }
        if (r.liveThumb !== undefined && r.liveThumb !== null) e.liveThumbUrl = String(r.liveThumb)
        e.group = g
        return e
    }
    function headEntry(g, kind, figure, action, first, rows) {
        var e = blank()
        e.key = (kind === "fold" ? "f:" : kind === "cleared" ? "c:" : "h:") + g
        e.kind = kind
        e.group = g
        e.title = title(g)
        e.figure = figure
        e.action = action
        e.first = first
        e.foldable = foldable(g)
        e.folded = kind === "fold"
        e.danger = g === "failed"
        return e
    }

    function build() {
        var byGroup = {}
        var cnt = {}
        for (var o = 0; o < order.length; ++o) { byGroup[order[o]] = []; cnt[order[o]] = 0 }
        var total = 0
        var q = tab ? tab.queue : null
        var rows = tab ? tab.rowsByKey : null
        if (q && rows) {
            for (var i = 0; i < q.count; ++i) {
                var key = q.get(i).key
                var r = rows[key]
                if (!r) continue
                var g = groupOf(r)
                if (byGroup[g] === undefined) { byGroup[g] = []; cnt[g] = 0 }
                byGroup[g].push(r)
                if (isImage(r)) { cnt[g] += 1; total += 1 }
            }
        }
        var shown = []
        for (var s = 0; s < order.length; ++s) if (byGroup[order[s]].length > 0) shown.push(order[s])
        var only = shown.length === 1 ? shown[0] : ""
        function heightOf(g) { return (shown.length > 1 ? 48 : 0) + 48 * byGroup[g].length }
        var pinWorking = byGroup.working.length > 0 && (bodyHeight <= 0 || heightOf("working") <= bodyHeight / 2)
        var pinFailed = byGroup.failed.length > 0 && (byGroup.working.length === 0 || pinWorking)
                        && heightOf("working") * (byGroup.working.length > 0 ? 1 : 0) + heightOf("failed") <= bodyHeight / 2
        var listHeight = 0
        for (var lh = 0; lh < shown.length; ++lh) {
            var lg = shown[lh]
            if ((lg === "working" && pinWorking) || (lg === "failed" && pinFailed)) continue
            listHeight += folded(lg) ? 48 : heightOf(lg)
        }
        var pinnedHeight = (pinWorking ? heightOf("working") : 0) + (pinFailed ? heightOf("failed") : 0)
        var listFits = bodyHeight > 0 && listHeight <= bodyHeight - pinnedHeight
        var out = []
        var firstIn = { pinned: true, list: true }
        for (var n = 0; n < shown.length; ++n) {
            var gk = shown[n]
            var col = (gk === "working" && pinWorking) || (gk === "failed" && pinFailed) ? "pinned" : "list"
            if (col === "list" && !firstIn.pinned) firstIn.list = false
            var first = firstIn[col]
            if (col === "pinned") firstIn.pinned = false
            var grows = byGroup[gk]
            var action = actionFor(gk, grows)
            if (gk === "cleared") {
                out.push({ column: col, entry: headEntry(gk, "cleared", -1, action, first, grows) })
                firstIn[col] = false
                continue
            }
            var isFold = folded(gk)
            if (isFold) {
                var fig = (gk === "done" && running) || resultsOpen ? -1 : cnt[gk]
                var peek = []
                if (!resultsOpen) for (var p = 0; p < grows.length; ++p) if (grows[p].key === selectedKey && isImage(grows[p])) peek.push(grows[p])
                var fe = headEntry(gk, "fold", fig, action, first, grows)
                fe.peek = peek.length > 0
                out.push({ column: col, entry: fe })
                for (var pk = 0; pk < peek.length; ++pk) out.push({ column: col, entry: rowEntry(peek[pk], gk) })
                firstIn[col] = false
                continue
            }
            var headed = !(only !== "" && (gk === "next" || gk === "done" || gk === "working" || gk === "later"))
            if (headed) {
                var imgs = grows.filter(isImage)
                var act = imgs.length === 1 && imgs[0].key === selectedKey && gk !== "cleared" ? "" : action
                out.push({ column: col, entry: headEntry(gk, "heading", cnt[gk], act, first, grows) })
            }
            var nImgs = 0
            for (var c0 = 0; c0 < grows.length; ++c0) if (isImage(grows[c0])) nImgs += 1
            var cap = gk === "next" && !resultsOpen && !(openGroups.nextTail === true) && !listFits && nImgs > nextHead + 1 ? nextHead : -1
            var seen = 0, tail = []
            for (var j = 0; j < grows.length; ++j) {
                if (cap >= 0 && isImage(grows[j]) && seen >= cap) { tail.push(grows[j]); continue }
                if (isImage(grows[j])) seen += 1
                out.push({ column: col, entry: rowEntry(grows[j], gk) })
            }
            if (tail.length > 0) {
                var te = headEntry("nextTail", "fold", -1, "", true, tail)
                te.title = tail.length + " more"
                te.group = "nextTail"
                var tpeek = []
                for (var tp = 0; tp < tail.length; ++tp) if (tail[tp].key === selectedKey) tpeek.push(tail[tp])
                te.peek = tpeek.length > 0
                out.push({ column: col, entry: te })
                for (var tq = 0; tq < tpeek.length; ++tq) out.push({ column: col, entry: rowEntry(tpeek[tq], gk) })
            }
            firstIn[col] = false
        }
        return { entries: out, shown: shown, counts: cnt, total: total }
    }

    function longestRun(keys, newAt) {
        var tails = [], tailAt = [], prev = []
        for (var i = 0; i < keys.length; ++i) {
            var v = newAt[keys[i]]
            var lo = 0, hi = tails.length
            while (lo < hi) { var mid = (lo + hi) >> 1; if (tails[mid] < v) lo = mid + 1; else hi = mid }
            tails[lo] = v; tailAt[lo] = i; prev[i] = lo > 0 ? tailAt[lo - 1] : -1
        }
        var out = {}
        for (var k = tails.length > 0 ? tailAt[tails.length - 1] : -1; k >= 0; k = prev[k]) out[keys[k]] = true
        return out
    }
    function patch(model, rows) {
        var newAt = {}
        for (var a = 0; a < rows.length; ++a) newAt[rows[a].key] = a
        for (var d = model.count - 1; d >= 0; --d) if (newAt[model.get(d).key] === undefined) model.remove(d)
        var keys = []
        for (var e = 0; e < model.count; ++e) keys.push(model.get(e).key)
        var stay = longestRun(keys, newAt)
        var inserted = {}
        for (var m = rows.length - 1; m >= 0; --m) {
            var key = rows[m].key
            var at = keys.indexOf(key)
            if (at >= 0 && stay[key]) continue
            var target = m === rows.length - 1 ? keys.length : keys.indexOf(rows[m + 1].key)
            if (at < 0) { model.insert(target, rows[m]); keys.splice(target, 0, key); inserted[key] = true; continue }
            var to = at < target ? target - 1 : target
            if (to !== at) { model.move(at, to, 1); keys.splice(at, 1); keys.splice(to, 0, key) }
        }
        for (var u = 0; u < rows.length; ++u) {
            if (inserted[rows[u].key]) continue
            var cur = model.get(u)
            var diff = false
            for (var r in rows[u]) { if (cur[r] !== rows[u][r]) { diff = true; break } }
            if (diff) model.set(u, rows[u])
        }
    }

    property real nameRoom: 0
    property var heads: ({})
    property FontMetrics nameMetrics: FontMetrics { font: Tokens.fontFor("label") }
    function nameParts(n) {
        var dot = n.lastIndexOf(".")
        var stem = dot > 0 ? n.slice(0, dot) : n
        var ext = dot > 0 ? n.slice(dot) : ""
        return { stem: stem, ext: ext, parts: stem.split(/([_ ])/) }
    }
    function headed(n, k) {
        var p = nameParts(n)
        if (p.parts.length < 5 || 2 * k - 1 > p.parts.length - 4) return ""
        return p.parts.slice(0, 2 * k - 1).join("") + "…" + p.parts.slice(p.parts.length - 3).join("") + p.ext
    }
    function fitsRoom(t) { return nameMetrics.advanceWidth(t) <= nameRoom }
    function computeHeads(names) {
        var byProject = {}
        for (var i = 0; i < names.length; ++i) {
            var n = names[i]
            if (fitsRoom(n)) continue
            var h1 = headed(n, 1)
            if (h1 === "" || !fitsRoom(h1)) continue
            var first = nameParts(n).parts[0]
            if (!byProject[first]) byProject[first] = []
            if (byProject[first].indexOf(n) < 0) byProject[first].push(n)
        }
        var out = {}
        for (var f in byProject) {
            var list = byProject[f]
            var best = 0
            for (var k = 1; k < 8; ++k) {
                var all = true, any = false
                for (var j = 0; j < list.length; ++j) {
                    var c = headed(list[j], k)
                    if (c === "") { all = false; break }
                    any = true
                    if (!fitsRoom(c)) { all = false; break }
                }
                if (!all || !any) break
                best = k
            }
            out[f] = best
        }
        return out
    }
    function uniformName(n) {
        heads
        if (n === "" || fitsRoom(n)) return n
        var k = heads[nameParts(n).parts[0]] || 0
        if (k <= 0) return ""
        var c = headed(n, k)
        return c !== "" && fitsRoom(c) ? c : ""
    }
    onNameRoomChanged: sync()

    property bool held: false
    property bool _pending: false
    readonly property bool pending: _pending
    signal releasing()
    onHeldChanged: {
        if (held || !_pending) return
        _pending = false
        releasing()
        sync()
    }

    function sync() {
        if (tab === null) return
        if (held) { _pending = true; return }
        var b = build()
        var names = []
        for (var ni = 0; ni < b.entries.length; ++ni) {
            var en = b.entries[ni].entry
            if (en.kind === "input" || en.kind === "job" || en.kind === "removed") names.push(en.name)
        }
        var h = computeHeads(names)
        if (JSON.stringify(h) !== JSON.stringify(heads)) heads = h
        var pin = [], lst = []
        for (var i = 0; i < b.entries.length; ++i) (b.entries[i].column === "pinned" ? pin : lst).push(b.entries[i].entry)
        patch(pinned, pin)
        patch(list, lst)
        if (groupCount !== b.shown.length) groupCount = b.shown.length
        if (images !== b.total) images = b.total
        if (JSON.stringify(groupsShown) !== JSON.stringify(b.shown)) groupsShown = b.shown
        if (JSON.stringify(counts) !== JSON.stringify(b.counts)) counts = b.counts
        synced()
    }

    onRunningChanged: { openGroups = ({}); sync() }
    onResultsOpenChanged: { openGroups = ({}); sync() }
    onOpenGroupsChanged: sync()
    onSelectedKeyChanged: sync()
    onBodyHeightChanged: sync()
    property Connections _tabWatch: Connections {
        target: qm.tab
        ignoreUnknownSignals: true
        function onQueuePatched() { qm.sync() }
        function onEarlierOpenChanged() { qm.sync() }
        function onScaleChanged() { qm.sync() }
        function onClearedLineChanged() { qm.sync() }
        function onFooterModeChanged() { qm.sync() }
    }
    onTabChanged: sync()
}

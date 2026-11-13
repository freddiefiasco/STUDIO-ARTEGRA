import QtQuick
import "format.js" as F

Item {
    id: bar
    objectName: "statusDock"
    property var tab: null
    visible: false
    width: 0
    height: 0
    readonly property var b: tab ? tab.batch : ({ active: false })

    function sentenceEnd(s) {
        var t = String(s || "")
        return t === "" || /[.…?]$/.test(t) ? t : t + "."
    }
    function firstSentence(s) {
        var t = String(s || "")
        var i = t.indexOf(". ")
        return i > 0 ? t.substring(0, i + 1) : t
    }
    readonly property string engineKind: {
        if (!tab) return ""
        if (tab.engineState === "problem") return "problem"
        if (tab.reconnecting) return "reconnecting"
        if (tab.engineState === "starting") return "starting"
        return ""
    }
    readonly property int seconds: tab ? Math.max(0, Math.floor(Number(tab.startingSeconds) || 0)) : 0
    function problemConsequence() {
        var k = tab.problemKind
        if (k === "output") return "Finished images wait until it is back."
        if (k === "models") return "Nothing can be upscaled until they are back."
        if (/graphics card|\bGPU \d/i.test(tab.problems.length > 0 ? tab.problems[0] : "")) return "Nothing can be upscaled until it is free."
        return "Nothing can be upscaled until it answers."
    }
    function shortProblem() {
        var t = tab.problems.length > 0 ? String(tab.problems[0]) : ""
        var k = tab.problemKind
        if (k === "models") return "The models are offline."
        if (k === "output") return /read-only|cannot be written/.test(t) ? "The output folder is locked." : "The output folder is offline."
        if (/did not start|could not start/.test(t)) return "The engine did not start."
        if (/connection to the engine was lost/.test(t)) return "The engine is offline."
        return "The engine has a problem."
    }
    readonly property string engineLine: {
        var k = engineKind
        if (k === "problem") return shortProblem()
        if (k === "reconnecting") return "Reconnecting to the engine" + (seconds > 0 ? " (" + seconds + " s)" : "")
        if (k === "starting") return "Starting the engine" + (seconds > 0 ? " (" + seconds + " s)" : "")
        return ""
    }
    readonly property string engineAction: engineKind !== "problem" ? "" : (tab.problemKind === "output" ? "Choose a folder…" : "Try again")
    function cardProblem() {
        return tab.problemKind === "engine" && /graphics card|\bGPU \d/i.test(tab.problems.length > 0 ? tab.problems[0] : "")
    }
    function problemHeading() {
        if (tab.problemKind === "models") return "The upscaler's models cannot be reached"
        if (cardProblem()) return String(tab.problems[0]).replace(/\.\s*$/, "")
        return String(tab.problemTitle || "")
    }
    readonly property string engineRecessTitle: engineKind === "problem" ? problemHeading() : ""
    readonly property string engineRecessText: {
        if (engineKind !== "problem") return ""
        if (cardProblem()) return problemConsequence()
        var body = tab.problems.length > 0 ? F.problemBody(tab.problems[0]).text : ""
        return body !== "" ? body : problemConsequence()
    }

    readonly property var workers: tab && tab.health && tab.health.engine && tab.health.engine.workers ? tab.health.engine.workers : []
    readonly property bool outWait: engineKind !== "problem" && engineKind !== "starting" && tab !== null && tab.outputWaiting === true
    readonly property var waitInfo: outWait ? F.outputWaitInfo(tab.batch.outputWaitMessage, tab.batch.outputWait) : ({ title: "", text: "" })
    readonly property string detailsText: {
        if (!tab) return ""
        if (engineKind === "problem") {
            var body = cardProblem() ? "" : (tab.problems.length > 0 ? F.problemBody(tab.problems[0]).text : "")
            return sentenceEnd(problemHeading()) + " " + (body !== "" ? body : problemConsequence())
        }
        if (outWait) return waitInfo.title + ". " + waitInfo.text
        if (engineKind === "reconnecting") return "Images already sent are kept and carry on when the engine is back."
        if (engineKind === "starting") return tab.connected ? "The engine answered and is getting ready."
                                                           : "Looking for the engine on this computer. It starts on its own."
        if (tab.stuckMinutes > 0) return "The engine still answers, but no new tile has arrived. It may be waiting for a graphics card."
        return ""
    }
    function workerLine(w) {
        var state = w.state === "idle" ? "ready"
                  : w.state === "working" || w.state === "busy" ? "working"
                  : w.state === "starting" ? "starting"
                  : w.state === "stopping" ? "stopping"
                  : w.state === "stopped" ? "resting until the next image"
                  : w.state === "failed" ? "could not start" + (w.problem ? ": " + w.problem : "")
                  : String(w.state || "unknown")
        var g = Number(w.gpu)
        return "GPU " + (isFinite(g) ? g + 1 : "?") + (w.name ? ", " + w.name : "") + ": " + state
               + (w.vram_free_gb !== undefined && w.vram_free_gb !== null ? ", " + Number(w.vram_free_gb).toFixed(0) + " GB free" : "")
    }
    readonly property var workerLines: workers.map(function(w) { return bar.workerLine(w) })

    readonly property bool running: b.active === true && Number(b.total) > 0
    readonly property string batchCount: running ? F.doneOf(Number(b.done) || 0, Number(b.total) || 0)
                                                   + (Number(b.failed) > 0 ? ", " + b.failed + " failed" : "") : ""
    property double now: Tokens.wallNow()
    Timer { interval: 20000; repeat: true; running: bar.running; triggeredOnStart: true; onTriggered: bar.now = Tokens.wallNow() }
    function hhmm(ms) {
        var d = new Date(ms)
        var h = d.getHours(), m = d.getMinutes()
        return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m
    }
    readonly property real etaS: running && b.etaS !== undefined ? Number(b.etaS) : -1
    readonly property string finishClock: {
        if (!(etaS > 0)) return ""
        var step = 5 * 60 * 1000
        return hhmm(Math.round((now + etaS * 1000) / step) * step)
    }
    readonly property string batchLineCount: running ? batchCount + (finishClock !== "" ? ", finishes about " : "") : ""
    readonly property string batchLineTime: running ? finishClock : ""
    readonly property string batchLine: batchLineCount + batchLineTime
    readonly property string stoppingLine: {
        if (!running || !tab || tab.stopRequested !== true) return ""
        var n = workingRows.length
        return n > 0 ? "Stopping after " + F.plural(n, "image", "images") + " in progress" : "Stopping"
    }

    readonly property var workingRows: {
        var out = []
        var m = tab ? tab.rowsByKey : null
        if (!m) return out
        for (var k in m) {
            var r = m[k]
            if (r.kind === "job" && F.contains(F.BUSY_ITEM_STATES, r.status)) out.push(r)
        }
        out.sort(function(a, c) { return (a.place || 0) - (c.place || 0) })
        return out
    }
    function rowCards(r) {
        if (!r) return []
        if (r.cards && r.cards.length > 0) return r.cards
        if (r.run && r.run.cards && r.run.cards.length > 0) return r.run.cards
        return r.gpu !== undefined && r.gpu !== null && Number(r.gpu) >= 0 ? [Number(r.gpu)] : []
    }
    readonly property var lanes: {
        var out = []
        if (!tab || (tab.imageCount || 0) === 0 || workers.length === 0) return out
        var known = false
        for (var i = 0; i < workingRows.length; ++i) if (rowCards(workingRows[i]).length > 0) known = true
        for (var w = 0; w < workers.length; ++w) if (workers[w].item_id || workers[w].media_id) known = true
        var used = {}
        for (var j = 0; j < workers.length; ++j) {
            var wk = workers[j]
            var g = Number(wk.gpu)
            var row = null
            var exact = false
            if (known && wk.item_id) {
                for (var q0 = 0; q0 < workingRows.length && row === null; ++q0) {
                    var r0 = workingRows[q0]
                    if (String(wk.item_id) === r0.itemId && (!wk.job_id || String(wk.job_id) === r0.jobId)) { row = r0; exact = true }
                }
            }
            for (var pass = 0; pass < 2 && row === null; ++pass) {
                for (var q = 0; q < workingRows.length && row === null; ++q) {
                    var r = workingRows[q]
                    var saving = r.status === "finishing"
                    if (known) {
                        if ((pass === 0) === saving) continue
                        if (saving && wk.item_id) continue
                        if (rowCards(r).indexOf(g) >= 0) { row = r; exact = true }
                        else if (!used[r.key] && !wk.item_id && wk.media_id && String(wk.media_id) === r.mediaId) row = r
                    } else if (pass === 0 && !used[r.key]) {
                        row = r
                    }
                }
            }
            var joined = false
            if (row !== null && exact) {
                for (var o = 0; o < out.length && !joined; ++o) {
                    if (out[o].row !== null && out[o].row.key === row.key) {
                        out[o].gpus.push(g)
                        out[o].span += 1
                        out[o].label += " + GPU " + (g + 1)
                        joined = true
                    }
                }
            }
            if (row !== null) used[row.key] = true
            if (!joined) out.push({ gpu: g, gpus: [g], span: 1, col: 0, label: "GPU " + (g + 1), row: row })
        }
        var col = 0
        for (var c = 0; c < out.length; ++c) { out[c].col = col; col += out[c].span }
        return out
    }
    readonly property var splitInfo: tab && tab.health && tab.health.engine && tab.health.engine.split ? tab.health.engine.split : null
    readonly property string floorMessage: splitInfo !== null && splitInfo.reason === "card_under_floor" && splitInfo.message
                                           ? String(splitInfo.message) : ""

    readonly property string rowOneKind: engineKind
    readonly property string rowOneText: engineLine
    readonly property string rowOneMore: ""
    readonly property string sentence: engineLine
    readonly property string markKind: ""
    readonly property string stepText: ""
    readonly property int viewerReserve: 0
    readonly property bool detailsOpen: tab !== null && tab.engineDetailsOpen === true
    function openEngineDetails() { if (tab) tab.openEngineDetails(null) }
}

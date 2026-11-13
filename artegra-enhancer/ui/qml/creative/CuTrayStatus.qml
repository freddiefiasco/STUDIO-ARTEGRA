import QtQuick
import "format.js" as F

QtObject {
    id: status
    property string kind: ""
    property string state: ""
    property real outW: 0
    property real outH: 0
    property int factor: 2
    property bool ownFactor: false
    property bool ownMode: false
    property string refusedReason: ""
    property int maxFactor: 0
    property real tookS: -1
    property int gpu: -1
    property string cardsText: ""
    property string atPass: ""
    property int atStep: -1
    property string livePass: ""
    property string message: ""
    property string errorText: ""
    property bool inView: false
    property bool fastResult: false
    property string removedState: ""
    property string removedText: ""
    property string text: full
    property string suffix: ""
    property real maxWidth: 200
    property string detail: ""
    property string iconName: ""
    property string tone: "quiet"
    readonly property bool chip: false

    readonly property bool working: kind === "job" && F.contains(F.BUSY_ITEM_STATES, state)
    readonly property bool queued: kind === "job" && (state === "queued" || state === "interrupted")
    readonly property bool refused: state === "refused"
    readonly property bool waiting: (kind === "input" && !refused) || queued
    readonly property bool done: kind === "job" && state === "done"
    readonly property bool failed: kind === "job" && state === "failed"
    readonly property bool stopped: kind === "job" && (state === "stopped" || state === "cancelled")

    readonly property string cards: cardsText !== "" ? cardsText : (gpu >= 0 ? "GPU " + (gpu + 1) : "")
    readonly property string passWords: livePass === "structure" ? "structure pass" : livePass === "detail" ? "detail pass" : ""
    readonly property string waitWords: F.waitingWords(message)
    readonly property bool barShown: working && !inView && (state === "running" || state === "finishing") && waitWords === ""

    readonly property string atText: {
        var n = atPass === "structure" ? "Structure pass" : atPass === "detail" ? "Detail pass" : ""
        if (n !== "") return atStep > 0 ? n + ", step " + atStep : n
        return atStep === 0 ? "While preparing" : ""
    }
    readonly property string tookText: tookWords !== "" ? "Took " + tookWords : ""
    readonly property string tookWords: {
        if (!(tookS >= 0)) return ""
        if (tookS < 60) return Math.max(1, Math.round(tookS)) + " s"
        var m = Math.round(tookS / 60)
        return m < 60 ? m + " min" : Math.floor(m / 60) + " h " + (m % 60) + " min"
    }
    readonly property string causeText: {
        var t = String(errorText || "")
        var m = /\b(GPU \d+) ran out of memory/i.exec(t)
        if (m) return "Out of memory on " + m[1]
        if (/out of memory/i.test(t)) return "Out of memory"
        var first = t.split(/\.\s/)[0].replace(/\.$/, "").trim()
        if (first !== "" && first.length <= 32) return first
        return atText
    }
    readonly property string becomesSize: F.size(outW, outH)
    readonly property string ownTail: ownFactor ? " at " + F.scaleLabel(factor) : ""

    readonly property string full: {
        if (kind === "removed") return removedState === "failed" ? undoWords : "Removed"
        if (kind !== "input" && kind !== "job") return ""
        if (refused) return maxFactor > 0 ? "Fits at " + F.scaleLabel(maxFactor) : "Too large at every scale"
        if (waiting) return becomesSize !== "" ? (ownMode ? "Standard, becomes " : "Becomes ") + becomesSize + ownTail : ""
        if (working) {
            if (waitWords !== "" && !(inView && waitWords === "Waiting for the output folder")) return waitWords
            if (state === "finishing") return inView ? "" : "Finishing"
            if (inView) return cards
            if (state === "preparing") return cards !== "" ? cards + ", preparing" : "Preparing"
            return passWords !== "" && cards !== "" ? cards + ", " + passWords : cards
        }
        if (done) {
            if (fastResult && !inView) return tookWords !== "" ? "Fast, took " + tookWords : "Fast"
            return tookText !== "" ? tookText : (inView ? "" : F.size(outW, outH))
        }
        if (failed) return inView ? "" : causeText
        if (stopped) return inView ? "" : atText
        return ""
    }
    readonly property string shortText: {
        if (refused || kind === "removed") return full
        if (waiting && becomesSize !== "") return (ownMode ? "Standard, → " : "→ ") + becomesSize + ownTail
        var m = /^(Structure|Detail) pass, step (\d+)$/.exec(full)
        if (m) return "Step " + m[2]
        return full
    }
    readonly property string shorterText: waiting && becomesSize !== "" ? (ownMode ? "Standard" : "→ " + becomesSize) : shortText

    readonly property string undoWords: {
        var t = String(removedText || "").replace(/^Could not be put back\.\s*/, "").replace(/\s*Try Undo again in a moment\.\s*$/, "").trim()
        if (/still starting/i.test(t)) return "Engine starting"
        if (/reconnecting/i.test(t)) return "Engine reconnecting"
        if (/busy/i.test(t)) return "Engine busy"
        return t !== "" && t.length <= 28 ? t.replace(/\.$/, "") : "Not put back"
    }
}

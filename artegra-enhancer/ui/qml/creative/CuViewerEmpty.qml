import QtQuick
import "format.js" as F

Item {
    id: empty

    property var viewer: null
    readonly property var tab: viewer ? viewer.tab : null
    readonly property bool inviting: viewer !== null && !viewer.hasRow
    property bool dragging: false
    readonly property real recessX: viewer ? viewer.recessX : 0
    readonly property real recessY: viewer ? viewer.recessY : 0
    readonly property real recessW: viewer ? viewer.recessW : 0
    readonly property real recessH: viewer ? viewer.recessH : 0
    readonly property real naturalWidth: recessW
    readonly property real growth: 0
    readonly property bool problemShown: kind === "problem"

    visible: inviting
    objectName: "viewerEmpty"

    readonly property bool canAdd: tab !== null && tab.canAddImages !== false
    readonly property string kind: {
        if (!tab) return ""
        if (dragging && canAdd) return "drop"
        if (tab.engineState === "problem" && tab.problemKind !== "output") return "problem"
        if (tab.reconnecting === true) return "reconnecting"
        if (tab.connected !== true || tab.engineState === "starting") return "starting"
        return "empty"
    }
    readonly property int dropCount: viewer ? viewer.dropCount : 0
    readonly property string dropLine: viewer && viewer.dropWords !== "" ? viewer.dropWords
                                       : viewer && viewer.dropFolder ? "Drop to add images"
                                       : dropCount === 1 ? "Drop to add 1 image"
                                       : dropCount > 1 ? "Drop to add " + dropCount + " images" : "Drop to add images"
    readonly property string problemText: tab && tab.problems && tab.problems.length > 0 ? String(tab.problems[0]) : ""
    readonly property string problemTitle: {
        if (!tab) return ""
        if (tab.engineRecessTitle !== undefined && String(tab.engineRecessTitle) !== "") return String(tab.engineRecessTitle)
        if (tab.problemKind === "models") return "The upscaler's models cannot be reached"
        return String(tab.problemTitle || F.problemTitle(problemText))
    }
    readonly property string problemSentence: {
        if (!tab) return ""
        if (tab.engineRecessText !== undefined && String(tab.engineRecessText) !== "") return String(tab.engineRecessText)
        var b = F.problemBody(problemText)
        return b && b.text ? String(b.text) : problemText
    }
    readonly property int seconds: tab && tab.startingSeconds !== undefined ? Math.floor(Number(tab.startingSeconds)) : 0
    readonly property bool detailsSupported: tab !== null && (typeof tab.openEngineDetails === "function" || tab.detailsAnchor !== undefined)

    CuRecess {
        id: recess
        objectName: "viewerEmptyState"
        x: empty.recessX
        y: empty.recessY
        width: empty.recessW
        height: empty.recessH
        ground: "stage"
        drop: empty.kind === "drop"
        title: empty.kind === "problem" ? empty.problemTitle : ""
        text: empty.kind === "drop" ? empty.dropLine
              : empty.kind === "problem" ? empty.problemSentence
              : empty.kind === "starting" ? "Starting the engine"
              : empty.kind === "reconnecting" ? "Reconnecting to the engine"
              : empty.kind === "empty" ? "Drop images here, or add them." : ""
        measure: (empty.kind === "starting" || empty.kind === "reconnecting") && empty.seconds > 0 ? empty.seconds + " s" : ""
        actionText: empty.kind === "empty" && empty.canAdd ? "Add images…"
                    : empty.kind === "problem" && empty.tab.problemKind !== "output" ? "Try again" : ""
        actionKind: empty.kind === "problem" ? "tile" : "white"
        actionTip: empty.kind === "empty" ? Tokens.keyTip("Choose images to upscale", "Ctrl+O") : ""
        secondText: empty.kind === "problem" && empty.detailsSupported ? "Details" : ""
        secondTip: "The engine's state, the graphics cards and the log"
        onAction: {
            if (empty.kind === "empty") empty.tab.openFileDialog()
            else if (empty.kind === "problem") empty.tab.retryEngine()
        }
        onSecondAction: {
            if (typeof empty.tab.openEngineDetails === "function") empty.tab.openEngineDetails(recess.secondItem)
            else empty.tab.detailsAnchor = recess.secondItem
        }
        Accessible.role: Accessible.Pane
        Accessible.name: text
    }
    readonly property Item detailsItem: recess.secondItem
    readonly property Item actionItem: recess.actionItem
}

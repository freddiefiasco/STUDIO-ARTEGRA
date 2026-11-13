import QtQuick
import QtQuick.Window
import QtQuick.Templates as T
import "format.js" as F

T.Popup {
    id: dialog
    objectName: "confirmDialog"
    property var tab: null
    property string title: ""
    property string body: ""
    property string confirmLabel: "Confirm"
    property string cancelLabel: "Cancel"
    property var onConfirm: null
    property string tone: "danger"
    property var returnFocus: null
    property string altLabel: ""
    property var onAlt: null
    property var onCancel: null
    property string purpose: ""
    property bool _answered: false
    readonly property bool isClose: purpose === "close"
    readonly property bool goIsWhite: tone === "go"

    parent: T.Overlay.overlay
    readonly property real winW: parent ? parent.width : 1280
    readonly property real winH: parent ? parent.height : 800
    x: 0
    y: 0
    width: winW
    height: winH
    padding: 0
    modal: true
    focus: true
    closePolicy: T.Popup.NoAutoClose
    T.Overlay.modal: Item {}
    enter: Transition { NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: Tokens.durFloatIn } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: Tokens.durFloatOut } }
    background: Item {}

    readonly property var b: tab ? tab.batch : ({ done: 0, total: 0 })
    readonly property var leg: tab ? tab.settingsItem : null
    readonly property string finish: {
        if (leg && leg.finishClock !== undefined && leg.finishClock) return String(leg.finishClock)
        var eta = b ? Number(b.etaS) : NaN
        if (!isFinite(eta) || eta <= 0) return ""
        var d = new Date(Tokens.wallNow ? Tokens.wallNow() + eta * 1000 : Date.now() + eta * 1000)
        return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2)
    }
    readonly property int inProgress: b && b.working ? b.working.length : 0
    readonly property int waiting: {
        if (!tab || !tab.rowsByKey) return 0
        var n = 0
        for (var k in tab.rowsByKey) {
            var r = tab.rowsByKey[k]
            if (r.kind === "job" && (r.status === "queued" || r.status === "interrupted")) n += 1
        }
        return n
    }
    readonly property bool notifies: !(tab && tab.health && tab.health.lifecycle && tab.health.lifecycle.notify
                                       && tab.health.lifecycle.notify.available === false)
    readonly property string closeBody: (b ? Number(b.done) || 0 : 0) + " of " + (b ? Number(b.total) || 0 : 0)
        + " done. Closing stops the engine. Unfinished images resume when you next open Artegra Enhancer."
    readonly property string finishTip: "The engine stops when this window closes."
    readonly property string stopTip: {
        var p = inProgress === 1 ? "The image in progress stops." : (inProgress > 1 ? "The " + inProgress + " images in progress stop." : "")
        var w = waiting === 1 ? "the one waiting" : (waiting > 1 ? "the " + waiting + " waiting" : "")
        var again = inProgress > 0 ? (w !== "" ? (inProgress === 1 ? " It and " : " They and ") + w + " start again when you next open Artegra Enhancer."
                                               : (inProgress === 1 ? " It starts" : " They start") + " again when you next open Artegra Enhancer.")
                                   : (w !== "" ? " " + F.capital(w) + " start again when you next open Artegra Enhancer." : "")
        return (p + again).trim()
    }

    readonly property var answers: {
        if (isClose)
            return [{ label: cancelLabel, value: "keep", kind: "text", tip: Tokens.keyTip(cancelLabel, "Esc") },
                    { label: confirmLabel, value: "go", kind: "danger", tip: stopTip }]
        if (tone === "go")
            return [{ label: cancelLabel, value: "keep", kind: "text", tip: Tokens.keyTip(cancelLabel, "Esc") },
                    { label: confirmLabel, value: "go", kind: "white", tip: Tokens.keyTip(confirmLabel, "Enter") }]
        var out = [{ label: cancelLabel, value: "keep", kind: "tile", tip: Tokens.keyTip(cancelLabel, "Esc") }]
        if (altLabel !== "") out.push({ label: altLabel, value: "alt", kind: "danger" })
        out.push({ label: confirmLabel, value: "go", kind: "danger" })
        return out
    }
    function nameAnswers() {
        for (var i = 0; i < answers.length; ++i) {
            var it = panel.actionAt(i)
            if (!it) continue
            var v = answers[i].value
            it.objectName = v === "keep" ? "confirmKeep" : (v === "alt" ? "confirmAlt" : "confirmGo")
        }
    }
    onAnswersChanged: Qt.callLater(nameAnswers)

    function ask(t, bd, confirmText, cancelText, fn, kind) {
        askChoice(t, bd, cancelText, "", null, confirmText, fn, kind === "go" ? "go" : "danger", null, "")
    }
    function askChoice(t, bd, cancelText, altText, altFn, confirmText, fn, kind, cancelFn, why) {
        if (opened && !_answered && onCancel) { var was = onCancel; onCancel = null; was() }
        tone = kind === "go" ? "go" : kind === "neutral" ? "neutral" : "danger"
        title = t
        body = bd
        confirmLabel = confirmText
        cancelLabel = cancelText
        onConfirm = fn
        altLabel = altText || ""
        onAlt = altFn || null
        onCancel = cancelFn || null
        purpose = why || ""
        _answered = false
        if (!opened) {
            var w = tab ? tab.Window.window : null
            returnFocus = w ? w.activeFocusItem : null
        }
        if (opened) Qt.callLater(focusDefault)
        else open()
    }
    function answer(fn) {
        _answered = true
        close()
        if (fn) fn()
    }
    function chosen(value) {
        if (value === "go") answer(onConfirm)
        else if (value === "alt") answer(onAlt)
        else close()
    }
    function focusDefault() {
        nameAnswers()
        var want = goIsWhite ? "go" : "keep"
        for (var i = 0; i < answers.length; ++i) {
            if (answers[i].value !== want) continue
            var it = panel.actionAt(i)
            if (it) it.forceActiveFocus(Qt.OtherFocusReason)
            return
        }
        panel.forceActiveFocus(Qt.OtherFocusReason)
    }

    onOpened: Qt.callLater(focusDefault)
    onClosed: {
        var dismissed = !_answered ? onCancel : null
        _answered = true
        onCancel = null
        purpose = ""
        if (returnFocus) returnFocus.forceActiveFocus()
        returnFocus = null
        if (dismissed) dismissed()
    }

    readonly property bool legsShown: tab ? !tab.panelsHidden : true
    readonly property real legW: legsShown ? Tokens.legWidth(winW) : 0
    readonly property rect opening: Qt.rect(legW, Tokens.hBand, Math.max(0, winW - 2 * legW), Math.max(0, winH - Tokens.hBand))

    contentItem: Item {
        id: holder
        Accessible.role: Accessible.Dialog
        Accessible.name: dialog.title
        Accessible.description: dialog.isClose ? dialog.closeBody : dialog.body

        CuDialog {
            id: panel
            anchors.fill: parent
            focus: true
            modal: true
            title: dialog.title
            message: dialog.isClose ? dialog.closeBody : dialog.body
            actions: dialog.answers
            escapeValue: "keep"
            defaultValue: dialog.goIsWhite ? "go" : "keep"
            centreRect: dialog.opening
            onChose: (value) => dialog.chosen(value)
        }
        Item {
            objectName: "dialogPlate"
            x: panel.panel.x
            y: panel.panel.y
            width: panel.panel.width
            height: panel.panel.height
        }
    }
}

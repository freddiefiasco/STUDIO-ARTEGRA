import QtQuick
import QtQuick.Window

Item {
    id: host
    objectName: "toastStack"
    property var tab: null
    property bool floating: true
    property int inset: Tokens.sp12
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int maxShown: tab !== null && tab.windowSpan === true ? 1 : 2
    readonly property int confirmMs: 6000
    readonly property int actionMs: 10000
    property int count: 0
    property int shownId: -1
    readonly property real stackHeight: height
    implicitWidth: Tokens.legContentMin
    height: 0

    function timeoutOf(kind, hasAction) {
        if (kind === "error" || kind === "stuck") return 0
        if (kind === "undo" || kind === "done") return actionMs
        return hasAction ? actionMs : confirmMs
    }
    function shownKind(kind, actionLabel) {
        return !(kind === "error" && actionLabel === "Show")
    }
    function relayout() {
        var items = []
        for (var i = 0; i < rep.count; ++i) {
            var it = rep.itemAt(i)
            if (it && it.drawable) items.push(it)
        }
        items.sort(function(a, b) { return a.toastId - b.toastId })
        var shown = items.slice(Math.max(0, items.length - maxShown))
        var total = 0
        for (var k = 0; k < shown.length; ++k) total += shown[k].height + (k > 0 ? Tokens.sp8 : 0)
        var y = total
        for (var j = shown.length - 1; j >= 0; --j) {
            y -= shown[j].height
            shown[j].y = Tokens.snap(y, dpr)
            y -= Tokens.sp8
        }
        for (var n = 0; n < items.length; ++n) items[n].onStack = shown.indexOf(items[n]) >= 0
        host.height = Tokens.snap(total, dpr)
        host.count = shown.length
        host.shownId = shown.length > 0 ? shown[shown.length - 1].toastId : -1
    }
    Timer { id: relayoutTimer; interval: 0; onTriggered: host.relayout() }
    onMaxShownChanged: relayoutSoon()
    function relayoutSoon() { relayoutTimer.restart() }
    onWidthChanged: relayoutSoon()

    Repeater {
        id: rep
        model: host.tab ? host.tab.toasts : null
        onItemAdded: host.relayoutSoon()
        onItemRemoved: host.relayoutSoon()
        CuToast {
            id: toast
            required property var model
            readonly property int toastId: model.toastId
            readonly property string kind: model.kind
            readonly property string title: model.title
            readonly property string name: model.name
            readonly property string body: model.body
            readonly property string logRef: model.logRef
            readonly property string actionLabel: model.actionLabel
            readonly property string detailText: model.detail
            property bool onStack: false
            readonly property bool drawable: host.shownKind(kind, actionLabel)
            objectName: "toast-" + kind
            visible: onStack && drawable
            width: host.width
            text: title + (name !== "" ? " " + name : "")
            detail: body
            actions: {
                var out = []
                if (kind === "error") {
                    if (logRef !== "" || toast.detailText !== "") out.push({ label: "Copy details", value: "copy" })
                    out.push({ label: "Dismiss", value: "dismiss" })
                } else if (kind === "stuck") {
                    out.push({ label: "Details", value: "details", tip: "The engine's state, the graphics cards and the log" })
                } else if (actionLabel !== "") {
                    out.push({ label: actionLabel, value: "action",
                               tip: actionLabel === "Review results" ? Tokens.keyTip("Review results", "R")
                                    : actionLabel === "Undo" ? Tokens.keyTip("Undo", "Ctrl+Z") : "" })
                }
                return out
            }
            onHeightChanged: host.relayoutSoon()
            onVisibleChanged: host.relayoutSoon()
            Component.onCompleted: host.relayoutSoon()
            onAction: (value) => {
                if (value === "dismiss") host.tab.dismissToast(toast.toastId)
                else if (value === "copy") {
                    host.tab.copyText([toast.title, toast.name, toast.body].filter(function(x) { return x !== "" }).join(" ")
                                      + (toast.detailText !== "" ? " (" + toast.detailText + ")" : "")
                                      + (toast.logRef !== "" ? " (Creative Upscaler log reference " + toast.logRef + ")" : ""))
                } else if (value === "details") {
                    if (typeof host.tab.openEngineDetails === "function") host.tab.openEngineDetails(toast)
                } else host.tab.toastAction(toast.toastId)
            }
            readonly property int timeout: host.timeoutOf(kind, actionLabel !== "")
            readonly property double bornMs: Date.now()
            readonly property bool seen: kind !== "done" || (host.tab !== null && Number(host.tab.lastActivityMs) > bornMs)
            Timer {
                running: toast.timeout > 0 && toast.seen && toast.visible && host.visible && host.tab !== null && host.tab.visible && !toast.held
                interval: toast.timeout
                onTriggered: host.tab.dismissToast(toast.toastId)
            }
            MouseArea {
                z: -1
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
                onWheel: (wheel) => { wheel.accepted = true }
            }
        }
    }
}

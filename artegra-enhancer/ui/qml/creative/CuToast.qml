import QtQuick
import QtQuick.Window

FocusScope {
    id: toast
    property string text: ""
    property string detail: ""
    property var actions: []
    property string forcedState: ""
    readonly property bool twoLines: detail !== ""
    readonly property bool held: toastHover.hovered || activeFocus
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property real contentWidth: Math.max(0, width - 2 * Tokens.sp12)
    readonly property real actionsWidth: actions.length > 0 ? actionRow.implicitWidth : 0
    readonly property bool actionsBelow: actions.length > 0 && contentWidth - actionsWidth - Tokens.sp16 < contentWidth / 2
    readonly property int lineCount: l1.lineCount
    readonly property real wordsHeight: l1.height + (twoLines ? 2 + l2.height : 0)
    readonly property real blockHeight: wordsHeight + (actionsBelow ? Tokens.sp8 + Tokens.lineOf("body") : 0)
    signal action(var value)
    function keepLastTwo(t) {
        var s = String(t || "")
        var i = s.lastIndexOf(" ")
        return i > 0 && s.indexOf(" ") < i ? s.slice(0, i) + "\u00a0" + s.slice(i + 1) : s
    }
    function balanced(t, room, fm) {
        var s = String(t || "")
        if (room <= 0 || s === "") return room
        var natural = fm.advanceWidth(s)
        if (natural <= room) return room
        var lines = Math.ceil(natural / room)
        var words = s.split(/[ \n]/)
        var longest = 0
        for (var i = 0; i < words.length; ++i) longest = Math.max(longest, fm.advanceWidth(words[i]))
        return Math.min(room, Math.ceil(natural / lines + longest + fm.advanceWidth(" ")))
    }
    FontMetrics { id: l1Metrics; font: l1.font }
    CuText { id: actionProbe; visible: false; role: "body"; text: "Undo" }
    FontMetrics { id: l2Metrics; font: l2.font }
    readonly property real l1Room: Math.max(0, actionsBelow || actions.length === 0 ? contentWidth : contentWidth - actionsWidth - Tokens.sp16)

    implicitWidth: Tokens.legContentMin
    implicitHeight: Math.max(Tokens.hToastOne, Tokens.onGrid(blockHeight + 2 * Tokens.toastAir))
    objectName: "toast"
    Accessible.role: Accessible.AlertMessage
    Accessible.name: text + (detail !== "" ? ". " + detail : "")

    HoverHandler { id: toastHover }
    CuPlate {
        anchors.fill: parent
    }
    readonly property real l1Y: Tokens.snap((height - blockHeight) / 2, dpr)
    CuText {
        id: l1
        objectName: "toastText"
        x: Tokens.sp12
        y: toast.l1Y
        width: toast.balanced(text, toast.l1Room, l1Metrics)
        text: toast.keepLastTwo(toast.text)
        role: "body"
        wrapMode: Text.WordWrap
        maximumLineCount: 3
        elide: Text.ElideRight
        color: Tokens.text1
    }
    CuText {
        id: l2
        objectName: "toastDetail"
        visible: toast.twoLines
        x: Tokens.sp12
        y: Tokens.snap(toast.l1Y + l1.height + 2, toast.dpr)
        width: toast.balanced(text, toast.contentWidth, l2Metrics)
        text: toast.keepLastTwo(toast.detail)
        role: "meta"
        wrapMode: Text.WordWrap
        maximumLineCount: 4
        elide: Text.ElideRight
        color: Tokens.text2
    }
    Row {
        id: actionRow
        objectName: "toastActions"
        x: Tokens.snap(toast.width - Tokens.sp12 - width, toast.dpr)
        readonly property real wordsY: toast.actionsBelow ? Tokens.snap(toast.l1Y + toast.wordsHeight + Tokens.sp8, toast.dpr) : l1.y
        y: Tokens.snap(wordsY + l1.baselineOffset - actionProbe.centredIn(Tokens.hControl) - actionProbe.baselineOffset, toast.dpr)
        spacing: Tokens.sp16
        Repeater {
            model: toast.actions
            CuButton {
                required property var modelData
                required property int index
                variant: "text"
                ground: "float"
                width: Tokens.onGrid(implicitWidth)
                text: modelData.label
                tooltip: modelData.tip || ""
                forcedState: toast.forcedState === "hover:" + index ? "hover" : (toast.forcedState === "focus:" + index ? "focus" : "")
                onClicked: toast.action(modelData.value)
            }
        }
    }
}

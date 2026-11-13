import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.Control {
    id: control

    property string text: ""
    property string hint: ""
    property string disabledReason: ""
    property bool checked: false
    property bool locked: false
    property string lockedReason: ""
    property bool card: false
    property int cardPadding: Tokens.sp12
    property bool lead: false
    property bool leadRules: false
    property string ground: "ink"
    property bool thinTick: false
    property color labelTone: Tokens.text2
    property string forcedState: ""
    readonly property bool usable: enabled && !locked
    readonly property bool hoverOn: usable && (hovered || forcedState === "hover")
    readonly property bool pressed: usable && (tap.pressed || forcedState === "pressed")
    readonly property bool ringShown: visualFocus || forcedState === "focus"
    readonly property int padY: 0
    readonly property bool block: false
    readonly property string lineUnder: !enabled && disabledReason !== "" ? disabledReason : hint
    readonly property bool twoLines: lineUnder !== ""
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int tickPx: Tokens.tickPx(dpr, thinTick)
    readonly property var tickRects: {
        var B = Math.round(Tokens.checkSize * dpr), k = B / Tokens.checkSize, s = tickPx
        var h = (s % 2) ? 0.5 : 0
        var n1 = Math.max(1, Math.round(2.5 * k)), n2 = Math.max(2, Math.round(5 * k))
        var x0 = Math.floor(4 * k) + h, y0 = Math.floor(8 * k) + h
        var out = [], t
        for (t = 0; t <= n1; ++t) out.push([x0 + t - s / 2, y0 + t - s / 2, s, s])
        for (t = 1; t <= n2; ++t) out.push([x0 + n1 + t - s / 2, y0 + n1 - t - s / 2, s, s])
        return out
    }
    readonly property color edgeColor: (!enabled || locked) ? Tokens.text4
                                       : (checked || hoverOn || pressed) ? Tokens.text2 : Tokens.controlEdge
    readonly property color boxBorder: edgeColor
    readonly property color labelColor: labelText.color

    signal toggled(bool checked)

    function activate() {
        if (usable) toggled(!checked)
    }

    implicitWidth: text !== "" ? Math.ceil(Tokens.checkSize + Tokens.sp12 + Math.max(labelText.implicitWidth, twoLines ? hintText.implicitWidth : 0))
                               : Tokens.checkSize
    implicitHeight: twoLines ? Tokens.hRowMedia : Tokens.hCheckRow
    hoverEnabled: true
    focusPolicy: usable ? Qt.TabFocus : Qt.NoFocus

    Accessible.role: Accessible.CheckBox
    Accessible.name: text
    Accessible.description: locked && lockedReason !== "" ? lockedReason : lineUnder
    Accessible.checkable: true
    Accessible.checked: checked
    Accessible.onToggleAction: activate()
    Accessible.onPressAction: activate()

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            control.activate()
            event.accepted = true
        }
    }

    readonly property real labelY: twoLines ? Tokens.sp4 : Tokens.snap((Tokens.hCheckRow - labelText.lineBox) / 2, dpr)
    Item {
        id: box
        objectName: "checkBox"
        x: 0
        y: Tokens.snap(control.labelY + labelText.lineBox / 2 - Tokens.checkSize / 2, control.dpr)
        width: Tokens.checkSize
        height: Tokens.checkSize
        Item {
            scale: 1 / control.dpr
            transformOrigin: Item.TopLeft
            readonly property int bDev: Math.round(Tokens.checkSize * control.dpr)
            Rectangle {
                width: parent.bDev
                height: parent.bDev
                radius: Tokens.radiusControl * control.dpr
                antialiasing: radius > 0
                color: control.pressed ? Tokens.pressOn(control.ground) : Tokens.wellOn(control.ground)
                border.width: Tokens.devPx("line", control.dpr)
                border.color: control.edgeColor
            }
            Item {
                objectName: "checkTick"
                visible: control.checked
                width: parent.bDev
                height: parent.bDev
                Repeater {
                    model: control.checked ? control.tickRects.length : 0
                    Rectangle {
                        required property int index
                        readonly property var r: control.tickRects[index] || [0, 0, 0, 0]
                        x: r[0]
                        y: r[1]
                        width: r[2]
                        height: r[3]
                        antialiasing: false
                        color: control.locked ? Tokens.text2 : (control.enabled ? Tokens.text1 : Tokens.text4)
                    }
                }
            }
        }
    }

    CuText {
        id: labelText
        objectName: "checkLabel"
        x: Tokens.checkSize + Tokens.sp12
        y: control.labelY
        width: Math.max(0, control.width - x)
        visible: text !== ""
        text: control.text
        role: "body"
        elide: Text.ElideRight
        color: !control.enabled ? Tokens.text4 : control.locked ? Tokens.text2
               : (control.checked || control.hoverOn) ? Tokens.text1 : control.labelTone
    }
    CuText {
        id: hintText
        x: labelText.x
        y: Tokens.sp24
        width: Math.max(0, control.width - x)
        visible: control.twoLines
        text: control.lineUnder
        role: "meta"
        elide: Text.ElideRight
        color: !control.enabled ? Tokens.text4 : Tokens.quietOn(control.ground)
    }

    MouseArea {
        id: tap
        anchors.fill: parent
        onClicked: {
            if (control.usable) control.forceActiveFocus(Qt.MouseFocusReason)
            control.activate()
        }
    }
    HoverHandler {
        cursorShape: control.usable ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    CuFocusRing {
        target: box
        shown: control.ringShown
    }

    CuHoverTip {
        shown: (control.locked && control.hovered) || (!control.enabled && control.hovered && control.disabledReason !== "" && !control.twoLines)
        text: control.locked ? control.lockedReason : control.disabledReason
    }
}

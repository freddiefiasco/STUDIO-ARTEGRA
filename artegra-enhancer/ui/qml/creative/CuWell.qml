import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.TextField {
    id: well
    property bool setByUser: false
    property string ground: "ink"
    property string accessibleName: ""
    property string unit: ""
    property bool error: false
    property string forcedState: ""
    readonly property bool editing: activeFocus
    readonly property bool hoveredWell: hovered || forcedState === "hover"
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    signal committed()
    signal stepped(int delta)
    signal reverted()

    FontMetrics { id: fm; font: Tokens.fontFor("body", true) }
    readonly property int unitWidth: unit !== "" ? Math.ceil(fm.advanceWidth(" " + unit)) : 0

    implicitWidth: Tokens.wellFigure
    implicitHeight: Tokens.hControl
    leftPadding: Tokens.textInset
    rightPadding: Tokens.textInset + unitWidth
    topPadding: Tokens.snap((Tokens.hControl - fm.height) / 2, dpr)
    bottomPadding: 0
    hoverEnabled: true
    horizontalAlignment: TextInput.AlignRight
    verticalAlignment: TextInput.AlignTop
    font: Tokens.fontFor("body", true)
    renderType: Tokens.renderType
    color: !enabled ? Tokens.text4 : (readOnly ? Tokens.text2 : (setByUser || activeFocus ? Tokens.text1 : Tokens.text2))
    selectByMouse: true
    selectionColor: Tokens.textSelection
    selectedTextColor: Tokens.text1
    maximumLength: 6
    inputMethodHints: Qt.ImhDigitsOnly
    validator: RegularExpressionValidator { regularExpression: /\d{0,6}/ }
    activeFocusOnTab: !readOnly
    cursorDelegate: Rectangle { width: Tokens.px(1, well.dpr); color: Tokens.text1; visible: well.cursorVisible }
    Accessible.role: Accessible.EditableText
    Accessible.name: accessibleName

    background: Item {
        Rectangle {
            objectName: "wellBody"
            anchors.fill: parent
            color: Tokens.wellOn(well.ground)
            radius: Tokens.radiusControl
            antialiasing: radius > 0
        }
        Item {
            visible: well.error || (well.hoveredWell && well.enabled && !well.readOnly)
            scale: 1 / well.dpr
            transformOrigin: Item.TopLeft
            Rectangle {
                width: Math.round(well.width * well.dpr)
                height: Math.round(well.height * well.dpr)
                color: "transparent"
                border.width: Tokens.devPx("line", well.dpr)
                border.color: well.error ? Tokens.danger : Tokens.reveal
                radius: Tokens.radiusControl * well.dpr
                antialiasing: radius > 0
            }
        }
        CuText {
            objectName: "wellUnit"
            visible: well.unit !== ""
            x: Tokens.snap(well.width - Tokens.textInset - Math.ceil(implicitWidth), well.dpr)
            y: Tokens.snap(well.topPadding + fm.ascent - baselineOffset, well.dpr)
            text: well.unit
            role: "body"
            color: well.enabled ? Tokens.text3 : Tokens.text4
        }
    }

    onActiveFocusChanged: {
        if (activeFocus) Qt.callLater(function() { if (well.activeFocus) well.selectAll() })
        else if (!readOnly) well.committed()
    }
    onAccepted: well.committed()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Escape) {
            well.reverted(); event.accepted = true
        } else if (event.key === Qt.Key_Up || event.key === Qt.Key_Down
                   || event.key === Qt.Key_PageUp || event.key === Qt.Key_PageDown) {
            var d = event.key === Qt.Key_Up ? 1 : event.key === Qt.Key_Down ? -1 : event.key === Qt.Key_PageUp ? 10 : -10
            well.stepped(d)
            well.selectAll()
            event.accepted = true
        }
    }

    CuFocusRing {
        target: well
        shown: (well.activeFocus && !well.readOnly) || well.forcedState === "focus"
    }
}

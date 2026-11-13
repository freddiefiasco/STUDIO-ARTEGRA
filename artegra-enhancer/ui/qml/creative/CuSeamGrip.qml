import QtQuick

Item {
    id: grip
    property bool withLine: false
    property real lineHeight: 72
    property real gripY: withLine ? Math.round((lineHeight - Tokens.gripHeight) / 2) : 0
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    objectName: "seamGrip"
    implicitWidth: Tokens.gripWidth
    implicitHeight: withLine ? lineHeight : Tokens.gripHeight
    width: implicitWidth
    height: implicitHeight

    Rectangle {
        visible: grip.withLine
        x: 0
        width: 3
        height: grip.lineHeight
        color: Tokens.seamHalo
    }
    Rectangle {
        visible: grip.withLine
        x: 1
        width: Tokens.px(1, grip.dpr)
        height: grip.lineHeight
        color: Tokens.seamLine
    }
    Rectangle {
        objectName: "seamGripBar"
        x: -1
        y: grip.gripY - 1
        width: Tokens.gripWidth + 2
        height: Tokens.gripHeight + 2
        color: "transparent"
        border.width: 1
        border.color: Tokens.liveOutlineHalo
        Rectangle {
            x: 1
            y: 1
            width: Tokens.gripWidth
            height: Tokens.gripHeight
            color: Tokens.text1
        }
    }
    MouseArea {
        x: -11
        y: grip.gripY - 4
        width: 24
        height: Tokens.gripHeight + 8
        acceptedButtons: Qt.NoButton
        hoverEnabled: true
        cursorShape: Qt.SplitHCursor
    }
}

import QtQuick

Item {
    id: mark
    property real fraction: 0
    property bool started: fraction > 0
    property int size: Tokens.markSize
    property color fillColor: Tokens.text1
    property color offColor: Tokens.fillOff
    property var resetKey: undefined
    readonly property string meaning: "work in progress"

    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int totalPx: Math.round(size * dpr)
    readonly property int targetPx: {
        var f = Math.max(0, Math.min(1, fraction))
        if (!started && f <= 0) return 0
        if (f >= 1) return totalPx
        return Math.min(totalPx, Math.max(Tokens.markMinPx, Math.round(totalPx * f)))
    }
    property int heldPx: 0
    onTargetPxChanged: if (targetPx > heldPx) heldPx = targetPx
    onResetKeyChanged: heldPx = targetPx
    Component.onCompleted: heldPx = targetPx
    property real shownPx: heldPx
    Behavior on shownPx { NumberAnimation { duration: Tokens.durFill; easing.type: Easing.OutCubic } }
    readonly property int fillPx: Math.round(shownPx)

    implicitWidth: size
    implicitHeight: size
    width: size
    height: size
    Accessible.role: Accessible.ProgressBar
    Accessible.name: started ? Math.round(Math.max(0, Math.min(1, fraction)) * 100) + " percent" : ""

    Item {
        scale: 1 / mark.dpr
        transformOrigin: Item.TopLeft
        width: mark.totalPx
        height: mark.totalPx
        Rectangle {
            anchors.fill: parent
            color: mark.offColor
        }
        Rectangle {
            objectName: "workingMarkFill"
            x: 0
            y: mark.totalPx - mark.fillPx
            width: mark.totalPx
            height: mark.fillPx
            visible: mark.fillPx > 0
            color: mark.fillColor
        }
    }
}

import QtQuick
import QtQuick.Templates as T

T.Control {
    id: seam
    objectName: "viewerSplitHandle"

    property var viewer: null
    readonly property bool dragging: drag.pressed
    readonly property bool lit: seam.hovered || seam.dragging
    signal moved()

    width: 24
    focusPolicy: Qt.TabFocus
    hoverEnabled: true

    Accessible.role: Accessible.Slider
    Accessible.name: "Before and after divider"
    Accessible.description: viewer ? Math.round(viewer.splitPos * 100) + "%" : ""
    Accessible.onIncreaseAction: setPos(viewer.splitPos + 0.01)
    Accessible.onDecreaseAction: setPos(viewer.splitPos - 0.01)

    function setPos(p) {
        if (!viewer) return
        viewer.splitPos = Math.max(0, Math.min(1, p))
        seam.moved()
    }

    Keys.onPressed: (event) => {
        var d = (event.modifiers & Qt.ShiftModifier) ? 0.1 : 0.01
        if (event.key === Qt.Key_Left) { setPos(viewer.splitPos - d); event.accepted = true }
        else if (event.key === Qt.Key_Right) { setPos(viewer.splitPos + d); event.accepted = true }
        else if (event.key === Qt.Key_Home) { setPos(0); event.accepted = true }
        else if (event.key === Qt.Key_End) { setPos(1); event.accepted = true }
    }

    Item {
        id: gripBox
        x: Math.round((seam.width - Tokens.gripWidth) / 2)
        y: Math.round((seam.height - Tokens.gripHeight) / 2)
        width: Tokens.gripWidth
        height: Tokens.gripHeight
    }
    CuFocusRing { target: gripBox; shown: seam.visualFocus }

    MouseArea {
        id: drag
        anchors.fill: parent
        cursorShape: Qt.SplitHCursor
        preventStealing: true
        onPressed: (mouse) => { if (seam.viewer) seam.viewer.forceActiveFocus(Qt.MouseFocusReason); seam.follow(mouse.x) }
        onPositionChanged: (mouse) => { if (pressed) seam.follow(mouse.x) }
    }
    function follow(localX) {
        if (!viewer) return
        var px = seam.x + localX
        var r = viewer.splitSpan
        setPos((px - r.x) / Math.max(1, r.width))
    }
}

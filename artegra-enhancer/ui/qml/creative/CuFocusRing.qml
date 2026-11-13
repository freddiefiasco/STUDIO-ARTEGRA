import QtQuick
import QtQuick.Window

Item {
    id: ring
    property Item target: parent
    property bool shown: false
    property bool inset: false
    property real targetRadius: Tokens.radiusControl
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int thick: Tokens.devPx("ring", dpr)
    readonly property int gap: Tokens.devOf(2, dpr, 1)
    readonly property int offsetDev: inset ? gap : -(gap + thick)

    visible: shown
    objectName: "focusRing"
    anchors.fill: target
    anchors.margins: offsetDev / dpr
    z: 50
    Accessible.ignored: true

    Rectangle {
        scale: 1 / ring.dpr
        transformOrigin: Item.TopLeft
        width: Math.round(ring.width * ring.dpr)
        height: Math.round(ring.height * ring.dpr)
        color: "transparent"
        antialiasing: radius > 0
        radius: ring.targetRadius > 0 ? Math.round((ring.targetRadius + (ring.inset ? -2 : 2)) * ring.dpr) : 0
        border.width: ring.thick
        border.color: Tokens.focus
    }
}

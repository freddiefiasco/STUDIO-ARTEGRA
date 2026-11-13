import QtQuick

Item {
    id: edge

    property real portWidth: 0
    property real portHeight: 0
    property int radius: 0
    property color surface: "transparent"
    property color topSurface: surface
    property color bottomSurface: surface
    property color color: Tokens.pictureRing

    readonly property bool leftIn: x >= 0 && x < portWidth
    readonly property bool topIn: y >= 0 && y < portHeight
    readonly property bool rightIn: x + width > 0 && x + width <= portWidth
    readonly property bool bottomIn: y + height > 0 && y + height <= portHeight
    readonly property real visX0: Math.max(0, -x)
    readonly property real visX1: Math.min(width, portWidth - x)
    readonly property real visY0: Math.max(0, -y)
    readonly property real visY1: Math.min(height, portHeight - y)

    Rectangle {
        objectName: "pictureRingTop"
        visible: edge.topIn && edge.visX1 > edge.visX0
        x: edge.visX0
        y: 0
        width: edge.visX1 - edge.visX0
        height: 1
        color: edge.color
    }
    Rectangle {
        objectName: "pictureRingBottom"
        visible: edge.bottomIn && edge.visX1 > edge.visX0
        x: edge.visX0
        y: edge.height - 1
        width: edge.visX1 - edge.visX0
        height: 1
        color: edge.color
    }
    Rectangle {
        objectName: "pictureRingLeft"
        visible: edge.leftIn && edge.visY1 > edge.visY0 + 2
        x: 0
        y: edge.visY0 + (edge.topIn ? 1 : 0)
        width: 1
        height: Math.max(0, edge.visY1 - edge.visY0 - (edge.topIn ? 1 : 0) - (edge.bottomIn ? 1 : 0))
        color: edge.color
    }
    Rectangle {
        objectName: "pictureRingRight"
        visible: edge.rightIn && edge.visY1 > edge.visY0 + 2
        x: edge.width - 1
        y: edge.visY0 + (edge.topIn ? 1 : 0)
        width: 1
        height: Math.max(0, edge.visY1 - edge.visY0 - (edge.topIn ? 1 : 0) - (edge.bottomIn ? 1 : 0))
        color: edge.color
    }
}

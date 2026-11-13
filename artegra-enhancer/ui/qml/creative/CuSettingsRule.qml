import QtQuick
import QtQuick.Window

Item {
    id: line
    property string ground: "ink"
    property color color: Tokens.ruleOn(ground)
    property bool vertical: false
    property string mark: "line"
    readonly property real d: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int thick: Tokens.devPx(mark, d)
    implicitHeight: vertical ? Tokens.hControl : 1
    implicitWidth: vertical ? 1 : Tokens.legContentMin
    height: vertical ? implicitHeight : 1
    Accessible.ignored: true
    Item {
        scale: 1 / line.d
        transformOrigin: Item.TopLeft
        width: line.vertical ? line.thick : Math.round(line.width * line.d)
        height: line.vertical ? Math.round(line.height * line.d) : line.thick
        Rectangle {
            objectName: "ruleLine"
            anchors.fill: parent
            color: line.color
            antialiasing: false
        }
    }
}

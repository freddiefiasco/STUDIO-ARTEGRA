import QtQuick
import QtQuick.Templates as T

T.ScrollBar {
    id: bar
    property color surface: Tokens.ink
    property bool alwaysShown: false
    property bool regionHovered: false
    readonly property bool scrolls: size < 1.0
    readonly property bool lit: hovered || pressed
    readonly property bool showing: scrolls && (alwaysShown || active || lit || regionHovered || hold.running)
    readonly property color thumbColor: lit ? Tokens.text3 : Tokens.trackInk
    implicitWidth: orientation === Qt.Vertical ? 12 : 100
    implicitHeight: orientation === Qt.Vertical ? 100 : 12
    padding: 0
    minimumSize: 0.08
    snapMode: T.ScrollBar.NoSnap
    hoverEnabled: true
    interactive: true
    policy: T.ScrollBar.AsNeeded
    visible: scrolls
    z: 30

    contentItem: Item {
        implicitWidth: Tokens.overlayBarWidth
        implicitHeight: Tokens.overlayBarWidth
        opacity: bar.showing ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: bar.showing ? 0 : (Tokens.reduceMotion ? 0 : Tokens.durHoverOut) } }
        Rectangle {
            objectName: "scrollThumb"
            anchors.right: bar.orientation === Qt.Vertical ? parent.right : undefined
            anchors.rightMargin: bar.orientation === Qt.Vertical ? Tokens.sp4 : 0
            anchors.bottom: bar.orientation === Qt.Vertical ? undefined : parent.bottom
            anchors.bottomMargin: bar.orientation === Qt.Vertical ? 0 : Tokens.sp4
            width: bar.orientation === Qt.Vertical ? Tokens.overlayBarWidth : parent.width
            height: bar.orientation === Qt.Vertical ? parent.height : Tokens.overlayBarWidth
            radius: 0
            color: bar.thumbColor
        }
    }
    onActiveChanged: { if (!active) hold.restart() }
    onRegionHoveredChanged: { if (!regionHovered) hold.restart() }
    Timer { id: hold; interval: Tokens.reduceMotion ? 0 : 600 }
}

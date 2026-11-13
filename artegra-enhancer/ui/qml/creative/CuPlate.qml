import QtQuick
import QtQuick.Window

Item {
    id: plate
    property bool shadow: true
    property bool modal: false
    property bool edge: true
    property color color: Tokens.float
    default property alias content: inner.data
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property real edgeWidth: edge ? Tokens.px(Tokens.devPx("line", dpr), dpr) : 0
    objectName: "plate"

    BorderImage {
        visible: plate.shadow && !plate.modal
        anchors.fill: parent
        anchors.margins: -Tokens.shadowFloatMargin
        source: Tokens.shadowFloat
        border { left: Tokens.shadowFloatBorder; top: Tokens.shadowFloatBorder; right: Tokens.shadowFloatBorder; bottom: Tokens.shadowFloatBorder }
    }
    BorderImage {
        visible: plate.shadow && plate.modal
        anchors.fill: parent
        anchors.margins: -Tokens.shadowModalMargin
        source: Tokens.shadowModal
        border { left: Tokens.shadowModalBorder; top: Tokens.shadowModalBorder; right: Tokens.shadowModalBorder; bottom: Tokens.shadowModalBorder }
    }
    Rectangle {
        objectName: "plateBody"
        scale: 1 / plate.dpr
        transformOrigin: Item.TopLeft
        width: Math.round(plate.width * plate.dpr)
        height: Math.round(plate.height * plate.dpr)
        color: plate.color
        antialiasing: false
        border.width: plate.edge ? Tokens.devPx("line", plate.dpr) : 0
        border.color: Tokens.reveal
    }
    Item {
        id: inner
        anchors.fill: parent
        anchors.margins: plate.edgeWidth
    }
}

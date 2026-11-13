import QtQuick
import QtQuick.Window

Item {
    id: dropRow
    property string words: ""
    property int inset: Tokens.legInset
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    objectName: "queueDropRow"
    implicitHeight: Tokens.hRowMedia
    Accessible.role: Accessible.StaticText
    Accessible.name: words

    Rectangle {
        anchors.fill: parent
        color: Tokens.wellInk
    }
    Item {
        id: edge
        readonly property int t: Tokens.devPx("bar", dropRow.dpr)
        readonly property int w: Math.round(dropRow.width * dropRow.dpr)
        readonly property int h: Math.round(dropRow.height * dropRow.dpr)
        scale: 1 / dropRow.dpr
        transformOrigin: Item.TopLeft
        Rectangle { width: edge.w; height: edge.t; color: Tokens.text1; antialiasing: false }
        Rectangle { y: edge.h - edge.t; width: edge.w; height: edge.t; color: Tokens.text1; antialiasing: false }
        Rectangle { width: edge.t; height: edge.h; color: Tokens.text1; antialiasing: false }
        Rectangle { x: edge.w - edge.t; width: edge.t; height: edge.h; color: Tokens.text1; antialiasing: false }
    }
    CuIcon {
        x: dropRow.inset
        y: Tokens.sp16
        iconName: "add"
        iconSize: Tokens.iconBox
        color: Tokens.text1
    }
    CuText {
        objectName: "dropWords"
        x: dropRow.inset + Tokens.miniBoxWidth + Tokens.sp12
        y: centredIn(dropRow.height)
        width: Math.max(0, dropRow.width - x - dropRow.inset)
        elide: Text.ElideRight
        role: "body"
        color: Tokens.text1
        text: dropRow.words
    }
}

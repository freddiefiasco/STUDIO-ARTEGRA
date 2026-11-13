import QtQuick
import QtQuick.Window

Rectangle {
    id: label
    property string text: ""
    property string tone: "neutral"
    property color swatch: "transparent"
    readonly property bool hasSwatch: false
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1

    objectName: "viewerTag"
    implicitWidth: Math.ceil(words.implicitWidth) + 2 * Tokens.sp8
    implicitHeight: Tokens.hTag
    width: implicitWidth
    height: implicitHeight
    radius: 0
    color: Tokens.tag
    Accessible.role: Accessible.StaticText
    Accessible.name: text

    CuText {
        id: words
        x: Tokens.sp8
        y: centredIn(label.height)
        text: label.text
        role: "meta"
        color: Tokens.text1
    }
}

import QtQuick
import QtQuick.Window

Item {
    id: recess
    property string ground: "stage"
    property string title: ""
    property string text: ""
    property string measure: ""
    property string actionText: ""
    property string actionKind: "white"
    property string actionTip: ""
    property string secondText: ""
    property string secondTip: ""
    property bool drop: false
    property bool busy: false
    property string forcedState: ""
    readonly property alias actionItem: actionButton
    readonly property alias secondItem: secondButton
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property real columnWidth: Math.min(Tokens.recessColumn, Math.max(0, width - 2 * Tokens.sp24))
    signal action()
    signal secondAction()

    objectName: "recess"
    implicitWidth: 640
    implicitHeight: 400

    Rectangle {
        anchors.fill: parent
        color: Tokens.wellOn(recess.ground)
    }
    Item {
        visible: recess.drop
        scale: 1 / recess.dpr
        transformOrigin: Item.TopLeft
        Rectangle {
            width: Math.round(recess.width * recess.dpr)
            height: Math.round(recess.height * recess.dpr)
            color: "transparent"
            border.width: Tokens.devPx("bar", recess.dpr)
            border.color: Tokens.text1
            antialiasing: false
        }
    }

    Item {
        id: column
        width: recess.columnWidth
        readonly property real actionsH: (actionButton.visible || secondButton.visible) ? Tokens.sp16 + actionButton.height : 0
        height: (titleText.visible ? titleText.height + Tokens.sp4 : 0) + lineText.height + actionsH
        x: Tokens.snap((recess.width - width) / 2, recess.dpr)
        y: Tokens.snap((recess.height - height) / 2, recess.dpr)
        CuText {
            id: titleText
            objectName: "recessTitle"
            visible: recess.title !== ""
            x: Tokens.snap((column.width - width) / 2, recess.dpr)
            y: 0
            width: Math.min(Math.ceil(implicitWidth), column.width)
            text: recess.title
            role: "title"
            elide: Text.ElideRight
            color: Tokens.text1
        }
        Item {
            id: lineText
            readonly property real wordsW: Math.min(column.width, Math.ceil(words.implicitWidth)
                                                     + (measureText.visible ? Tokens.sp8 + Math.ceil(measureText.implicitWidth) : 0))
            x: Tokens.snap((column.width - wordsW) / 2, recess.dpr)
            y: titleText.visible ? titleText.height + Tokens.sp4 : 0
            width: wordsW
            height: Tokens.onGrid(words.height)
            CuText {
                id: words
                objectName: "recessLine"
                x: 0
                width: Math.min(Math.ceil(implicitWidth), column.width - (measureText.visible ? Tokens.sp8 + Math.ceil(measureText.implicitWidth) : 0))
                text: recess.text
                role: "body"
                wrapMode: recess.title !== "" ? Text.WordWrap : Text.NoWrap
                elide: Text.ElideRight
                maximumLineCount: 2
                horizontalAlignment: Text.AlignHCenter
                color: Tokens.text2
            }
            CuText {
                id: measureText
                visible: recess.measure !== ""
                x: words.width + Tokens.sp8
                text: recess.measure
                role: "body"
                tabular: true
                color: Tokens.text1
            }
        }
        Item {
            id: actions
            readonly property real w: (actionButton.visible ? actionButton.width : 0)
                                      + (secondButton.visible ? (actionButton.visible ? Tokens.sp16 + Tokens.textControlPad : 0) + secondButton.width : 0)
            x: Tokens.snap((column.width - w) / 2, recess.dpr)
            y: lineText.y + lineText.height + Tokens.sp16
            width: w
            height: actionButton.height
            CuButton {
                id: actionButton
                objectName: "recessAction"
                visible: recess.actionText !== ""
                x: 0
                variant: recess.actionKind === "tile" ? "tile" : "primary"
                commit: true
                ground: recess.ground
                text: recess.actionText
                tooltip: recess.actionTip
                busy: recess.busy
                forcedState: recess.forcedState
                onClicked: recess.action()
            }
            CuButton {
                id: secondButton
                objectName: "recessSecond"
                visible: recess.secondText !== ""
                x: actionButton.visible ? actionButton.width + Tokens.sp16 + Tokens.textControlPad : 0
                y: Tokens.snap((actionButton.height - height) / 2, recess.dpr)
                variant: "text"
                commit: true
                ground: "stage"
                hoverFill: Tokens.tileOn(recess.ground)
                pressFill: Tokens.pressOn(recess.ground)
                text: recess.secondText
                tooltip: recess.secondTip
                onClicked: recess.secondAction()
            }
        }
    }
}

import QtQuick
import QtQuick.Window

FocusScope {
    id: sheet
    property string title: ""
    property string ground: "ink"
    property int inset: Tokens.legInset
    property string closeText: "Close"
    property string closeTip: Tokens.keyTip("Close", "Esc")
    property string secondText: ""
    property string secondTip: ""
    property bool secondEnabled: true
    readonly property alias secondButton: secondAction
    signal secondClicked()
    default property alias content: scroll.flickableData
    readonly property alias area: scroll
    readonly property alias closeButton: closeAction
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    signal closeRequested()

    objectName: "sheet"
    Accessible.role: Accessible.Pane
    Accessible.name: title
    Keys.onEscapePressed: (event) => { sheet.closeRequested(); event.accepted = true }

    Rectangle {
        anchors.fill: parent
        color: Tokens.groundTone(sheet.ground)
    }
    Item {
        id: titleRow
        x: sheet.inset
        y: Tokens.sp12
        width: sheet.width - 2 * sheet.inset
        height: Tokens.hTitleRow
        CuText {
            id: titleText
            objectName: "sheetTitle"
            x: 0
            y: centredIn(Tokens.hTitleRow)
            width: Math.max(0, (secondAction.visible ? secondAction.x : closeAction.x) - Tokens.sp16)
            text: sheet.title
            role: "title"
            elide: Text.ElideRight
            color: Tokens.text1
            Accessible.role: Accessible.Heading
            Accessible.name: text
        }
        CuButton {
            id: closeAction
            objectName: "sheetClose"
            variant: "text"
            ground: sheet.ground
            text: sheet.closeText
            tooltip: sheet.closeTip
            x: Tokens.snap(titleRow.width - width, sheet.dpr)
            y: Tokens.snap(titleText.y + titleText.baselineOffset - (labelItem.y + labelItem.baselineOffset), sheet.dpr)
            onClicked: sheet.closeRequested()
        }
        CuButton {
            id: secondAction
            objectName: "sheetSecond"
            visible: sheet.secondText !== ""
            variant: "text"
            ground: sheet.ground
            text: sheet.secondText
            tooltip: sheet.secondTip
            enabled: sheet.secondEnabled
            x: Tokens.snap(closeAction.x - Tokens.sp16 - Tokens.textControlPad - width, sheet.dpr)
            y: closeAction.y
            onClicked: sheet.secondClicked()
        }
    }
    CuScrollArea {
        id: scroll
        objectName: "sheetScroll"
        x: 0
        y: Tokens.hBand
        width: sheet.width
        height: Math.max(0, sheet.height - Tokens.hBand)
        surface: Tokens.groundTone(sheet.ground)
        ground: sheet.ground
        regionHovered: sheetHover.hovered
    }
    HoverHandler { id: sheetHover }
}

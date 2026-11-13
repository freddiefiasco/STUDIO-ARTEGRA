import QtQuick
import QtQuick.Window

Item {
    id: slot
    property string status: ""
    property string statusValue: ""
    property bool statusDanger: false
    property string statusTip: ""
    readonly property alias statusItem: statusLine
    readonly property alias statusTextItem: countText
    property string detailsText: ""
    property string detailsTip: ""
    property string ground: "ink"
    property bool ruleShown: false
    property string forcedState: ""
    default property alias row: commitRow.data
    readonly property alias commitItem: commitRow
    readonly property alias detailsItem: detailsButton
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    signal details()

    implicitWidth: Tokens.legContentMin
    implicitHeight: Tokens.hFootSlot
    height: Tokens.hFootSlot
    objectName: "footSlot"

    CuSettingsRule {
        visible: slot.ruleShown
        x: -Tokens.legInset
        y: -Tokens.sp24
        width: slot.width + 2 * Tokens.legInset
        ground: slot.ground
    }
    Item {
        id: statusLine
        objectName: "footStatus"
        x: 0
        y: 0
        width: slot.width
        height: Tokens.hFootStatus
        CuText {
            id: countText
            objectName: slot.statusDanger ? "footProblem" : "footStatusText"
            x: 0
            y: centredIn(Tokens.hFootStatus)
            width: Math.min(Math.ceil(implicitWidth), Math.max(0, statusLine.width - (detailsButton.visible ? detailsButton.width + Tokens.sp16 : 0)))
            text: slot.status
            role: "body"
            tabular: !slot.statusDanger
            elide: Text.ElideRight
            color: slot.statusDanger ? Tokens.danger : Tokens.text2
        }
        CuText {
            id: valueText
            objectName: "footStatusValue"
            x: countText.x + countText.width
            y: countText.y
            visible: slot.statusValue !== "" && !slot.statusDanger
            width: Math.min(Math.ceil(implicitWidth), Math.max(0, statusLine.width - x - (detailsButton.visible ? detailsButton.width + Tokens.sp16 : 0)))
            text: slot.statusValue
            role: "body"
            tabular: true
            elide: Text.ElideRight
            color: Tokens.text1
        }
        CuButton {
            id: detailsButton
            objectName: "footDetails"
            visible: slot.detailsText !== ""
            variant: "text"
            ground: slot.ground
            text: slot.detailsText
            tooltip: slot.detailsTip
            forcedState: slot.forcedState
            x: Tokens.snap(statusLine.width - width, slot.dpr)
            y: Tokens.snap(countText.y + countText.baselineOffset - (labelItem.y + labelItem.baselineOffset), slot.dpr)
            onClicked: slot.details()
        }
        Item {
            objectName: "footStatusTipArea"
            x: 0
            y: 0
            width: detailsButton.visible ? Math.max(0, statusLine.width - detailsButton.width - Tokens.sp16) : statusLine.width
            height: Tokens.hFootStatus
            readonly property string tip: slot.statusTip !== "" ? slot.statusTip : (countText.truncated ? slot.status : "")
            visible: tip !== ""
            HoverHandler { id: statusHover }
            CuHoverTip { shown: statusHover.hovered; text: parent.tip; placement: "above" }
        }
    }
    Item {
        id: commitRow
        objectName: "footCommitRow"
        x: 0
        y: Tokens.hFootStatus + Tokens.sp8
        width: slot.width
        height: Tokens.hCommit
    }
}

import QtQuick
import QtQuick.Window

Item {
    id: row
    property string title: ""
    property string description: ""
    property bool leadingControl: false
    property string ground: "ink"
    default property alias control: controlSlot.data
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property real slotWidth: controlSlot.childrenRect.width
    implicitWidth: Tokens.pageColumn
    implicitHeight: Tokens.hRowSetting
    objectName: "settingRow"
    Accessible.role: Accessible.Grouping
    Accessible.name: title
    Accessible.description: description

    Item {
        id: controlSlot
        x: row.leadingControl ? 0 : Tokens.snap(row.width - row.slotWidth, row.dpr)
        y: 0
        width: row.slotWidth
        height: Tokens.hControl
    }
    CuText {
        id: titleText
        objectName: "settingTitle"
        x: row.leadingControl ? row.slotWidth + Tokens.sp12 : 0
        y: Tokens.sp8
        width: Math.max(0, (row.leadingControl ? row.width : row.width - row.slotWidth - Tokens.sp24) - x)
        text: row.title
        role: "body"
        elide: Text.ElideRight
        color: row.enabled ? Tokens.text1 : Tokens.text2
    }
    CuText {
        id: descText
        objectName: "settingDescription"
        visible: row.description !== ""
        x: titleText.x
        y: Tokens.sp24 + Tokens.sp4
        width: titleText.width
        text: row.description
        role: "meta"
        elide: Text.ElideRight
        color: Tokens.quietOn(row.ground)
        HoverHandler { id: descHover }
        CuHoverTip { shown: descHover.hovered && descText.truncated; text: row.description }
    }
}

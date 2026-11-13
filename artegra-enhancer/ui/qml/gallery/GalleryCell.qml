import QtQuick
import "../creative"

Item {
    id: cell
    property string name: ""
    property string ground: "ink"
    property int pad: 16
    property real contentWidth: -1
    property real contentHeight: -1
    default property alias content: stageArea.data
    readonly property real shownW: contentWidth >= 0 ? contentWidth : stageArea.childrenRect.x + stageArea.childrenRect.width
    readonly property real shownH: contentHeight >= 0 ? contentHeight : stageArea.childrenRect.y + stageArea.childrenRect.height
    readonly property real stageW: Math.ceil((shownW + 2 * pad) / 4) * 4
    readonly property real stageH: Math.ceil((shownH + 2 * pad) / 4) * 4
    objectName: "galleryCell"

    implicitWidth: Math.max(stageW, Math.ceil((label.implicitWidth) / 4) * 4)
    implicitHeight: 20 + stageH

    CuText {
        id: label
        x: 0
        y: 0
        text: cell.name
        role: "meta"
        color: Tokens.text3
    }
    Rectangle {
        id: stage
        x: 0
        y: 20
        width: cell.stageW
        height: cell.stageH
        color: Tokens.groundTone(cell.ground)
        Item {
            id: stageArea
            x: cell.pad
            y: cell.pad
            width: Math.max(0, cell.stageW - 2 * cell.pad)
            height: Math.max(0, cell.stageH - 2 * cell.pad)
        }
    }
}

import QtQuick
import QtQuick.Window

Item {
    id: row
    property string label: ""
    property string note: ""
    property string actionText: ""
    property string actionTip: ""
    property string value: ""
    property string forcedState: ""
    property string ground: "ink"
    readonly property bool isFact: value !== ""
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    signal actionClicked()

    implicitWidth: Tokens.legContentMin
    implicitHeight: isFact ? (valueLines.length > 1 ? 2 * labelText.lineBox + Tokens.sp4 : Tokens.hFactRow) : Tokens.hLabelRow
    readonly property real valueRoom: Math.max(0, Math.floor(width - Math.ceil(labelMetrics.advanceWidth(label)) - Tokens.sp8))
    FontMetrics { id: labelMetrics; font: labelText.font }
    FontMetrics { id: valueMetrics; font: valueText.font }
    readonly property var valueLines: {
        if (!isFact || valueMetrics.advanceWidth(value) <= valueRoom) return [value]
        var parts = value.split(", ")
        for (var n = parts.length - 1; n >= 1; --n) {
            var head = parts.slice(0, n).join(", ") + ","
            var tail = parts.slice(n).join(", ")
            if (valueMetrics.advanceWidth(head) <= valueRoom && valueMetrics.advanceWidth(tail) <= valueRoom) return [head, tail]
        }
        return [value]
    }
    objectName: isFact ? "factRow" : "labelRow"

    function onBaseline(base) { return Tokens.snap(labelText.y + labelText.baselineOffset - base, dpr) }

    CuText {
        id: labelText
        objectName: "labelRowLabel"
        x: 0
        y: centredIn(row.isFact ? Tokens.hFactRow : row.height)
        width: Math.min(implicitWidth, Math.max(0, row.width - rightWidth - (rightWidth > 0 ? Tokens.sp8 : 0)))
        readonly property real rightWidth: row.isFact ? valueText.width
                                          : row.actionText !== "" ? action.width
                                          : row.note !== "" ? Math.ceil(noteText.implicitWidth) : 0
        text: row.label
        role: "body"
        elide: Text.ElideRight
        color: row.enabled ? Tokens.text2 : Tokens.text4
    }
    CuText {
        id: noteText
        objectName: "labelRowNote"
        visible: !row.isFact && row.actionText === "" && row.note !== ""
        x: Tokens.snap(row.width - Math.ceil(implicitWidth), row.dpr)
        y: row.onBaseline(baselineOffset)
        text: row.note
        role: "meta"
        color: Tokens.quietOn(row.ground)
    }
    CuButton {
        id: action
        visible: !row.isFact && row.actionText !== ""
        variant: "text"
        ground: row.ground
        text: row.actionText
        tooltip: row.actionTip
        forcedState: row.forcedState
        enabled: row.enabled
        x: Tokens.snap(row.width - width, row.dpr)
        y: Tokens.snap(labelText.y + labelText.baselineOffset - (labelItem.y + labelItem.baselineOffset), row.dpr)
        onClicked: row.actionClicked()
    }
    CuText {
        id: valueText
        objectName: "factValue"
        visible: row.isFact
        width: Math.min(Math.ceil(implicitWidth), row.valueRoom)
        x: Tokens.snap(row.width - width, row.dpr)
        y: labelText.y
        text: row.valueLines.join("\n")
        horizontalAlignment: Text.AlignRight
        role: "body"
        elide: Text.ElideRight
        color: row.enabled ? Tokens.text1 : Tokens.text4
        HoverHandler { id: valueHover }
        CuHoverTip { shown: valueHover.hovered && valueText.truncated; text: row.value }
    }
}

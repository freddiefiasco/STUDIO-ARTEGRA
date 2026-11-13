import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.Control {
    id: title
    property string text: ""
    property bool divider: false
    property string role: "title"
    property string note: ""
    property string actionText: ""
    property bool foldable: false
    property bool open: false
    property string summary: ""
    property string forcedState: ""
    property string noteTip: ""
    property string titleTip: ""
    property string openActionText: ""
    signal openActionClicked()
    property string ground: "ink"
    default property alias trailing: trailingRow.data
    readonly property int lineHeight: Tokens.hTitleRow
    readonly property int topGap: 0
    readonly property alias titleItem: label
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property bool hoverOn: foldable && enabled && (hovered || forcedState === "hover")
    readonly property bool ringShown: foldable && (visualFocus || forcedState === "focus")
    function onBaseline(base) { return Tokens.snap(label.y + label.baselineOffset - base, dpr) }

    signal actionClicked()
    signal toggled(bool open)

    implicitHeight: Tokens.hTitleRow
    implicitWidth: Tokens.legContentMin
    width: parent ? parent.width : Tokens.legContentMin
    hoverEnabled: foldable
    focusPolicy: foldable ? Qt.TabFocus : Qt.NoFocus
    padding: 0

    Accessible.role: foldable ? Accessible.Button : Accessible.Heading
    Accessible.name: text
    Accessible.description: foldable ? (open ? "Open" : summary) : note
    Accessible.onPressAction: { if (title.foldable) title.toggled(!title.open) }

    Keys.onPressed: (event) => {
        if (title.foldable && (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) {
            title.toggled(!title.open)
            event.accepted = true
        }
    }

    Item {
        id: hit
        visible: title.foldable
        x: 0
        y: -Tokens.sp4
        width: title.width
        height: Tokens.hTitleRow + 2 * Tokens.sp4
    }
    MouseArea {
        anchors.fill: hit
        enabled: title.foldable
        cursorShape: title.foldable ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: { title.forceActiveFocus(Qt.MouseFocusReason); title.toggled(!title.open) }
    }

    CuText {
        id: label
        objectName: "sectionTitle"
        x: 0
        y: centredIn(Tokens.hTitleRow)
        width: Math.min(implicitWidth, Math.max(0, rightEnd.x - Tokens.sp8))
        text: title.text
        role: title.role
        elide: Text.ElideRight
        color: title.enabled ? Tokens.text1 : Tokens.text4
        Accessible.role: Accessible.Heading
        Accessible.name: text
        HoverHandler { id: titleHover; enabled: title.titleTip !== "" }
        CuHoverTip { shown: titleHover.hovered && title.titleTip !== ""; text: title.titleTip; placement: "above" }
    }

    Item {
        id: rightEnd
        readonly property real w: title.foldable ? foldBox.width
                                  : title.actionText !== "" ? action.width
                                  : title.note !== "" ? Math.ceil(noteText.implicitWidth)
                                  : trailingRow.width
        x: Tokens.snap(title.width - w, title.dpr)
        y: 0
        width: w
        height: Tokens.hTitleRow
        CuText {
            id: noteText
            objectName: "sectionNote"
            visible: !title.foldable && title.actionText === "" && title.note !== ""
            x: 0
            y: title.onBaseline(baselineOffset)
            text: title.note
            role: "meta"
            color: Tokens.quietOn(title.ground)
            HoverHandler { id: noteHover; enabled: title.noteTip !== "" }
            CuHoverTip { shown: noteHover.hovered && title.noteTip !== ""; text: title.noteTip; placement: "above" }
        }
        CuButton {
            id: action
            visible: !title.foldable && title.actionText !== ""
            variant: "text"
            ground: title.ground
            text: title.actionText
            x: 0
            y: title.onBaseline(labelItem.y + labelItem.baselineOffset)
            onClicked: title.actionClicked()
        }
        Row {
            id: trailingRow
            visible: !title.foldable && title.actionText === "" && title.note === ""
            x: 0
            y: Tokens.snap((Tokens.hTitleRow - height) / 2, title.dpr)
            spacing: Tokens.sp8
        }
        Item {
            id: foldBox
            visible: title.foldable
            width: (summaryText.visible ? Math.ceil(summaryText.implicitWidth) + Tokens.sp8 : 0)
                   + (openAction.visible ? Math.ceil(openAction.width) + Tokens.sp16 : 0) + Tokens.iconBox
            height: Tokens.hTitleRow
            CuButton {
                id: openAction
                objectName: "sectionOpenAction"
                visible: title.foldable && title.open && title.openActionText !== ""
                variant: "text"
                ground: title.ground
                text: title.openActionText
                x: 0
                y: title.onBaseline(labelItem.y + labelItem.baselineOffset)
                onClicked: title.openActionClicked()
            }
            CuText {
                id: summaryText
                objectName: "foldSummary"
                visible: !title.open && title.summary !== ""
                x: 0
                y: title.onBaseline(baselineOffset)
                text: title.summary
                role: "meta"
                color: !title.enabled ? Tokens.text4
                       : (title.hoverOn || title.ringShown)
                         ? (Tokens.groundKey(title.ground) === "float" ? Tokens.text1 : Tokens.text2)
                         : Tokens.quietOn(title.ground)
            }
            CuIcon {
                objectName: "foldChevron"
                x: Tokens.snap(title.width - Tokens.iconBox, title.dpr) - rightEnd.x
                y: Tokens.snap((Tokens.hTitleRow - Tokens.iconBox) / 2, title.dpr)
                iconName: title.open ? "chevronDown" : "chevronRight"
                color: !title.enabled ? Tokens.text4 : (title.hoverOn || title.ringShown) ? Tokens.text1 : Tokens.text3
            }
        }
    }

    CuFocusRing {
        target: hit
        inset: false
        shown: title.ringShown
        targetRadius: 0
    }
}

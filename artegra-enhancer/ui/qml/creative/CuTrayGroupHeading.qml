import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

Item {
    id: heading
    property Item rail: null
    property var tab: null
    property string group: ""
    property string kind: "heading"
    property string title: ""
    property int figure: -1
    property string action: ""
    property bool first: false
    property bool foldable: false
    property bool folded: false
    property bool danger: false
    property bool batchRunning: rail !== null && rail.batchRunning === true
    property bool sheetOpen: rail !== null && rail.model !== undefined && rail.model.resultsOpen === true
    property string actionTip: ""

    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    function near(v) { return Tokens.snap(v + 0.5 / dpr, dpr) }
    readonly property int inset: rail !== null ? rail.inset : Tokens.legInset
    readonly property bool isTail: group === "nextTail"
    readonly property bool isCleared: kind === "cleared"
    readonly property bool chevronShown: !isCleared && (kind === "fold" || foldable)
    readonly property bool figureShown: kind === "fold" && !isTail && figure >= 0 && !batchRunning && !sheetOpen
    readonly property bool lit: fold.enabled && (fold.hovered || fold.visualFocus)
    readonly property int lineY: isTail ? Tokens.sp12 : Tokens.sp16
    readonly property real chevronX: Tokens.snap(width - inset - Tokens.iconBox, dpr)
    readonly property real actionRight: chevronShown ? chevronX - Tokens.sp16 : width - inset

    implicitHeight: Tokens.hGroupHead
    Accessible.ignored: true

    T.AbstractButton {
        id: fold
        objectName: "queueGroupFold-" + heading.group
        x: 0
        y: 0
        width: actionBtn.visible ? Math.max(0, actionBtn.x - Tokens.textBleed) : heading.width
        height: heading.height
        enabled: heading.chevronShown
        hoverEnabled: true
        focusPolicy: enabled ? Qt.TabFocus : Qt.NoFocus
        Accessible.role: Accessible.Button
        Accessible.name: heading.title + (heading.figureShown ? ", " + heading.figure : "")
        Accessible.description: heading.folded ? "Folded. Activate to show its images." : "Shown. Activate to fold it."
        onClicked: if (heading.rail) heading.rail.toggleGroup(heading.group)
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                if (heading.rail) heading.rail.toggleGroup(heading.group)
                event.accepted = true
            }
        }
        background: Item {}
        contentItem: Item {}
        HoverHandler { cursorShape: fold.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
        CuFocusRing { target: fold; shown: fold.visualFocus; inset: true; targetRadius: 0 }
    }

    CuText {
        id: titleText
        objectName: heading.isCleared ? "queueGroup-cleared" : "queueGroup-" + heading.group
        x: heading.isTail ? heading.inset + Tokens.miniBoxWidth + Tokens.sp12 : heading.inset
        y: heading.lineY
        width: Math.min(Math.ceil(implicitWidth), Math.max(0, (actionBtn.visible ? actionBtn.x - Tokens.sp16
                                                                 : (heading.chevronShown ? heading.chevronX - Tokens.sp16 : heading.width - heading.inset))
                                                              - x - (heading.figureShown ? Math.ceil(figureText.implicitWidth) + Tokens.sp8 : 0)))
        elide: Text.ElideRight
        role: heading.isTail || heading.isCleared ? "body" : "bodyStrong"
        text: heading.title
        color: heading.danger ? Tokens.danger
               : heading.isCleared ? Tokens.text3
               : heading.lit ? Tokens.text1 : Tokens.text2
        Accessible.role: Accessible.Heading
        Accessible.name: heading.title
    }
    CuText {
        id: figureText
        objectName: "queueGroupFigure-" + heading.group
        visible: heading.figureShown
        x: Tokens.snap(titleText.x + Math.ceil(titleText.width) + Tokens.sp8, heading.dpr)
        y: heading.near(titleText.y + titleText.baselineOffset - baselineOffset)
        role: "meta"
        tabular: true
        color: Tokens.text3
        text: heading.figureShown ? String(heading.figure) : ""
        Accessible.ignored: true
    }
    CuButton {
        id: actionBtn
        objectName: heading.isCleared ? "railUndoClear" : heading.group === "skipped" ? "noteDismiss" : "queueGroupAction-" + heading.group
        visible: heading.action !== ""
        x: Tokens.snap(heading.actionRight - width, heading.dpr)
        y: heading.near(titleText.y + titleText.baselineOffset - (labelItem.y + labelItem.baselineOffset))
        variant: "text"
        ground: "ink"
        text: heading.action
        tooltip: heading.actionTip !== "" ? heading.actionTip
                 : heading.isCleared ? "Shows the finished images in the list again"
                 : heading.group === "stopped" ? "Puts every stopped image back in the queue"
                 : heading.group === "refused" ? heading.action + " for these images. The others keep their scale."
                 : heading.group === "later" ? "Queues these images after the batch, " + heading.action.replace("Queue at ", "at ")
                 : ""
        accessibleDescription: tooltip
        onClicked: if (heading.rail) heading.rail.groupAction(heading.group)
    }
    CuIcon {
        objectName: "queueGroupChevron-" + heading.group
        visible: heading.chevronShown
        x: heading.chevronX
        y: heading.lineY
        iconName: heading.folded ? "chevronRight" : "chevronDown"
        iconSize: Tokens.iconBox
        color: heading.lit ? Tokens.text1 : Tokens.text3
    }
}

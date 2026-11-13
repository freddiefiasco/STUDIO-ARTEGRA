import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.Control {
    id: row
    property string kind: "media"
    property string ground: "ink"
    property bool selected: false
    property string text: ""
    property string meta: ""
    property string value: ""
    property bool nameMiddle: false
    property bool twoLines: false
    property real progress: -1
    property int inset: Tokens.legInset
    property bool focusable: false
    property string forcedState: ""
    property bool strong: false
    property string metaTone: ""
    property alias leading: leadingSlot.data
    property alias trailing: trailingSlot.data
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property bool hoverOn: enabled && (hovered || forcedState === "hover")
    readonly property bool pressed: enabled && (tap.pressed || forcedState === "pressed")
    readonly property bool ringShown: visualFocus || forcedState === "focus"
    readonly property bool bodyShown: selected || hoverOn || pressed
    readonly property color bodyColor: pressed ? Tokens.pressOn(ground)
                                       : selected ? Tokens.raisedOn(ground)
                                       : hoverOn ? Tokens.tileOn(ground) : "transparent"
    function stepTone(tone) {
        if (!enabled) return Tokens.text4
        if (!bodyShown) return Qt.colorEqual(tone, Tokens.text3) ? Tokens.quietOn(ground) : tone
        if (Qt.colorEqual(tone, Tokens.text3)) return Tokens.text2
        if (Qt.colorEqual(tone, Tokens.text2)) return Tokens.text1
        return tone
    }
    readonly property bool hasLeading: leadingSlot.children.length > 0
    readonly property real textX: kind === "media" ? inset + Tokens.miniBoxWidth + Tokens.sp12
                                  : (hasLeading ? inset + Tokens.checkSize + Tokens.sp12 : inset)
    readonly property Item trailingItem: trailingSlot.children.length > 0 ? trailingSlot.children[0] : null
    readonly property bool trailingOnMeta: kind === "media" && (meta !== "" || twoLines)
    readonly property bool trailingShown: trailingItem !== null && trailingItem.visible
    readonly property real trailingRoom: trailingItem !== null ? trailingItem.width + Tokens.sp16 : 0
    readonly property real trailingWidth: trailingShown ? trailingItem.width : 0
    readonly property real rightX: width - inset - (trailingItem !== null && !trailingOnMeta ? trailingRoom : 0)
    readonly property real metaRight: width - inset - (trailingOnMeta && trailingShown ? trailingRoom : 0)
    function fitFields(s, room) {
        if (s === "" || metaMetrics.advanceWidth(s) <= room) return s
        var parts = s.split(", ")
        for (var n = parts.length - 1; n >= 1; --n) {
            var t = parts.slice(0, n).join(", ")
            if (metaMetrics.advanceWidth(t) <= room) return t
        }
        return parts[0]
    }
    signal clicked()
    signal doubleClicked()

    implicitWidth: Tokens.legContentMin + 2 * Tokens.legInset
    implicitHeight: kind === "media" ? Tokens.hRowMedia : (kind === "plain" ? Tokens.hRow : 0)
    hoverEnabled: true
    focusPolicy: focusable ? Qt.TabFocus : Qt.NoFocus
    padding: 0
    objectName: "listRow"

    Accessible.role: Accessible.ListItem
    Accessible.name: text
    Accessible.description: meta
    Accessible.selected: selected
    Accessible.onPressAction: row.clicked()

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            row.clicked()
            event.accepted = true
        }
    }

    Rectangle {
        id: body
        objectName: "listRowBody"
        anchors.fill: parent
        color: row.bodyColor
        Behavior on color { ColorAnimation { duration: row.hoverOn || row.pressed ? Tokens.durHoverIn : Tokens.durHoverOut } }
    }
    MouseArea {
        id: tap
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onClicked: row.clicked()
        onDoubleClicked: row.doubleClicked()
    }

    Item {
        id: leadingSlot
        x: row.inset
        y: row.kind === "media" ? Tokens.sp12 : Tokens.snap((row.height - Tokens.hControl) / 2, row.dpr)
        width: row.kind === "media" ? Tokens.miniBoxWidth : Tokens.checkSize
        height: row.kind === "media" ? Tokens.miniBoxHeight : Tokens.hControl
    }
    CuText {
        id: nameText
        objectName: "listRowText"
        visible: row.kind !== "cell" && row.text !== ""
        x: row.textX
        y: row.kind === "media" ? Tokens.sp4 : Tokens.sp12
        width: Math.max(0, (row.kind === "plain" && row.value !== "" ? valueText.x - Tokens.sp8 : row.rightX) - x)
        text: row.text
        role: row.strong ? "bodyStrong" : "body"
        elide: row.nameMiddle ? Text.ElideMiddle : Text.ElideRight
        color: row.stepTone(row.selected || row.strong ? Tokens.text1 : Tokens.text2)
    }
    CuText {
        id: metaText
        objectName: "listRowMeta"
        visible: row.kind === "media" && row.meta !== ""
        x: row.textX
        y: Tokens.sp24
        width: Math.max(0, row.metaRight - x)
        text: row.fitFields(row.meta, width)
        role: "meta"
        tabular: true
        elide: Text.ElideRight
        color: row.metaTone === "danger" ? Tokens.danger : row.stepTone(Tokens.text3)
    }
    FontMetrics { id: metaMetrics; font: metaText.font }
    CuText {
        id: valueText
        objectName: "listRowValue"
        visible: row.kind === "plain" && row.value !== ""
        x: Tokens.snap(row.rightX - Math.ceil(implicitWidth), row.dpr)
        y: Tokens.snap(nameText.y + nameText.baselineOffset - baselineOffset, row.dpr)
        text: row.value
        role: "meta"
        tabular: true
        color: row.stepTone(Tokens.text3)
    }
    Item {
        id: trailingSlot
        objectName: "listRowTrailing"
        readonly property Item item: row.trailingItem
        readonly property Item words: item !== null && item.labelItem !== undefined ? item.labelItem : null
        readonly property Item line: row.trailingOnMeta ? metaText : nameText
        x: Tokens.snap(row.width - row.inset - width, row.dpr)
        y: item === null ? 0
           : words !== null ? Tokens.snap(line.y + line.baselineOffset - (words.y + words.baselineOffset), row.dpr)
           : Tokens.snap((row.height - height) / 2, row.dpr)
        width: item !== null ? item.width : 0
        height: item !== null ? item.height : 0
    }
    CuProgressBar {
        visible: row.kind === "media" && row.progress >= 0
        x: row.inset + Tokens.sp48
        y: Tokens.hRowMedia - Tokens.sp4
        width: Math.max(0, row.width - row.inset - x)
        value: Math.max(0, row.progress)
        ground: "ink"
    }

    CuFocusRing {
        target: body
        inset: true
        shown: row.ringShown
        targetRadius: 0
    }
}

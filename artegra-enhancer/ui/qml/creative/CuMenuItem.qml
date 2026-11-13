import QtQuick
import QtQuick.Window

Item {
    id: item
    property string text: ""
    property bool current: false
    property bool highlighted: false
    property bool ringShown: false
    property bool danger: false
    property bool separator: false
    property bool available: true
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property bool lit: highlighted && available && !separator
    signal triggered()
    signal hoveredIn()

    implicitHeight: separator ? Tokens.sp8 : Tokens.hMenuItem
    implicitWidth: separator ? Tokens.menuMinWidth
                             : Math.ceil(words.implicitWidth) + 2 * Tokens.sp12 + (current ? Tokens.iconBox + Tokens.sp8 : 0)
    objectName: separator ? "menuSeparator" : "menuItem"
    Accessible.role: separator ? Accessible.Separator : Accessible.MenuItem
    Accessible.name: text
    Accessible.checkable: current
    Accessible.checked: current
    Accessible.onPressAction: { if (item.available && !item.separator) item.triggered() }

    Rectangle {
        anchors.fill: parent
        visible: item.lit
        color: Tokens.tileFloat
    }
    CuSettingsRule {
        visible: item.separator
        x: 0
        y: Tokens.snap(item.height / 2, item.dpr)
        width: item.width
        color: Tokens.reveal
    }
    CuText {
        id: words
        visible: !item.separator
        x: Tokens.sp12
        y: centredIn(item.height)
        width: Math.max(0, Math.min(implicitWidth, item.width - x - Tokens.sp12 - (item.current ? Tokens.iconBox + Tokens.sp8 : 0)))
        elide: Text.ElideRight
        text: item.text
        role: "body"
        color: !item.available ? Tokens.text4 : item.danger ? Tokens.danger : (item.lit || item.current ? Tokens.text1 : Tokens.text2)
    }
    Item {
        id: tickBox
        visible: item.current && !item.separator
        x: item.width - Tokens.sp12 - Tokens.iconBox
        y: Tokens.snap((item.height - Tokens.iconBox) / 2, item.dpr)
        width: Tokens.iconBox
        height: Tokens.iconBox
        readonly property int s: Tokens.devPx("check", item.dpr)
        readonly property var rects: {
            var B = Math.round(Tokens.iconBox * item.dpr), k = B / Tokens.iconBox
            var h = (s % 2) ? 0.5 : 0
            var n1 = Math.max(1, Math.round(2.5 * k)), n2 = Math.max(2, Math.round(5 * k))
            var x0 = Math.floor(4 * k) + h, y0 = Math.floor(8 * k) + h
            var out = [], t
            for (t = 0; t <= n1; ++t) out.push([x0 + t - s / 2, y0 + t - s / 2, s, s])
            for (t = 1; t <= n2; ++t) out.push([x0 + n1 + t - s / 2, y0 + n1 - t - s / 2, s, s])
            return out
        }
        Item {
            scale: 1 / item.dpr
            transformOrigin: Item.TopLeft
            Repeater {
                model: tickBox.visible ? tickBox.rects.length : 0
                Rectangle {
                    required property int index
                    readonly property var r: tickBox.rects[index] || [0, 0, 0, 0]
                    x: r[0]; y: r[1]; width: r[2]; height: r[3]
                    antialiasing: false
                    color: item.available ? Tokens.text1 : Tokens.text4
                }
            }
        }
    }
    CuFocusRing { target: item; inset: true; shown: item.ringShown && !item.separator }

    MouseArea {
        anchors.fill: parent
        enabled: !item.separator
        hoverEnabled: true
        cursorShape: item.available && !item.separator ? Qt.PointingHandCursor : Qt.ArrowCursor
        onContainsMouseChanged: { if (containsMouse) item.hoveredIn() }
        onClicked: { if (item.available && !item.separator) item.triggered() }
    }
}

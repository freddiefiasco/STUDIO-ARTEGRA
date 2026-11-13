import QtQuick
import QtQuick.Window

FocusScope {
    id: menu
    property var model: []
    property var currentValue: undefined
    property real minWidth: 0
    property int highlighted: -1
    property bool keyboardLit: false
    property int startIndex: -1
    readonly property int count: model ? model.length : 0
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property real edge: Tokens.px(Tokens.devPx("line", dpr), dpr)
    signal chosen(var value, int index)
    signal closeRequested()

    function usable(i) { return i >= 0 && i < count && !model[i].separator && model[i].enabled !== false }
    function move(dir) {
        if (highlighted < 0 && startIndex >= 0 && usable(startIndex)) { highlighted = startIndex; keyboardLit = true; return }
        var i = highlighted >= 0 ? highlighted : (dir > 0 ? -1 : count)
        for (var n = 0; n < count; ++n) {
            i = (i + dir + count) % count
            if (usable(i)) { highlighted = i; keyboardLit = true; return }
        }
    }
    function choose(i) { if (usable(i)) chosen(model[i].value, i) }
    function currentIndex() {
        for (var i = 0; i < count; ++i) if (!model[i].separator && model[i].value === currentValue) return i
        return -1
    }
    function reset() { highlighted = -1; startIndex = currentIndex(); keyboardLit = false }

    readonly property real widest: {
        var w = 0
        for (var i = 0; i < repeater.count; ++i) { var it = repeater.itemAt(i); if (it) w = Math.max(w, it.implicitWidth) }
        return w
    }
    implicitWidth: Math.ceil(Math.max(Tokens.menuMinWidth, minWidth, widest + 2 * Tokens.menuPad + 2 * edge))
    implicitHeight: Math.ceil(column.implicitHeight + 2 * Tokens.menuPad + 2 * edge)
    objectName: "menu"
    Accessible.role: Accessible.PopupMenu
    Accessible.name: "Menu"

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Down) { menu.move(1); event.accepted = true }
        else if (event.key === Qt.Key_Up) { menu.move(-1); event.accepted = true }
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) { menu.choose(menu.highlighted); event.accepted = true }
        else if (event.key === Qt.Key_Escape) { menu.closeRequested(); event.accepted = true }
        else if (event.text && event.text.length === 1 && /\S/.test(event.text)) {
            var c = event.text.toLowerCase()
            for (var n = 1; n <= menu.count; ++n) {
                var i = (menu.highlighted + n + menu.count) % menu.count
                if (menu.usable(i) && String(menu.model[i].label).toLowerCase().indexOf(c) === 0) { menu.highlighted = i; menu.keyboardLit = true; break }
            }
            event.accepted = true
        }
    }

    CuPlate {
        anchors.fill: parent
        Column {
            id: column
            x: Tokens.menuPad
            y: Tokens.menuPad
            width: parent.width - 2 * Tokens.menuPad
            Repeater {
                id: repeater
                model: menu.model
                CuMenuItem {
                    required property var modelData
                    required property int index
                    width: column.width
                    text: modelData.label !== undefined ? String(modelData.label) : ""
                    separator: modelData.separator === true
                    danger: modelData.danger === true
                    available: modelData.enabled !== false
                    current: !separator && menu.currentValue !== undefined && modelData.value === menu.currentValue
                    highlighted: menu.highlighted === index
                    ringShown: menu.keyboardLit && menu.highlighted === index
                    onHoveredIn: { if (available && !separator) { menu.highlighted = index; menu.keyboardLit = false } }
                    onTriggered: menu.choose(index)
                }
            }
        }
    }
}

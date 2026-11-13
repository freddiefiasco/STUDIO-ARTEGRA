import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.Control {
    id: control

    property var model: []
    property var currentValue: undefined
    property string accessibleName: ""
    property bool dropUp: false
    property string ground: "ink"
    property string forcedState: ""
    readonly property int count: model ? model.length : 0
    readonly property int currentIndex: {
        for (var i = 0; i < count; ++i) if (model[i].value === currentValue) return i
        return -1
    }
    readonly property bool open: popup.visible
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property bool hoverOn: enabled && (hovered || forcedState === "hover")
    readonly property bool ringShown: (visualFocus && !popup.visible) || forcedState === "focus"

    signal activated(var value)

    implicitWidth: Tokens.settingControl
    implicitHeight: Tokens.hControl
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    Accessible.role: Accessible.ComboBox
    Accessible.name: accessibleName
    Accessible.description: currentIndex >= 0 ? model[currentIndex].label : ""

    function choose(i) {
        if (i >= 0 && i < count && i !== currentIndex) activated(model[i].value)
    }
    function openList() { if (count > 0 && enabled) popup.open() }
    function closeList() { popup.close() }
    Component.onCompleted: { if (forcedState === "open") Qt.callLater(function() { if (control.visible) control.openList() }) }

    Keys.onPressed: (event) => {
        if (count === 0) return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter
            || (event.key === Qt.Key_Down && (event.modifiers & Qt.AltModifier))) { popup.open(); event.accepted = true }
        else if (event.key === Qt.Key_Down) { choose(Math.min(count - 1, currentIndex + 1)); event.accepted = true }
        else if (event.key === Qt.Key_Up) { choose(Math.max(0, currentIndex - 1)); event.accepted = true }
    }

    Rectangle {
        id: box
        objectName: "selectBody"
        anchors.fill: parent
        radius: Tokens.radiusControl
        antialiasing: radius > 0
        color: Tokens.wellOn(control.ground)
    }
    Item {
        visible: control.hoverOn || popup.visible
        scale: 1 / control.dpr
        transformOrigin: Item.TopLeft
        Rectangle {
            width: Math.round(control.width * control.dpr)
            height: Math.round(control.height * control.dpr)
            color: "transparent"
            border.width: Tokens.devPx("line", control.dpr)
            border.color: Tokens.reveal
            radius: Tokens.radiusControl * control.dpr
            antialiasing: radius > 0
        }
    }
    CuText {
        objectName: "selectValue"
        x: Tokens.textInset
        y: centredIn(control.height)
        width: Math.max(0, arrow.x - Tokens.sp8 - x)
        elide: Text.ElideRight
        role: "body"
        text: control.currentIndex >= 0 ? control.model[control.currentIndex].label : "Choose…"
        color: !control.enabled ? Tokens.text4 : (control.currentIndex >= 0 ? Tokens.text1 : Tokens.text3)
    }
    CuIcon {
        id: arrow
        x: control.width - Tokens.textInset - Tokens.iconBox
        y: Tokens.snap((control.height - Tokens.iconBox) / 2, control.dpr)
        iconName: popup.visible ? "chevronUp" : "chevronDown"
        color: !control.enabled ? Tokens.text4 : (control.hoverOn || popup.visible || control.ringShown) ? Tokens.text1 : Tokens.text3
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {
            control.forceActiveFocus(Qt.MouseFocusReason)
            if (popup.visible) popup.close(); else control.openList()
        }
    }
    HoverHandler { cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }

    CuFocusRing {
        target: box
        shown: control.ringShown
    }

    onVisibleChanged: if (!visible && popup.visible) popup.close()
    T.Popup {
        id: popup
        property real roomBelow: 1e6
        function measure() {
            var w = control.Window.window
            if (!w || !w.contentItem) { roomBelow = 1e6; return }
            var p = control.mapToItem(w.contentItem, 0, control.height)
            roomBelow = w.contentItem.height - p.y - Tokens.sp8
        }
        readonly property bool above: control.dropUp || roomBelow < implicitHeight + Tokens.sp4
        x: 0
        y: above ? -implicitHeight - Tokens.sp4 : control.height + Tokens.sp4
        padding: 0
        modal: false
        focus: true
        closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent
        implicitWidth: list.implicitWidth
        implicitHeight: list.implicitHeight
        background: null
        enter: Transition { NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: Tokens.durFloatIn } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: Tokens.durFloatOut } }
        onAboutToShow: { measure(); list.reset() }
        onOpened: list.forceActiveFocus(Qt.PopupFocusReason)
        function closeByKey() { popup.close(); control.forceActiveFocus(Qt.TabFocusReason) }
        contentItem: CuMenu {
            id: list
            objectName: "selectMenu"
            model: control.model
            currentValue: control.currentValue
            minWidth: control.width
            focus: true
            onChosen: (value, index) => { control.choose(index); popup.closeByKey() }
            onCloseRequested: popup.closeByKey()
        }
    }
}

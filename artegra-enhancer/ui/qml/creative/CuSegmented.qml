import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.Control {
    id: control

    property var model: []
    property var currentValue: undefined
    property string accessibleName: ""
    property int controlHeight: Tokens.hControl
    property int fontSize: 13
    property bool tabular: false
    property string ground: "ink"
    property bool equalCells: true
    property string forcedState: ""
    readonly property int count: model ? model.length : 0
    readonly property int currentIndex: {
        for (var i = 0; i < count; ++i) if (model[i].value === currentValue) return i
        return -1
    }
    readonly property bool warnSelected: currentIndex >= 0 && model[currentIndex].warn === true
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int insetDev: Tokens.devPx("inset", dpr)
    readonly property color trackColor: Tokens.wellOn(ground)
    readonly property color hoverColor: Tokens.tileOn(ground)
    readonly property color pressedColor: Tokens.pressOn(ground)
    readonly property color chosenColor: Tokens.raisedOn(ground)
    readonly property int forcedIndex: {
        var m = /^(hover|pressed):(\d+)$/.exec(forcedState)
        return m ? parseInt(m[2], 10) : -1
    }
    readonly property bool ringShown: visualFocus || forcedState === "focus"

    FontMetrics { id: fm; font: Tokens.fontFor("body", control.tabular) }
    FontMetrics { id: fmSub; font: Tokens.fontFor("body", true) }
    function naturalWidth(i) {
        var m = model[i]
        return Math.ceil(fm.advanceWidth(m.label) + (m.sub ? Tokens.sp4 + fmSub.advanceWidth(m.sub) : 0)) + Tokens.sp32
    }
    readonly property int cellNatural: {
        var w = 0
        for (var i = 0; i < count; ++i) w = Math.max(w, naturalWidth(i))
        return Tokens.onGrid(w)
    }
    readonly property var natural: {
        var out = []
        for (var i = 0; i < count; ++i) out.push(cellNatural)
        return out
    }
    function cellX(i) { return Tokens.snap(i * width / Math.max(1, count), dpr) }
    function cellW(i) { return (i + 1 >= count ? width : cellX(i + 1)) - cellX(i) }

    signal activated(var value)

    property bool tipMuted: false
    onHoveredChanged: { if (!hovered) tipMuted = false }

    implicitWidth: equalCells ? Tokens.settingControl : count * cellNatural
    implicitHeight: controlHeight
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    Accessible.role: Accessible.Grouping
    Accessible.name: accessibleName

    function optionEnabled(i) {
        return control.enabled && i >= 0 && i < count && model[i].enabled !== false
    }
    function step(dir) {
        var i = currentIndex < 0 ? (dir > 0 ? -1 : count) : currentIndex
        for (var n = 0; n < count; ++n) {
            i += dir
            if (i < 0 || i >= count) return
            if (optionEnabled(i)) { control.activated(model[i].value); return }
        }
    }
    function toEnd(dir) {
        for (var n = 0; n < count; ++n) {
            var i = dir < 0 ? n : count - 1 - n
            if (optionEnabled(i)) { if (i !== currentIndex) control.activated(model[i].value); return }
        }
    }

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Right || event.key === Qt.Key_Down) { step(1); event.accepted = true }
        else if (event.key === Qt.Key_Left || event.key === Qt.Key_Up) { step(-1); event.accepted = true }
        else if (event.key === Qt.Key_Home) { toEnd(-1); event.accepted = true }
        else if (event.key === Qt.Key_End) { toEnd(1); event.accepted = true }
    }

    Rectangle {
        id: track
        objectName: "segmentedTrack"
        anchors.fill: parent
        color: control.trackColor
        radius: Tokens.radiusControl
        antialiasing: radius > 0
    }

    Item {
        id: devLayer
        scale: 1 / control.dpr
        transformOrigin: Item.TopLeft
        width: Math.round(control.width * control.dpr)
        height: Math.round(control.height * control.dpr)
        readonly property int hDev: Math.round(control.height * control.dpr)
        function xDev(i) { return Math.round(control.cellX(i) * control.dpr) }
        function wDev(i) { return Math.round((control.cellX(i) + control.cellW(i)) * control.dpr) - xDev(i) }
        Rectangle {
            id: indicator
            objectName: "segmentedChosen"
            visible: control.currentIndex >= 0
            x: devLayer.xDev(Math.max(0, control.currentIndex)) + control.insetDev
            y: control.insetDev
            width: Math.max(0, devLayer.wDev(Math.max(0, control.currentIndex)) - 2 * control.insetDev)
            height: devLayer.hDev - 2 * control.insetDev
            color: control.chosenColor
            radius: Tokens.innerRadius(Tokens.radiusControl, Tokens.px(control.insetDev, control.dpr)) * control.dpr
            antialiasing: radius > 0
            Behavior on x {
                NumberAnimation { duration: Tokens.durChosen; easing.type: Easing.BezierSpline; easing.bezierCurve: Tokens.easeEnter }
            }
        }
    }

    Repeater {
        model: control.model
        delegate: Item {
            id: seg
            required property var modelData
            required property int index
            readonly property bool selected: control.currentIndex === index
            readonly property bool usable: modelData.enabled !== false && control.enabled
            readonly property bool warn: modelData.warn === true && usable
            readonly property bool over: (segHover.hovered || (control.forcedIndex === index && control.forcedState.indexOf("hover") === 0)) && usable
            readonly property bool down: (cellTap.pressed || (control.forcedIndex === index && control.forcedState.indexOf("pressed") === 0)) && usable
            readonly property bool onBody: selected || over || down
            objectName: "segment-" + modelData.label
            x: control.cellX(index)
            y: 0
            width: control.cellW(index)
            height: control.height

            Accessible.role: Accessible.RadioButton
            Accessible.name: modelData.label
            Accessible.description: modelData.tip || ""
            Accessible.checkable: true
            Accessible.checked: selected
            Accessible.onPressAction: { if (usable) control.activated(modelData.value) }

            Item {
                visible: !seg.selected && (seg.over || seg.down)
                scale: 1 / control.dpr
                transformOrigin: Item.TopLeft
                Rectangle {
                    x: control.insetDev
                    y: control.insetDev
                    width: Math.max(0, devLayer.wDev(seg.index) - 2 * control.insetDev)
                    height: devLayer.hDev - 2 * control.insetDev
                    color: seg.down ? control.pressedColor : control.hoverColor
                    antialiasing: false
                }
            }
            readonly property real wordsW: Math.ceil(segLabel.implicitWidth) + (subText.visible ? Tokens.sp4 + Math.ceil(subText.implicitWidth) : 0)
            CuText {
                id: segLabel
                objectName: "segmentLabel"
                x: Tokens.snap(Math.max(Tokens.textInset, (seg.width - seg.wordsW) / 2), control.dpr)
                y: centredIn(seg.height)
                width: Math.min(implicitWidth, Math.max(0, seg.width - 2 * Tokens.textInset))
                elide: Text.ElideRight
                text: seg.modelData.label
                role: "body"
                tabular: control.tabular
                color: !control.enabled ? Tokens.text4
                     : seg.selected ? Tokens.text1
                     : (!seg.usable || seg.warn) ? Tokens.text4
                     : (seg.over || seg.down) ? Tokens.text1 : Tokens.text2
            }
            CuText {
                id: subText
                x: segLabel.x + segLabel.width + Tokens.sp4
                y: segLabel.y
                visible: (seg.modelData.sub || "") !== ""
                text: seg.modelData.sub || ""
                role: "body"
                tabular: true
                color: !seg.usable ? Tokens.text4 : Tokens.onBody(Tokens.text3, seg.onBody)
            }
            MouseArea {
                id: cellTap
                anchors.fill: parent
                onPressed: control.tipMuted = true
                onClicked: {
                    control.forceActiveFocus(Qt.MouseFocusReason)
                    if (seg.usable && !seg.selected) control.activated(seg.modelData.value)
                }
            }
            HoverHandler {
                id: segHover
                cursorShape: seg.usable ? Qt.PointingHandCursor : Qt.ArrowCursor
            }
            CuHoverTip {
                shown: (segHover.hovered && !control.tipMuted) || (control.visualFocus && seg.selected)
                text: seg.modelData.tip || ""
            }
        }
    }

    CuFocusRing {
        target: track
        shown: control.ringShown
    }
}

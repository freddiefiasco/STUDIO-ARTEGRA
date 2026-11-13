import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.Control {
    id: control

    property string label: ""
    property string description: ""
    property string lowLabel: ""
    property string highLabel: ""
    property real value: 0
    property real resetValue: 0
    property string resetName: ""
    property real from: 0
    property real to: 100
    property string ground: "ink"
    property string forcedState: ""
    readonly property bool changed: value.toFixed(0) !== resetValue.toFixed(0)
    readonly property bool setByLook: !changed
    readonly property bool dragging: track.pressed || forcedState === "pressed"
    readonly property bool hoverOn: enabled && (track.hovered || forcedState === "hover")
    readonly property bool lit: enabled && (hoverOn || dragging)
    readonly property bool editing: readout.activeFocus || forcedState === "typing"
    property string clampNote: ""
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property real line: Tokens.px(1, dpr)
    readonly property real span: Math.max(1, to - from)
    readonly property real tickX: scaleRow.xOf((track.shownValue - from) / span)
    readonly property bool ringShown: (visualFocus && !readout.activeFocus) || forcedState === "focus"

    signal moved(real newValue)

    implicitWidth: Tokens.legContentMin
    implicitHeight: Tokens.hSlider
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    Accessible.role: Accessible.Slider
    Accessible.name: label
    Accessible.description: description
    Accessible.onIncreaseAction: setValue(value + 1)
    Accessible.onDecreaseAction: setValue(value - 1)

    function clamp(v) {
        return Math.max(from, Math.min(to, Math.round(v)))
    }
    function setValue(v) {
        var next = clamp(v)
        if (next !== Math.round(value)) moved(next)
    }
    function commitField() {
        var t = readout.text.trim()
        if (/^\d{1,3}$/.test(t)) {
            var typed = parseInt(t, 10)
            if (typed > to) { clampNote = "Set to " + Math.round(to) + ", the maximum."; noteTimer.restart() }
            else if (typed < from) { clampNote = "Set to " + Math.round(from) + ", the minimum."; noteTimer.restart() }
            setValue(typed)
        }
        readout.text = String(Math.round(control.value))
    }
    function beginEdit(text) {
        readout.forceActiveFocus(Qt.MouseFocusReason)
        readout.text = text
        readout.cursorPosition = readout.length
    }

    Keys.onPressed: (event) => {
        var big = (event.modifiers & Qt.ShiftModifier) ? 10 : 1
        if (event.key === Qt.Key_Right || event.key === Qt.Key_Up) { setValue(value + big); event.accepted = true }
        else if (event.key === Qt.Key_Left || event.key === Qt.Key_Down) { setValue(value - big); event.accepted = true }
        else if (event.key === Qt.Key_PageUp) { setValue(value + 10); event.accepted = true }
        else if (event.key === Qt.Key_PageDown) { setValue(value - 10); event.accepted = true }
        else if (event.key === Qt.Key_Home) { setValue(from); event.accepted = true }
        else if (event.key === Qt.Key_End) { setValue(to); event.accepted = true }
        else if (event.text.length === 1 && event.text >= "0" && event.text <= "9") { beginEdit(event.text); event.accepted = true }
    }

    function syncReadout() { if (!readout.activeFocus) readout.text = String(Math.round(control.value)) }
    onValueChanged: { if (readout.text !== "" || readout.activeFocus) syncLater.restart() }
    Timer { id: syncLater; interval: 0; onTriggered: control.syncReadout() }

    Timer {
        id: noteTimer
        interval: 4000
        onTriggered: control.clampNote = ""
    }

    CuText {
        id: nameText
        objectName: "sliderName"
        x: 0
        y: centredIn(Tokens.hSliderName)
        width: Math.max(0, readout.x - Tokens.sp8)
        text: control.label
        role: "body"
        elide: Text.ElideRight
        color: !control.enabled ? Tokens.text4 : (control.lit ? Tokens.text1 : Tokens.text2)
        HoverHandler { id: nameHover }
        CuHoverTip {
            shown: nameHover.hovered
            text: control.description
            detail: control.lowLabel !== "" && control.highLabel !== ""
                    ? control.lowLabel + " at " + Math.round(control.from) + ", " + control.highLabel + " at " + Math.round(control.to) : ""
            placement: "above"
        }
    }
    FontMetrics { id: readoutMetrics; font: Tokens.fontFor("body", true) }
    T.TextField {
        id: readout
        objectName: "sliderValueField"
        readonly property real textW: Math.ceil(readoutMetrics.advanceWidth(text !== "" ? text : "0"))
        width: Tokens.onGrid(Math.max(textW, Math.ceil(readoutMetrics.advanceWidth("000"))) + 1)
        x: control.width - width
        y: Tokens.snap(nameText.y + nameText.baselineOffset - readoutMetrics.ascent, control.dpr)
        height: Math.ceil(readoutMetrics.height)
        padding: 0
        horizontalAlignment: TextInput.AlignRight
        verticalAlignment: TextInput.AlignTop
        font: Tokens.fontFor("body", true)
        renderType: Tokens.renderType
        color: !control.enabled ? Tokens.text4 : (control.changed || control.editing || control.dragging ? Tokens.text1 : Tokens.text2)
        text: control.value.toFixed(0)
        selectByMouse: true
        selectionColor: Tokens.textSelection
        selectedTextColor: Tokens.text1
        maximumLength: 3
        inputMethodHints: Qt.ImhDigitsOnly
        validator: RegularExpressionValidator { regularExpression: /\d{0,3}/ }
        activeFocusOnTab: false
        enabled: control.enabled
        hoverEnabled: true
        background: null
        cursorDelegate: Rectangle { width: Tokens.px(1, control.dpr); color: Tokens.text1; visible: readout.cursorVisible }
        Accessible.role: Accessible.EditableText
        Accessible.name: control.label + " value, " + Math.round(control.from) + " to " + Math.round(control.to)
        onActiveFocusChanged: {
            if (activeFocus) Qt.callLater(function() { if (readout.activeFocus && readout.length > 1) readout.selectAll() })
            else control.commitField()
        }
        onAccepted: { control.commitField(); control.forceActiveFocus(Qt.TabFocusReason) }
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Escape) {
                readout.text = String(Math.round(control.value)); control.forceActiveFocus(Qt.TabFocusReason); event.accepted = true
            } else if (event.key === Qt.Key_Up || event.key === Qt.Key_Down
                       || event.key === Qt.Key_PageUp || event.key === Qt.Key_PageDown) {
                var d = event.key === Qt.Key_Up ? 1 : event.key === Qt.Key_Down ? -1 : event.key === Qt.Key_PageUp ? 10 : -10
                control.setValue(control.value + d)
                readout.text = String(Math.round(control.value))
                readout.selectAll()
                event.accepted = true
            }
        }
        HoverHandler { cursorShape: Qt.IBeamCursor }
        CuHoverTip { shown: control.clampNote !== ""; text: control.clampNote; placement: "above" }
    }
    Item {
        objectName: "sliderTypingMark"
        visible: control.editing
        x: readout.x + readout.width - readout.textW - 1
        y: Tokens.snap(readout.y + readoutMetrics.ascent + 2, control.dpr)
        width: readout.textW + 1
        height: 1
        Item {
            scale: 1 / control.dpr
            transformOrigin: Item.TopLeft
            Rectangle {
                width: Math.round((readout.textW + 1) * control.dpr)
                height: Tokens.devPx("line", control.dpr)
                color: Tokens.text2
                antialiasing: false
            }
        }
    }
    Rectangle {
        visible: control.forcedState === "typing"
        x: Tokens.snap(readout.x + readout.width, control.dpr)
        y: readout.y
        width: Tokens.px(1, control.dpr)
        height: readout.height
        color: Tokens.text1
    }
    MouseArea {
        anchors.fill: readout
        enabled: !readout.activeFocus && control.enabled
        cursorShape: Qt.IBeamCursor
        onClicked: { readout.forceActiveFocus(Qt.MouseFocusReason); readout.selectAll() }
    }

    T.Slider {
        id: track
        x: 0
        y: Tokens.hSliderName - Tokens.sp4
        width: control.width
        height: Tokens.hitScale
        from: control.from
        to: control.to
        stepSize: 1
        value: control.value
        live: true
        padding: 0
        hoverEnabled: true
        focusPolicy: Qt.NoFocus
        enabled: control.enabled
        Accessible.ignored: true
        property double lastPress: 0
        onPressedChanged: {
            if (!pressed) return
            control.forceActiveFocus(Qt.MouseFocusReason)
            var now = Date.now()
            if (now - lastPress <= Qt.styleHints.mouseDoubleClickInterval) {
                lastPress = 0
                Qt.callLater(function() { control.moved(control.resetValue) })
            } else {
                lastPress = now
            }
        }
        onMoved: control.setValue(track.value)
        property real shownValue: pressed ? value : control.value
        Behavior on shownValue {
            enabled: !track.pressed
            NumberAnimation { duration: Tokens.durChosen; easing.type: Easing.BezierSpline; easing.bezierCurve: Tokens.easeEnter }
        }
        background: Item {
            width: track.width
            height: track.height
            CuScaleTrack {
                id: scaleRow
                x: 0
                y: Tokens.sp4
                width: track.width
                ground: control.ground
                value: (track.shownValue - control.from) / control.span
                markValue: control.changed ? (control.resetValue - control.from) / control.span : -1
                tickColor: !control.enabled ? Tokens.text4 : (control.dragging ? Tokens.white : Tokens.text1)
            }
        }
        handle: Item { width: 0; height: 0 }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
    }
    Item {
        id: unit
        anchors.fill: parent
    }
    CuFocusRing {
        target: unit
        shown: control.ringShown
        targetRadius: 0
    }
}

import QtQuick

Item {
    id: mark
    objectName: "modeMark"
    property string mode: "standard"
    property bool chosen: false
    property bool animated: false
    property color color: Tokens.text3
    property color restColor: Tokens.text3
    readonly property bool bolt: mode === "fast"
    property real drawn: 1
    property real ink: 1
    property real s0: 0
    property real s1: 0
    property real s2: 0

    implicitWidth: Tokens.icon
    implicitHeight: Tokens.icon
    width: implicitWidth
    height: implicitHeight
    Accessible.ignored: true

    function mix(a, b, t) { return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, a.a + (b.a - a.a) * t) }
    function play() {
        settleAnim.stop(); strikeAnim.stop(); quietAnim.stop()
        if (Tokens.reduceMotion) { quietAnim.restart(); return }
        if (bolt) strikeAnim.restart()
        else settleAnim.restart()
    }
    function finish() {
        settleAnim.stop(); strikeAnim.stop(); quietAnim.stop()
        drawn = 1; ink = 1; s0 = 0; s1 = 0; s2 = 0; icon.opacity = 1
    }
    onChosenChanged: { if (chosen && animated && visible) play(); else if (!chosen) finish() }
    onModeChanged: finish()

    CuIcon {
        id: icon
        iconName: Tokens.modeGlyph(mark.mode)
        color: mark.ink >= 1 ? mark.color : mark.mix(mark.restColor, mark.color, mark.ink)
        drawn: mark.drawn
        shiftUnits: mark.bolt ? [] : [mark.s0, mark.s1, mark.s1, mark.s2, mark.s2]
    }

    ParallelAnimation {
        id: settleAnim
        PropertyAction { target: mark; property: "s0"; value: 2 }
        PropertyAction { target: mark; property: "s1"; value: 2 }
        PropertyAction { target: mark; property: "s2"; value: 2 }
        NumberAnimation { target: mark; property: "s0"; to: 0; duration: 160; easing.type: Easing.BezierSpline; easing.bezierCurve: Tokens.easeEnter }
        SequentialAnimation {
            PauseAnimation { duration: 60 }
            NumberAnimation { target: mark; property: "s1"; to: 0; duration: 160; easing.type: Easing.BezierSpline; easing.bezierCurve: Tokens.easeEnter }
        }
        SequentialAnimation {
            PauseAnimation { duration: 120 }
            NumberAnimation { target: mark; property: "s2"; to: 0; duration: 160; easing.type: Easing.BezierSpline; easing.bezierCurve: Tokens.easeEnter }
        }
    }
    SequentialAnimation {
        id: strikeAnim
        PropertyAction { target: mark; property: "ink"; value: 0 }
        NumberAnimation { target: mark; property: "drawn"; from: 0; to: 1; duration: 200; easing.type: Easing.Linear }
        NumberAnimation { target: mark; property: "ink"; from: 0; to: 1; duration: 100; easing.type: Easing.Linear }
    }
    NumberAnimation { id: quietAnim; target: icon; property: "opacity"; from: 0.6; to: 1; duration: 120 }
}

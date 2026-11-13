import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.Control {
    id: stops
    property var names: []
    property int currentIndex: -1
    property bool custom: false
    property bool narrow: false
    property var limited: []
    property string limitTip: ""
    property string ground: "ink"
    readonly property int count: names ? names.length : 0
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property real columnWidth: width / Math.max(1, count)
    readonly property real tickHeight: Tokens.tickLong
    function position(i) { return (i + 0.5) / Math.max(1, count) }
    function isLimited(i) { return (limited || []).indexOf(i) >= 0 }
    readonly property real tickX: currentIndex >= 0 ? track.xOf(position(currentIndex)) : -1
    signal activated(int index)

    FontMetrics { id: tracked; font: Tokens.fontFor("meta") }
    FontMetrics {
        id: untracked
        font.family: tracked.font.family
        font.pixelSize: tracked.font.pixelSize
        font.weight: tracked.font.weight
        font.hintingPreference: Tokens.hinting
        font.letterSpacing: 0
    }
    function gapWith(fm) {
        var g = 1e6
        for (var i = 0; i + 1 < count; ++i)
            g = Math.min(g, columnWidth - fm.advanceWidth(names[i]) / 2 - fm.advanceWidth(names[i + 1]) / 2)
        return g
    }
    readonly property real tracking: gapWith(tracked) < Tokens.sp4 ? 0 : Tokens.type.meta.track
    readonly property real smallestGap: tracking === 0 ? gapWith(untracked) : gapWith(tracked)

    implicitWidth: Tokens.legContentMin
    implicitHeight: Tokens.hLook
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.role: Accessible.Grouping
    Accessible.name: "Look"

    function stepFrom(i, dir) {
        for (var n = 0; n < count; ++n) {
            i += dir
            if (i < 0 || i >= count) return -1
            if (!isLimited(i)) return i
        }
        return -1
    }
    Keys.onPressed: (event) => {
        if (stops.count === 0) return
        var i = -1
        var cur = stops.currentIndex
        if (event.key === Qt.Key_Right || event.key === Qt.Key_Up) i = stops.stepFrom(cur < 0 ? -1 : cur, 1)
        else if (event.key === Qt.Key_Left || event.key === Qt.Key_Down) i = stops.stepFrom(cur < 0 ? stops.count : cur, -1)
        else if (event.key === Qt.Key_Home) i = stops.stepFrom(-1, 1)
        else if (event.key === Qt.Key_End) i = stops.stepFrom(stops.count, -1)
        else return
        event.accepted = true
        if (i >= 0 && i !== cur) stops.activated(i)
    }

    CuScaleTrack {
        id: track
        objectName: "lookTrack"
        x: 0
        y: 0
        width: stops.width
        ground: stops.ground
        stops: {
            var out = []
            for (var i = 0; i < stops.count; ++i) if (!stops.isLimited(i)) out.push(stops.position(i))
            return out
        }
        value: stops.currentIndex >= 0 ? stops.position(stops.currentIndex) : 0
        tickShown: stops.currentIndex >= 0
        tickColor: !stops.enabled ? Tokens.text4 : (stops.custom ? Tokens.text2 : Tokens.text1)
        Behavior on value {
            NumberAnimation { duration: Tokens.durChosen; easing.type: Easing.BezierSpline; easing.bezierCurve: Tokens.easeEnter }
        }
    }
    CuScaleTrack {
        objectName: "lookTrackLimited"
        visible: (stops.limited || []).length > 0
        x: 0
        y: 0
        width: stops.width
        ground: stops.ground
        lineColor: "transparent"
        stopColor: Tokens.text4
        tickShown: false
        stops: {
            var out = []
            for (var i = 0; i < stops.count; ++i) if (stops.isLimited(i)) out.push(stops.position(i))
            return out
        }
    }

    Repeater {
        model: stops.count
        Item {
            id: stop
            required property int index
            readonly property bool chosen: index === stops.currentIndex
            readonly property bool limitedStop: stops.isLimited(index)
            readonly property real colX: Tokens.snap(index * stops.columnWidth, stops.dpr)
            readonly property real colEnd: index + 1 >= stops.count ? stops.width : Tokens.snap((index + 1) * stops.columnWidth, stops.dpr)
            objectName: "stop-" + stops.names[index]
            x: colX
            y: 0
            width: colEnd - colX
            height: Tokens.hLook
            Accessible.role: Accessible.RadioButton
            Accessible.name: stops.names[index]
            Accessible.checkable: true
            Accessible.checked: chosen
            Accessible.description: limitedStop ? stops.limitTip : ""
            Accessible.onPressAction: { if (!stop.limitedStop) stops.activated(stop.index) }
            CuText {
                id: nameText
                objectName: "lookName"
                x: Tokens.snap(track.xOf(stops.position(stop.index)) - stop.colX - implicitWidth / 2, stops.dpr)
                y: Tokens.hScaleRow
                text: stops.names[stop.index]
                role: "meta"
                font.letterSpacing: stops.tracking
                color: !stops.enabled || stop.limitedStop ? Tokens.text4
                       : (stop.chosen || stopHover.hovered) ? Tokens.text1 : Tokens.text2
            }
            HoverHandler {
                id: stopHover
                enabled: !stop.limitedStop
                cursorShape: Qt.PointingHandCursor
            }
            HoverHandler { id: limitHover; enabled: stop.limitedStop }
            MouseArea {
                anchors.fill: parent
                enabled: !stop.limitedStop
                onClicked: {
                    stops.forceActiveFocus(Qt.MouseFocusReason)
                    if (!stop.chosen || stops.custom) stops.activated(stop.index)
                }
            }
            CuHoverTip {
                shown: (limitHover.hovered && stop.limitedStop) || (stopHover.hovered && stop.chosen && stops.custom)
                text: stop.limitedStop ? stops.limitTip : ("Back to " + stops.names[stop.index] + "'s values")
            }
        }
    }
    CuFocusRing {
        target: stops
        shown: stops.visualFocus
        targetRadius: 0
    }
}

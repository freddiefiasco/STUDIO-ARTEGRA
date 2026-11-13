import QtQuick
import QtQuick.Window

Item {
    id: track
    property var stops: []
    property real value: 0
    property bool tickShown: true
    property color tickColor: Tokens.text1
    property real markValue: -1
    property string ground: "ink"
    property color lineColor: Tokens.trackOn(ground)
    property color stopColor: Tokens.text3
    property color markColor: Tokens.text3
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int wDev: Math.max(1, Math.round(width * dpr))
    readonly property int hDev: Math.round(Tokens.hScaleRow * dpr)
    readonly property int midDev: Math.round(Tokens.hScaleRow / 2 * dpr)
    readonly property int barDev: Tokens.devPx("bar", dpr)
    readonly property int tickDev: Tokens.devPx("tick", dpr)
    readonly property int lineDev: Tokens.devPx("line", dpr)
    function colOf(p) { return Math.round(Math.max(0, Math.min(1, p)) * (wDev - 1)) }
    function leftOf(p, w) { return Math.max(0, Math.min(wDev - w, colOf(p) - Math.floor((w - 1) / 2))) }
    function xOf(p) { return (colOf(p) + 0.5) / dpr }
    function topOf(len) { var l = Math.round(len * dpr); return midDev - Math.floor(l / 2) }

    implicitWidth: Tokens.legContentMin
    implicitHeight: Tokens.hScaleRow
    objectName: "scaleTrack"
    Accessible.ignored: true

    Item {
        scale: 1 / track.dpr
        transformOrigin: Item.TopLeft
        width: track.wDev
        height: track.hDev
        Rectangle {
            objectName: "scaleLine"
            x: 0
            y: track.midDev - Math.floor(track.barDev / 2)
            width: track.wDev
            height: track.barDev
            color: track.lineColor
            antialiasing: false
        }
        Repeater {
            model: track.stops ? track.stops.length : 0
            Rectangle {
                required property int index
                objectName: "scaleStop"
                x: track.leftOf(track.stops[index], track.lineDev)
                y: track.topOf(Tokens.stopShort)
                width: track.lineDev
                height: Math.round(Tokens.stopShort * track.dpr)
                color: track.stopColor
                antialiasing: false
            }
        }
        Rectangle {
            objectName: "scaleLookMark"
            visible: track.markValue >= 0
            x: track.leftOf(Math.max(0, track.markValue), track.lineDev)
            y: track.topOf(Tokens.lookMark)
            width: track.lineDev
            height: Math.round(Tokens.lookMark * track.dpr)
            color: track.markColor
            antialiasing: false
        }
        Rectangle {
            objectName: "scaleTick"
            visible: track.tickShown
            x: track.leftOf(track.value, track.tickDev)
            y: track.topOf(Tokens.tickLong)
            width: track.tickDev
            height: Math.round(Tokens.tickLong * track.dpr)
            color: track.tickColor
            antialiasing: false
        }
    }
}

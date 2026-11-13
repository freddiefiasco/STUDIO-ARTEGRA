import QtQuick
import QtQuick.Window

Item {
    id: bar
    property real value: 0
    property var segments: [1]
    property string ground: "ink"
    property color doneColor: Tokens.text1
    property color restColor: Tokens.trackOn(ground)
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int thickDev: Tokens.devPx("bar", dpr)
    readonly property int gapDev: Math.round(Tokens.sp4 * dpr)
    readonly property int wDev: Math.max(0, Math.round(width * dpr))
    property real shown: 0
    onValueChanged: {
        var v = Math.max(0, Math.min(1, value))
        if (v < shown) { anim.stop(); shown = v } else { anim.to = v; anim.restart() }
    }
    Component.onCompleted: shown = Math.max(0, Math.min(1, value))
    NumberAnimation { id: anim; target: bar; property: "shown"; duration: Tokens.durFill; easing.type: Easing.Linear }

    function partDone(p) { var span = p.to - p.from; return span > 0 ? Math.max(0, Math.min(1, (shown - p.from) / span)) : 0 }
    readonly property var parts: {
        var segs = segments && segments.length ? segments : [1]
        var total = 0, i
        for (i = 0; i < segs.length; ++i) total += Math.max(0, segs[i])
        if (total <= 0) total = 1
        var room = Math.max(0, wDev - gapDev * (segs.length - 1))
        var out = [], x = 0, acc = 0
        for (i = 0; i < segs.length; ++i) {
            acc += Math.max(0, segs[i])
            var end = i === segs.length - 1 ? room : Math.round(room * acc / total)
            var start = out.length ? out[out.length - 1].end : 0
            out.push({ x: x, w: end - start, end: end, from: (acc - Math.max(0, segs[i])) / total, to: acc / total })
            x += (end - start) + gapDev
        }
        return out
    }

    implicitWidth: Tokens.legContentMin
    implicitHeight: Tokens.px(thickDev, dpr)
    height: implicitHeight
    objectName: "progressBar"
    Accessible.role: Accessible.ProgressBar
    Accessible.name: Math.round(value * 100) + "%"

    Item {
        scale: 1 / bar.dpr
        transformOrigin: Item.TopLeft
        Repeater {
            model: bar.parts.length
            Item {
                required property int index
                readonly property var p: bar.parts[index]
                readonly property real local: bar.partDone(p)
                x: p.x
                width: p.w
                height: bar.thickDev
                Rectangle {
                    anchors.fill: parent
                    color: bar.restColor
                    antialiasing: false
                }
                Rectangle {
                    objectName: "progressDone"
                    width: Math.round(parent.width * parent.local)
                    height: parent.height
                    color: bar.doneColor
                    antialiasing: false
                }
            }
        }
    }
}

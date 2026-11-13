import QtQuick

Item {
    id: root
    property string iconName: ""
    property int iconSize: Tokens.icon
    property color color: Tokens.text2
    readonly property string resolvedName: Tokens.glyphName(iconName)
    readonly property bool isWindowGlyph: resolvedName === "windowMin" || resolvedName === "windowMax" || resolvedName === "windowClose"
    readonly property bool known: Tokens.isGlyph(resolvedName) || isWindowGlyph
    readonly property bool retired: iconName !== "" && !known && retiredNames.indexOf(iconName) >= 0
    readonly property string kind: isWindowGlyph ? "window" : (Tokens.glyphKinds[resolvedName] || "")

    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int strokeDev: Tokens.strokePx(dpr)
    readonly property int boxDev: Math.round(iconSize * dpr)
    readonly property int grid: isWindowGlyph ? 10 : 16

    implicitWidth: iconSize
    implicitHeight: iconSize
    width: iconSize
    height: iconSize
    Accessible.ignored: true

    readonly property var retiredNames: ["close", "check", "image", "image_file", "retry", "tryAgain", "try_again", "reset", "stop",
        "pause", "queued", "queue", "slash", "saving", "error", "danger", "warning", "info", "copy", "clipboard", "show_file",
        "showFile", "reveal_in_explorer", "log", "console", "help", "compare", "before_after", "fit", "zoom_in", "zoomIn",
        "zoom_out", "zoomOut", "upscale", "clear_done", "external", "working", "loading"]

    function dev(u) {
        var k = boxDev / grid
        var h = (strokeDev % 2) ? 0.5 : 0
        var v = Math.floor(u * k - h + 0.5 - 1e-6) + h
        return Math.max(strokeDev / 2, Math.min(boxDev - strokeDev / 2, v))
    }
    readonly property var strokes: ({
        "add": [[7.5, 3.5, 7.5, 11.5], [3.5, 7.5, 11.5, 7.5]],
        "folder": [[2.5, 4.5, 6.5, 4.5, 7.5, 5.5, 13.5, 5.5, 13.5, 12.5, 2.5, 12.5, "Z"]],
        "addFolder": [[2.5, 4.5, 6.5, 4.5, 7.5, 5.5, 13.5, 5.5, 13.5, 12.5, 2.5, 12.5, "Z"], [7.5, 6.5, 7.5, 10.5], [5.5, 8.5, 9.5, 8.5]],
        "grid": [[2.5, 2.5, 6.5, 2.5, 6.5, 6.5, 2.5, 6.5, "Z"], [9.5, 2.5, 13.5, 2.5, 13.5, 6.5, 9.5, 6.5, "Z"],
                 [2.5, 9.5, 6.5, 9.5, 6.5, 13.5, 2.5, 13.5, "Z"], [9.5, 9.5, 13.5, 9.5, 13.5, 13.5, 9.5, 13.5, "Z"]],
        "panels": [[0.5, 2.5, 15.5, 2.5, 15.5, 13.5, 0.5, 13.5, "Z"]],
        "panelsOff": [[0.5, 2.5, 15.5, 2.5, 15.5, 13.5, 0.5, 13.5, "Z"]],
        "chevronRight": [[6.5, 4.5, 9.5, 7.5, 6.5, 10.5]],
        "chevronLeft": [[9.5, 4.5, 6.5, 7.5, 9.5, 10.5]],
        "chevronDown": [[4.5, 6.5, 7.5, 9.5, 10.5, 6.5]],
        "chevronUp": [[4.5, 9.5, 7.5, 6.5, 10.5, 9.5]],
        "windowMin": [[0.5, 5.5, 9.5, 5.5]],
        "windowMax": [[0.5, 0.5, 9.5, 0.5, 9.5, 9.5, 0.5, 9.5, "Z"]],
        "windowClose": [[0.5, 0.5, 9.5, 9.5], [9.5, 0.5, 0.5, 9.5]]
    })
    readonly property var deviceRects: {
        var out = []
        if (!known) return out
        var list = strokes[resolvedName] || []
        var s = strokeDev, k = boxDev / grid
        for (var i = 0; i < list.length; ++i) {
            var p = list[i]
            var closed = p[p.length - 1] === "Z"
            var units = [], j
            for (j = 0; j + 1 < p.length; j += 2) units.push([p[j], p[j + 1]])
            if (closed) units.push(units[0])
            var pts = [[dev(units[0][0]), dev(units[0][1])]]
            for (j = 1; j < units.length; ++j) {
                var du = units[j][0] - units[j - 1][0], dv = units[j][1] - units[j - 1][1]
                var prev = pts[j - 1]
                if (closed && j === units.length - 1) { pts.push(pts[0]); continue }
                if (du === 0 || dv === 0)
                    pts.push([du === 0 ? prev[0] : dev(units[j][0]), dv === 0 ? prev[1] : dev(units[j][1])])
                else {
                    var n = Math.max(1, Math.round(Math.abs(du) * k))
                    pts.push([prev[0] + (du > 0 ? n : -n), prev[1] + (dv > 0 ? n : -n)])
                }
            }
            for (j = 1; j < pts.length; ++j) {
                var a = pts[j - 1], b = pts[j]
                if (a[0] === b[0] || a[1] === b[1]) {
                    var x0 = Math.min(a[0], b[0]) - s / 2, y0 = Math.min(a[1], b[1]) - s / 2
                    out.push([x0, y0, Math.abs(b[0] - a[0]) + s, Math.abs(b[1] - a[1]) + s])
                } else {
                    var steps = Math.abs(b[0] - a[0]), sx = b[0] > a[0] ? 1 : -1, sy = b[1] > a[1] ? 1 : -1
                    for (var t = 0; t <= steps; ++t) out.push([a[0] + t * sx - s / 2, a[1] + t * sy - s / 2, s, s])
                }
            }
        }
        if (resolvedName === "panels" || resolvedName === "panelsOff") {
            var oL = dev(0.5) + s / 2, oR = dev(15.5) - s / 2, oT = dev(2.5) + s / 2, oB = dev(13.5) - s / 2
            var lL = dev(4.5) - s / 2, lR = dev(11.5) - s / 2
            if (resolvedName === "panels") {
                out.push([oL, oT, lL - oL, oB - oT])
                out.push([lR + s, oT, oR - lR - s, oB - oT])
            } else {
                out.push([lL, oT, s, oB - oT])
                out.push([lR, oT, s, oB - oT])
            }
        }
        return out
    }

    function checkName() {
        var n = Tokens.glyphName(iconName)
        var ok = Tokens.isGlyph(n) || n === "windowMin" || n === "windowMax" || n === "windowClose"
        if (iconName !== "" && !ok && retiredNames.indexOf(iconName) < 0)
            console.warn("CuIcon: unknown icon name \"" + iconName + "\"")
    }
    onIconNameChanged: checkName()
    Component.onCompleted: checkName()

    Item {
        scale: 1 / root.dpr
        transformOrigin: Item.TopLeft
        width: root.boxDev
        height: root.boxDev
        Repeater {
            model: root.deviceRects.length
            Rectangle {
                required property int index
                readonly property var r: root.deviceRects[index] || [0, 0, 0, 0]
                x: r[0]
                y: r[1]
                width: r[2]
                height: r[3]
                color: root.color
                antialiasing: false
            }
        }
    }
}

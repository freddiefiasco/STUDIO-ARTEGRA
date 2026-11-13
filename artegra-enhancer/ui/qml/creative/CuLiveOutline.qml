import QtQuick

Item {
    id: outline
    property var rects: []
    property real dpr: 1
    readonly property int line: Tokens.devPx("line", dpr)
    readonly property int armDev: Math.round(Tokens.sp8 * dpr)
    objectName: "liveOutline"

    Repeater {
        model: outline.rects ? outline.rects.length : 0
        Item {
            id: bucket
            required property int index
            readonly property var r: outline.rects[index] || ({ x: 0, y: 0, w: 0, h: 0 })
            readonly property int x0: Math.max(0, Math.round(r.x * outline.width))
            readonly property int y0: Math.max(0, Math.round(r.y * outline.height))
            readonly property int x1: Math.min(Math.round(outline.width), Math.round((r.x + r.w) * outline.width))
            readonly property int y1: Math.min(Math.round(outline.height), Math.round((r.y + r.h) * outline.height))
            readonly property bool usable: x1 - x0 >= 4 && y1 - y0 >= 4
            readonly property int arm: Math.max(2, Math.min(outline.armDev, Math.floor(Math.min(x1 - x0, y1 - y0) / 3)))
            readonly property bool onLeft: x0 <= 1
            readonly property bool onTop: y0 <= 1
            readonly property bool onRight: x1 >= Math.round(outline.width) - 1
            readonly property bool onBottom: y1 >= Math.round(outline.height) - 1
            objectName: "liveBucket"
            visible: usable

            Repeater {
                model: 4
                Item {
                    id: corner
                    required property int index
                    readonly property bool isRight: index === 1 || index === 2
                    readonly property bool isBottom: index === 2 || index === 3
                    readonly property bool shown: !(isRight ? bucket.onRight : bucket.onLeft) && !(isBottom ? bucket.onBottom : bucket.onTop)
                    readonly property int w: outline.line
                    readonly property int cx: isRight ? bucket.x1 - w : bucket.x0
                    readonly property int cy: isBottom ? bucket.y1 - w : bucket.y0
                    readonly property int hx: isRight ? bucket.x1 - bucket.arm : bucket.x0
                    readonly property int vy: isBottom ? bucket.y1 - bucket.arm : bucket.y0
                    readonly property int haloY: isBottom ? cy + w : cy - w
                    readonly property int haloX: isRight ? cx + w : cx - w
                    objectName: "liveBucketCorner"
                    visible: shown
                    Rectangle { x: corner.isRight ? corner.hx : corner.haloX; y: corner.haloY; width: bucket.arm + corner.w; height: corner.w
                                color: Tokens.liveOutlineHalo; antialiasing: false }
                    Rectangle { x: corner.haloX; y: corner.vy; width: corner.w; height: bucket.arm
                                color: Tokens.liveOutlineHalo; antialiasing: false }
                    Rectangle { x: corner.hx; y: corner.cy; width: bucket.arm; height: corner.w; color: Tokens.liveOutline; antialiasing: false }
                    Rectangle { x: corner.cx; y: corner.vy; width: corner.w; height: bucket.arm; color: Tokens.liveOutline; antialiasing: false }
                }
            }
        }
    }
}

import QtQuick

WheelHandler {
    id: wheel
    property int step: 48
    readonly property Flickable view: parent instanceof Flickable ? parent
                                      : (parent && parent.parent instanceof Flickable ? parent.parent : null)
    readonly property real minY: view ? view.originY - view.topMargin : 0
    readonly property real maxY: view ? Math.max(minY, view.originY + view.contentHeight + view.bottomMargin - view.height) : 0
    property real carried: 0
    property real carriedAt: NaN

    target: null
    orientation: Qt.Vertical
    enabled: view !== null && maxY > minY + 0.5

    function deltaOf(event) {
        return event.pixelDelta.y !== 0 ? event.pixelDelta.y : event.angleDelta.y / 120 * step
    }
    function exactY(event) {
        var carry = Math.abs(view.contentY - carriedAt) < 0.01 ? carried : 0
        return Math.max(minY, Math.min(maxY, view.contentY + carry - deltaOf(event)))
    }
    function targetY(event) { return Math.round(exactY(event)) }
    onWheel: (event) => {
        if (!view) return
        var exact = exactY(event)
        var y = Math.round(exact)
        if (y !== view.contentY) view.contentY = y
        carried = exact - y
        carriedAt = view.contentY
    }
}

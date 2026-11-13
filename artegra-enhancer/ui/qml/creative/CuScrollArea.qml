import QtQuick
import QtQuick.Templates as T

Flickable {
    id: area
    property color surface: Tokens.ink
    property string ground: Qt.colorEqual(surface, Tokens.ink) ? "ink" : "stage"
    property int fadeInset: 0
    property bool edgesShown: true
    readonly property bool topEdgeShown: edgesShown && overflows && contentY > minY + 0.5
    readonly property bool bottomEdgeShown: edgesShown && overflows && contentY < maxY - 0.5
    property bool followFocus: true
    readonly property alias bar: scrollBar
    readonly property real minY: originY - topMargin
    readonly property real maxY: Math.max(minY, originY + contentHeight + bottomMargin - height)
    readonly property bool overflows: maxY > minY + 0.5

    clip: true
    interactive: false
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick
    contentWidth: width
    readonly property Item column: contentItem.children.length > 0 ? contentItem.children[0] : null
    contentHeight: column ? column.y + column.height : 0

    property bool regionHovered: false
    HoverHandler { id: areaHover }
    T.ScrollBar.vertical: CuScrollBar {
        id: scrollBar
        surface: area.surface
        regionHovered: areaHover.hovered || area.regionHovered
    }
    CuWheelScroll { }

    function clampY(y) { return Math.max(minY, Math.min(maxY, y)) }
    function revealY(top, bottom) { return Tokens.revealY(area, top, bottom) }
    function spanOf(item) {
        var p = item.mapToItem(area.contentItem, 0, 0)
        return { top: p.y, bottom: p.y + item.height }
    }
    function reveal(item, alsoItem) {
        if (!item) return contentY
        var s = spanOf(item)
        if (alsoItem) {
            var h = spanOf(alsoItem)
            var top = Math.min(s.top, h.top), bottom = Math.max(s.bottom, h.bottom)
            if (bottom - top <= height - 2 * Tokens.revealMargin) s = { top: top, bottom: bottom }
        }
        var y = revealY(s.top, s.bottom)
        if (y !== contentY) contentY = y
        return y
    }

    function keyboardFocused(item) {
        for (var p = item; p && p !== area; p = p.parent) {
            if (p.visualFocus !== undefined) return p.visualFocus === true
            if (p.focusReason !== undefined) return p.focusReason === Qt.TabFocusReason || p.focusReason === Qt.BacktabFocusReason
        }
        return false
    }
    function inside(item) {
        for (var p = item; p; p = p.parent) if (p === area.contentItem) return true
        return false
    }
    function headingFor(item) {
        for (var p = item; p && p !== area.contentItem; p = p.parent)
            if (p.sectionHeading !== undefined && p.sectionHeading) return p.sectionHeading
        return null
    }
    Timer {
        id: focusLater
        interval: 0
        onTriggered: {
            var w = area.Window.window
            var it = w ? w.activeFocusItem : null
            if (!it || !area.inside(it) || !area.keyboardFocused(it)) return
            var target = it
            for (var p = it; p && p !== area.contentItem; p = p.parent) if (p.visualFocus !== undefined) { target = p; break }
            area.reveal(target, area.headingFor(target))
        }
    }
    Connections {
        target: area.followFocus ? area.Window.window : null
        function onActiveFocusItemChanged() { focusLater.restart() }
    }
    Keys.onPressed: (event) => {
        if (!area.overflows) return
        var page = Math.max(48, area.height - 48)
        if (event.key === Qt.Key_PageDown) { area.contentY = Math.round(area.clampY(area.contentY + page)); event.accepted = true }
        else if (event.key === Qt.Key_PageUp) { area.contentY = Math.round(area.clampY(area.contentY - page)); event.accepted = true }
    }

    readonly property Item topFade: CuSettingsRule {
        parent: area
        objectName: "scrollEdgeTop"
        visible: area.topEdgeShown
        x: area.fadeInset
        y: 0
        z: 20
        width: area.width - 2 * area.fadeInset
        ground: area.ground
    }
    readonly property Item bottomFade: CuSettingsRule {
        parent: area
        objectName: "scrollEdgeBottom"
        visible: area.bottomEdgeShown
        x: area.fadeInset
        y: area.height - Tokens.px(Tokens.devPx("line", d), d)
        z: 20
        width: area.width - 2 * area.fadeInset
        ground: area.ground
    }
}

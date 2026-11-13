import QtQuick

Item {
    id: nav
    objectName: "viewerNavigator"
    property var viewer: null
    property bool floating: false
    property real inset: floating ? Tokens.sp8 : Tokens.legInset
    property real maxBoxH: 0
    readonly property bool shown: viewer !== null && viewer.navigatorShown
    readonly property real dpr: viewer && viewer.dpr > 0 ? viewer.dpr : 1
    readonly property real boxW: Math.max(0, width - 2 * inset)
    readonly property real boxH: Math.max(0, Tokens.snap(maxBoxH > 0 ? Math.min(boxW / 1.6, maxBoxH) : boxW / 1.6, dpr))
    readonly property real aspect: viewer && viewer.pw > 0 && viewer.ph > 0 ? viewer.pw / viewer.ph : 1.6
    readonly property bool widthLimited: boxH > 0 && aspect >= boxW / boxH
    readonly property real picW: Tokens.snap(widthLimited ? boxW : boxH * aspect, dpr)
    readonly property real picH: Tokens.snap(widthLimited ? boxW / aspect : boxH, dpr)
    implicitWidth: Tokens.legWidth(1280)
    implicitHeight: boxH + (floating ? 2 * inset : inset)

    CuPlate {
        anchors.fill: parent
        visible: nav.floating
    }
    Item {
        id: box
        objectName: "navigatorBox"
        x: Tokens.snap(nav.inset + (nav.boxW - nav.picW) / 2, nav.dpr)
        y: Tokens.snap((nav.floating ? nav.inset : 0) + (nav.boxH - nav.picH) / 2, nav.dpr)
        width: nav.picW
        height: nav.picH
        readonly property rect view: nav.viewer ? nav.viewer.viewFraction : Qt.rect(0, 0, 1, 1)
        Item {
            id: dev
            scale: 1 / nav.dpr
            transformOrigin: Item.TopLeft
            width: Math.round(box.width * nav.dpr)
            height: Math.round(box.height * nav.dpr)
            Image {
                objectName: "navigatorChecker"
                anchors.fill: parent
                visible: nav.shown && nav.viewer !== null && nav.viewer.hasAlpha === true
                source: Tokens.checkerTile
                sourceSize: Qt.size(Math.round(2 * Tokens.checkerSize * nav.dpr), Math.round(2 * Tokens.checkerSize * nav.dpr))
                fillMode: Image.Tile
                smooth: false
                mipmap: false
            }
            Image {
                objectName: "navigatorPicture"
                anchors.fill: parent
                asynchronous: true
                cache: true
                retainWhileLoading: true
                smooth: true
                mipmap: false
                sourceSize: Qt.size(2 * dev.width, 2 * dev.height)
                source: nav.shown && nav.viewer ? nav.viewer.navigatorUrl : ""
            }
            readonly property int line: Tokens.devPx("line", nav.dpr)
            readonly property real vw: box.view.width * dev.width
            readonly property real vh: box.view.height * dev.height
            readonly property real grow: vw > 0 && vw < 10 * nav.dpr ? 10 * nav.dpr / vw : 1
            Rectangle {
                objectName: "navigatorView"
                width: Math.round(dev.vw * dev.grow) + 2 * dev.line
                height: Math.round(dev.vh * dev.grow) + 2 * dev.line
                x: Math.round((box.view.x + box.view.width / 2) * dev.width - width / 2)
                y: Math.round((box.view.y + box.view.height / 2) * dev.height - height / 2)
                color: "transparent"
                border.width: dev.line
                border.color: Tokens.liveOutlineHalo
                antialiasing: false
                Rectangle {
                    x: dev.line
                    y: dev.line
                    width: parent.width - 2 * dev.line
                    height: parent.height - 2 * dev.line
                    color: "transparent"
                    border.width: dev.line
                    border.color: Tokens.text1
                    antialiasing: false
                }
            }
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            preventStealing: true
            function go(mx, my) {
                if (nav.viewer) nav.viewer.centreOn(Math.max(0, Math.min(1, mx / box.width)), Math.max(0, Math.min(1, my / box.height)))
            }
            onPressed: (mouse) => go(mouse.x, mouse.y)
            onPositionChanged: (mouse) => { if (pressed) go(mouse.x, mouse.y) }
        }
    }
    Accessible.role: Accessible.Graphic
    Accessible.name: "Navigator"
}

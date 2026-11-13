import QtQuick

Item {
    id: mini

    property url source: ""
    property real aspect: 0
    property bool hasAlpha: false
    property int maxWidth: Tokens.miniMaxWidth
    property int maxHeight: Tokens.miniHeight
    property bool hug: false
    property int horizontalAlignment: Qt.AlignRight
    property color surface: Tokens.panel
    readonly property int radius: Tokens.rMiniature

    property real loadedAspect: 0
    onSourceChanged: loadedAspect = 0
    readonly property real shownAspect: aspect > 0 ? aspect : (loadedAspect > 0 ? loadedAspect : 1.5)
    readonly property bool wide: shownAspect >= maxWidth / Math.max(1, maxHeight)
    readonly property int pictureWidth: wide ? maxWidth : Math.max(Tokens.miniMinSide, Math.min(maxWidth, Math.round(maxHeight * shownAspect)))
    readonly property int pictureHeight: wide ? Math.max(Tokens.miniMinSide, Math.min(maxHeight, Math.round(maxWidth / shownAspect))) : maxHeight
    readonly property bool loaded: picture.status === Image.Ready
    readonly property bool failed: picture.status === Image.Error
    readonly property int status: picture.status
    readonly property real devicePixelRatio: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property size decodeSize: Qt.size(Math.ceil(pictureWidth * devicePixelRatio), Math.ceil(pictureHeight * devicePixelRatio))

    implicitWidth: hug ? pictureWidth : maxWidth
    implicitHeight: hug ? pictureHeight : maxHeight
    Accessible.ignored: true

    Item {
        id: box
        width: mini.pictureWidth
        height: mini.pictureHeight
        x: mini.horizontalAlignment === Qt.AlignLeft ? 0
           : mini.horizontalAlignment === Qt.AlignHCenter ? Math.round((mini.width - width) / 2)
           : mini.width - width
        y: Math.round((mini.height - height) / 2)

        Rectangle {
            objectName: "miniaturePlaceholder"
            anchors.fill: parent
            visible: !mini.loaded
            radius: mini.radius
            color: Tokens.miniaturePlaceholder
        }
        Image {
            objectName: "miniatureChecker"
            anchors.fill: parent
            visible: mini.hasAlpha && mini.loaded
            source: mini.hasAlpha ? Tokens.checkerTile : ""
            fillMode: Image.Tile
            smooth: false
        }
        Image {
            id: picture
            objectName: "miniaturePicture"
            anchors.fill: parent
            source: mini.source
            asynchronous: true
            cache: true
            smooth: true
            mipmap: false
            fillMode: Image.PreserveAspectCrop
            sourceSize: mini.decodeSize
            visible: mini.loaded
            onStatusChanged: {
                if (status === Image.Ready && mini.aspect <= 0 && mini.loadedAspect <= 0 && implicitHeight > 0)
                    mini.loadedAspect = implicitWidth / implicitHeight
            }
        }
        Repeater {
            model: mini.loaded && mini.radius > 0 ? 4 : 0
            Item {
                required property int index
                readonly property bool atRight: index === 1 || index === 3
                readonly property bool atBottom: index >= 2
                width: mini.radius
                height: mini.radius
                x: atRight ? box.width - width : 0
                y: atBottom ? box.height - height : 0
                clip: true
                Rectangle {
                    x: parent.atRight ? -(box.width - mini.radius) - 1 : -1
                    y: parent.atBottom ? -(box.height - mini.radius) - 1 : -1
                    width: box.width + 2
                    height: box.height + 2
                    radius: mini.radius + 1
                    color: "transparent"
                    border.width: 1
                    border.color: mini.surface
                    antialiasing: true
                }
            }
        }
    }
}

import QtQuick
import QtQuick.Window

Item {
    id: ruler
    property real value: 0
    property var segments: [1, 1]
    property string tip: ""
    property string imageId: ""
    property string pass: ""
    property int step: 0
    property int total: 30
    property bool structureDone: false
    property bool detailDone: false
    property var labels: []
    readonly property string encoding: "progress graphic"
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    function doneCells(bar) { return 0 }
    function currentCell(bar) { return -1 }

    objectName: "viewerRuler"
    implicitWidth: Tokens.legContentMin
    implicitHeight: bar.height
    Accessible.role: Accessible.ProgressBar
    Accessible.name: tip

    CuProgressBar {
        id: bar
        objectName: "viewerProgressBar"
        width: ruler.width
        ground: "stage"
        value: ruler.value
        segments: ruler.segments
    }
    MouseArea {
        id: hit
        x: 0
        y: -Tokens.sp8
        width: ruler.width
        height: ruler.height + 2 * Tokens.sp8
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        cursorShape: Qt.ArrowCursor
    }
    CuHoverTip { shown: hit.containsMouse && ruler.tip !== ""; text: ruler.tip; placement: "below" }
}

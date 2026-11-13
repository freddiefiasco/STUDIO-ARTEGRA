import QtQuick
import "creative"

Rectangle {
    id: root
    objectName: "creativeUpscalerView"
    property var appBridge: null
    property bool panelsShown: true
    signal panelsToggleRequested()
    readonly property var tabItem: loader.status === Loader.Ready ? loader.item : null
    readonly property var runSlot: tabItem ? tabItem.runSlot : null
    readonly property var gpuLanes: tabItem ? tabItem.gpuLanes : []
    readonly property int servicePort: tabItem ? tabItem.servicePort : 0
    color: Tokens.opening
    function holdAppClose(proceed) { return tabItem ? tabItem.holdAppClose(proceed) : false }
    function load() {
        loader.setSource("creative/CreativeUpscalerTab.qml", { appBridge: root.appBridge,
                         hostLogFolder: root.appBridge ? root.appBridge.logFolder : "" })
    }
    Loader {
        id: loader
        objectName: "creativeTabLoader"
        anchors.fill: parent
        onLoaded: {
            item.panelsShown = Qt.binding(function() { return root.panelsShown })
            item.panelsToggleRequested.connect(root.panelsToggleRequested)
        }
    }
    Column {
        visible: loader.status === Loader.Error
        anchors.centerIn: parent
        spacing: 16
        CuText { text: "The image workspace could not load."; color: Tokens.text1; role: "label" }
        CuButton { text: "Try again"; onClicked: root.load() }
        CuButton { text: "Open logs"; onClicked: { if (root.appBridge) root.appBridge.openLogs() } }
    }
    Component.onCompleted: load()
}

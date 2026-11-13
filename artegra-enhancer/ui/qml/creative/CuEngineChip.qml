import QtQuick
import QtQuick.Window
import QtQuick.Templates as T
import "format.js" as F

Item {
    id: chip
    objectName: "engineChip"
    property var tab: null
    property var status: null
    property Item anchorItem: null
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int floatWidth: 320
    readonly property alias popupOpen: popup.opened
    readonly property alias popupItem: popup
    readonly property real popupHeight: popup.height
    readonly property string st: tab ? tab.engineState : "starting"
    readonly property string word: st === "problem" ? "Problem" : st === "working" ? "Working" : st === "ready" ? "Ready"
                                   : (tab && tab.reconnecting) ? "Reconnecting" : "Starting"
    width: 0
    height: 0

    function openAt(item) {
        anchorItem = item || null
        place()
        if (!popup.opened) popup.open()
    }
    function close() { popup.close() }
    function place() {
        var host = chip.parent
        if (!host) return
        var w = Math.min(floatWidth, Math.max(0, host.width - 2 * Tokens.sp8))
        var h = popup.implicitHeight
        var ax = host.width - Tokens.sp16, ay = Tokens.snap(host.height - Tokens.hFootSlot, dpr), ah = 0
        if (anchorItem && anchorItem.visible) {
            var p = anchorItem.mapToItem(host, 0, 0)
            ax = p.x + anchorItem.width
            ay = p.y
            ah = anchorItem.height
        }
        var x = Math.max(Tokens.sp8, Math.min(host.width - w - Tokens.sp8, ax - w))
        var above = ay - Tokens.sp8 - h
        var y = above >= Tokens.sp8 ? above : Math.min(host.height - h - Tokens.sp8, ay + ah + Tokens.sp8)
        popup.x = Tokens.snap(x, dpr) - chip.x
        popup.y = Tokens.snap(Math.max(Tokens.sp8, y), dpr) - chip.y
        popup.width = w
    }

    readonly property real hostW: chip.parent ? chip.parent.width : 0
    readonly property real hostH: chip.parent ? chip.parent.height : 0
    onHostWChanged: if (popup.opened) Qt.callLater(chip.place)
    onHostHChanged: if (popup.opened) Qt.callLater(chip.place)
    Connections {
        target: chip.anchorItem
        ignoreUnknownSignals: true
        function onXChanged() { if (popup.opened) Qt.callLater(chip.place) }
        function onYChanged() { if (popup.opened) Qt.callLater(chip.place) }
        function onWidthChanged() { if (popup.opened) Qt.callLater(chip.place) }
        function onVisibleChanged() { if (popup.opened) Qt.callLater(chip.place) }
    }
    readonly property bool problem: st === "problem"
    readonly property string actionWords: status ? status.engineAction : ""
    readonly property bool fromRecess: anchorItem !== null && anchorItem.objectName === "recessSecond"
    readonly property bool fromFoot: anchorItem !== null && anchorItem.objectName === "footDetails"
    readonly property string wordsShown: {
        var t = status ? String(status.detailsText || "") : ""
        if (fromFoot && problem) {
            var i = t.indexOf(". ")
            if (i > 0 && i + 2 < t.length) t = t.slice(i + 2)
        }
        return t.replace(/Try again/g, "Try again").replace(/Choose a folder/g, "Choose a folder")
    }

    T.Popup {
        id: popup
        objectName: "engineStatusPopup"
        implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding)
        padding: Tokens.sp16
        focus: true
        closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutside
        onImplicitHeightChanged: { if (opened) chip.place() }
        onOpened: { chip.place(); if (copyButton.visible) copyButton.forceActiveFocus() }
        onClosed: { if (chip.anchorItem && chip.anchorItem.visible) chip.anchorItem.forceActiveFocus(); chip.anchorItem = null }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Tokens.durFloatIn } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Tokens.durFloatOut } }
        background: CuPlate { }
        contentItem: Column {
            objectName: "engineDetails"
            spacing: Tokens.sp8
            Accessible.role: Accessible.Dialog
            Accessible.name: "Engine details"
            CuText {
                objectName: "engineDetailsText"
                width: parent.width
                visible: text !== "" && !chip.fromRecess
                text: chip.wordsShown
                role: "body"
                color: Tokens.text1
                wrapMode: Text.WordWrap
                maximumLineCount: 4
                elide: Text.ElideRight
            }
            Column {
                width: parent.width
                spacing: 0
                visible: chip.status !== null && chip.status.workerLines.length > 0
                Repeater {
                    model: chip.status ? chip.status.workerLines : []
                    CuText {
                        required property string modelData
                        objectName: "engineWorker"
                        width: popup.availableWidth
                        wrapMode: Text.WordWrap
                        text: modelData
                        role: "meta"
                        tabular: true
                        color: Tokens.text2
                    }
                }
            }
            Item { width: 1; height: Tokens.sp8 }
            Row {
                spacing: Tokens.sp8 + Tokens.textControlPad
                CuButton {
                    objectName: "engineRetry"
                    visible: chip.problem && chip.actionWords !== "" && !chip.fromRecess
                    variant: "tile"
                    ground: "float"
                    text: chip.actionWords
                    onClicked: {
                        popup.close()
                        if (chip.tab.problemKind === "output") chip.tab.openOutputDialog()
                        else chip.tab.retryEngine()
                    }
                }
                CuButton {
                    id: copyButton
                    objectName: "engineCopyDetails"
                    anchors.verticalCenter: parent.verticalCenter
                    variant: "text"
                    ground: "float"
                    text: "Copy details"
                    tooltip: "The engine's state, its version and where its logs are"
                    onClicked: { chip.tab.copyText(chip.tab.engineDetails()); popup.close() }
                }
                CuButton {
                    objectName: "engineOpenLogs"
                    anchors.verticalCenter: parent.verticalCenter
                    variant: "text"
                    ground: "float"
                    text: "Open log folder"
                    tooltip: chip.tab ? chip.tab.engineLogFolder : ""
                    onClicked: { chip.tab.openLogFolder(); popup.close() }
                }
            }
        }
    }
}

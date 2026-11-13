import QtQuick
import QtQuick.Window
import "creative"

Window {
    id: window
    objectName: "artegraEnhancerWindow"
    visible: true
    width: 1440
    height: 900
    minimumWidth: 1100
    minimumHeight: 720
    color: Tokens.ink
    title: view.runSlot ? view.runSlot.title + " � Artegra Enhancer" : "Artegra Enhancer"
    property bool panelsShown: true
    property bool settingsShown: !hostBridge.ready
    property bool closingAccepted: false
    readonly property bool tabLoaded: view.tabItem !== null
    readonly property bool tabConnected: view.tabItem ? view.tabItem.connected : false
    readonly property bool fastAvailable: view.tabItem ? view.tabItem.fastAvailable : false
    onClosing: (close) => {
        if (!closingAccepted && view.holdAppClose(function() { window.closingAccepted = true; window.close() }))
            close.accepted = false
    }
    Connections {
        target: hostBridge
        function onChanged() { if (hostBridge.ready) window.settingsShown = false }
    }
    Rectangle {
        id: header
        height: 56
        anchors { left: parent.left; right: parent.right; top: parent.top }
        color: Tokens.ink
        Row {
            anchors { left: parent.left; leftMargin: 24; verticalCenter: parent.verticalCenter }
            spacing: 24
            CuText { text: "ARTEGRA"; role: "label"; color: Tokens.text1; anchors.verticalCenter: parent.verticalCenter }
            CuText { text: "Enhancer"; role: "label"; color: Tokens.text2; anchors.verticalCenter: parent.verticalCenter }
            CuButton { text: window.panelsShown ? "Hide panels" : "Show panels"; onClicked: window.panelsShown = !window.panelsShown }
            CuButton { text: "Activity"; onClicked: { if (view.tabItem) view.tabItem.setActivityOpen(!view.tabItem.activityOpen) } }
            CuButton { text: "Shortcuts"; onClicked: { if (view.tabItem) view.tabItem.shortcuts.openAt("shortcuts") } }
            CuText { text: view.runSlot ? view.runSlot.text : "Creative Upscaler"; role: "label"; color: Tokens.text2; anchors.verticalCenter: parent.verticalCenter }
        }
        CuButton {
            anchors { right: parent.right; rightMargin: 24; verticalCenter: parent.verticalCenter }
            text: "Settings"
            onClicked: window.settingsShown = !window.settingsShown
        }
        Rectangle { anchors { bottom: parent.bottom; left: parent.left; right: parent.right } height: 2; color: Tokens.reveal }
    }
    CreativeUpscalerView {
        id: view
        anchors { top: header.bottom; bottom: status.top; left: parent.left; right: parent.right }
        appBridge: hostBridge
        panelsShown: window.panelsShown
        onPanelsToggleRequested: window.panelsShown = !window.panelsShown
    }
    Rectangle {
        id: status
        height: 28
        anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
        color: Tokens.ink
        CuText { anchors { left: parent.left; leftMargin: 24; verticalCenter: parent.verticalCenter } text: hostBridge.status; role: "small"; color: Tokens.text3 }
    }
    Rectangle {
        anchors { top: header.bottom; bottom: status.top; left: parent.left; right: parent.right }
        color: Tokens.ink
        visible: window.settingsShown || !hostBridge.ready
        MouseArea { anchors.fill: parent }
        Column {
            anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: parent.verticalCenter }
            width: 660
            spacing: 16
            CuText { text: hostBridge.demo ? "Demo settings" : "Set up Artegra Enhancer"; role: "dialog"; color: Tokens.text1 }
            CuText { width: parent.width; text: "Choose existing local folders. Model files remain in their original location. No models are downloaded."; wrapMode: Text.WordWrap; role: "label"; color: Tokens.text2 }
            CuText { width: parent.width; text: "The v5 engine is experimental. Runtime setup confirms installation; image quality still needs validation."; wrapMode: Text.WordWrap; role: "small"; color: Tokens.text3 }
            Repeater {
                model: [{ key: "models_dir", name: "Models folder", value: hostBridge.modelsDir },
                        { key: "runtime_dir", name: "Image-engine runtime folder", value: hostBridge.runtimeDir },
                        { key: "output_dir", name: "Output folder", value: hostBridge.outputDir }]
                delegate: Column {
                    required property var modelData
                    width: 660
                    spacing: 8
                    CuText { text: modelData.name; role: "label"; color: Tokens.text2 }
                    Row {
                        width: parent.width
                        spacing: 12
                        CuTextField {
                            width: 556
                            text: modelData.value
                            enabled: !hostBridge.ready && !hostBridge.busy && (!hostBridge.demo || modelData.key === "output_dir")
                            onCommitted: (text) => hostBridge.setFolder(modelData.key, text)
                            Accessible.name: modelData.name
                        }
                        CuButton {
                            text: "Browse…"
                            enabled: !hostBridge.ready && !hostBridge.busy && (!hostBridge.demo || modelData.key === "output_dir")
                            onClicked: hostBridge.chooseFolder(modelData.key)
                        }
                    }
                }
            }
            CuText { width: parent.width; text: hostBridge.status; wrapMode: Text.WordWrap; role: "label"; color: Tokens.text1 }
            Row {
                spacing: 12
                CuButton { text: hostBridge.busy ? "Starting…" : "Start engine"; enabled: !hostBridge.ready && !hostBridge.busy; onClicked: hostBridge.start() }
                CuButton { text: "Edit folders"; visible: hostBridge.ready; enabled: !view.tabItem || !view.tabItem.batch.active; onClicked: hostBridge.stop() }
                CuButton { text: "Back to images"; visible: hostBridge.ready; onClicked: window.settingsShown = false }
                CuButton { text: "Open logs"; onClicked: hostBridge.openLogs() }
            }
            CuText { width: parent.width; visible: hostBridge.ready; text: "Finish or cancel the current batch before changing folders."; role: "small"; color: Tokens.text3 }
        }
    }
}

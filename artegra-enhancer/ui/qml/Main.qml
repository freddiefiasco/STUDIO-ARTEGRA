import QtQuick
import QtQuick.Window
import "creative"

Window {
    id: window
    objectName: "artegraEnhancerWindow"
    visible: true
    width: Math.min(1440, Screen.desktopAvailableWidth)
    height: Math.min(900, Screen.desktopAvailableHeight)
    minimumWidth: Math.min(960, Screen.desktopAvailableWidth)
    minimumHeight: Math.min(540, Screen.desktopAvailableHeight)
    color: Tokens.ink
    title: view.runSlot ? view.runSlot.title + " · Artegra Enhancer" : "Artegra Enhancer"
    property bool panelsShown: true
    property bool settingsShown: !hostBridge.ready
    property bool modelSetupShown: false
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
            spacing: window.width < 1200 ? 12 : 24
            CuText { text: "ARTEGRA"; role: "label"; color: Tokens.text1; anchors.verticalCenter: parent.verticalCenter }
            CuText { text: "Enhancer"; role: "label"; color: Tokens.text2; anchors.verticalCenter: parent.verticalCenter }
            CuButton { text: window.panelsShown ? "Hide panels" : "Show panels"; onClicked: window.panelsShown = !window.panelsShown }
            CuButton { text: "Activity"; onClicked: { if (view.tabItem) view.tabItem.setActivityOpen(!view.tabItem.activityOpen) } }
            CuButton { text: "Shortcuts"; onClicked: { if (view.tabItem) view.tabItem.shortcuts.openAt("shortcuts") } }
            CuText { visible: window.width >= 1200; text: view.runSlot ? view.runSlot.text : "Creative Upscaler"; role: "label"; color: Tokens.text2; anchors.verticalCenter: parent.verticalCenter }
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
        CuText { anchors { left: parent.left; right: parent.right; margins: 24; verticalCenter: parent.verticalCenter } text: hostBridge.status; elide: Text.ElideRight; role: "small"; color: Tokens.text3 }
    }
    Rectangle {
        anchors { top: header.bottom; bottom: status.top; left: parent.left; right: parent.right }
        color: Tokens.ink
        visible: window.settingsShown || !hostBridge.ready
        MouseArea { anchors.fill: parent }
        Flickable {
            objectName: "setupScroll"
            anchors.fill: parent
            clip: true
            contentHeight: settingsColumn.height + 56
            boundsBehavior: Flickable.StopAtBounds
        Column {
            id: settingsColumn
            objectName: "setupContent"
            x: (parent.width - width) / 2
            y: 28
            width: Math.min(860, parent.width - 80)
            spacing: 16
            CuText { text: hostBridge.demo ? "Demo settings" : "Set up Artegra Enhancer"; role: "dialog"; color: Tokens.text1 }
            CuText { width: parent.width; text: "Choose your folders. Use existing model files, or download them directly from their publishers after reviewing their terms."; wrapMode: Text.WordWrap; role: "label"; color: Tokens.text2 }
            CuText { width: parent.width; text: "First install the image-engine runtime, then choose its folder below. Hardware and memory checks help choose settings for your computer."; wrapMode: Text.WordWrap; role: "small"; color: Tokens.text3 }
            CuButton { text: "Open installation guide"; onClicked: hostBridge.openSetupGuide() }
            Column {
                objectName: "memorySettings"
                width: parent.width
                spacing: 8
                visible: hostBridge.ready && view.tabItem !== null
                CuText { text: "Graphics memory"; role: "label"; color: Tokens.text1 }
                CuText { width: parent.width; text: "Auto chooses tiles and memory offloading for your graphics card. You can choose a smaller profile to leave more memory free. Smaller tiles may change the image; CPU offloading can take longer."; wrapMode: Text.WordWrap; role: "small"; color: Tokens.text2 }
                Flow {
                    width: parent.width
                    spacing: 8
                    Repeater {
                        model: [{ key: "auto", label: "Auto" }, { key: "balanced", label: "Balanced" }, { key: "compact", label: "Compact" }, { key: "minimum", label: "Minimum" }]
                        delegate: CuButton {
                            required property var modelData
                            text: (view.tabItem && view.tabItem.memoryProfile === modelData.key ? "✓ " : "") + modelData.label
                            enabled: view.tabItem && view.tabItem.settingsLoaded && !view.tabItem.batch.active && !view.tabItem.savingMemoryProfile
                            onClicked: view.tabItem.setMemoryProfile(modelData.key)
                        }
                    }
                }
                CuText { width: parent.width; text: view.tabItem ? view.tabItem.memoryProfileStatus : ""; wrapMode: Text.WordWrap; role: "small"; color: Tokens.text2 }
                Repeater {
                    model: view.tabItem && view.tabItem.health && view.tabItem.health.engine && view.tabItem.health.engine.memory ? view.tabItem.health.engine.memory.profiles : []
                    delegate: CuText {
                        required property var modelData
                        width: settingsColumn.width
                        text: modelData.gpu_name + ": " + modelData.name + " · " + modelData.tile_px + " px tiles" + (modelData.offload ? " · CPU offloading" : "") + (modelData.warnings.length ? "\n" + modelData.warnings.join("\n") : "")
                        wrapMode: Text.WordWrap; role: "small"; color: Tokens.text2
                    }
                }
            }
            Repeater {
                model: [{ key: "models_dir", name: "Models folder", value: hostBridge.modelsDir },
                        { key: "runtime_dir", name: "Image-engine runtime folder", value: hostBridge.runtimeDir },
                        { key: "output_dir", name: "Output folder", value: hostBridge.outputDir }]
                delegate: Column {
                    required property var modelData
                    width: settingsColumn.width
                    spacing: 8
                    CuText { text: modelData.name; role: "label"; color: Tokens.text2 }
                    Row {
                        width: parent.width
                        spacing: 12
                        CuTextField {
                            width: parent.width - 104
                            text: modelData.value
                            enabled: !hostBridge.ready && !hostBridge.busy && !modelSetupBridge.busy && (!hostBridge.demo || modelData.key === "output_dir")
                            onCommitted: (text) => hostBridge.setFolder(modelData.key, text)
                            Accessible.name: modelData.name
                        }
                        CuButton {
                            text: "Browse..."
                            enabled: !hostBridge.ready && !hostBridge.busy && !modelSetupBridge.busy && (!hostBridge.demo || modelData.key === "output_dir")
                            onClicked: hostBridge.chooseFolder(modelData.key)
                        }
                    }
                }
            }
            CuButton {
                text: window.modelSetupShown ? "Hide model setup" : "Set up or verify models..."
                visible: !hostBridge.demo
                onClicked: window.modelSetupShown = !window.modelSetupShown
            }
            Column {
                width: parent.width
                spacing: 16
                visible: window.modelSetupShown && !hostBridge.demo
                CuText { text: "Models"; role: "dialog"; color: Tokens.text1 }
                CuText {
                    width: parent.width
                    text: "Standard needs five files (13.03 GiB). Fast adds 0.73 GiB. Detailed preview is optional. Downloads can be paused and resumed. Existing files are checked and never replaced."
                    wrapMode: Text.WordWrap; role: "label"; color: Tokens.text2
                }
                CuText {
                    width: parent.width
                    text: "Each model has its own terms. Review the publisher card and terms, then accept each selected model. TTPlanet specifies only a licence family; its missing full terms and no-adult-content request are disclosed below. Model weights are not included in the app."
                    wrapMode: Text.WordWrap; role: "small"; color: Tokens.text3
                }
                Repeater {
                    model: modelSetupBridge.models
                    delegate: Column {
                        required property var modelData
                        width: settingsColumn.width
                        spacing: 6
                        Flow {
                            width: parent.width
                            spacing: 14
                            CuCheckBox {
                                width: parent.width
                                text: modelData.name + " / " + modelData.purpose + " / " + modelData.size
                                checked: modelData.selected
                                enabled: !modelSetupBridge.busy && !hostBridge.ready && !hostBridge.busy
                                onToggled: (checked) => modelSetupBridge.setSelected(modelData.id, checked)
                            }
                            CuButton { text: "Publisher"; onClicked: modelSetupBridge.openPublisher(modelData.id, "card") }
                            CuButton { text: "Terms"; onClicked: modelSetupBridge.openPublisher(modelData.id, "terms") }
                            CuButton { text: "Saved terms"; onClicked: modelSetupBridge.openSavedTerms(modelData.id) }
                        }
                        CuText { width: parent.width; text: modelData.notice; wrapMode: Text.WordWrap; role: "small"; color: Tokens.text3 }
                        Column {
                            width: parent.width; spacing: 4
                            CuCheckBox {
                                text: "I have read and accept the publisher's card and terms"
                                checked: modelData.accepted
                                enabled: modelData.selected && !modelSetupBridge.busy
                                onToggled: (checked) => modelSetupBridge.setAccepted(modelData.id, checked)
                            }
                            CuText { text: modelData.state; role: "small"; color: Tokens.text2 }
                        }
                        Rectangle { width: parent.width; height: 1; color: Tokens.controlEdge }
                    }
                }
                Rectangle {
                    width: parent.width; height: 3; color: Tokens.controlEdge
                    visible: modelSetupBridge.busy
                    Rectangle { width: parent.width * modelSetupBridge.fraction; height: parent.height; color: Tokens.reveal }
                }
                CuText { width: parent.width; text: modelSetupBridge.status; wrapMode: Text.WordWrap; role: "label"; color: Tokens.text1 }
                Flow {
                    width: parent.width
                    spacing: 12
                    CuButton {
                        text: "Download selected"
                        enabled: modelSetupBridge.canDownload && !hostBridge.ready && !hostBridge.busy
                        onClicked: modelSetupBridge.download()
                    }
                    CuButton {
                        text: "Verify existing files"
                        enabled: !modelSetupBridge.busy && !hostBridge.ready && !hostBridge.busy
                        onClicked: modelSetupBridge.verify()
                    }
                    CuButton { text: "Pause download"; visible: modelSetupBridge.busy; onClicked: modelSetupBridge.cancel() }
                }
            }
            CuText { width: parent.width; text: hostBridge.status; wrapMode: Text.WordWrap; role: "label"; color: Tokens.text1 }
            Flow {
                objectName: "setupActions"
                width: parent.width
                spacing: 12
                CuButton { text: hostBridge.busy ? "Starting..." : "Start engine"; enabled: !hostBridge.ready && !hostBridge.busy && !modelSetupBridge.busy; onClicked: hostBridge.start() }
                CuButton { text: "Edit folders"; visible: hostBridge.ready; enabled: !view.tabItem || !view.tabItem.batch.active; onClicked: hostBridge.stop() }
                CuButton { text: "Back to images"; visible: hostBridge.ready; onClicked: window.settingsShown = false }
                CuButton { text: "Open logs"; onClicked: hostBridge.openLogs() }
                CuButton { text: "Save diagnostic bundle"; onClicked: hostBridge.saveDiagnosticBundle() }
            }
            CuText { width: parent.width; visible: hostBridge.ready; text: "Finish or cancel the current batch before changing folders."; role: "small"; color: Tokens.text3 }
        }
        }
    }
}

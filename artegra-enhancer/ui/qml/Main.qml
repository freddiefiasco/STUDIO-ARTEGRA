import QtQuick
import QtQuick.Window
import QtQuick.Controls
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
    title: view.runSlot ? view.runSlot.title + " · " + hostBridge.displayName : hostBridge.displayName
    property bool panelsShown: true
    property bool settingsShown: false
    property bool aboutShown: false
    property bool closingAccepted: false
    // Settings and About are pages over the workspace, and setup covers it until the engine is ready. While one is up
    // the workspace is hidden, so none of its keys, shortcuts, drops or focus can act behind the page (audit AUD-02).
    readonly property bool pageShown: settingsShown || aboutShown
    readonly property bool workspaceShown: hostBridge.ready && !pageShown
    function closePage() {
        window.settingsShown = false
        window.aboutShown = false
    }
    readonly property bool tabLoaded: view.tabItem !== null
    readonly property bool tabConnected: view.tabItem ? view.tabItem.connected : false
    readonly property bool fastAvailable: view.tabItem ? view.tabItem.fastAvailable : false
    readonly property bool imageWorkActive: view.tabItem ? view.tabItem.batch.active || view.tabItem.maskBusy : false
    readonly property var tabItem: view.tabItem
    onClosing: (close) => {
        if (installationBridge.busy) {
            close.accepted = false
            installationBridge.requestClose()
        } else if (!closingAccepted && view.holdAppClose(function() { window.closingAccepted = true; window.close() })) {
            close.accepted = false
        }
    }
    // The uninstaller asked the app to close: stop and close without a prompt. Setup pauses safely; unfinished images
    // wait for the next start of an installed copy.
    function quitForUninstall() {
        window.closingAccepted = true
        if (installationBridge.busy) installationBridge.requestClose()
        else window.close()
    }
    function askUninstall() {
        if (!view.tabItem || window.imageWorkActive) return
        view.tabItem.confirmDialog.ask("Uninstall " + hostBridge.displayName + "?",
            "The app closes and Windows removes it. You can keep or remove the downloaded enhancement files and your settings. Your enhanced images are never removed.",
            "Uninstall", "Keep it", function() {
                if (hostBridge.startUninstall()) { window.closingAccepted = true; window.close() }
            }, "danger")
    }
    Connections {
        target: installationBridge
        function onCloseReady() { window.closingAccepted = true; window.close() }
    }
    Connections {
        target: hostBridge
        function onChanged() { if (!hostBridge.ready) { window.settingsShown = false; window.aboutShown = false } }
    }
    Connections {
        target: view.tabItem
        function onOutputDirChanged() { hostBridge.rememberOutput(view.tabItem.outputDir) }
    }
    Rectangle {
        id: header
        height: 56
        anchors { left: parent.left; right: parent.right; top: parent.top }
        color: Tokens.ink
        Row {
            anchors { left: parent.left; leftMargin: 24; verticalCenter: parent.verticalCenter }
            spacing: window.width < 1200 ? 12 : 24
            Row {
                spacing: 8
                anchors.verticalCenter: parent.verticalCenter
                CuText { text: "ARTEGRA"; role: "label"; color: Tokens.text1; anchors.verticalCenter: parent.verticalCenter }
                CuText { text: "Enhancer"; role: "label"; color: Tokens.text2; anchors.verticalCenter: parent.verticalCenter }
                CuText { objectName: "headerBeta"; text: "Beta"; role: "small"; color: Tokens.text3; anchors.verticalCenter: parent.verticalCenter }
            }
            CuButton { objectName: "headerPanels"; visible: hostBridge.ready; enabled: !window.pageShown; text: window.panelsShown ? "Hide panels" : "Show panels"; onClicked: window.panelsShown = !window.panelsShown }
            CuButton { objectName: "headerActivity"; visible: hostBridge.ready; enabled: !window.pageShown; text: "Activity"; onClicked: { if (view.tabItem) view.tabItem.setActivityOpen(!view.tabItem.activityOpen) } }
            CuButton { objectName: "headerShortcuts"; visible: hostBridge.ready; enabled: !window.pageShown; text: "Shortcuts"; onClicked: { if (view.tabItem) view.tabItem.shortcuts.openAt("shortcuts") } }
            CuText { visible: hostBridge.ready && window.width >= 1200 && text !== ""; text: view.runSlot ? view.runSlot.text : ""; role: "label"; color: Tokens.text2; anchors.verticalCenter: parent.verticalCenter }
        }
        Row {
            anchors { right: parent.right; rightMargin: 24; verticalCenter: parent.verticalCenter }
            spacing: 12
            CuButton {
                objectName: "headerAbout"
                text: "About"
                onClicked: { window.aboutShown = !window.aboutShown; if (window.aboutShown) window.settingsShown = false }
            }
            CuButton {
                objectName: "headerSettings"
                visible: hostBridge.ready; text: "Settings"
                onClicked: { window.settingsShown = !window.settingsShown; if (window.settingsShown) window.aboutShown = false }
            }
        }
        Rectangle { anchors { bottom: parent.bottom; left: parent.left; right: parent.right } height: 2; color: Tokens.reveal }
    }
    CreativeUpscalerView {
        id: view
        anchors { top: header.bottom; bottom: status.top; left: parent.left; right: parent.right }
        visible: window.workspaceShown
        appBridge: hostBridge
        panelsShown: window.panelsShown
        onPanelsToggleRequested: window.panelsShown = !window.panelsShown
    }
    // Esc closes Settings or About, unless a dialog of its own (the uninstall question) is open.
    Shortcut {
        sequence: "Escape"
        enabled: window.pageShown && Tokens.tipsOpen === 0 && !(view.tabItem && view.tabItem.overlayOpen)
        onActivated: window.closePage()
    }
    Rectangle {
        id: status
        height: 28
        anchors { bottom: parent.bottom; left: parent.left; right: parent.right }
        color: Tokens.ink
        CuText { anchors { left: parent.left; right: parent.right; margins: 24; verticalCenter: parent.verticalCenter } text: installationBridge.busy ? installationBridge.status : hostBridge.status; elide: Text.ElideRight; role: "small"; color: Tokens.text3 }
    }
    component UpdateControl: Column {
        width: parent ? parent.width : 400
        spacing: 12
        Flow {
            width: parent.width; spacing: 12
            CuButton {
                objectName: "updateDownload"
                visible: updateBridge.state === "available"
                text: "Download"; variant: "primary"
                tooltip: "Opens the release page in your browser"
                onClicked: updateBridge.openDownload()
            }
            CuButton {
                objectName: "updateCheck"
                text: "Check for updates"
                enabled: updateBridge.state !== "checking"
                onClicked: updateBridge.check()
            }
        }
        CuText {
            objectName: "updateMessage"
            width: parent.width
            visible: updateBridge.message !== ""
            text: updateBridge.message
            wrapMode: Text.WordWrap; role: "body"
            color: updateBridge.state === "available" ? Tokens.text1 : Tokens.text2
        }
    }
    Rectangle {
        anchors { top: header.bottom; bottom: status.top; left: parent.left; right: parent.right }
        color: Tokens.ink
        visible: window.settingsShown && hostBridge.ready
        MouseArea { anchors.fill: parent }
        Flickable {
            objectName: "settingsScroll"
            anchors.fill: parent; clip: true
            contentHeight: settingsColumn.height + 64
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: CuScrollBar { alwaysShown: true }
            Column {
                id: settingsColumn
                objectName: "settingsContent"
                x: (parent.width - width) / 2; y: 32
                width: Math.min(760, parent.width - 64)
                spacing: 22
                CuText { text: "Settings"; role: "dialog"; color: Tokens.text1 }
                Column {
                    width: parent.width; spacing: 12
                    CuText { text: "Save enhanced images to"; role: "label"; color: Tokens.text1 }
                    CuTextField {
                        width: parent.width; readOnly: true; pathMode: true
                        text: view.tabItem && view.tabItem.outputDir ? view.tabItem.outputDir : hostBridge.outputDir
                        accessibleName: "Output folder"
                    }
                    CuButton { text: "Change folder…"; enabled: !window.imageWorkActive; onClicked: { if (view.tabItem) view.tabItem.openOutputDialog() } }
                    CuText {
                        width: parent.width
                        visible: view.tabItem && view.tabItem.outputDirRefused !== null
                        text: view.tabItem && view.tabItem.outputDirRefused ? view.tabItem.outputDirRefused.reason : ""
                        wrapMode: Text.WordWrap; role: "small"; color: Tokens.text2
                    }
                }
                Rectangle { width: parent.width; height: 1; color: Tokens.controlEdge }
                Column {
                    objectName: "memorySettings"
                    width: parent.width; spacing: 12
                    CuText { text: "Graphics memory"; role: "label"; color: Tokens.text1 }
                    CuText { width: parent.width; text: "Auto chooses the memory setting for your graphics card. Saving memory may take longer; 64 GB of system memory is recommended."; wrapMode: Text.WordWrap; role: "body"; color: Tokens.text2 }
                    Flow {
                        width: parent.width; spacing: 8
                        Repeater {
                            model: [{ key: "auto", label: "Auto (recommended)" }, { key: "reference", label: "Original settings" }, { key: "balanced", label: "Save GPU memory" }]
                            CuButton {
                                required property var modelData
                                objectName: "memoryProfile_" + modelData.key
                                text: modelData.label
                                variant: view.tabItem && view.tabItem.memoryProfile === modelData.key ? "primary" : "tile"
                                enabled: view.tabItem !== null && view.tabItem.connected && view.tabItem.settingsLoaded && !view.tabItem.savingMemoryProfile && !window.imageWorkActive
                                onClicked: view.tabItem.setMemoryProfile(modelData.key)
                            }
                        }
                    }
                    CuText { width: parent.width; text: view.tabItem ? view.tabItem.memoryProfileError : ""; visible: text !== ""; wrapMode: Text.WordWrap; role: "small"; color: Tokens.text2 }
                }
                Rectangle { width: parent.width; height: 1; color: Tokens.controlEdge }
                Column {
                    objectName: "updateSettings"
                    width: parent.width; spacing: 12
                    CuText { text: "Updates"; role: "label"; color: Tokens.text1 }
                    CuText { width: parent.width; text: "Check GitHub for a newer version. Nothing is downloaded or installed until you choose to."; wrapMode: Text.WordWrap; role: "body"; color: Tokens.text2 }
                    UpdateControl { width: parent.width }
                }
                Rectangle { width: parent.width; height: 1; color: Tokens.controlEdge }
                Column {
                    width: parent.width; spacing: 12
                    CuText { text: "Help and maintenance"; role: "label"; color: Tokens.text1 }
                    CuText { width: parent.width; text: "Repair checks the installed files and downloads anything missing. Your images and saved work are kept."; wrapMode: Text.WordWrap; role: "body"; color: Tokens.text2 }
                    Flow {
                        width: parent.width; spacing: 12
                        CuButton { text: "Repair installation"; visible: !hostBridge.demo; enabled: !window.imageWorkActive; onClicked: hostBridge.repair() }
                        CuButton { text: "Save support details"; onClicked: hostBridge.saveDiagnosticBundle() }
                        CuButton { text: "Open logs"; onClicked: hostBridge.openLogs() }
                        CuButton {
                            objectName: "uninstallEntry"
                            text: "Uninstall Artegra Enhancer…"
                            variant: "danger"
                            visible: hostBridge.uninstallAvailable
                            enabled: !window.imageWorkActive
                            tooltip: window.imageWorkActive ? "Finish or cancel the current image work first." : ""
                            onClicked: window.askUninstall()
                        }
                    }
                    CuText { width: parent.width; visible: window.imageWorkActive; text: "Finish or cancel the current image work before changing these settings."; wrapMode: Text.WordWrap; role: "small"; color: Tokens.text3 }
                }
                CuButton { text: "Back to images"; variant: "primary"; onClicked: window.settingsShown = false }
            }
        }
    }
    Rectangle {
        objectName: "aboutPage"
        anchors { top: header.bottom; bottom: status.top; left: parent.left; right: parent.right }
        color: Tokens.ink
        visible: window.aboutShown
        MouseArea { anchors.fill: parent }
        Flickable {
            anchors.fill: parent; clip: true
            contentHeight: aboutColumn.height + 96
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: CuScrollBar { alwaysShown: true }
            Column {
                id: aboutColumn
                objectName: "aboutContent"
                x: Math.round((parent.width - width) / 2); y: 64
                width: Math.min(480, parent.width - 64)
                spacing: 24
                Image {
                    objectName: "aboutWordmark"
                    source: "creative/assets/brand/SA_LOGO-03.svg"
                    height: 12
                    width: Math.round(height * 1024 / 90.46)
                    sourceSize: Qt.size(width * 2, height * 2)
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                }
                Column {
                    width: parent.width; spacing: 6
                    CuText { objectName: "aboutName"; text: hostBridge.displayName; role: "dialog"; color: Tokens.text1 }
                    CuText { objectName: "aboutVersion"; text: "Version " + hostBridge.versionText; role: "body"; tabular: true; color: Tokens.text2 }
                }
                UpdateControl { width: parent.width }
                Flow {
                    width: parent.width; spacing: 12
                    CuButton { objectName: "aboutReleaseNotes"; text: "Release notes"; onClicked: hostBridge.openPage("release") }
                    CuButton { objectName: "aboutSource"; text: "Source on GitHub"; onClicked: hostBridge.openPage("source") }
                    CuButton { objectName: "aboutLicences"; text: "Licences"; onClicked: hostBridge.openPage("licences") }
                }
                CuText {
                    width: parent.width
                    text: "Made by Studio Artegra. Uses Qt under the LGPLv3. The model licences are listed in MODEL-LICENSES.md in the app folder."
                    wrapMode: Text.WordWrap; role: "small"; color: Tokens.text3
                }
                CuButton { text: "Back"; variant: "primary"; onClicked: window.aboutShown = false }
            }
        }
    }
    SetupView {
        anchors { top: header.bottom; bottom: status.top; left: parent.left; right: parent.right }
        visible: !hostBridge.ready && !window.aboutShown
    }
}

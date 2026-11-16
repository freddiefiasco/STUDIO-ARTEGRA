import QtQuick
import QtQuick.Controls
import "creative"

Rectangle {
    id: setup
    color: Tokens.ink
    property bool showTerms: false
    readonly property bool preparing: installationBridge.busy || hostBridge.busy
    readonly property bool installed: installationBridge.complete
    // An installed copy starting its engine is not setup: no steps, no progress bar, no setup notes (audit AUD-09).
    readonly property bool opening: installed && !installationBridge.busy && (hostBridge.busy || !hostBridge.engineStarted)
    // An installed copy whose engine stopped (a crash, a start that took too long or a problem it reported) is not
    // back at the install step either (audit AUD-10).
    readonly property bool engineStopped: installed && !installationBridge.busy && !hostBridge.busy && hostBridge.engineStarted
    readonly property bool failed: installationBridge.stage === "error" || engineStopped
    readonly property bool paused: installationBridge.stage === "paused"
    readonly property bool setupSteps: !installed
    readonly property string heading: opening ? "Opening your workspace"
        : engineStopped ? "The image engine is not running"
        : preparing ? "Getting things ready"
        : failed ? "Setup stopped"
        : paused ? "Your setup is paused" : "Install Artegra Enhancer (Beta)"
    MouseArea { anchors.fill: parent }
    Flickable {
        id: scroll
        objectName: "installationScroll"
        anchors.fill: parent
        clip: true
        contentHeight: content.height + 72
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        Column {
            id: content
            objectName: "installationContent"
            width: Math.min(680, scroll.width - 64)
            x: (scroll.width - width) / 2
            y: 36
            spacing: 24
            CuText { objectName: "setupWelcome"; visible: setup.setupSteps; text: "Welcome to Artegra Enhancer (Beta)"; role: "small"; color: Tokens.text3 }
            CuText { objectName: "setupHeading"; width: parent.width; text: setup.heading; role: "dialog"; wrapMode: Text.WordWrap; color: Tokens.text1 }
            CuText {
                objectName: "setupLead"
                width: parent.width
                visible: !setup.opening
                text: setup.engineStopped ? "Your images and the waiting list are kept. Unfinished images carry on when the engine starts again."
                    : setup.preparing ? "You can leave this window open while we prepare the app."
                    : setup.failed ? "Your images are safe. Use the options below to continue."
                    : setup.paused ? "Your download progress is saved. Resume whenever you're ready."
                    : "We'll download and prepare the image tools automatically, then open your workspace."
                role: "label"; wrapMode: Text.WordWrap; color: Tokens.text2
            }
            Rectangle { visible: setup.setupSteps; width: parent.width; height: 1; color: Tokens.controlEdge }
            Row {
                objectName: "setupSteps"
                visible: setup.setupSteps
                width: parent.width; spacing: 16
                Repeater {
                    model: ["1  Install", "2  Prepare", "3  Create"]
                    CuText {
                        required property string modelData
                        required property int index
                        width: (content.width - 32) / 3
                        text: modelData; role: "label"
                        color: index === (setup.preparing || setup.paused ? 1 : 0) ? Tokens.text1 : Tokens.text3
                    }
                }
            }
            Column {
                width: parent.width; spacing: 16
                visible: !setup.preparing && !setup.installed && !setup.paused && !setup.failed
                CuText {
                    width: parent.width
                    text: "The first setup needs an internet connection and downloads several gigabytes. You can pause and resume at any time."
                    wrapMode: Text.WordWrap; role: "body"; color: Tokens.text2
                }
                CuText {
                    width: parent.width
                    text: "Your images stay on your computer. After setup, enhancement works locally."
                    wrapMode: Text.WordWrap; role: "small"; color: Tokens.text3
                }
            }
            Column {
                width: parent.width; spacing: 14
                visible: !setup.preparing && !setup.installed && installationBridge.needsConsent
                CuButton {
                    objectName: "reviewInstallationTerms"
                    text: setup.showTerms ? "Hide licence details" : "Review application and model licences"
                    onClicked: setup.showTerms = !setup.showTerms
                }
                Column {
                    width: parent.width; spacing: 20; visible: setup.showTerms
                    CuButton { text: "Application licence"; onClicked: installationBridge.openTerms("application") }
                    Repeater {
                        model: installationBridge.terms
                        Column {
                            required property var modelData
                            width: content.width; spacing: 6
                            CuText { width: parent.width; text: modelData.name; role: "label"; wrapMode: Text.WordWrap; color: Tokens.text1 }
                            CuText { width: parent.width; text: modelData.notice; role: "small"; wrapMode: Text.WordWrap; color: Tokens.text2 }
                            CuButton { text: "Read licence"; onClicked: installationBridge.openTerms(modelData.id) }
                        }
                    }
                }
                CuCheckBox {
                    objectName: "acceptInstallationTerms"
                    width: parent.width
                    text: "I agree to the application and model licence terms."
                    checked: installationBridge.accepted
                    onToggled: (value) => installationBridge.setAccepted(value)
                }
            }
            Column {
                width: parent.width; spacing: 12
                visible: setup.preparing || setup.failed || setup.paused
                CuText {
                    objectName: "installationStatus"
                    width: parent.width
                    text: setup.installed ? hostBridge.status : installationBridge.status
                    wrapMode: Text.WordWrap; role: "label"; color: Tokens.text1
                    Accessible.role: Accessible.StaticText
                    Accessible.name: text
                }
                // Only setup reports a real fraction; starting the engine has none, so it shows no bar.
                Rectangle {
                    objectName: "installationProgress"
                    width: parent.width; height: 4; radius: 2
                    color: Tokens.controlEdge; clip: true
                    visible: installationBridge.busy
                    Rectangle {
                        width: parent.width * installationBridge.fraction
                        height: parent.height; radius: 2; color: Tokens.text1
                    }
                }
                CuText {
                    text: Math.round(installationBridge.fraction * 100) + "%"
                    visible: installationBridge.busy; role: "small"; tabular: true; color: Tokens.text3
                }
            }
            Flow {
                width: parent.width; spacing: 12
                CuButton {
                    objectName: "installOrResume"
                    visible: !setup.preparing && !setup.installed
                    text: setup.paused ? "Resume setup" : setup.failed ? "Try again" : "Set up Artegra Enhancer"
                    variant: enabled ? "primary" : "tile"
                    enabled: !installationBridge.needsConsent || installationBridge.accepted
                    onClicked: installationBridge.start()
                }
                CuButton {
                    objectName: "pauseInstallation"
                    visible: installationBridge.busy
                    text: installationBridge.stage === "pausing" ? "Pausing…" : "Pause setup"
                    enabled: installationBridge.stage !== "pausing"
                    onClicked: installationBridge.pause()
                }
                CuButton {
                    objectName: "retryWorkspace"
                    visible: setup.engineStopped
                    text: "Try again"; variant: "primary"
                    onClicked: hostBridge.start()
                }
                CuButton {
                    objectName: "repairFromSetup"
                    visible: setup.engineStopped && !hostBridge.demo
                    text: "Repair installation"; onClicked: hostBridge.repair()
                }
                CuButton {
                    visible: setup.failed
                    text: "Save support details"; onClicked: hostBridge.saveDiagnosticBundle()
                }
            }
            CuText {
                objectName: "setupCloseNote"
                width: parent.width; visible: installationBridge.busy
                text: "Closing this window pauses setup safely. Open Artegra Enhancer again to continue."
                wrapMode: Text.WordWrap; role: "small"; color: Tokens.text3
            }
        }
    }
}

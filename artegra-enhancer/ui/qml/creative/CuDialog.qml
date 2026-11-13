import QtQuick
import QtQuick.Window

FocusScope {
    id: dialog
    property bool modal: true
    property bool form: false
    property string title: ""
    property string message: ""
    property var actions: []
    property var escapeValue: actions.length ? actions[0].value : undefined
    property bool escapeCloses: true
    readonly property bool lastIsDanger: actions.length > 0 && actions[actions.length - 1].kind === "danger"
    property var defaultValue: actions.length ? (lastIsDanger ? actions[0].value : actions[actions.length - 1].value) : undefined
    property rect centreRect: Qt.rect(0, 0, width, height)
    property int forcedFocus: -1
    default property alias content: formColumn.data
    readonly property alias panel: panelItem
    readonly property alias actionsItem: actionRow
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int panelWidth: form ? Tokens.dialogForm : Tokens.dialogQuestion
    readonly property real contentInset: Tokens.dialogPad - panelItem.edgeWidth
    readonly property real ruleX: -contentInset
    readonly property real ruleWidth: panelWidth - 2 * panelItem.edgeWidth
    signal chose(var value)

    function actionAt(i) { return actionRepeater.itemAt(i) }
    function focusDefault() {
        var idx = -1
        for (var i = 0; i < actions.length; ++i) if (actions[i].value === defaultValue) idx = i
        var it = actionRepeater.itemAt(idx >= 0 ? idx : 0)
        if (it) it.forceActiveFocus(Qt.TabFocusReason)
    }

    objectName: "dialog"
    Accessible.role: Accessible.Dialog
    Accessible.name: title

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Escape) {
            if (dialog.escapeCloses && dialog.escapeValue !== undefined) dialog.chose(dialog.escapeValue)
            event.accepted = true
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            var f = dialog.Window.activeFocusItem
            var onAction = false
            for (var i = 0; i < actionRepeater.count; ++i) if (actionRepeater.itemAt(i) === f) onAction = true
            if (!onAction && dialog.defaultValue !== undefined) { dialog.chose(dialog.defaultValue); event.accepted = true }
        }
    }

    Rectangle {
        visible: dialog.modal
        anchors.fill: parent
        color: Tokens.scrim
        MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.AllButtons; onWheel: (w) => { w.accepted = true } }
    }

    CuPlate {
        id: panelItem
        objectName: "dialogPanel"
        modal: true
        width: dialog.panelWidth
        height: Math.ceil(inner.implicitHeight) + 2 * Tokens.dialogPad
        x: Tokens.snap(dialog.centreRect.x + (dialog.centreRect.width - width) / 2, dialog.dpr)
        y: Tokens.snap(dialog.centreRect.y + (dialog.centreRect.height - height) / 2, dialog.dpr)

        Column {
            id: inner
            x: dialog.contentInset
            y: dialog.contentInset
            width: dialog.panelWidth - 2 * Tokens.dialogPad
            spacing: 0
            CuText {
                id: titleText
                objectName: "dialogTitle"
                width: parent.width
                visible: dialog.title !== ""
                text: dialog.title
                role: "heading"
                wrapMode: Text.WordWrap
                color: Tokens.text1
                Accessible.role: Accessible.Heading
                Accessible.name: text
            }
            Item { width: 1; height: Tokens.sp8; visible: dialog.title !== "" && dialog.message !== "" }
            CuText {
                objectName: "dialogMessage"
                width: parent.width
                height: Tokens.onGrid(implicitHeight)
                visible: dialog.message !== ""
                text: dialog.message
                role: "body"
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                elide: Text.ElideRight
                color: Tokens.text2
            }
            Item { width: 1; height: Tokens.sp24; visible: formColumn.children.length > 0 }
            Column {
                id: formColumn
                width: parent.width
                spacing: 0
            }
            Item { width: 1; height: Tokens.sp24 }
            CuSettingsRule {
                objectName: "dialogRule"
                visible: dialog.form
                x: dialog.ruleX
                width: dialog.ruleWidth
                ground: "float"
            }
            Item { width: 1; height: Tokens.sp24 - 1; visible: dialog.form }
            Item {
                width: parent.width
                height: Tokens.hCommit
                Row {
                    id: actionRow
                    objectName: "dialogActions"
                    anchors.right: parent.right
                    spacing: Tokens.sp8
                    Repeater {
                        id: actionRepeater
                        model: dialog.actions
                        CuButton {
                            required property var modelData
                            required property int index
                            objectName: "dialogAction-" + modelData.label
                            ground: "float"
                            commit: true
                            variant: modelData.kind === "white" ? "primary" : (modelData.kind || "tile")
                            text: modelData.label
                            tooltip: modelData.tip || ""
                            enabled: modelData.enabled !== false
                            bleed: false
                            width: Tokens.onGrid(implicitWidth)
                            forcedState: dialog.forcedFocus === index ? "focus" : ""
                            onClicked: dialog.chose(modelData.value)
                        }
                    }
                }
            }
        }
    }
}

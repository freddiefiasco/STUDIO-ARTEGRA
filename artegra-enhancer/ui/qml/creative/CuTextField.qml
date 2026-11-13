import QtQuick
import QtQuick.Templates as T
import QtQuick.Window
import "format.js" as F

Item {
    id: control

    property string text: ""
    property string placeholderText: ""
    property int maximumLength: 32767
    property bool digitsOnly: false
    property bool readOnly: false
    property bool error: false
    property string errorText: ""
    property bool monospace: false
    property bool pathMode: false
    property string accessibleName: placeholderText
    property string ground: "ink"
    property string forcedState: ""
    readonly property alias editing: input.activeFocus
    readonly property bool counting: !readOnly && maximumLength <= 1000 && input.length > Math.floor(maximumLength * 0.75)
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property bool hoverOn: (wellHover.hovered || forcedState === "hover") && enabled && !readOnly

    signal edited(string text)
    signal committed(string text)

    implicitWidth: Tokens.settingControl
    implicitHeight: Tokens.hControl
    activeFocusOnTab: false

    onTextChanged: { if (!input.activeFocus && input.text !== text) { input.text = text; input.cursorPosition = 0 } }

    FontMetrics { id: fm; font: Tokens.fontFor("body", control.digitsOnly) }

    Rectangle {
        id: well
        objectName: "fieldBody"
        x: 0
        y: 0
        width: control.width
        height: Tokens.hControl
        radius: Tokens.radiusControl
        antialiasing: radius > 0
        color: Tokens.wellOn(control.ground)
        HoverHandler { id: wellHover; cursorShape: control.readOnly ? Qt.ArrowCursor : Qt.IBeamCursor }
    }
    Item {
        visible: control.error || control.hoverOn
        scale: 1 / control.dpr
        transformOrigin: Item.TopLeft
        Rectangle {
            width: Math.round(well.width * control.dpr)
            height: Math.round(well.height * control.dpr)
            color: "transparent"
            border.width: Tokens.devPx("line", control.dpr)
            border.color: control.error ? Tokens.danger : Tokens.reveal
            radius: Tokens.radiusControl * control.dpr
            antialiasing: radius > 0
        }
    }
    CuFocusRing {
        target: well
        shown: (!control.readOnly && input.activeFocus) || control.forcedState === "focus"
    }

    CuText {
        id: valueText
        x: Tokens.textInset
        y: centredIn(Tokens.hControl)
        width: Math.max(0, control.width - 2 * Tokens.textInset)
        visible: control.readOnly
        role: "body"
        elide: Text.ElideMiddle
        text: control.text === "" ? control.placeholderText
              : control.pathMode ? F.shortPath(control.text, function(t) { return pathMetrics.advanceWidth(t) <= width - 2 }) : control.text
        color: !control.enabled ? Tokens.text4 : (control.text !== "" ? Tokens.text2 : Tokens.text3)
        Accessible.role: Accessible.StaticText
        Accessible.name: control.accessibleName + ": " + (control.text !== "" ? control.text : text)
        FontMetrics {
            id: pathMetrics
            font: valueText.font
        }
        HoverHandler { id: pathHover; enabled: control.readOnly }
    }
    CuHoverTip {
        shown: control.readOnly && pathHover.hovered
        text: control.text
    }

    T.TextField {
        id: input
        hoverEnabled: false
        x: Tokens.textInset
        y: Tokens.snap((Tokens.hControl - fm.height) / 2, control.dpr)
        width: Math.max(0, control.width - 2 * Tokens.textInset - (control.counting ? counter.implicitWidth + Tokens.sp8 : 0))
        height: Math.ceil(fm.height)
        padding: 0
        background: null
        visible: !control.readOnly
        enabled: !control.readOnly && control.enabled
        activeFocusOnTab: !control.readOnly
        horizontalAlignment: control.digitsOnly ? TextInput.AlignRight : TextInput.AlignLeft
        verticalAlignment: TextInput.AlignTop
        clip: true
        font: Tokens.fontFor("body", control.digitsOnly)
        renderType: Tokens.renderType
        color: control.enabled ? Tokens.text1 : Tokens.text4
        selectByMouse: true
        selectionColor: Tokens.textSelection
        selectedTextColor: Tokens.text1
        maximumLength: control.maximumLength
        inputMethodHints: control.digitsOnly ? Qt.ImhDigitsOnly : Qt.ImhNone
        validator: RegularExpressionValidator { regularExpression: control.digitsOnly ? /\d{0,19}/ : /[\s\S]*/ }
        text: control.text
        cursorDelegate: Rectangle { width: Tokens.px(1, control.dpr); color: Tokens.text1; visible: input.cursorVisible }
        Accessible.role: Accessible.EditableText
        Accessible.name: control.accessibleName
        onTextEdited: control.edited(text)
        onEditingFinished: control.committed(text)
        onActiveFocusChanged: { if (!activeFocus) cursorPosition = 0 }
        Component.onCompleted: cursorPosition = 0

        CuText {
            x: 0
            y: Tokens.snap(fm.ascent - baselineOffset, control.dpr)
            width: parent.width
            visible: input.text === "" && !input.activeFocus
            text: control.placeholderText
            role: "body"
            elide: Text.ElideRight
            horizontalAlignment: control.digitsOnly ? Text.AlignRight : Text.AlignLeft
            color: Tokens.text3
        }
    }
    CuText {
        id: counter
        objectName: "fieldCounter"
        x: Tokens.snap(control.width - Tokens.textInset - Math.ceil(implicitWidth), control.dpr)
        y: Tokens.snap(input.y + fm.ascent - baselineOffset, control.dpr)
        visible: control.counting
        role: "meta"
        tabular: true
        color: Tokens.text3
        text: Number(input.length).toLocaleString(Qt.locale("en_GB"), "f", 0) + "\u00a0/\u00a0"
              + Number(control.maximumLength).toLocaleString(Qt.locale("en_GB"), "f", 0)
    }
    CuText {
        objectName: "fieldError"
        x: 0
        y: Tokens.hControl + Tokens.sp4
        width: control.width
        visible: control.error && control.errorText !== ""
        text: control.errorText
        role: "meta"
        elide: Text.ElideRight
        color: Tokens.danger
    }
}

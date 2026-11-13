import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.Control {
    id: control

    property string iconName: ""
    property string text: ""
    property string tooltip: ""
    property string accessibleName: tooltip !== "" ? tooltip : text
    property int buttonSize: Tokens.panelsToggleSize
    property int iconSize: Tokens.iconBox
    property bool checkable: false
    property bool checked: false
    property color iconColor: Tokens.text3
    property color swatch: "transparent"
    property bool iconFixedColor: false
    property bool swatchEmpty: false
    property bool exclusive: false
    property bool compact: false
    property string ground: "stage"
    property string forcedState: ""
    horizontalPadding: Tokens.tileGlyphPad
    readonly property bool hasSwatch: swatch.a > 0
    readonly property bool wordsShown: text !== "" && !compact
    readonly property bool isTile: text !== ""
    readonly property bool hoverOn: enabled && (hovered || forcedState === "hover")
    readonly property bool pressed: enabled && (tap.pressed || forcedState === "pressed")
    readonly property bool ringShown: visualFocus || forcedState === "focus"
    readonly property bool iconShown: iconName !== "" && Tokens.isGlyph(iconName)
    readonly property color labelColor: label.color
    readonly property color frameColor: "transparent"
    readonly property color bodyColor: frame.color
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property color trackColor: Tokens.tileOn(ground)
    readonly property color hoverColor: isTile ? Tokens.raisedOn(ground) : Tokens.tileOn(ground)
    readonly property color pressedColor: Tokens.pressOn(ground)
    readonly property color chosenColor: Tokens.raisedOn(ground)
    readonly property bool keyToggle: isTile && hasSwatch && (checkable || exclusive)
    readonly property bool keyLit: !keyToggle || checked
    readonly property color keyColor: keyLit ? swatch : (enabled ? Tokens.text3 : Tokens.text4)

    signal clicked()

    function activate() {
        if (enabled) clicked()
    }

    readonly property int barWidth: hasSwatch ? Tokens.keyBarWidth : 0
    readonly property int glyphWidth: iconShown ? iconSize : 0
    readonly property int innerWidth: barWidth + glyphWidth + (wordsShown ? Math.ceil(label.implicitWidth) : 0)
                                      + ((barWidth > 0 || glyphWidth > 0) && wordsShown ? Tokens.sp8 : 0)
                                      + (barWidth > 0 && glyphWidth > 0 ? Tokens.sp8 : 0)
    implicitWidth: wordsShown ? innerWidth + 2 * horizontalPadding : buttonSize
    implicitHeight: buttonSize
    hoverEnabled: true
    focusPolicy: Qt.TabFocus

    Accessible.role: exclusive ? Accessible.RadioButton : (checkable ? Accessible.CheckBox : Accessible.Button)
    Accessible.name: accessibleName
    Accessible.checkable: checkable || exclusive
    Accessible.checked: checked
    Accessible.onPressAction: activate()
    Accessible.onToggleAction: activate()

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            control.activate()
            event.accepted = true
        }
    }

    Rectangle {
        id: frame
        objectName: "iconButtonBody"
        anchors.fill: parent
        radius: Tokens.radiusControl
        antialiasing: radius > 0
        color: {
            if (control.isTile) {
                if (!control.enabled) return control.trackColor
                if (control.pressed) return control.pressedColor
                if (control.hoverOn) return control.chosenColor
                return control.checked && !control.keyToggle ? control.chosenColor : control.trackColor
            }
            if (!control.enabled) return "transparent"
            if (control.pressed) return control.pressedColor
            if (control.checked) return control.chosenColor
            return control.hoverOn ? control.hoverColor : "transparent"
        }
        Behavior on color { ColorAnimation { duration: control.hoverOn ? Tokens.durHoverIn : Tokens.durHoverOut } }
    }

    readonly property real startX: wordsShown ? horizontalPadding : Tokens.snap((width - innerWidth) / 2, dpr)
    Item {
        objectName: "buttonSwatch"
        visible: control.hasSwatch
        x: control.startX
        y: Tokens.snap((control.height - Tokens.keyBarHeight) / 2, control.dpr)
        width: Tokens.keyBarWidth
        height: Tokens.keyBarHeight
        Rectangle {
            scale: 1 / control.dpr
            transformOrigin: Item.TopLeft
            y: control.swatchEmpty ? Math.floor(Tokens.keyBarHeight * control.dpr / 2) : 0
            width: Math.round(Tokens.keyBarWidth * control.dpr)
            height: control.swatchEmpty ? Tokens.devPx("line", control.dpr) : Math.round(Tokens.keyBarHeight * control.dpr)
            color: control.keyColor
            antialiasing: false
        }
    }
    CuIcon {
        id: glyph
        x: control.startX + (control.barWidth > 0 ? control.barWidth + Tokens.sp8 : 0)
        y: Tokens.snap((control.height - control.iconSize) / 2, control.dpr)
        visible: control.iconShown
        iconName: control.iconShown ? control.iconName : ""
        iconSize: control.iconSize
        color: !control.enabled ? Tokens.text4
               : control.iconFixedColor ? control.iconColor
               : (control.checked || control.hoverOn || control.pressed || control.ringShown) ? Tokens.text1 : control.iconColor
    }
    CuText {
        id: label
        x: control.startX + (control.barWidth > 0 ? control.barWidth + Tokens.sp8 : 0)
           + (control.glyphWidth > 0 ? control.glyphWidth + Tokens.sp8 : 0)
        y: centredIn(control.height)
        visible: control.wordsShown
        text: control.text
        role: "body"
        color: !control.enabled ? Tokens.text4
               : (control.checked || control.hoverOn || control.pressed || control.ringShown) ? Tokens.text1 : Tokens.text2
    }

    MouseArea {
        id: tap
        anchors.fill: parent
        onPressed: control.tipMuted = true
        onClicked: control.activate()
    }
    HoverHandler {
        cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    CuFocusRing {
        target: frame
        shown: control.ringShown
    }

    property bool tipMuted: false
    onHoveredChanged: { if (!hovered) tipMuted = false }
    CuHoverTip {
        shown: (control.hovered && !control.tipMuted) || control.visualFocus
        text: control.compact && control.tooltip === "" ? control.text : control.tooltip
    }
}

import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

T.Control {
    id: control

    property string text: ""
    property string iconName: ""
    property string trailingIconName: ""
    property string variant: "tile"
    property bool busy: false
    property real progress: 0
    property string tooltip: ""
    property string accessibleDescription: ""
    property int fontSize: 13
    property bool alignLeft: false
    property bool underline: true
    property color textColor: Tokens.text2
    property string labelRole: ""
    property bool bleed: true
    property int leadingSpace: 0
    property color iconColor: "transparent"
    property string ground: "ink"
    property string keyCap: ""
    property bool commit: false
    property var menuModel: []
    property var folded: []
    property string forcedState: ""
    readonly property string groundKey: Tokens.groundKey(ground)
    readonly property color groundTrack: Tokens.tileOn(ground)
    readonly property color groundHover: Tokens.raisedOn(ground)
    readonly property color groundPressed: Tokens.pressOn(ground)
    property color hoverFill: Tokens.tileOn(ground)
    property color pressFill: Tokens.pressOn(ground)

    readonly property bool isPrimary: variant === "primary" || variant === "white"
    readonly property bool isWhite: isPrimary
    readonly property bool isDanger: variant === "danger" || variant === "textDanger"
    readonly property bool isDangerText: isDanger
    readonly property bool isReading: variant === "reading"
    readonly property bool isText: variant === "text" || variant === "link" || variant === "ghost" || isReading || isDanger
    readonly property bool isTile: !isPrimary && !isText
    readonly property bool isLink: isText
    readonly property bool isBordered: false
    readonly property var menuItems: {
        var a = (menuModel || []).slice()
        var f = folded || []
        if (a.length > 0 && f.length > 0) a.push({ separator: true })
        return a.concat(f)
    }
    readonly property bool isSplit: isTile && menuItems.length > 0
    readonly property bool iconShown: iconName !== "" && Tokens.isGlyph(iconName) && !isText
    readonly property string tone: isPrimary ? "primary" : (isReading ? "reading" : "control")
    readonly property bool trailingShown: false
    readonly property int bleedX: isText && bleed ? Tokens.textControlPad : 0
    property int buttonHeight: isPrimary || commit ? Tokens.hCommit : Tokens.hControl
    readonly property int shapeHeight: buttonHeight
    horizontalPadding: isText ? (bleed ? 0 : Tokens.textControlPad) : Tokens.tileGlyphPad
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1

    readonly property bool hoverOn: enabled && !busy && (hovered || forcedState === "hover")
    readonly property bool mainPressed: enabled && !busy && (tap.pressed || forcedState === "pressed")
    readonly property bool chevronPressed: enabled && !busy && chevTap.pressed
    readonly property bool pressed: mainPressed || chevronPressed
    readonly property bool menuOpen: menuPopup.visible || forcedState === "menu"
    readonly property bool ringShown: visualFocus || forcedState === "focus"
    readonly property bool lit: hoverOn || pressed || menuOpen
    readonly property bool showSpinner: false
    readonly property string sizeRole: isPrimary ? "title"
                                       : labelRole !== "" ? Tokens.controlRole(labelRole)
                                       : (fontSize <= 12 ? "meta" : "body")
    readonly property string textRole: sizeRole
    readonly property real radiusValue: isText ? 0 : Tokens.radiusControl
    readonly property color restColor: isPrimary ? Tokens.inkOnWhite
                                       : isDanger ? Tokens.danger
                                       : Tokens.text2
    readonly property color bodyColor: frame.color
    readonly property alias labelItem: label
    readonly property color labelColor: label.color
    readonly property color underlineColor: !enabled ? Tokens.text4 : ((lit || ringShown) ? Tokens.text1 : Tokens.text3)
    readonly property color borderColor: "transparent"
    readonly property int borderWidth: 0
    readonly property string tipText: keyCap !== "" ? Tokens.keyTip(tooltip !== "" ? tooltip : text, keyCap) : tooltip

    signal clicked()
    signal menuChosen(var value)

    function activate() {
        if (enabled && !busy) clicked()
    }
    function openMenu() {
        if (!isSplit || !enabled || busy) return
        menuPopup.open()
    }
    function closeMenu() { menuPopup.close() }
    Component.onCompleted: { if (forcedState === "menu") Qt.callLater(function() { if (control.visible) control.openMenu() }) }

    readonly property int glyphBox: iconShown ? Tokens.iconBox : 0
    readonly property int iconBox: glyphBox
    readonly property int markBox: 0
    readonly property int capWidth: 0
    readonly property int wordsWidth: text !== "" ? Math.ceil(label.implicitWidth) : 0
    readonly property int contentWidth_: leadingSpace + glyphBox + (glyphBox > 0 && text !== "" ? Tokens.sp8 : 0) + wordsWidth
    readonly property int chevronWidth: isSplit ? Tokens.chevronCell : 0
    readonly property int mainWidth: width - chevronWidth
    implicitHeight: shapeHeight
    implicitWidth: {
        if (isPrimary) return Math.ceil(Math.max(shapeHeight, contentWidth_ + 2 * Tokens.whitePadMin) / 4) * 4
        if (isText) return Math.max(bleed ? 0 : Tokens.hControl, contentWidth_ + 2 * horizontalPadding)
        return Math.ceil(Math.max(shapeHeight, contentWidth_ + 2 * horizontalPadding) / 4) * 4 + chevronWidth
    }
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    containmentMask: bleedX > 0 ? frame : null

    Accessible.role: isSplit ? Accessible.ButtonMenu : Accessible.Button
    Accessible.name: text !== "" ? text : tooltip
    Accessible.description: accessibleDescription !== "" ? accessibleDescription : tipText
    Accessible.onPressAction: control.activate()

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            control.activate()
            event.accepted = true
        } else if (control.isSplit && event.key === Qt.Key_Down) {
            control.openMenu()
            event.accepted = true
        }
    }

    Rectangle {
        id: frame
        objectName: "buttonBody"
        x: -control.bleedX
        y: 0
        width: control.width + 2 * control.bleedX
        height: control.height
        radius: control.radiusValue
        antialiasing: radius > 0
        color: {
            if (control.isPrimary) {
                if (!control.enabled) return "transparent"
                if (control.busy || control.mainPressed) return Tokens.whitePressed
                return control.hoverOn ? Tokens.whiteHover : Tokens.white
            }
            if (control.isTile) {
                if (control.busy) return control.groundPressed
                if (!control.enabled) return control.groundTrack
                if (control.mainPressed) return control.groundPressed
                return control.lit ? control.groundHover : control.groundTrack
            }
            if (!control.enabled) return "transparent"
            if (control.isDanger) return (control.busy || control.lit) ? Tokens.dangerBody : "transparent"
            if (control.busy || control.mainPressed) return control.pressFill
            return control.hoverOn ? control.hoverFill : "transparent"
        }
        Behavior on color { ColorAnimation { duration: control.hoverOn ? Tokens.durHoverIn : Tokens.durHoverOut } }
    }
    Rectangle {
        visible: control.isSplit && control.chevronPressed
        x: control.mainWidth
        width: control.chevronWidth
        height: control.height
        color: control.groundPressed
    }
    CuSettingsRule {
        visible: control.isSplit
        vertical: true
        x: Tokens.snap(control.mainWidth, control.dpr)
        y: 0
        height: control.height
        color: Tokens.reveal
    }

    readonly property real contentX: {
        if (control.isText) return control.horizontalPadding + control.leadingSpace
        if (control.alignLeft || control.iconShown) return control.horizontalPadding + control.leadingSpace
        return Tokens.snap((control.mainWidth - control.contentWidth_) / 2, control.dpr) + control.leadingSpace
    }
    CuIcon {
        id: glyph
        x: control.contentX
        y: Tokens.snap((control.height - Tokens.iconBox) / 2, control.dpr)
        visible: control.iconShown
        iconName: control.iconShown ? control.iconName : ""
        color: !control.enabled ? Tokens.text4
               : control.iconColor.a > 0 ? control.iconColor
               : (control.lit || control.ringShown) ? Tokens.text1 : Tokens.text3
    }
    CuText {
        id: label
        objectName: "buttonLabel"
        x: control.contentX + (control.glyphBox > 0 ? control.glyphBox + Tokens.sp8 : 0)
        y: centredIn(control.height)
        visible: control.text !== ""
        text: control.text
        role: control.textRole
        elide: Text.ElideRight
        width: Math.min(implicitWidth, Math.max(0, control.mainWidth - x - (control.isText ? 0 : control.horizontalPadding)))
        color: {
            if (control.isPrimary) return Tokens.inkOnWhite
            if (!control.enabled) return Tokens.text4
            if (control.isDanger) return Tokens.danger
            return (control.lit || control.ringShown || control.busy) ? Tokens.text1 : control.restColor
        }
        opacity: control.isPrimary && !control.enabled ? 0 : 1
    }
    Item {
        objectName: "textControlMark"
        visible: control.isText && !control.isDanger && control.text !== ""
        x: label.x
        y: Tokens.snap(label.y + label.baselineOffset + 2, control.dpr)
        width: label.width
        height: 1
        Item {
            scale: 1 / control.dpr
            transformOrigin: Item.TopLeft
            Rectangle {
                width: Math.round(label.width * control.dpr)
                height: Tokens.devPx("line", control.dpr)
                color: control.underlineColor
                antialiasing: false
            }
        }
    }
    CuIcon {
        objectName: "splitChevron"
        visible: control.isSplit
        x: control.mainWidth + Tokens.snap((control.chevronWidth - Tokens.iconBox) / 2, control.dpr)
        y: Tokens.snap((control.height - Tokens.iconBox) / 2, control.dpr)
        iconName: control.menuOpen ? "chevronUp" : "chevronDown"
        color: !control.enabled ? Tokens.text4 : (control.lit || control.ringShown) ? Tokens.text1 : Tokens.text3
    }

    MouseArea {
        id: tap
        x: frame.x
        width: control.isSplit ? control.mainWidth : frame.width
        height: control.height
        enabled: !control.busy
        onPressed: control.tipMuted = true
        onClicked: control.activate()
    }
    MouseArea {
        id: chevTap
        visible: control.isSplit
        x: control.mainWidth
        width: control.chevronWidth
        height: control.height
        enabled: control.isSplit && !control.busy
        onPressed: control.tipMuted = true
        onClicked: { if (menuPopup.visible) menuPopup.close(); else control.openMenu() }
    }
    HoverHandler {
        cursorShape: control.enabled && !control.busy ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    CuFocusRing {
        target: frame
        shown: control.ringShown
        targetRadius: control.radiusValue
    }

    T.Popup {
        id: menuPopup
        property real roomBelow: 1e6
        function measure() {
            var w = control.Window.window
            if (!w || !w.contentItem) { roomBelow = 1e6; return }
            var p = control.mapToItem(w.contentItem, 0, control.height)
            roomBelow = w.contentItem.height - p.y - Tokens.sp8
        }
        x: 0
        y: roomBelow >= implicitHeight + Tokens.sp4 ? control.height + Tokens.sp4 : -implicitHeight - Tokens.sp4
        padding: 0
        modal: false
        focus: true
        closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent
        implicitWidth: splitMenu.implicitWidth
        implicitHeight: splitMenu.implicitHeight
        background: null
        enter: Transition { NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: Tokens.durFloatIn } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: Tokens.durFloatOut } }
        onAboutToShow: { measure(); splitMenu.reset() }
        onOpened: splitMenu.forceActiveFocus(Qt.PopupFocusReason)
        contentItem: CuMenu {
            id: splitMenu
            model: control.menuItems
            minWidth: control.width
            focus: true
            onChosen: (value) => { menuPopup.close(); control.forceActiveFocus(Qt.TabFocusReason); control.menuChosen(value) }
            onCloseRequested: { menuPopup.close(); control.forceActiveFocus(Qt.TabFocusReason) }
        }
    }

    onVisibleChanged: if (!visible && menuPopup.visible) menuPopup.close()
    property bool tipMuted: false
    onHoveredChanged: { if (!hovered) tipMuted = false }
    CuHoverTip {
        shown: ((control.hovered && !control.tipMuted) || control.visualFocus) && !control.menuOpen
        text: control.tipText
    }
}

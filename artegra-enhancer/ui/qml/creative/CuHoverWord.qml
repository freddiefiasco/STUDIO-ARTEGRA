import QtQuick

CuButton {
    id: word
    property bool rowHovered: false
    property bool rowFocused: false
    readonly property bool showing: rowHovered || rowFocused || visualFocus || forcedState !== ""
    objectName: "hoverWord"
    variant: "text"
    labelRole: "small"
    buttonHeight: Tokens.hRowWord
    ground: "ink"
    hoverFill: Tokens.raisedOn(ground)
    opacity: showing ? 1 : 0
    visible: opacity > 0
    focusPolicy: showing ? Qt.TabFocus : Qt.NoFocus
    Behavior on opacity { NumberAnimation { duration: word.showing ? 0 : (Tokens.reduceMotion ? 0 : Tokens.durHoverOut) } }
}

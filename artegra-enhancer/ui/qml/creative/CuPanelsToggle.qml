import QtQuick

CuIconButton {
    id: toggle
    property bool panelsShown: true
    signal toggled()
    objectName: "panelsToggle"
    ground: "stage"
    buttonSize: Tokens.panelsToggleSize
    iconName: panelsShown ? "panels" : "panelsOff"
    tooltip: Tokens.keyTip(panelsShown ? "Hide panels" : "Show panels", "Tab")
    accessibleName: panelsShown ? "Hide panels" : "Show panels"
    onClicked: toggle.toggled()
}

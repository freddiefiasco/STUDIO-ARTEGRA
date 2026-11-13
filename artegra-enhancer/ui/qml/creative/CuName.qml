import QtQuick

CuText {
    id: nameText
    property string name: ""
    property real maxWidth: 200
    property bool allowCodeWins: false
    readonly property string fullName: name
    readonly property bool elided: text !== name
    readonly property bool keepsProject: Tokens.nameKeepsProject(name, text)
    readonly property bool keepsRule: Tokens.nameKeepsRule(name, text, allowCodeWins)
    objectName: "fileName"
    role: "label"
    FontMetrics { id: fm; font: nameText.font }
    text: Tokens.elideName(name, maxWidth, fm, allowCodeWins)
    width: Math.min(Math.ceil(implicitWidth), Math.max(0, maxWidth))
    elide: Text.ElideNone
    Accessible.name: name
}

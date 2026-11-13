import QtQuick

Item {
    id: sec
    property string title: ""
    property bool open: false
    property bool foldable: true
    property string summary: ""
    property string note: ""
    property int trail: Tokens.gapSection
    property var leg: null
    property string name: ""
    readonly property alias rowItem: row
    property Item sectionHeading: row
    readonly property real bodyHeight: body.height
    default property alias content: body.data
    signal toggled(bool open)

    width: parent ? parent.width : Tokens.legContentMin
    height: Tokens.hTitleRow + reveal.height + trail
    Accessible.role: Accessible.Grouping
    Accessible.name: title

    CuSettingsSectionRow {
        id: row
        objectName: sec.objectName !== "" ? sec.objectName + "Row" : "sectionRow"
        section: sec
        x: 0
        y: 0
        width: sec.width
    }
    Item {
        id: reveal
        objectName: "sectionBody"
        x: 0
        y: Tokens.hTitleRow
        width: sec.width
        height: sec.open ? Tokens.gapTitle + body.height : 0
        visible: sec.open
        opacity: sec.open ? 1 : 0
        Behavior on opacity {
            NumberAnimation { duration: Tokens.durSection; easing.type: Easing.BezierSpline; easing.bezierCurve: Tokens.easeEnter }
        }
        Column {
            id: body
            x: 0
            y: Tokens.gapTitle
            width: sec.width
        }
    }
}

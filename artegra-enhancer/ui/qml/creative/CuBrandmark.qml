import QtQuick

Item {
    id: mark
    property int unit: Tokens.brandUnit
    property color color: Tokens.white
    objectName: "brandmark"
    implicitWidth: 3 * unit
    implicitHeight: 3 * unit
    width: implicitWidth
    height: implicitHeight
    Accessible.role: Accessible.Graphic
    Accessible.name: "Studio Artegra"

    Rectangle { objectName: "brandmarkLeftLeg"; x: 0; y: mark.unit; width: mark.unit; height: 2 * mark.unit; color: mark.color }
    Rectangle { objectName: "brandmarkKeystone"; x: mark.unit; y: 0; width: mark.unit; height: mark.unit; color: mark.color }
    Rectangle { objectName: "brandmarkRightLeg"; x: 2 * mark.unit; y: mark.unit; width: mark.unit; height: 2 * mark.unit; color: mark.color }
}

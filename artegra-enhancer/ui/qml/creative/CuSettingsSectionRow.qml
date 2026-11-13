import QtQuick

CuSectionTitle {
    id: srow
    property Item section: null
    property var leg: null
    readonly property bool isOpen: section ? section.open : false
    text: section ? section.title : ""
    foldable: section ? section.foldable : false
    open: isOpen
    summary: section ? section.summary : ""
    note: section && !section.foldable ? section.note : ""
    onToggled: (o) => { if (srow.section) srow.section.toggled(o) }
}

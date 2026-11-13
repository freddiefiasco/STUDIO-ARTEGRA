import QtQuick

Loader {
    id: tip
    property string text: ""
    property bool shown: false
    property int delay: Tokens.tooltipDelay
    property string placement: "above"
    property Item avoidItem: null
    property rect avoidRect: Qt.rect(0, 0, 0, 0)
    property url picture: ""
    property real pictureAspect: 0
    property bool pictureAlpha: false
    property string detail: ""
    property real cardWidth: 0
    readonly property bool open: item !== null && item.visible && !item.blocked
    readonly property bool blocked: item !== null && item.blocked
    anchors.fill: parent
    active: shown && text !== ""
    sourceComponent: Component {
        CuToolTip {
            text: tip.text
            placement: tip.placement
            avoidItem: tip.avoidItem
            avoidRect: tip.avoidRect
            picture: tip.picture
            pictureAspect: tip.pictureAspect
            pictureAlpha: tip.pictureAlpha
            detail: tip.detail
            cardWidth: tip.cardWidth
            Component.onCompleted: visible = true
        }
    }
}

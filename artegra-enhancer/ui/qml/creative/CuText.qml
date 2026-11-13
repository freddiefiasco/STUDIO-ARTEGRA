import QtQuick
import QtQuick.Window

Text {
    id: root
    property string role: "body"
    property bool tabular: false
    property bool quiet: false
    readonly property var spec: Tokens.type[role] || Tokens.type.body
    readonly property int lineBox: spec.line
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    function centredIn(h) {
        var cap = Tokens.capHeightFor(font)
        var y = h / 2 + cap / 2 - baselineOffset
        return Math.round(y * dpr) / dpr
    }

    color: quiet ? Tokens.text3 : Tokens.toneFor(role)
    font.family: Tokens.familyFor(spec.weight)
    font.pixelSize: spec.size
    font.weight: spec.weight
    font.letterSpacing: spec.track
    font.hintingPreference: Tokens.hinting
    font.features: tabular ? { "tnum": 1 } : { "tnum": 0 }
    lineHeightMode: Text.FixedHeight
    lineHeight: spec.line
    verticalAlignment: Text.AlignTop
    textFormat: Text.PlainText
    renderType: Tokens.renderType
}

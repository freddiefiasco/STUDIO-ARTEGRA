import QtQuick
import QtQuick.Window

CuFootSlot {
    id: foot
    objectName: "settingsFoot"
    property string footState: "empty"
    property string line: ""
    property string lineValue: ""
    property string lineDanger: ""
    property string lineTip: ""
    property string whiteText: ""
    property bool whiteEnabled: true
    property bool whiteBusy: false
    property string whiteTip: ""
    property string whiteDescription: ""
    property string tileText: ""
    property bool tileEnabled: true
    property bool tileBusy: false
    property string tileTip: ""
    property bool stopEnabled: true
    property string stopTip: ""
    property string cancelTip: ""
    signal startClicked()
    signal tileClicked()
    signal stopClicked()
    signal cancelClicked()
    signal detailsClicked(Item anchor)

    readonly property bool running: footState === "running" || footState === "stopping"
    readonly property bool stopping: footState === "stopping"
    readonly property rect commitRect: Qt.rect(0, Tokens.hFootStatus + Tokens.sp8, width, Tokens.hCommit)

    readonly property int rowTop: Tokens.hFootStatus + Tokens.sp8
    status: lineDanger !== "" ? lineDanger : line
    statusValue: lineDanger !== "" ? "" : lineValue
    statusDanger: lineDanger !== ""
    statusTip: lineDanger !== "" ? "" : lineTip
    detailsTip: "The cause and what to do"
    onDetails: foot.detailsClicked(foot.detailsItem)

    FontMetrics { id: bodyMetrics; font: Tokens.fontFor("body") }
    readonly property int stopNatural: Tokens.onGrid(Math.ceil(Math.max(bodyMetrics.advanceWidth("Stop after current"),
                                                                     bodyMetrics.advanceWidth("Stopping…"))) + 2 * Tokens.tileGlyphPad)
    readonly property int cancelFootprint: Math.ceil(bodyMetrics.advanceWidth("Cancel batch")) + 2 * Tokens.textControlPad
    readonly property bool folded: stopNatural + Tokens.sp8 + cancelFootprint > width

    CuButton {
        id: white
        objectName: "primaryAction"
        visible: foot.footState === "start" && foot.whiteText !== ""
        x: 0
        y: 0
        width: foot.width
        variant: "primary"
        text: foot.whiteText
        busy: foot.whiteBusy
        enabled: foot.whiteEnabled
        tooltip: foot.whiteTip
        accessibleDescription: foot.whiteDescription
        onClicked: foot.startClicked()
    }
    CuButton {
        id: tile
        objectName: foot.footState === "engine" ? "footTryAgain" : "againAction"
        visible: (foot.footState === "again" || foot.footState === "engine") && foot.tileText !== ""
        x: 0
        y: 0
        width: foot.width
        variant: "tile"
        commit: true
        ground: "ink"
        text: foot.tileText
        busy: foot.tileBusy
        enabled: foot.tileEnabled
        tooltip: foot.tileTip
        onClicked: foot.tileClicked()
    }
    CuButton {
        id: stopTile
        objectName: "bandStopAfter"
        visible: foot.running
        x: 0
        y: 0
        width: foot.folded ? foot.width : Math.max(0, foot.width - foot.cancelFootprint - Tokens.sp8)
        variant: "tile"
        commit: true
        ground: "ink"
        text: foot.stopping ? "Stopping…" : "Stop after current"
        busy: foot.stopping
        enabled: foot.stopEnabled || foot.stopping
        tooltip: foot.stopTip
        folded: foot.folded ? [{ label: "Cancel batch…", value: "cancel", danger: true }] : []
        onClicked: foot.stopClicked()
        onMenuChosen: (value) => { if (value === "cancel") foot.cancelClicked() }
    }
    CuButton {
        id: cancel
        objectName: "statusCancel"
        visible: foot.running && !foot.folded
        x: Tokens.snap(foot.width - width, foot.dpr)
        y: 0
        variant: "danger"
        commit: true
        ground: "ink"
        text: "Cancel batch"
        tooltip: foot.cancelTip
        accessibleDescription: "Cancel the batch"
        onClicked: foot.cancelClicked()
    }
}

import QtQuick
import QtQuick.Templates as T
import QtQuick.Window
import "format.js" as F

Item {
    id: caption
    objectName: "viewerCaption"

    property var viewer: null
    readonly property var tab: viewer ? viewer.tab : null
    readonly property var row: viewer ? viewer.row : null
    readonly property bool hasRow: viewer !== null && viewer.hasRow && row !== null && row !== undefined
    readonly property bool failed: hasRow && viewer.failedShown
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    property string mode: "full"
    readonly property bool folded: false
    readonly property real slotHeight: Tokens.capSlot
    readonly property real drawnHeight: Tokens.capSlot
    readonly property real naturalWidth: width
    property alias message: caption
    property bool detailsOpen: detailsPopup.opened

    readonly property int barY: Tokens.sp8
    readonly property int l1Y: Tokens.sp16
    readonly property int l2Y: 36
    readonly property int actionsY: 20

    readonly property string rowKey: viewer ? viewer.rowKey : ""
    onRowKeyChanged: { detailsPopup.close(); tile.closeMenu(); retry.closeMenu() }

    CuPassRuler {
        id: ruler
        x: caption.viewer ? caption.viewer.barX : 0
        y: caption.barY
        width: caption.viewer ? caption.viewer.barW : caption.width
        visible: caption.hasRow && caption.viewer.rulerShown
        value: caption.viewer ? caption.viewer.barValue : 0
        segments: caption.viewer ? caption.viewer.barSegments : [1, 1]
        tip: caption.viewer ? caption.viewer.rulerTip : ""
        imageId: caption.hasRow ? caption.row.key : ""
        pass: caption.viewer ? caption.viewer.rulerPass : ""
        step: caption.viewer ? caption.viewer.rulerStep : 0
    }

    readonly property var actionOrder: [retry, details, showFile, useSettings, againStandard, tile]
    readonly property var actionXs: {
        var out = {}
        var edge = caption.width
        var first = true
        var left = caption.width
        for (var i = actionOrder.length - 1; i >= 0; --i) {
            var it = actionOrder[i]
            if (!it || !it.visible) continue
            var bleed = it.isText ? Tokens.textControlPad : 0
            var bodyRight = first ? edge + bleed : edge
            var x = Tokens.snap(bodyRight - bleed - it.width, caption.dpr)
            out[it.objectName] = x
            left = x - bleed
            edge = left - Tokens.sp8
            first = false
        }
        out["_left"] = left
        return out
    }
    readonly property real actionsLeft: actionXs["_left"]
    readonly property bool actionsShown: actionsLeft < caption.width
    readonly property real lineRoom: Math.max(0, (actionsShown ? actionsLeft - Tokens.sp24 : caption.width))

    CuButton {
        id: retry
        objectName: "viewerRetry"
        visible: caption.failed
        x: caption.actionXs[objectName] !== undefined ? caption.actionXs[objectName] : 0
        y: caption.actionsY
        variant: "tile"
        ground: "stage"
        readonly property int smaller: caption.viewer ? caption.viewer.retrySmaller : 0
        text: !caption.hasRow ? "" : smaller > 0 ? "Try again at " + F.factor(smaller) : "Try again at " + F.factor(caption.row.factor)
        tooltip: smaller > 0 ? "Same settings, a smaller upscale" : "Same settings as before"
        menuModel: smaller > 0 && caption.hasRow ? [{ label: "Try again at " + F.factor(caption.row.factor), value: "same" }] : []
        onClicked: { if (smaller > 0) caption.tab.retryItem(caption.row, smaller); else caption.tab.retryItem(caption.row) }
        onMenuChosen: (value) => { if (value === "same") caption.tab.retryItem(caption.row) }
    }
    CuButton {
        id: details
        objectName: "viewerFailDetails"
        visible: caption.failed
        x: caption.actionXs[objectName] !== undefined ? caption.actionXs[objectName] : 0
        y: caption.actionsY
        variant: "text"
        ground: "stage"
        text: "Details"
        tooltip: "The log reference for this image"
        accessibleDescription: detailsPopup.opened ? "Hide the log reference" : "Show the log reference"
        onClicked: detailsPopup.opened ? detailsPopup.close() : detailsPopup.openAbove(details)
    }
    CuButton {
        id: showFile
        objectName: "viewerShowInExplorer"
        visible: caption.hasRow && caption.viewer.doneActionsShown && String(caption.row.output || "") !== ""
        x: caption.actionXs[objectName] !== undefined ? caption.actionXs[objectName] : 0
        y: caption.actionsY
        variant: "text"
        ground: "stage"
        text: "Show file"
        tooltip: "Show the result in Explorer"
        onClicked: caption.tab.openPath(caption.row.output, "file location")
    }
    CuButton {
        id: useSettings
        objectName: "viewerUseSettings"
        visible: caption.hasRow && caption.viewer.doneActionsShown && caption.viewer.useSettingsSupported
        x: caption.actionXs[objectName] !== undefined ? caption.actionXs[objectName] : 0
        y: caption.actionsY
        variant: "text"
        ground: "stage"
        text: "Use these settings"
        tooltip: "Sets the settings to what this image was made with"
        onClicked: caption.viewer.useTheseSettings()
    }
    CuButton {
        id: againStandard
        objectName: "viewerAgainStandard"
        visible: caption.hasRow && caption.viewer.doneActionsShown && caption.row.run !== undefined && caption.row.run !== null
                 && caption.row.run.mode === "fast" && caption.tab !== null && typeof caption.tab.upscaleAgainStandard === "function"
        x: caption.actionXs[objectName] !== undefined ? caption.actionXs[objectName] : 0
        y: caption.actionsY
        variant: "tile"
        ground: "stage"
        text: "Upscale again in Standard"
        tooltip: "Makes this image again in Standard, for a final"
        onClicked: caption.tab.upscaleAgainStandard(caption.row)
    }
    FontMetrics { id: tileMetrics; font: Tokens.fontFor("body") }
    CuButton {
        id: tile
        objectName: "viewerTile"
        readonly property bool shown: caption.hasRow && caption.viewer.tileKind !== ""
        visible: shown
        x: caption.actionXs[objectName] !== undefined ? caption.actionXs[objectName] : 0
        y: caption.actionsY
        width: Math.max(implicitWidth, shown && caption.viewer.tileKind === "stop"
                        ? Tokens.onGrid(Math.ceil(tileMetrics.advanceWidth("Stop this image")) + 2 * Tokens.tileGlyphPad) : 0)
        variant: "tile"
        ground: "stage"
        text: caption.viewer ? caption.viewer.tileLabel : ""
        tooltip: caption.viewer ? caption.viewer.tileTip : ""
        busy: caption.viewer !== null && (caption.viewer.actionBusy || caption.viewer.tilePending)
        menuModel: caption.viewer !== null && caption.viewer.tileMenu ? [{ label: caption.viewer.asBeforeLabel, value: "asBefore" }] : []
        onClicked: caption.viewer.tileClicked()
        onMenuChosen: (value) => { if (value === "asBefore") caption.viewer.queueAgain(true) }
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.RightButton
            enabled: caption.viewer !== null && caption.viewer.tileMenu
            onClicked: tile.openMenu()
        }
        Keys.onMenuPressed: (event) => { if (caption.viewer.tileMenu) { tile.openMenu(); event.accepted = true } }
    }
    readonly property Item tileMore: tile
    readonly property real nameActionsW: actionsShown ? caption.width - actionsLeft : 0

    FontMetrics { id: nameMetrics; font: Tokens.fontFor("body") }
    FontMetrics { id: factMetrics; font: factText.font }
    readonly property string factFull: viewer ? viewer.captionFact : ""
    readonly property real factW: factFull !== "" ? Math.ceil(factMetrics.advanceWidth(factFull)) : 0
    readonly property real nameNatural: hasRow ? Math.ceil(nameMetrics.advanceWidth(nameText.name)) : 0
    readonly property real nameFloor: hasRow ? Math.min(nameNatural, Math.max(Tokens.nameFloors(nameText.name, nameMetrics).project, 160)) : 0
    readonly property bool factShown: factFull !== "" && lineRoom - factW - Tokens.sp12 >= nameFloor
    Item {
        id: l1
        objectName: "viewerNameLine"
        visible: caption.hasRow
        x: 0
        y: caption.l1Y
        width: caption.lineRoom
        height: nameText.lineBox
        CuName {
            id: nameText
            objectName: "viewerTitle"
            x: 0
            y: 0
            role: "body"
            color: Tokens.text1
            name: caption.viewer ? caption.viewer.captionName : ""
            maxWidth: Math.max(40, caption.lineRoom - (caption.factShown ? caption.factW + Tokens.sp12 : 0))
            text: {
                var n = name
                var m = /^(.*)(_cu\d+x(?:_\d+)?)(\.[A-Za-z0-9]+)$/.exec(n)
                if (!m || nameMetrics.advanceWidth(n) <= maxWidth) return Tokens.elideName(n, maxWidth, nameMetrics, false)
                var e = Tokens.elideName(m[1] + m[3], maxWidth - nameMetrics.advanceWidth(m[2]), nameMetrics, false)
                return e.slice(0, e.length - m[3].length) + m[2] + m[3]
            }
            HoverHandler { id: titleHover }
            CuHoverTip { shown: titleHover.hovered && nameText.elided; text: shown ? nameText.name : "" }
            Accessible.role: Accessible.Heading
        }
        CuText {
            id: factText
            objectName: "viewerSizes"
            visible: caption.factShown
            x: Tokens.snap(nameText.width + Tokens.sp12, caption.dpr)
            y: Tokens.snap(nameText.baselineOffset - baselineOffset, caption.dpr)
            role: "meta"
            tabular: true
            color: Tokens.text3
            text: caption.factFull
        }
    }

    readonly property string l2Kind: !hasRow ? "" : viewer.stateLine !== "" ? "state"
                                     : (viewer.haltLine !== "" || viewer.refusalLine !== "") ? "halt"
                                     : viewer.captionFacts !== "" ? "facts" : ""
    readonly property string l2Text: l2Kind === "state" ? viewer.stateLine
                                     : l2Kind === "halt" ? (viewer.haltLine !== "" ? viewer.haltLine : viewer.refusalLine)
                                     : l2Kind === "facts" ? viewer.captionFacts : ""
    readonly property string l2Quiet: hasRow && viewer.readingBQuiet ? viewer.readingB : ""
    FontMetrics { id: l2Metrics; font: Tokens.fontFor("meta", true) }
    readonly property string l2Shown: {
        if (caption.l2Kind !== "facts") return caption.l2Text
        var parts = caption.l2Text.split(", ")
        for (var n = parts.length; n >= 1; --n) {
            var t = parts.slice(0, n).join(", ")
            if (Math.ceil(l2Metrics.advanceWidth(t)) <= caption.lineRoom) return t
        }
        return parts[0]
    }
    Item {
        id: l2
        objectName: "viewerLine2"
        visible: caption.hasRow && caption.l2Kind !== ""
        x: 0
        y: caption.l2Y
        width: caption.lineRoom
        height: l2Text.lineBox
        CuText {
            id: l2Text
            objectName: caption.l2Kind === "state" ? "viewerState" : caption.failed ? "viewerFailText"
                        : caption.l2Kind === "halt" ? "viewerNote" : "viewerFacts"
            x: 0
            y: 0
            width: Math.min(Math.ceil(implicitWidth), l2.width - (quietText.visible ? quietText.width + Tokens.sp12 : 0))
            role: caption.l2Kind === "facts" ? "meta" : "body"
            tabular: true
            elide: Text.ElideRight
            color: caption.l2Kind === "state" ? Tokens.text1 : caption.l2Kind === "halt" ? Tokens.text2 : Tokens.text3 // gitleaks:allow -- colour-token expression
            text: caption.l2Shown
            HoverHandler { id: l2Hover }
            CuHoverTip { shown: l2Hover.hovered && (l2Text.truncated || caption.l2Shown !== caption.l2Text); text: shown ? caption.l2Text : "" }
        }
        CuText {
            id: quietText
            objectName: "viewerStep"
            visible: caption.l2Quiet !== "" && caption.l2Kind === "state"
            x: Tokens.snap(Math.ceil(l2Text.width) + Tokens.sp12, caption.dpr)
            y: Tokens.snap(l2Text.baselineOffset - baselineOffset, caption.dpr)
            role: "meta"
            color: Tokens.text3
            text: caption.l2Quiet
        }
    }

    T.Popup {
        id: detailsPopup
        objectName: "viewerFailReferenceRow"
        padding: 0
        modal: false
        focus: true
        closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent
        implicitWidth: Math.min(320,
                                Math.ceil(Math.max(refText.implicitWidth, copyButton.width)) + 2 * Tokens.sp16)
        implicitHeight: Tokens.sp16 + refText.height + Tokens.sp8 + copyButton.height + Tokens.sp8
        function openAbove(item) {
            var p = item.mapToItem(caption, 0, 0)
            var w = implicitWidth
            x = Tokens.snap(p.x + item.width - w, caption.dpr)
            var above = p.y - implicitHeight - Tokens.sp8
            var room = caption.Window.window && caption.Window.window.contentItem
                       ? caption.mapToItem(caption.Window.window.contentItem, 0, above).y : above
            y = Tokens.snap(room >= 0 ? above : p.y + item.height + Tokens.sp8, caption.dpr)
            open()
        }
        background: CuPlate {}
        enter: Transition { NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: Tokens.durFloatIn } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: Tokens.durFloatOut } }
        contentItem: Item {
            CuText {
                id: refText
                objectName: "viewerFailReference"
                x: Tokens.sp16
                y: Tokens.sp16
                width: Math.min(Math.ceil(implicitWidth), detailsPopup.width - 2 * Tokens.sp16)
                wrapMode: Text.WordWrap
                role: "meta"
                tabular: true
                color: Tokens.text2
                text: !caption.hasRow ? "" : (caption.viewer.failText !== caption.viewer.failCause ? caption.viewer.failText + "\n" : "")
                                             + "Log reference " + (caption.row.logRef !== "" ? caption.row.logRef : "not given") + ", batch "
                                             + caption.row.jobId + ", image " + caption.row.itemId
            }
            CuButton {
                id: copyButton
                objectName: "viewerFailCopy"
                x: Tokens.sp16
                y: refText.y + refText.height + Tokens.sp8
                visible: caption.hasRow && caption.row.logRef !== ""
                variant: "text"
                ground: "float"
                text: "Copy details"
                onClicked: {
                    caption.tab.copyText("Artegra Enhancer log reference " + caption.row.logRef + " (batch " + caption.row.jobId
                                         + ", image " + caption.row.itemId + "): " + caption.row.errorText)
                    detailsPopup.close()
                }
            }
        }
    }
}

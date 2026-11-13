import QtQuick
import QtQuick.Window
import "format.js" as F

Item {
    id: row
    property var tab: null
    property Item rail: null
    property var view: null
    property Item tray: rail
    property bool listFocused: false
    property int inset: Tokens.legInset

    required property var model
    required property int index
    required property string key
    required property string kind
    required property string mediaId
    required property string name
    required property string path
    required property real srcW
    required property real srcH
    required property real outW
    required property real outH
    required property int factor
    required property string status
    required property real progress
    required property int stage
    required property int stages
    required property string message
    required property string errorText
    required property string thumbUrl
    required property bool duplicate
    required property bool alpha
    required property string refusedReason
    required property int maxFactor
    required property string group
    required property int place

    function role(n, d) { return row.model && row.model[n] !== undefined && row.model[n] !== null ? row.model[n] : d }
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    function near(v) { return Tokens.snap(v + 0.5 / dpr, dpr) }

    readonly property bool isHead: kind === "heading" || kind === "fold" || kind === "cleared"
    readonly property bool isRemoved: kind === "removed"
    readonly property bool isImage: kind === "input" || kind === "job"
    readonly property bool isCleared: false
    readonly property string removedState: isRemoved ? String(role("removedState", "")) : ""
    readonly property bool undoFailed: removedState === "failed"
    readonly property string removedText: isRemoved ? String(role("removedText", "")) : ""

    readonly property bool running: rail !== null && rail.running === true
    readonly property bool working: meta.working
    readonly property bool queued: meta.queued
    readonly property bool refused: meta.refused
    readonly property bool waitingInput: kind === "input" && !refused
    readonly property bool stoppedRow: meta.stopped
    readonly property bool failedRow: meta.failed
    readonly property bool doneRow: meta.done
    readonly property bool busy: working

    readonly property bool selected: isImage && tab !== null && tab.selectedKey === key
    readonly property bool keyCurrent: listFocused && selected
    readonly property bool pointed: rowHover.hovered
    readonly property bool lifted: isImage && (selected || pointed)

    readonly property string inViewKey: rail !== null && rail.inViewKey !== undefined ? rail.inViewKey
                                        : (tab !== null && tab.readingKey !== undefined ? tab.readingKey : "")
    readonly property bool stateUnderPicture: (working || stoppedRow) && inViewKey !== "" && inViewKey === key
    readonly property bool shownInViewer: isImage && tab !== null && tab.selectedKey === key && tab.resultsOpen !== true
                                          && tab.viewerItem !== undefined && tab.viewerItem !== null && tab.viewerItem.hasRow === true
    readonly property bool factsUnderPicture: stateUnderPicture || (failedRow && inViewKey !== "" && inViewKey === key)
                                              || (doneRow && shownInViewer)
    readonly property string livePass: {
        var p = String(role("livePass", ""))
        if (p !== "" || !working || tab === null || tab.viewerItem === undefined || tab.viewerItem === null) return p
        var feed = tab.viewerItem.liveFeed
        if (!feed || !feed.items) return ""
        var it = feed.items[String(role("jobId", "")) + ":" + String(role("itemId", ""))]
        return it && it.state === "sampling" && it.pass ? String(it.pass) : ""
    }
    readonly property bool fastResult: {
        if (kind !== "job" || status !== "done") return false
        if (/_fast\.[A-Za-z0-9]+$/.test(String(role("output", "")))) return true
        if (String(role("mode", "")) === "fast") return true
        var r = sourceRow()
        return r !== null && r !== undefined && r.effective !== undefined && r.effective !== null && r.effective.mode === "fast"
    }
    CuTrayStatus {
        id: meta
        kind: row.kind
        state: row.status
        outW: row.outW
        outH: row.outH
        factor: row.factor
        ownFactor: row.role("ownFactor", false) === true
        ownMode: row.kind === "input" && row.tab !== null && row.tab.anyInputFast === true && String(row.role("mode", "")) === "standard"
        refusedReason: row.refusedReason
        maxFactor: row.maxFactor
        tookS: Number(row.role("tookS", -1))
        gpu: Number(row.role("gpu", -1))
        cardsText: String(row.role("cardsText", ""))
        atPass: String(row.role("atPass", ""))
        atStep: Number(row.role("atStep", -1))
        livePass: row.livePass
        message: row.message
        errorText: row.errorText
        inView: row.factsUnderPicture
        fastResult: row.fastResult
        removedState: row.removedState
        removedText: row.removedText
    }
    readonly property string metaText: meta.full
    readonly property bool twoLines: isImage || isRemoved
    readonly property real metaRoom: Math.max(0, width - textX - inset - (word.visible ? Math.ceil(word.width) + Tokens.sp16 : 0))
    FontMetrics { id: metaFm; font: Tokens.fontFor("meta", true) }
    readonly property string metaShown: {
        if (!word.visible || metaFm.advanceWidth(meta.full) <= metaRoom) return meta.full
        if (metaFm.advanceWidth(meta.shortText) <= metaRoom) return meta.shortText
        return meta.shorterText
    }

    readonly property int retryFactor: {
        var s = F.smallerScale(factor, tab && tab.controlsInfo ? tab.controlsInfo.scales : null)
        return s > 0 ? s : factor
    }
    readonly property string wordText: {
        if (!isImage) return ""
        if (waitingInput || queued) return "Remove"
        if (refused) return maxFactor > 0 ? "Use " + F.scaleLabel(maxFactor) : "Remove"
        if (doneRow) return String(role("output", "")) !== "" ? "Show file" : ""
        if (failedRow) return retryFactor < factor ? "Try again at " + F.scaleLabel(retryFactor) : "Try again"
        if (stoppedRow) return running ? "Queue again" : "Upscale again"
        return ""
    }
    readonly property string wordTip: {
        if (waitingInput || (refused && maxFactor <= 0)) return Tokens.keyTip("Remove from the list", "Delete")
        if (queued) return Tokens.keyTip("Take out of the batch", "Delete")
        if (refused) return "Upscale this image at " + F.scaleLabel(maxFactor)
        if (doneRow) return "Show the result in File Explorer"
        if (failedRow) return "Try again at " + F.scaleLabel(retryFactor) + " with the same settings"
        if (stoppedRow) return running ? "Queue this image again, at the head of Next" : "Upscale this image again"
        return ""
    }
    function sourceRow() { return tab !== null && tab.rowsByKey ? tab.rowsByKey[key] : null }
    function act() {
        if (tab === null) return
        var r = sourceRow()
        if (waitingInput || (refused && maxFactor <= 0)) { tab.removeInput(mediaId); return }
        if (queued) { if (r) tab.requestCancelItem(r); return }
        if (refused) {
            if (typeof tab.useFactorFor === "function") tab.useFactorFor([r], maxFactor)
            else tab.startInputAt(mediaId, maxFactor)
            return
        }
        if (doneRow) { tab.openPath(String(role("output", "")), "file location"); return }
        if (failedRow) { if (r) tab.retryItem(r, retryFactor < factor ? retryFactor : undefined); return }
        if (stoppedRow && r) {
            if (typeof tab.queueAgain === "function") tab.queueAgain([r], false)
            else tab.requestRedo(r)
        }
    }

    readonly property string liveThumb: String(role("liveThumbUrl", ""))
    readonly property string thumbSource: {
        if (!isImage || tab === null || !tab.everConnected || mediaId === "") return ""
        if (liveThumb !== "" && (working || stoppedRow || failedRow)) return tab.service.mediaUrl(liveThumb)
        return tab.service.mediaUrl(thumbUrl !== "" ? thumbUrl : "/api/media/" + encodeURIComponent(mediaId) + "/thumb")
    }
    readonly property string proxySource: {
        var p = String(role("proxyUrl", ""))
        return isImage && tab !== null && tab.everConnected && p !== "" ? tab.service.mediaUrl(p) : ""
    }
    readonly property real aspect: srcW > 0 && srcH > 0 ? srcW / srcH : 0

    readonly property int rowHeight: Tokens.hRowMedia
    readonly property real textX: inset + Tokens.miniBoxWidth + Tokens.sp12
    readonly property real nameRoom: Math.max(0, width - textX - inset)
    FontMetrics { id: nameFm; font: Tokens.fontFor("body") }
    readonly property string shownName: {
        if (!isImage && !isRemoved) return ""
        var u = rail && rail.model ? rail.model.uniformName(name) : ""
        return u !== "" ? u : Tokens.elideName(name, nameRoom, nameFm, false)
    }
    readonly property var dropSpot: rail !== null && rail.dropSpot !== undefined ? rail.dropSpot : null
    readonly property bool dropBelow: dropSpot !== null && dropSpot.after === true && dropSpot.key === key
    readonly property bool dropAbove: dropSpot !== null && dropSpot.after === false && dropSpot.key === key
    readonly property int dropRoom: dropBelow || dropAbove ? Tokens.hRowMedia : 0
    readonly property int bodyTop: dropAbove ? Tokens.hRowMedia : 0
    readonly property int entryHeight: isHead ? Tokens.hGroupHead : rowHeight

    width: view ? view.width : (rail ? rail.width : 0)
    height: entryHeight + dropRoom

    Accessible.role: isHead ? Accessible.Heading : Accessible.ListItem
    Accessible.name: isHead ? String(role("title", ""))
                   : name + (metaText !== "" ? ", " + metaText : "") + (isRemoved ? "" : ", " + F.size(srcW, srcH))
    Accessible.description: isRemoved && undoFailed ? removedText : ""
    Accessible.selected: selected
    Accessible.onPressAction: if (isImage) tab.selectKey(key)

    CuTrayGroupHeading {
        visible: row.isHead
        y: row.bodyTop
        width: row.width
        height: Tokens.hGroupHead
        rail: row.rail
        tab: row.tab
        group: row.group
        kind: row.isHead ? row.kind : ""
        title: String(row.role("title", ""))
        figure: Number(row.role("figure", -1))
        action: String(row.role("action", ""))
        first: row.role("first", false) === true
        foldable: row.role("foldable", false) === true
        folded: row.role("folded", false) === true
        danger: row.role("danger", false) === true
    }

    CuListRow {
        id: media
        objectName: "rowBody"
        visible: row.isImage
        y: row.bodyTop
        width: row.width
        height: Tokens.hRowMedia
        kind: "media"
        ground: "ink"
        inset: row.inset
        twoLines: row.twoLines
        selected: row.selected
        text: row.isImage ? row.shownName : ""
        meta: row.isImage ? row.metaShown : ""
        progress: meta.barShown ? row.progress : -1
        Accessible.ignored: true
        leading: CuMiniature {
            objectName: "rowMiniature"
            maxWidth: Tokens.miniBoxWidth
            maxHeight: Tokens.miniBoxHeight
            horizontalAlignment: Qt.AlignLeft
            source: row.thumbSource
            aspect: row.aspect
            hasAlpha: row.alpha
            surface: media.bodyShown ? media.bodyColor : Tokens.ink
        }
        trailing: CuHoverWord {
            id: word
            objectName: "rowAction"
            ground: "ink"
            rowHovered: row.isImage && row.pointed && !row.wordMuted && row.wordText !== ""
            rowFocused: row.keyCurrent && row.wordText !== ""
            visible: row.isImage && row.wordText !== "" && opacity > 0
            text: row.wordText
            tooltip: row.wordTip
            accessibleDescription: row.wordTip + ": " + row.name
            onClicked: { row.wordMuted = true; row.act() }
        }
        onClicked: {
            if (row.view) row.view.takePointerFocus()
            row.tab.selectKey(row.key)
        }
        onPressedChanged: if (pressed) { row.plateMuted = true; if (row.rail) row.rail.closePlate(row) }
    }
    CuFocusRing {
        objectName: "rowFocusRing"
        target: media
        shown: row.keyCurrent && row.isImage
        inset: true
        targetRadius: 0
    }
    property bool wordMuted: false

    CuText {
        id: removedName
        objectName: "rowRemovedName"
        visible: row.isRemoved
        x: row.textX
        y: row.bodyTop + Tokens.sp4
        width: Math.min(Math.ceil(implicitWidth), row.nameRoom)
        role: "body"
        color: Tokens.text3
        text: row.isRemoved ? row.shownName : ""
        Accessible.ignored: true
    }
    CuText {
        id: removedWords
        objectName: "rowRemovedText"
        visible: row.isRemoved
        x: row.textX
        y: row.bodyTop + Tokens.sp24
        width: Math.min(Math.ceil(implicitWidth), Math.max(0, row.nameRoom - Math.ceil(undoBtn.width) - Tokens.sp8 - Tokens.textBleed))
        elide: Text.ElideRight
        role: "meta"
        color: Tokens.text3
        text: row.isRemoved ? meta.full : ""
        Accessible.ignored: true
    }
    CuButton {
        id: undoBtn
        objectName: "rowUndo"
        visible: row.isRemoved
        enabled: row.removedState !== "busy"
        x: Tokens.snap(removedWords.x + Math.ceil(removedWords.width) + Tokens.sp8 + Tokens.textBleed, row.dpr)
        y: row.near(removedWords.y + removedWords.baselineOffset - (labelItem.y + labelItem.baselineOffset))
        variant: "text"
        labelRole: "small"
        buttonHeight: Tokens.hRowWord
        text: "Undo"
        tooltip: row.undoFailed ? row.removedText : ""
        accessibleDescription: row.undoFailed ? row.removedText : "Puts " + row.name + " back in the list where it was"
        onClicked: row.tab.undoRemoval(row.key)
    }

    Loader {
        active: row.dropRoom > 0
        y: row.dropAbove ? 0 : row.entryHeight
        width: row.width
        height: Tokens.hRowMedia
        sourceComponent: CuQueueDropRow {
            inset: row.inset
            words: row.rail !== null && row.rail.dropWords !== undefined ? row.rail.dropWords : ""
        }
    }

    HoverHandler { id: rowHover; enabled: row.isImage }

    property bool plateMuted: false
    readonly property bool plateWanted: isImage && pointed && !plateMuted && !word.hovered && !media.pressed
    onPointedChanged: { if (!pointed) { plateMuted = false; wordMuted = false } }
    onPlateWantedChanged: {
        if (plateWanted) plateTimer.restart()
        else { plateTimer.stop(); if (rail) rail.closePlate(row) }
    }
    Timer {
        id: plateTimer
        interval: Tokens.tooltipDelay
        onTriggered: { if (row.plateWanted && row.rail) row.rail.openPlate(row) }
    }
    ListView.onReused: { plateMuted = false; wordMuted = false; plateTimer.stop() }
    ListView.onPooled: { plateTimer.stop(); if (rail) rail.closePlate(row) }
}

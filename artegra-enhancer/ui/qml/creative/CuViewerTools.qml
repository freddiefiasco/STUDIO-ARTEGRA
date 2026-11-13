import QtQuick
import QtQuick.Templates as T
import QtQuick.Window

Item {
    id: tools
    property var viewer: null
    readonly property var tab: viewer ? viewer.tab : null
    readonly property bool maskShown: viewer !== null && viewer.mask !== null
    readonly property bool stale: viewer !== null && viewer.maskStale
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property real controlY: Tokens.snap((Tokens.hToolLine - Tokens.hControl) / 2, dpr)
    objectName: "viewerTools"
    height: Tokens.hToolLine

    CuSegmented {
        id: measureFull
        visible: false
        equalCells: false
        ground: "stage"
        model: [{ label: "Before", value: "before" }, { label: "After", value: "after" }, { label: "Split", value: "split" },
                { label: "Side by side", value: "side" }]
    }
    CuSegmented {
        id: measureFolded
        visible: false
        equalCells: false
        ground: "stage"
        model: [{ label: "Before", value: "before" }, { label: "After", value: "after" }, { label: "Split", value: "split" }]
    }
    CuIconButton {
        id: measureProtect
        visible: false
        ground: "stage"
        swatch: Tokens.protectTint
        checkable: true
        text: "Protected areas"
    }
    CuSegmented {
        id: measureZoom
        visible: false
        equalCells: false
        tabular: true
        ground: "stage"
        model: [{ label: "Fit", value: "fit", sub: "100%" }, { label: "100%", value: "actual" }]
    }
    CuSegmented {
        id: measureZoomBare
        visible: false
        equalCells: false
        tabular: true
        ground: "stage"
        model: [{ label: "Fit", value: "fit" }, { label: "100%", value: "actual" }]
    }
    FontMetrics { id: figureMetrics; font: Tokens.fontFor("body", true) }
    readonly property real gap: Tokens.sp8
    readonly property real middle: Tokens.sp24
    readonly property real viewFullW: measureFull.implicitWidth
    readonly property real viewFoldW: measureFolded.implicitWidth + Tokens.chevronCell
    readonly property real protectFullW: measureProtect.implicitWidth
    readonly property real protectKeyW: Tokens.hControl
    readonly property real freeFigureW: Math.ceil(figureMetrics.advanceWidth("800%")) + gap
    function zoomGroupW(sub) { return Math.max(sub ? measureZoom.implicitWidth : measureZoomBare.implicitWidth, freeFigureW + measureZoomBare.implicitWidth) }
    readonly property bool fold1: width < viewFullW + middle + protectFullW + gap + zoomGroupW(true)
    readonly property bool fold2: fold1 && width < viewFoldW + middle + protectFullW + gap + zoomGroupW(true)
    readonly property bool fold3: fold2 && width < viewFoldW + middle + protectKeyW + gap + zoomGroupW(true)
    readonly property real middleNow: right.x - (view.visible ? view.x + view.width + (splitMore.visible ? splitMore.width : 0) : 0)

    readonly property bool hasResult: viewer !== null && viewer.sideAvailable === true
    readonly property bool canSplit: viewer !== null && viewer.compareAvailable
    readonly property bool second: viewer !== null && viewer.secondAvailable
    readonly property bool side: viewer !== null && viewer.sideBySide === true
    readonly property string secondLabel: viewer ? viewer.secondLabel : "After"
    readonly property string secondTip: secondLabel === "Live" ? Tokens.keyTip(viewer ? viewer.liveTip : "", "B")
                                        : secondLabel === "Last frame" ? Tokens.keyTip("The last frame before it stopped. Hold Space for the original.", "B")
                                        : Tokens.keyTip("After, the result. Hold Space for the original.", "B")
    CuSegmented {
        id: view
        objectName: "viewerViewControl"
        visible: tools.second
        x: 0
        y: tools.controlY
        ground: "stage"
        equalCells: false
        accessibleName: "View"
        model: {
            var m = [{ label: "Before", value: "before", tip: Tokens.keyTip("Before, the original", "B") },
                     { label: tools.secondLabel, value: "after", tip: tools.secondTip }]
            if (!tools.canSplit) return m
            m.push({ label: "Split", value: "split", tip: Tokens.keyTip("Split, before on the left", "S") })
            if (tools.hasResult && !tools.fold1) m.push({ label: "Side by side", value: "side", tip: Tokens.keyTip("Side by side, the same place in both", "Y") })
            return m
        }
        currentValue: !tools.viewer ? "before"
                      : (tools.viewer.viewCell === "split" && tools.side && tools.hasResult ? "side" : tools.viewer.viewCell)
        onActivated: (value) => {
            if (value === "side") { tools.viewer.sideBySide = true; tools.viewer.viewMode = "split" }
            else if (value === "split") { if (tools.hasResult) tools.viewer.sideBySide = false; tools.viewer.viewMode = "split" }
            else tools.viewer.chooseView(value)
        }
    }
    T.Control {
        id: splitMore
        objectName: "viewerSplitMore"
        visible: view.visible && tools.hasResult && tools.fold1
        x: view.x + view.width
        y: view.y
        width: Tokens.chevronCell
        height: Tokens.hControl
        hoverEnabled: true
        focusPolicy: Qt.TabFocus
        readonly property int insetDev: Tokens.devPx("inset", tools.dpr)
        readonly property bool menuOpen: morePopup.visible
        readonly property bool chosen: tools.side && tools.hasResult && tools.viewer !== null && tools.viewer.viewCell === "split"
        readonly property bool lit: hovered || moreTap.pressed || menuOpen || visualFocus || chosen
        Accessible.checked: chosen
        Accessible.role: Accessible.ButtonMenu
        Accessible.name: "More ways to compare"
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Down) {
                morePopup.open()
                event.accepted = true
            }
        }
        Rectangle {
            anchors.fill: parent
            color: Tokens.wellOn("stage")
            radius: Tokens.radiusControl
        }
        Item {
            scale: 1 / tools.dpr
            transformOrigin: Item.TopLeft
            Rectangle {
                x: 0
                y: splitMore.insetDev
                width: Tokens.devPx("line", tools.dpr)
                height: Math.round(splitMore.height * tools.dpr) - 2 * splitMore.insetDev
                color: Tokens.reveal
                antialiasing: false
            }
            Rectangle {
                visible: splitMore.chosen && !(splitMore.hovered || moreTap.pressed)
                x: splitMore.insetDev + Tokens.devPx("line", tools.dpr)
                y: splitMore.insetDev
                width: Math.round(splitMore.width * tools.dpr) - 2 * splitMore.insetDev - Tokens.devPx("line", tools.dpr)
                height: Math.round(splitMore.height * tools.dpr) - 2 * splitMore.insetDev
                color: Tokens.raisedOn("stage")
                antialiasing: false
            }
            Rectangle {
                visible: splitMore.hovered || moreTap.pressed
                x: splitMore.insetDev + Tokens.devPx("line", tools.dpr)
                y: splitMore.insetDev
                width: Math.round(splitMore.width * tools.dpr) - 2 * splitMore.insetDev - Tokens.devPx("line", tools.dpr)
                height: Math.round(splitMore.height * tools.dpr) - 2 * splitMore.insetDev
                color: moreTap.pressed ? Tokens.pressOn("stage") : Tokens.tileOn("stage")
                antialiasing: false
            }
        }
        CuIcon {
            x: Tokens.snap((splitMore.width - Tokens.iconBox) / 2, tools.dpr)
            y: Tokens.snap((splitMore.height - Tokens.iconBox) / 2, tools.dpr)
            iconName: "chevronDown"
            iconSize: Tokens.iconBox
            color: splitMore.lit ? Tokens.text1 : Tokens.text3
        }
        CuFocusRing { target: splitMore; shown: splitMore.visualFocus }
        MouseArea {
            id: moreTap
            anchors.fill: parent
            onClicked: morePopup.visible ? morePopup.close() : morePopup.open()
        }
        CuHoverTip { shown: splitMore.hovered && !splitMore.menuOpen; text: Tokens.keyTip("Side by side, and Split", "Y") }
        T.Popup {
            id: morePopup
            readonly property real roomBelow: {
                var w = splitMore.Window.window
                if (!w || !w.contentItem) return 1e6
                var p = splitMore.mapToItem(w.contentItem, 0, splitMore.height)
                return w.contentItem.height - p.y - Tokens.sp8
            }
            x: -view.cellW(view.count - 1)
            y: roomBelow >= implicitHeight + Tokens.sp4 ? splitMore.height + Tokens.sp4 : -implicitHeight - Tokens.sp4
            padding: 0
            modal: false
            focus: true
            closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent
            implicitWidth: moreMenu.implicitWidth
            implicitHeight: moreMenu.implicitHeight
            background: null
            enter: Transition { NumberAnimation { property: "opacity"; from: 0.0; to: 1.0; duration: Tokens.durFloatIn } }
            exit: Transition { NumberAnimation { property: "opacity"; from: 1.0; to: 0.0; duration: Tokens.durFloatOut } }
            onAboutToShow: moreMenu.reset()
            onOpened: moreMenu.forceActiveFocus(Qt.PopupFocusReason)
            contentItem: CuMenu {
                id: moreMenu
                objectName: "viewerCompareMenu"
                model: [{ label: "Split", value: "split" }, { label: "Side by side", value: "side" }]
                currentValue: tools.viewer && tools.viewer.viewCell === "split" ? (tools.side ? "side" : "split") : undefined
                minWidth: view.cellW(view.count - 1) + splitMore.width
                focus: true
                onChosen: (value) => {
                    morePopup.close()
                    tools.viewer.sideBySide = value === "side"
                    tools.viewer.viewMode = "split"
                }
                onCloseRequested: { morePopup.close(); splitMore.forceActiveFocus(Qt.TabFocusReason) }
            }
        }
    }

    Row {
        id: right
        objectName: "viewerZoomGroup"
        x: Tokens.snap(tools.width - width, tools.dpr)
        y: tools.controlY
        spacing: tools.gap
        CuIconButton {
            id: maskToggle
            objectName: "viewerMaskToggle"
            visible: tools.maskShown
            ground: "stage"
            swatch: Tokens.protectTint
            swatchEmpty: tools.stale
            text: "Protected areas"
            compact: tools.fold2
            checkable: true
            checked: tools.viewer !== null && tools.viewer.maskShown
            readonly property string staleWords: "Your protect choices changed after this preview. Preview again to update it."
            tooltip: compact ? (tools.stale ? "Protected areas. " + staleWords : Tokens.keyTip("Protected areas", "M"))
                     : (tools.stale ? staleWords : Tokens.keyTip(checked ? "Hide the protected areas" : "Show the protected areas", "M"))
            accessibleName: "Protected areas"
            onClicked: tools.tab.maskVisible = !tools.tab.maskVisible
        }
        CuText {
            id: freeFigure
            objectName: "viewerZoomText"
            visible: tools.viewer !== null && tools.viewer.freeZoom
            y: centredIn(Tokens.hControl)
            role: "body"
            tabular: true
            color: Tokens.text2
            text: tools.viewer ? tools.viewer.zoomFigure : ""
            Accessible.role: Accessible.StaticText
            Accessible.name: "Zoom " + text
        }
        CuSegmented {
            id: zoomControl
            objectName: "viewerZoom"
            ground: "stage"
            equalCells: false
            accessibleName: "Zoom"
            tabular: true
            width: tools.fold3 ? measureZoomBare.implicitWidth : measureZoom.implicitWidth
            readonly property bool atFit: tools.viewer !== null && tools.viewer.zoomMode === "fit"
            model: [
                { label: "Fit", value: "fit", sub: atFit && !tools.fold3 && tools.viewer ? tools.viewer.fitFigure : "",
                  tip: tools.fold3 && tools.viewer ? Tokens.keyTip("Fit, " + tools.viewer.fitFigure, "0")
                                                   : Tokens.keyTip("Fit, the whole picture. L for a loupe", "0") },
                { label: "100%", value: "actual",
                  tip: Tokens.keyTip(tools.viewer && tools.viewer.layoutInResult ? "One pixel of the result per screen pixel"
                                                                                 : "One pixel of the original per screen pixel", "1") }
            ]
            currentValue: tools.viewer === null ? "fit" : tools.viewer.zoomMode === "fit" ? "fit"
                          : (Math.abs(tools.viewer.zoom - 1) < 0.001 ? "actual" : undefined)
            onActivated: (value) => { if (value === "fit") tools.viewer.fit(); else tools.viewer.actualSize() }
        }
    }
    readonly property Item fitCell: zoomControl
    readonly property Item viewControl: view
    readonly property Item protectTile: maskToggle
}

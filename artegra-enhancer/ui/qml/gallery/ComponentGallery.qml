import QtQuick
import QtQuick.Window
import "../creative"
import "../creative/format.js" as F

Rectangle {
    id: page
    property string only: ""
    property int pageWidth: 1600
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property bool all: only === ""
    objectName: "componentGallery"
    width: pageWidth
    height: Math.ceil((sections.y + sections.height + 48) / 4) * 4
    color: Tokens.ink

    function hex(c) {
        function h2(v) { var s = Math.round(v * 255).toString(16).toUpperCase(); return s.length < 2 ? "0" + s : s }
        return (c.a < 0.999 ? "#" + h2(c.a) : "#") + h2(c.r) + h2(c.g) + h2(c.b)
    }
    function lum(c) {
        function ch(v) { return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
        return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b)
    }
    function ratio(a, b) {
        var la = lum(a), lb = lum(b)
        return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
    }

    component Section: Column {
        property string title: ""
        property string note: ""
        property string key: ""
        visible: page.all || page.only === key
        width: page.pageWidth - 64
        spacing: 16
        CuText { text: parent.title; role: "title"; color: Tokens.text1 }
        CuText { visible: parent.note !== ""; text: parent.note; role: "meta"; color: Tokens.text3; width: parent.width; elide: Text.ElideRight }
    }
    component Cells: Flow {
        width: page.pageWidth - 64
        spacing: 16
    }

    Column {
        id: sections
        x: 32
        y: 32
        spacing: 48

        Column {
            visible: page.all
            spacing: 8
            CuText { text: "Artegra Enhancer component gallery, v5"; role: "heading"; color: Tokens.text1 }
            CuText {
                height: 20
                text: "Scale " + Math.round(page.dpr * 100) + "%, corners " + Tokens.radiusControl + " px, the face "
                      + (Tokens.brandFace ? "Helvetica Neue" : Tokens.fallbackSans) + ". Every state is set by a property."
                role: "body"
                color: Tokens.text2
            }
        }

        Section {
            key: "type"
            title: "Type"
            note: ""
            Cells {
                Repeater {
                    model: [
                        { role: "meta", spec: "meta 12 / 16, 400, +0.1", sample: "Helper line, units, row meta, tooltips" },
                        { role: "body", spec: "body 13 / 18, 400, +0.05", sample: "Labels, values, names, menu items" },
                        { role: "bodyStrong", spec: "bodyStrong 13 / 18, 500", sample: "Group heading, the open tab" },
                        { role: "title", spec: "title 14 / 20, 500", sample: "Section title, the white block" },
                        { role: "heading", spec: "heading 18 / 24, 500, -0.2", sample: "Dialog and page title" }
                    ]
                    GalleryCell {
                        required property var modelData
                        name: modelData.spec
                        Column {
                            spacing: 4
                            CuText { height: Math.ceil(lineBox / 4) * 4; text: modelData.sample; role: modelData.role; color: Tokens.text1 }
                            CuText { height: Math.ceil(lineBox / 4) * 4; text: "3,840 × 2,400 → 7,680 × 4,800 px, 31%, 19:25"; role: modelData.role; tabular: true; color: Tokens.text2 }
                            CuText { height: Math.ceil(lineBox / 4) * 4; text: "1111 2222 0000 8888"; role: modelData.role; tabular: true; color: Tokens.text3 }
                        }
                    }
                }
            }
        }

        Section {
            key: "ramp"
            title: "Neutral ramp"
            note: ""
            Cells {
                Repeater {
                    model: [
                        { g: "ink", names: ["wellInk", "ink", "pressInk", "tileInk", "raisedInk"] },
                        { g: "stage", names: ["wellStage", "stage", "pressStage", "tileStage", "raisedStage"] },
                        { g: "float", names: ["wellFloat", "float", "pressFloat", "tileFloat", "raisedFloat"] }
                    ]
                    GalleryCell {
                        required property var modelData
                        name: "Bodies on " + modelData.g
                        ground: modelData.g
                        Row {
                            spacing: 0
                            Repeater {
                                model: modelData.names
                                Rectangle {
                                    required property string modelData
                                    width: 96
                                    height: 72
                                    color: Tokens[modelData]
                                    CuText { x: 8; y: 8; text: modelData; role: "meta"; color: Tokens.text1 }
                                    CuText { x: 8; y: 28; text: page.hex(Tokens[modelData]); role: "meta"; tabular: true; color: Tokens.text2 }
                                }
                            }
                        }
                    }
                }
                GalleryCell {
                    name: "Text tones, lines and marks"
                    Row {
                        spacing: 0
                        Repeater {
                            model: ["text1", "text2", "text3", "text4", "danger", "white", "rule", "reveal", "trackInk", "trackStage", "controlEdge", "protectTint"]
                            Rectangle {
                                required property string modelData
                                width: 96
                                height: 72
                                color: Tokens.ink
                                Rectangle { x: 8; y: 8; width: 80; height: 24; color: Tokens[modelData] }
                                CuText { x: 8; y: 36; text: modelData; role: "meta"; color: Tokens.text2 }
                                CuText { x: 8; y: 52; text: page.hex(Tokens[modelData]); role: "meta"; tabular: true; color: Tokens.text3 }
                            }
                        }
                    }
                }
            }
        }

        Section {
            key: "contrast"
            title: "Contrast pairs"
            note: ""
            Cells {
                Repeater {
                    model: ["wellInk", "ink", "pressInk", "tileInk", "raisedInk", "wellStage", "stage", "tileStage", "raisedStage", "wellFloat", "float", "tileFloat", "raisedFloat"]
                    GalleryCell {
                        required property string modelData
                        readonly property string surface: modelData
                        name: modelData
                        pad: 0
                        Rectangle {
                            width: 112
                            height: 112
                            color: Tokens[surface]
                            Column {
                                x: 8
                                y: 8
                                spacing: 4
                                Repeater {
                                    model: ["text1", "text2", "text3", "text4"]
                                    CuText {
                                        required property string modelData
                                        readonly property bool drawn: !(modelData === "text3" && surface !== "wellInk" && surface !== "ink" && surface !== "wellStage" && surface !== "stage" && surface !== "wellFloat")
                                        text: modelData + "  " + page.ratio(Tokens[modelData], Tokens[surface]).toFixed(1) + (drawn ? "" : "  never")
                                        role: "meta"
                                        tabular: true
                                        color: Tokens[modelData]
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Section {
            key: "marks"
            title: "Icons, device-px marks and snapped cells"
            note: ""
            Cells {
                GalleryCell {
                    name: "Glyphs, rest and lit (stroke " + Tokens.strokePx(page.dpr) + " dev)"
                    Column {
                        spacing: 8
                        Row {
                            spacing: 16
                            Repeater {
                                model: ["add", "addFolder", "folder", "grid", "panels", "panelsOff", "chevronRight", "chevronDown", "chevronUp", "chevronLeft"]
                                CuIcon { required property string modelData; iconName: modelData; color: Tokens.text3 }
                            }
                        }
                        Row {
                            spacing: 16
                            Repeater {
                                model: ["add", "addFolder", "folder", "grid", "panels", "panelsOff", "chevronRight", "chevronDown", "chevronUp", "chevronLeft"]
                                CuIcon { required property string modelData; iconName: modelData; color: Tokens.text1 }
                            }
                        }
                    }
                }
                GalleryCell {
                    name: "Marks at " + Math.round(page.dpr * 100) + "%"
                    Column {
                        spacing: 8
                        Repeater {
                            model: ["line", "beam", "bar", "tick", "check", "inset", "ring", "icon"]
                            Item {
                                required property string modelData
                                width: 224
                                height: 16
                                CuText { x: 0; y: 0; width: 96; text: modelData + "  " + Tokens.devPx(modelData, page.dpr) + " dev"; role: "meta"; tabular: true; color: Tokens.text2 }
                                Item {
                                    x: 112
                                    y: 8
                                    Rectangle {
                                        scale: 1 / page.dpr
                                        transformOrigin: Item.TopLeft
                                        width: Math.round(96 * page.dpr)
                                        height: Tokens.devPx(modelData, page.dpr)
                                        color: Tokens.text1
                                        antialiasing: false
                                    }
                                }
                            }
                        }
                    }
                }
                GalleryCell {
                    name: "Centred in a 333 × 211 room, bottom-anchored to H 211"
                    contentWidth: 333
                    contentHeight: 211
                    Rectangle {
                        id: oddRoom
                        width: 333
                        height: 211
                        color: Tokens.stage
                        readonly property real hs: Tokens.snap(height, page.dpr)
                        Rectangle {
                            objectName: "snappedCentre"
                            width: 120
                            height: 72
                            x: Tokens.snap((oddRoom.width - width) / 2, page.dpr)
                            y: Tokens.snap((oddRoom.height - height) / 2, page.dpr)
                            color: Tokens.wellStage
                            CuText { x: 8; y: centredIn(72); text: "centred"; role: "body"; color: Tokens.text2 }
                        }
                        Rectangle {
                            objectName: "snappedBottom"
                            x: 16
                            width: oddRoom.width - 32
                            height: 40
                            y: oddRoom.hs - 16 - height
                            color: Tokens.raisedStage
                            CuText { x: 12; y: centredIn(40); text: "Hs - 56 to Hs - 16"; role: "body"; tabular: true; color: Tokens.text1 }
                        }
                    }
                }
                GalleryCell {
                    name: "Elevation: docked, float, modal"
                    ground: "stage"
                    Row {
                        spacing: 48
                        Rectangle { width: 160; height: 96; color: Tokens.raisedStage; CuText { x: 12; y: 12; text: "Docked, no shadow"; role: "meta"; color: Tokens.text2 } }
                        CuPlate { width: 160; height: 96; CuText { x: 12; y: 12; text: "Float, shadowFloat"; role: "meta"; color: Tokens.text2 } }
                        CuPlate { width: 160; height: 96; modal: true; CuText { x: 12; y: 12; text: "Dialog, shadowModal"; role: "meta"; color: Tokens.text2 } }
                    }
                }
            }
        }

        Section {
            key: "buttons"
            title: "Buttons: white block, tile, text control, danger"
            note: ""
            Repeater {
                model: ["ink", "stage", "float"]
                Cells {
                    id: buttonRow
                    required property string modelData
                    readonly property string g: modelData
                    GalleryCell { name: "White block, rest"; ground: buttonRow.g; CuButton { variant: "primary"; text: "Upscale 4 images at 4×"; ground: buttonRow.g } }
                    GalleryCell { name: "Hover"; ground: buttonRow.g; CuButton { variant: "primary"; text: "Add images…"; ground: buttonRow.g; forcedState: "hover" } }
                    GalleryCell { name: "Pressed"; ground: buttonRow.g; CuButton { variant: "primary"; text: "Add images…"; ground: buttonRow.g; forcedState: "pressed" } }
                    GalleryCell { name: "Focus"; ground: buttonRow.g; CuButton { variant: "primary"; text: "Add images…"; ground: buttonRow.g; forcedState: "focus" } }
                    GalleryCell { name: "Busy"; ground: buttonRow.g; CuButton { variant: "primary"; text: "Starting 4 images…"; ground: buttonRow.g; busy: true } }
                    GalleryCell { name: "Tile, rest"; ground: buttonRow.g; CuButton { variant: "tile"; text: "Queue again"; ground: buttonRow.g } }
                    GalleryCell { name: "Hover"; ground: buttonRow.g; CuButton { variant: "tile"; text: "Queue again"; ground: buttonRow.g; forcedState: "hover" } }
                    GalleryCell { name: "Pressed"; ground: buttonRow.g; CuButton { variant: "tile"; text: "Queue again"; ground: buttonRow.g; forcedState: "pressed" } }
                    GalleryCell { name: "Focus"; ground: buttonRow.g; CuButton { variant: "tile"; text: "Queue again"; ground: buttonRow.g; forcedState: "focus" } }
                    GalleryCell { name: "Disabled"; ground: buttonRow.g; CuButton { variant: "tile"; text: "Queue again"; ground: buttonRow.g; enabled: false } }
                    GalleryCell { name: "Busy"; ground: buttonRow.g; CuButton { variant: "tile"; text: "Stopping…"; ground: buttonRow.g; busy: true } }
                    GalleryCell { name: "Glyph and word"; ground: buttonRow.g; CuButton { variant: "tile"; text: "Open folder"; iconName: "folder"; ground: buttonRow.g } }
                    GalleryCell { name: "Commit 40"; ground: buttonRow.g; CuButton { variant: "tile"; text: "Try again"; commit: true; ground: buttonRow.g } }
                    GalleryCell { name: "Text control, rest"; ground: buttonRow.g; CuButton { variant: "text"; text: "Details"; ground: buttonRow.g } }
                    GalleryCell { name: "Hover"; ground: buttonRow.g; CuButton { variant: "text"; text: "Details"; ground: buttonRow.g; forcedState: "hover" } }
                    GalleryCell { name: "Pressed"; ground: buttonRow.g; CuButton { variant: "text"; text: "Details"; ground: buttonRow.g; forcedState: "pressed" } }
                    GalleryCell { name: "Focus"; ground: buttonRow.g; CuButton { variant: "text"; text: "Details"; ground: buttonRow.g; forcedState: "focus" } }
                    GalleryCell { name: "Disabled"; ground: buttonRow.g; CuButton { variant: "text"; text: "Details"; ground: buttonRow.g; enabled: false } }
                    GalleryCell { name: "Danger, rest"; ground: buttonRow.g; CuButton { variant: "danger"; text: "Cancel batch"; ground: buttonRow.g } }
                    GalleryCell { name: "Hover"; ground: buttonRow.g; CuButton { variant: "danger"; text: "Cancel batch"; ground: buttonRow.g; forcedState: "hover" } }
                    GalleryCell { name: "Focus"; ground: buttonRow.g; CuButton { variant: "danger"; text: "Cancel batch"; ground: buttonRow.g; forcedState: "focus" } }
                    GalleryCell { name: "Disabled"; ground: buttonRow.g; CuButton { variant: "danger"; text: "Cancel batch"; ground: buttonRow.g; enabled: false } }
                    GalleryCell { name: "White block, disabled: not drawn"; ground: buttonRow.g; CuButton { variant: "primary"; text: "Upscale"; ground: buttonRow.g; enabled: false } }
                }
            }
            Cells {
                GalleryCell {
                    name: "Split tile, rest"
                    CuButton { variant: "tile"; text: "Add"; iconName: "add"; menuModel: [{ label: "Add images…", value: "images" }, { label: "Add a folder…", value: "folder" }] }
                }
                GalleryCell {
                    name: "Split tile, hover"
                    CuButton { variant: "tile"; text: "Add"; iconName: "add"; forcedState: "hover"; menuModel: [{ label: "Add images…", value: "images" }] }
                }
                GalleryCell {
                    name: "Split tile, menu open"
                    contentWidth: 224
                    contentHeight: 120
                    CuButton {
                        variant: "tile"; text: "Queue again"; forcedState: "menu"
                        menuModel: [{ label: "With these settings", value: "these" }, { label: "With the settings it ran with", value: "earlier" }]
                    }
                }
                GalleryCell {
                    name: "The Stop tile with a folded item (224 foot)"
                    contentWidth: 224
                    contentHeight: 112
                    CuButton {
                        variant: "tile"; text: "Stop after current"; width: 224; commit: true; forcedState: "menu"
                        menuModel: []
                        folded: [{ label: "Cancel batch…", value: "cancel", danger: true }]
                    }
                }
                GalleryCell {
                    name: "Text control beside a label of the same size and tone, rest and hover"
                    Column {
                        spacing: 16
                        CuLabelRow { objectName: "proofLabelRowRest"; width: 224; label: "Variation number"; actionText: "New number" }
                        CuLabelRow { objectName: "proofLabelRowHover"; width: 224; label: "Variation number"; actionText: "New number"; forcedState: "hover" }
                    }
                }
                GalleryCell {
                    name: "At the end of a text2 status line, rest and hover"
                    Column {
                        spacing: 16
                        Item { width: 224; height: Tokens.hFootStatus; CuFootSlot { objectName: "proofFootRest"; width: 224; status: "The engine stopped."; detailsText: "Details" } }
                        Item { width: 224; height: Tokens.hFootStatus; CuFootSlot { objectName: "proofFootHover"; width: 224; status: "The engine stopped."; detailsText: "Details"; forcedState: "hover" } }
                    }
                }
                GalleryCell {
                    name: "Tooltip with a key"
                    contentWidth: 224
                    contentHeight: 96
                    CuButton {
                        id: tipButton
                        y: 56
                        variant: "tile"; text: "Stop after current"; tooltip: "Stop after current"; keyCap: "Ctrl+."
                        property bool tipForced: false
                        Timer { interval: 1200; running: true; onTriggered: tipButton.tipForced = true }
                        CuHoverTip { shown: tipButton.tipForced && tipButton.visible; text: tipButton.tipText; placement: "above" }
                    }
                }
            }
        }

        Section {
            key: "iconbutton"
            title: "Icon button and toggle tile"
            note: ""
            Repeater {
                model: ["ink", "stage"]
                Column {
                    id: ibRow
                    required property string modelData
                    readonly property string g: modelData
                    spacing: 16
                    Cells {
                        GalleryCell { name: "Panels toggle, rest"; ground: ibRow.g; CuIconButton { iconName: "panels"; ground: ibRow.g; tooltip: Tokens.keyTip("Hide panels", "Tab") } }
                        GalleryCell { name: "Hover"; ground: ibRow.g; CuIconButton { iconName: "panels"; ground: ibRow.g; forcedState: "hover" } }
                        GalleryCell { name: "Pressed"; ground: ibRow.g; CuIconButton { iconName: "panels"; ground: ibRow.g; forcedState: "pressed" } }
                        GalleryCell { name: "Focus"; ground: ibRow.g; CuIconButton { iconName: "panelsOff"; ground: ibRow.g; forcedState: "focus" } }
                        GalleryCell { name: "Disabled"; ground: ibRow.g; CuIconButton { iconName: "panels"; ground: ibRow.g; enabled: false } }
                    }
                    Cells {
                        GalleryCell { name: "Toggle tile, off"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; ground: ibRow.g } }
                        GalleryCell { name: "Off, hover"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; ground: ibRow.g; forcedState: "hover" } }
                        GalleryCell { name: "On"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; checked: true; ground: ibRow.g } }
                        GalleryCell { name: "On, hover"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; checked: true; ground: ibRow.g; forcedState: "hover" } }
                        GalleryCell { name: "Pressed"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; ground: ibRow.g; forcedState: "pressed" } }
                        GalleryCell { name: "Focus (on)"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; checked: true; ground: ibRow.g; forcedState: "focus" } }
                    }
                    Cells {
                        GalleryCell { name: "Stale, on (key emptied)"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; checked: true; swatchEmpty: true; ground: ibRow.g } }
                        GalleryCell { name: "Stale, off"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; swatchEmpty: true; ground: ibRow.g } }
                        GalleryCell { name: "Folded, off"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; compact: true; ground: ibRow.g } }
                        GalleryCell { name: "Folded, on"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; checked: true; compact: true; ground: ibRow.g } }
                        GalleryCell { name: "Folded, on, hover"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; checked: true; compact: true; ground: ibRow.g; forcedState: "hover" } }
                        GalleryCell { name: "Off, disabled"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; ground: ibRow.g; enabled: false } }
                        GalleryCell { name: "On, disabled"; ground: ibRow.g; CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; checked: true; ground: ibRow.g; enabled: false } }
                    }
                }
            }
        }

        Section {
            key: "fields"
            title: "Well, text field, select"
            note: ""
            Repeater {
                model: ["ink", "stage", "float"]
                Cells {
                    id: fRow
                    required property string modelData
                    readonly property string g: modelData
                    GalleryCell { name: "Well, set by the Look"; ground: fRow.g; CuWell { width: 96; text: "3840"; unit: "px"; ground: fRow.g } }
                    GalleryCell { name: "Typed"; ground: fRow.g; CuWell { width: 96; text: "4096"; unit: "px"; setByUser: true; ground: fRow.g } }
                    GalleryCell { name: "Hover"; ground: fRow.g; CuWell { width: 96; text: "4096"; unit: "px"; ground: fRow.g; forcedState: "hover" } }
                    GalleryCell { name: "Focus"; ground: fRow.g; CuWell { width: 96; text: "4096"; unit: "px"; ground: fRow.g; forcedState: "focus" } }
                    GalleryCell { name: "Error"; ground: fRow.g; CuWell { width: 96; text: "0"; unit: "px"; error: true; ground: fRow.g } }
                    GalleryCell { name: "Disabled"; ground: fRow.g; CuWell { width: 96; text: "4096"; unit: "px"; enabled: false; ground: fRow.g } }
                    GalleryCell { name: "Field, placeholder"; ground: fRow.g; CuTextField { width: 224; placeholderText: "For example, stone and timber…"; ground: fRow.g } }
                    GalleryCell { name: "Filled"; ground: fRow.g; CuTextField { width: 224; text: "Warm evening light"; ground: fRow.g } }
                    GalleryCell { name: "Hover"; ground: fRow.g; CuTextField { width: 224; text: "Warm evening light"; ground: fRow.g; forcedState: "hover" } }
                    GalleryCell { name: "Focus"; ground: fRow.g; CuTextField { width: 224; text: "Warm evening light"; ground: fRow.g; forcedState: "focus" } }
                    GalleryCell { name: "Error with its line"; ground: fRow.g; contentWidth: 224; contentHeight: 52; CuTextField { width: 224; text: "/missing/output"; error: true; errorText: "The output folder is not available."; ground: fRow.g } }
                    GalleryCell { name: "Disabled"; ground: fRow.g; CuTextField { width: 224; text: "Warm evening light"; enabled: false; ground: fRow.g } }
                    GalleryCell { name: "Read-only path"; ground: fRow.g; CuTextField { width: 224; text: "/images/upscaled"; readOnly: true; pathMode: true; ground: fRow.g } }
                    GalleryCell { name: "Select, rest"; ground: fRow.g; CuComboBox { width: 224; ground: fRow.g; model: [{ label: "PNG", value: "png" }, { label: "TIFF, 16-bit", value: "tif16" }]; currentValue: "png" } }
                    GalleryCell { name: "Hover"; ground: fRow.g; CuComboBox { width: 224; ground: fRow.g; forcedState: "hover"; model: [{ label: "PNG", value: "png" }]; currentValue: "png" } }
                    GalleryCell { name: "Focus"; ground: fRow.g; CuComboBox { width: 224; ground: fRow.g; forcedState: "focus"; model: [{ label: "PNG", value: "png" }]; currentValue: "png" } }
                    GalleryCell { name: "Disabled"; ground: fRow.g; CuComboBox { width: 224; ground: fRow.g; enabled: false; model: [{ label: "PNG", value: "png" }]; currentValue: "png" } }
                }
            }
            Cells {
                GalleryCell {
                    name: "Select, open with its menu"
                    contentWidth: 224
                    contentHeight: 152
                    CuComboBox {
                        width: 224
                        forcedState: "open"
                        model: [{ label: "PNG", value: "png" }, { label: "TIFF, 16-bit", value: "tif16" }, { label: "JPEG, quality 95", value: "jpg" }]
                        currentValue: "tif16"
                    }
                }
                GalleryCell {
                    name: "Field counting past three quarters"
                    CuTextField { width: 224; maximumLength: 40; text: "Stone, oak, warm dusk light, wet terrace" }
                }
            }
        }

        Section {
            key: "segmented"
            title: "Segmented control"
            note: ""
            Repeater {
                model: ["ink", "stage", "float"]
                Cells {
                    id: sRow
                    required property string modelData
                    readonly property string g: modelData
                    readonly property var scales: [{ label: "2×", value: 2 }, { label: "4×", value: 4 }, { label: "6×", value: 6 }, { label: "8×", value: 8 }]
                    GalleryCell { name: "Rest, 4× chosen (224)"; ground: sRow.g; CuSegmented { width: 224; ground: sRow.g; model: sRow.scales; currentValue: 4; tabular: true } }
                    GalleryCell { name: "Hover on 6×"; ground: sRow.g; CuSegmented { width: 224; ground: sRow.g; model: sRow.scales; currentValue: 4; forcedState: "hover:2"; tabular: true } }
                    GalleryCell { name: "Pressed on 8×"; ground: sRow.g; CuSegmented { width: 224; ground: sRow.g; model: sRow.scales; currentValue: 4; forcedState: "pressed:3"; tabular: true } }
                    GalleryCell { name: "Focus"; ground: sRow.g; CuSegmented { width: 224; ground: sRow.g; model: sRow.scales; currentValue: 4; forcedState: "focus"; tabular: true } }
                    GalleryCell {
                        name: "Unchosen beside disabled (8× too large)"
                        ground: sRow.g
                        CuSegmented { width: 224; ground: sRow.g; tabular: true; currentValue: 2; model: [{ label: "2×", value: 2 }, { label: "4×", value: 4 }, { label: "6×", value: 6 }, { label: "8×", value: 8, enabled: false, tip: "Too large for 8×" }] }
                    }
                    GalleryCell {
                        name: "Words plus 32, with a sub-value"
                        ground: sRow.g
                        CuSegmented { equalCells: false; ground: sRow.g; currentValue: "fit"; model: [{ label: "Fit", value: "fit", sub: "31%" }, { label: "100%", value: "full" }] }
                    }
                    GalleryCell { name: "Disabled"; ground: sRow.g; CuSegmented { width: 224; ground: sRow.g; model: sRow.scales; currentValue: 4; enabled: false; tabular: true } }
                }
            }
        }

        Section {
            key: "scales"
            title: "Scale track: slider and Look"
            note: ""
            Repeater {
                model: ["ink", "stage"]
                Cells {
                    id: scRow
                    required property string modelData
                    readonly property string g: modelData
                    GalleryCell { name: "Slider, set by the Look"; ground: scRow.g; CuSlider { width: 224; ground: scRow.g; label: "Creativity"; value: 50; resetValue: 50; description: "How much new detail the upscale may invent."; lowLabel: "Faithful"; highLabel: "Inventive" } }
                    GalleryCell { name: "Set by you (the Look's mark)"; ground: scRow.g; CuSlider { width: 224; ground: scRow.g; label: "Creativity"; value: 72; resetValue: 50 } }
                    GalleryCell { name: "Hover, the Look's value"; ground: scRow.g; CuSlider { width: 224; ground: scRow.g; label: "Creativity"; value: 50; resetValue: 50; forcedState: "hover" } }
                    GalleryCell { name: "Hover, yours"; ground: scRow.g; CuSlider { width: 224; ground: scRow.g; label: "Creativity"; value: 72; resetValue: 50; forcedState: "hover" } }
                    GalleryCell { name: "Dragged"; ground: scRow.g; CuSlider { width: 224; ground: scRow.g; label: "Creativity"; value: 72; resetValue: 50; forcedState: "pressed" } }
                    GalleryCell { name: "Focus"; ground: scRow.g; CuSlider { width: 224; ground: scRow.g; label: "Creativity"; value: 72; resetValue: 50; forcedState: "focus" } }
                    GalleryCell { name: "Readout typing"; ground: scRow.g; CuSlider { width: 224; ground: scRow.g; label: "Creativity"; value: 72; resetValue: 50; forcedState: "typing" } }
                    GalleryCell { name: "Disabled"; ground: scRow.g; CuSlider { width: 224; ground: scRow.g; label: "Creativity"; value: 72; resetValue: 50; enabled: false } }
                }
            }
            Cells {
                Repeater {
                    model: [{ name: "Look, Default chosen", stop: 1, custom: false }, { name: "Look in Custom, from Default", stop: 1, custom: true }]
                    GalleryCell {
                        id: lookCell
                        required property var modelData
                        name: modelData.name + " (224)"
                        readonly property var names: ["Light", "Default", "Strong", "Heavy", "Extreme"]
                        FontMetrics { id: lookFm; font: Tokens.fontFor("meta", false) }
                        FontMetrics { id: lookFm0; font.family: Tokens.familyFor(400); font.pixelSize: 12; font.letterSpacing: 0; font.hintingPreference: Tokens.hinting }
                        function gapWith(fm) {
                            var w = 224, c = w / 5, g = 1e9
                            for (var i = 0; i < 4; ++i) {
                                var r = (i + 0.5) * c + fm.advanceWidth(names[i]) / 2
                                var l = (i + 1.5) * c - fm.advanceWidth(names[i + 1]) / 2
                                g = Math.min(g, l - r)
                            }
                            return g
                        }
                        readonly property real gapTracked: gapWith(lookFm)
                        readonly property real gapPlain: gapWith(lookFm0)
                        readonly property bool dropTracking: gapTracked < 4
                        readonly property real minGap: dropTracking ? gapPlain : gapTracked
                        Column {
                            spacing: 8
                            Item {
                                width: 224
                                height: Tokens.hTitleRow
                                CuSectionTitle { width: 224; text: "Look"; note: lookCell.modelData.custom ? "Custom, from Default" : "" }
                            }
                            Item {
                                width: 224
                                height: Tokens.hLook
                                CuScaleTrack {
                                    width: 224
                                    stops: [0.1, 0.3, 0.5, 0.7, 0.9]
                                    value: 0.1 + 0.2 * lookCell.modelData.stop
                                    tickColor: lookCell.modelData.custom ? Tokens.text2 : Tokens.text1
                                }
                                Repeater {
                                    model: lookCell.names
                                    CuText {
                                        required property string modelData
                                        required property int index
                                        x: Tokens.snap((index + 0.5) * 224 / 5 - implicitWidth / 2, page.dpr)
                                        y: Tokens.hScaleRow
                                        text: modelData
                                        role: "meta"
                                        font.letterSpacing: lookCell.dropTracking ? 0 : 0.1
                                        color: index === lookCell.modelData.stop && !lookCell.modelData.custom ? Tokens.text1 : Tokens.text2
                                    }
                                }
                            }
                            CuText { text: "Smallest gap " + lookCell.gapTracked.toFixed(1) + " px tracked, " + lookCell.gapPlain.toFixed(1) + " px at 0" + (lookCell.dropTracking ? ", drawn at 0" : ""); role: "meta"; tabular: true; color: Tokens.text3 }
                        }
                    }
                }
            }
        }

        Section {
            key: "checkbox"
            title: "Checkbox"
            note: ""
            Repeater {
                model: ["ink", "stage", "float"]
                Cells {
                    id: cRow
                    required property string modelData
                    readonly property string g: modelData
                    GalleryCell { name: "Off"; ground: cRow.g; CuCheckBox { text: "Reduce motion"; ground: cRow.g } }
                    GalleryCell { name: "Hover"; ground: cRow.g; CuCheckBox { text: "Reduce motion"; ground: cRow.g; forcedState: "hover" } }
                    GalleryCell { name: "Pressed"; ground: cRow.g; CuCheckBox { text: "Reduce motion"; ground: cRow.g; forcedState: "pressed" } }
                    GalleryCell { name: "Focus"; ground: cRow.g; CuCheckBox { text: "Reduce motion"; ground: cRow.g; forcedState: "focus" } }
                    GalleryCell { name: "On"; ground: cRow.g; CuCheckBox { text: "Reduce motion"; checked: true; ground: cRow.g } }
                    GalleryCell { name: "On, hover"; ground: cRow.g; CuCheckBox { text: "Reduce motion"; checked: true; ground: cRow.g; forcedState: "hover" } }
                    GalleryCell { name: "Disabled"; ground: cRow.g; CuCheckBox { text: "Match earlier results"; enabled: false; ground: cRow.g } }
                    GalleryCell { name: "Disabled, on"; ground: cRow.g; CuCheckBox { text: "Match earlier results"; checked: true; enabled: false; ground: cRow.g } }
                    GalleryCell { name: "With a line under it (48)"; ground: cRow.g; CuCheckBox { text: "Speed up upscaling"; hint: "About 13% quicker at 2×."; ground: cRow.g } }
                    GalleryCell { name: "Disabled, the reason under it"; ground: cRow.g; CuCheckBox { text: "Speed up upscaling"; disabledReason: "Off while Match earlier results is on."; enabled: false; ground: cRow.g } }
                }
            }
        }

        Section {
            key: "rows"
            title: "Section title, fold, label row, fact row"
            note: ""
            Cells {
                GalleryCell { name: "Title with a note"; CuSectionTitle { width: 224; text: "Scale"; note: "147 MP, A0 at 328 ppi" } }
                GalleryCell { name: "Title with a text control"; CuSectionTitle { width: 224; text: "Variation"; actionText: "New number" } }
                GalleryCell { name: "Fold, folded"; CuSectionTitle { width: 224; text: "Detail"; foldable: true; summary: "As the Look sets it" } }
                GalleryCell { name: "Fold, hover"; CuSectionTitle { width: 224; text: "Detail"; foldable: true; summary: "As the Look sets it"; forcedState: "hover" } }
                GalleryCell { name: "Fold, focus"; CuSectionTitle { width: 224; text: "Protect"; foldable: true; summary: "People, plants"; forcedState: "focus" } }
                GalleryCell { name: "Fold, open"; CuSectionTitle { width: 224; text: "Detail"; foldable: true; open: true; summary: "As the Look sets it" } }
                GalleryCell {
                    name: "Label row with a note, and its control 4 below"
                    Column {
                        spacing: 4
                        CuLabelRow { width: 224; label: "Output folder"; note: "34 GB free" }
                        CuTextField { width: 224; text: "/images/upscaled"; readOnly: true; pathMode: true }
                    }
                }
                GalleryCell {
                    name: "Label row with a text control, rest and hover"
                    Column {
                        spacing: 16
                        CuLabelRow { width: 224; label: "Folder"; actionText: "Browse…" }
                        CuLabelRow { width: 224; label: "Folder"; actionText: "Browse…"; forcedState: "hover" }
                    }
                }
                GalleryCell {
                    name: "Fact row"
                    Column {
                        spacing: 8
                        CuLabelRow { width: 224; label: "Ran with"; value: "2×, Default look, sped up" }
                        CuLabelRow { width: 224; label: "Ran with"; value: "4×, Custom from Default" }
                    }
                }
            }
        }

        Section {
            key: "lists"
            title: "List rows"
            note: ""
            Repeater {
                model: ["ink", "stage", "float"]
                Cells {
                    id: lRow
                    required property string modelData
                    readonly property string g: modelData
                    Repeater {
                        model: [{ n: "Media row, rest", s: "", sel: false }, { n: "Hover", s: "hover", sel: false }, { n: "Selected", s: "", sel: true },
                                { n: "Pressed", s: "pressed", sel: false }, { n: "Focus", s: "focus", sel: false }]
                        GalleryCell {
                            required property var modelData
                            name: modelData.n
                            ground: lRow.g
                            pad: 0
                            CuListRow {
                                width: 256
                                ground: lRow.g
                                kind: "media"
                                text: "Scene_Exterior_REV-C.png"
                                nameMiddle: true
                                meta: "3,840 × 2,400 px, 24 MB"
                                selected: modelData.sel
                                forcedState: modelData.s
                                leading: Rectangle { width: 36; height: 24; color: Tokens.checkB }
                                trailing: CuHoverWord { text: "Remove"; rowHovered: modelData.s === "hover"; ground: lRow.g }
                            }
                        }
                    }
                    GalleryCell {
                        name: "Working row with its bar"
                        ground: lRow.g
                        pad: 0
                        CuListRow {
                            width: 256; ground: lRow.g; kind: "media"; text: "Scene_Interior_AM.tif"; meta: "GPU 2, detail pass"; progress: 0.62
                            leading: Rectangle { width: 36; height: 24; color: Tokens.checkA }
                        }
                    }
                }
            }
            Cells {
                Repeater {
                    model: [{ n: "Plain row, rest", s: "", sel: false }, { n: "Hover", s: "hover", sel: false }, { n: "Selected", s: "", sel: true }]
                    GalleryCell {
                        required property var modelData
                        name: modelData.n
                        pad: 0
                        CuListRow {
                            width: 256; kind: "plain"; text: "Remove noise"; value: "Medium"; selected: modelData.sel; forcedState: modelData.s
                            leading: CuCheckBox { checked: true }
                        }
                    }
                }
                Repeater {
                    model: [{ n: "Results cell, rest", s: "", sel: false }, { n: "Hover", s: "hover", sel: false }, { n: "Selected", s: "", sel: true }]
                    GalleryCell {
                        required property var modelData
                        name: modelData.n
                        ground: "stage"
                        pad: 8
                        CuListRow {
                            id: cellRow
                            width: 192; height: 160; kind: "cell"; ground: "stage"; inset: 8; selected: modelData.sel; forcedState: modelData.s
                            Rectangle { x: 8; y: 8; width: 176; height: 110; color: Tokens.wellStage; Rectangle { x: 18; y: 8; width: 140; height: 94; color: Tokens.checkB } }
                            CuText { x: 8; y: 124; width: 176; text: "Scene_Exterior.png"; role: "bodyStrong"; elide: Text.ElideMiddle; color: Tokens.text1 }
                            CuText { x: 8; y: 144; width: 176; text: "7,680 × 4,800 px, PNG, 61 MB"; role: "meta"; tabular: true; color: cellRow.stepTone(Tokens.text3) }
                        }
                    }
                }
                GalleryCell {
                    name: "Setting row with a select, a checkbox, and disabled"
                    Column {
                        spacing: 0
                        CuSettingRow {
                            width: 560; title: "Picture surround"; description: "The tone round the picture in the opening."
                            CuComboBox { width: 240; model: [{ label: "Charcoal", value: "c" }, { label: "Mid grey", value: "m" }]; currentValue: "c" }
                        }
                        CuSettingRow {
                            width: 560; title: "Speed up upscaling"; description: "About 13% quicker at 2×."
                            CuCheckBox { checked: false }
                        }
                        CuSettingRow {
                            width: 560; title: "Detailed live preview"; description: "Opens with the Creative Upscaler tab"; enabled: false
                            CuCheckBox { checked: true; enabled: false }
                        }
                    }
                }
            }
        }

        Section {
            key: "floats"
            title: "Menu, tooltip, toast"
            note: ""
            Cells {
                GalleryCell {
                    name: "Menu: current, hover, keyboard, separator, disabled, danger"
                    ground: "stage"
                    CuMenu {
                        minWidth: 224
                        currentValue: "tif16"
                        highlighted: 2
                        keyboardLit: true
                        model: [{ label: "PNG", value: "png" }, { label: "TIFF, 16-bit", value: "tif16" }, { label: "JPEG, quality 95", value: "jpg" },
                                { separator: true }, { label: "Same as the source", value: "src", enabled: false }, { label: "Cancel batch…", value: "cancel", danger: true }]
                    }
                }
                GalleryCell {
                    name: "Menu item, hover"
                    ground: "stage"
                    CuMenu { minWidth: 224; highlighted: 0; model: [{ label: "Add images…", value: "i" }, { label: "Add a folder…", value: "f" }] }
                }
                GalleryCell {
                    name: "Tooltips: a key, two lines, a detail"
                    ground: "stage"
                    contentWidth: 720
                    contentHeight: 120
                    Item {
                        width: 720
                        height: 120
                        Item {
                            id: tipA
                            x: 0; y: 88; width: 32; height: 32
                            property bool on: false
                            Timer { interval: 1200; running: true; onTriggered: tipA.on = true }
                            CuHoverTip { shown: tipA.on && tipA.visible; text: Tokens.keyTip("Fit", "0"); placement: "above" }
                        }
                        Item {
                            id: tipB
                            x: 280; y: 88; width: 32; height: 32
                            property bool on: false
                            Timer { interval: 1200; running: true; onTriggered: tipB.on = true }
                            CuHoverTip { shown: tipB.on && tipB.visible; text: "Finishes the images in progress, then stops. Waiting images move to Stopped."; placement: "above" }
                        }
                        Item {
                            id: tipC
                            x: 600; y: 88; width: 32; height: 32
                            property bool on: false
                            Timer { interval: 1200; running: true; onTriggered: tipC.on = true }
                            CuHoverTip { shown: tipC.on && tipC.visible; text: "Creativity"; detail: "Faithful at 0, Inventive at 100"; placement: "above" }
                        }
                    }
                }
                GalleryCell {
                    name: "Toast at 224, one action"
                    ground: "stage"
                    CuToast { width: 224; text: "Every waiting image set to 2×"; actions: [{ label: "Undo", value: "undo" }] }
                }
                GalleryCell {
                    name: "Toast at 224, two lines"
                    ground: "stage"
                    CuToast { width: 224; text: "1 image keeps the earlier settings"; detail: "It started before the change."; actions: [{ label: "Dismiss", value: "dismiss" }] }
                }
                GalleryCell {
                    name: "Toast at 224, two actions on their own line"
                    ground: "stage"
                    CuToast { width: 224; text: "Kept running while the window was closed, 23:36 to 00:25"; actions: [{ label: "Review results", value: "review" }, { label: "Dismiss", value: "dismiss" }] }
                }
                GalleryCell {
                    name: "Toast at 224, one line"
                    ground: "stage"
                    CuToast { width: 224; text: "Copied"; actions: [{ label: "Dismiss", value: "dismiss" }] }
                }
                GalleryCell {
                    name: "Action hovered"
                    ground: "stage"
                    CuToast { width: 224; text: "Copied"; actions: [{ label: "Dismiss", value: "dismiss" }]; forcedState: "hover:0" }
                }
                GalleryCell {
                    name: "Toast at 288 (a wider leg), one line with an action"
                    ground: "stage"
                    CuToast { width: 288; text: "Every waiting image set to 2×"; actions: [{ label: "Undo", value: "undo" }] }
                }
            }
        }

        Section {
            key: "dialogs"
            title: "Dialog and sheet"
            note: ""
            Cells {
                GalleryCell {
                    name: "Question dialog over the scrim (the safe action focused)"
                    ground: "stage"
                    pad: 0
                    contentWidth: 640
                    contentHeight: 320
                    CuDialog {
                        width: 640
                        height: 320
                        title: "Images are still upscaling"
                        message: "2 of 12 are done. Finish in the background keeps the engine running after the window closes."
                        forcedFocus: 0
                        actions: [{ label: "Keep open", value: "keep", kind: "text", tip: Tokens.keyTip("Keep open", "Esc") },
                                  { label: "Stop and close", value: "stop", kind: "danger" },
                                  { label: "Finish in the background", value: "bg", kind: "white", tip: Tokens.keyTip("Finish in the background", "Enter") }]
                    }
                }
                GalleryCell {
                    name: "Form dialog with a section"
                    ground: "stage"
                    pad: 0
                    contentWidth: 720
                    contentHeight: 440
                    CuDialog {
                        id: formDialog
                        width: 720
                        height: 440
                        form: true
                        title: "Export"
                        actions: [{ label: "Cancel", value: "cancel", kind: "text" }, { label: "Export 3 images", value: "go", kind: "white" }]
                        Column {
                            width: 512
                            spacing: 0
                            CuSectionTitle { width: 512; ground: "float"; text: "Format"; note: "PNG keeps transparency" }
                            Item { width: 1; height: Tokens.gapTitle }
                            CuSegmented { width: 512; ground: "float"; currentValue: "png"; model: [{ label: "PNG", value: "png" }, { label: "TIFF", value: "tif" }, { label: "JPEG", value: "jpg" }] }
                            Item { width: 1; height: Tokens.sp24 }
                            CuSettingsRule { x: formDialog.ruleX; width: formDialog.ruleWidth; ground: "float" }
                            Item { width: 1; height: Tokens.sp24 - 1 }
                            CuSectionTitle { width: 512; ground: "float"; text: "Folder" }
                            Item { width: 1; height: Tokens.gapTitle }
                            CuTextField { width: 512; ground: "float"; text: "/images/exports"; readOnly: true; pathMode: true }
                        }
                    }
                }
                GalleryCell {
                    name: "Sheet in a 256 leg"
                    pad: 0
                    contentWidth: 256
                    contentHeight: 240
                    CuSheet {
                        width: 256
                        height: 240
                        title: "Activity"
                        Column {
                            x: 16
                            width: 224
                            spacing: 0
                            Repeater {
                                model: ["19:02  Added 4 images", "19:03  Started 4 images at 4×", "19:24  Scene_Exterior done", "19:25  Every waiting image set to 2×",
                                        "19:31  GPU 2 ran out of memory", "19:32  Tried again at 2×", "19:40  Scene_Interior done", "19:52  2 of 4 done", "20:01  Paused"]
                                CuText { required property string modelData; width: 224; height: 24; text: modelData; role: "body"; tabular: true; elide: Text.ElideRight; color: Tokens.text2 }
                            }
                        }
                        Component.onCompleted: Qt.callLater(function() { area.contentY = 48; area.regionHovered = true })
                    }
                }
            }
        }

        Section {
            key: "states"
            title: "Progress bar, recess, foot slot, tag"
            note: ""
            Cells {
                GalleryCell {
                    name: "Progress bar, one pass, on ink"
                    Column { spacing: 16; CuProgressBar { width: 224; value: 0.4 } CuProgressBar { width: 224; value: 1 } }
                }
                GalleryCell {
                    name: "Two passes and the gap, on the stage"
                    ground: "stage"
                    CuProgressBar { width: 480; ground: "stage"; segments: [1, 3]; value: 0.55 }
                }
                GalleryCell {
                    name: "Recess, empty"
                    ground: "stage"
                    pad: 24
                    CuRecess { width: 480; height: 300; text: "Drop images here, or add them."; actionText: "Add images…" }
                }
                GalleryCell {
                    name: "Recess, drop"
                    ground: "stage"
                    pad: 24
                    CuRecess { width: 480; height: 300; text: "Drop to add 3 images"; drop: true }
                }
                GalleryCell {
                    name: "Recess, engine starting"
                    ground: "stage"
                    pad: 24
                    CuRecess { width: 480; height: 300; text: "Starting the engine"; measure: "12 s" }
                }
                GalleryCell {
                    name: "Recess, engine problem"
                    ground: "stage"
                    pad: 24
                    CuRecess {
                        width: 480; height: 300
                        title: "The models cannot be reached"
                        text: "The upscaler's models on the studio NAS cannot be reached. Check the NAS is on, then try again."
                        actionText: "Try again"; actionKind: "tile"; secondText: "Details"
                    }
                }
                GalleryCell {
                    name: "Foot slot, images added (white block in the foot)"
                    contentWidth: 224
                    contentHeight: 84
                    CuFootSlot {
                        width: 224
                        status: "About 1 h 45 min"
                        CuButton { variant: "primary"; text: "Upscale 4 images at 4×"; width: 224 }
                    }
                }
                GalleryCell {
                    name: "Foot slot, running at 224 (folded Cancel batch…)"
                    contentWidth: 224
                    contentHeight: 84
                    CuFootSlot {
                        width: 224
                        status: "2 of 12 done, finishes about "
                        statusValue: "19:25"
                        CuButton { variant: "tile"; text: "Stop after current"; commit: true; width: 224; folded: [{ label: "Cancel batch…", value: "cancel", danger: true }] }
                    }
                }
                GalleryCell {
                    name: "Foot slot, a problem with Details"
                    contentWidth: 224
                    contentHeight: 84
                    CuFootSlot {
                        width: 224
                        status: "The engine stopped."
                        detailsText: "Details"
                        CuButton { variant: "tile"; text: "Try again"; commit: true }
                    }
                }
                GalleryCell {
                    name: "Tags on the picture"
                    ground: "stage"
                    Rectangle {
                        width: 320; height: 120; color: Tokens.checkB
                        Rectangle { x: 160; width: 160; height: 120; color: Tokens.surroundMid }
                        CuPlateLabel { x: 8; y: 120 - 8 - height; text: "Before" }
                        CuPlateLabel { x: 168; y: 120 - 8 - height; text: "After" }
                    }
                }
                GalleryCell {
                    name: "Scroll area: the pinned edge and the overlay bar"
                    pad: 0
                    contentWidth: 256
                    contentHeight: 200
                    CuScrollArea {
                        id: demoScroll
                        width: 256
                        height: 200
                        surface: Tokens.ink
                        regionHovered: true
                        Column {
                            x: 16
                            width: 224
                            Repeater {
                                model: 12
                                CuListRow { required property int index; width: 256; x: -16; kind: "plain"; text: "Row " + (index + 1); value: (index + 1) * 4 + " MB" }
                            }
                        }
                        Component.onCompleted: Qt.callLater(function() { demoScroll.contentY = 120 })
                    }
                }
            }
        }

        Section {
            key: "real"
            title: "Every kind, key states (the real-program board)"
            note: ""
            visible: page.only === "real"
            Cells {
                GalleryCell { name: "White block, rest"; CuButton { variant: "primary"; text: "Upscale 4 images at 4×" } }
                GalleryCell { name: "Hover"; CuButton { variant: "primary"; text: "Add images…"; forcedState: "hover" } }
                GalleryCell { name: "Focus"; CuButton { variant: "primary"; text: "Add images…"; forcedState: "focus" } }
                GalleryCell { name: "Tile, rest"; CuButton { variant: "tile"; text: "Queue again" } }
                GalleryCell { name: "Hover"; CuButton { variant: "tile"; text: "Queue again"; forcedState: "hover" } }
                GalleryCell { name: "Pressed"; CuButton { variant: "tile"; text: "Queue again"; forcedState: "pressed" } }
                GalleryCell { name: "Disabled"; CuButton { variant: "tile"; text: "Queue again"; enabled: false } }
                GalleryCell { name: "Split tile"; CuButton { variant: "tile"; text: "Add"; iconName: "add"; menuModel: [{ label: "Add images…", value: "i" }] } }
                GalleryCell { name: "Text control, rest and hover"; Row { spacing: 24; CuButton { variant: "text"; text: "Details"; width: Math.ceil(implicitWidth / 4) * 4 } CuButton { variant: "text"; text: "Details"; forcedState: "hover"; width: Math.ceil(implicitWidth / 4) * 4 } } }
                GalleryCell { name: "Danger, rest and hover"; Row { spacing: 24; CuButton { variant: "danger"; text: "Cancel batch"; width: Math.ceil(implicitWidth / 4) * 4 } CuButton { variant: "danger"; text: "Cancel batch"; forcedState: "hover"; width: Math.ceil(implicitWidth / 4) * 4 } } }
            }
            Cells {
                GalleryCell { name: "Well, set by the Look"; CuWell { objectName: "wellProbe"; width: 96; text: "3840"; unit: "px" } }
                GalleryCell { name: "Typed"; CuWell { width: 96; text: "4096"; unit: "px"; setByUser: true } }
                GalleryCell { name: "Hover"; CuWell { width: 96; text: "4096"; unit: "px"; forcedState: "hover" } }
                GalleryCell { name: "Focus"; CuWell { width: 96; text: "4096"; unit: "px"; forcedState: "focus" } }
                GalleryCell { name: "Error"; CuWell { width: 96; text: "0"; unit: "px"; error: true } }
                GalleryCell { name: "Field, placeholder"; CuTextField { width: 224; placeholderText: "For example, stone and timber…" } }
                GalleryCell { name: "Select"; CuComboBox { width: 224; model: [{ label: "TIFF, 16-bit", value: "t" }]; currentValue: "t" } }
                GalleryCell { name: "Select, hover"; CuComboBox { width: 224; forcedState: "hover"; model: [{ label: "TIFF, 16-bit", value: "t" }]; currentValue: "t" } }
            }
            Cells {
                GalleryCell { name: "Segmented"; CuSegmented { width: 224; tabular: true; currentValue: 4; model: [{ label: "2×", value: 2 }, { label: "4×", value: 4 }, { label: "6×", value: 6 }, { label: "8×", value: 8 }] } }
                GalleryCell { name: "Hover on 6×, 8× disabled"; CuSegmented { width: 224; tabular: true; currentValue: 4; forcedState: "hover:2"; model: [{ label: "2×", value: 2 }, { label: "4×", value: 4 }, { label: "6×", value: 6 }, { label: "8×", value: 8, enabled: false }] } }
                GalleryCell { name: "Focus"; CuSegmented { width: 224; tabular: true; currentValue: 4; forcedState: "focus"; model: [{ label: "2×", value: 2 }, { label: "4×", value: 4 }, { label: "6×", value: 6 }, { label: "8×", value: 8 }] } }
                GalleryCell { name: "Checkboxes"; Column { CuCheckBox { text: "Reduce motion" } CuCheckBox { text: "Reduce motion"; checked: true } CuCheckBox { text: "Reduce motion"; forcedState: "hover" } CuCheckBox { text: "Match earlier results"; enabled: false } } }
                GalleryCell { name: "With a line under it"; CuCheckBox { text: "Speed up upscaling"; hint: "About 13% quicker at 2×." } }
                GalleryCell { name: "Slider, the Look's value and yours"; Column { spacing: 16; CuSlider { width: 224; label: "Creativity"; value: 50; resetValue: 50 } CuSlider { width: 224; label: "Creativity"; value: 72; resetValue: 50 } } }
            }
            Cells {
                GalleryCell { name: "Section titles"; Column { spacing: 16; CuSectionTitle { width: 224; text: "Scale"; note: "147 MP, A0 at 328 ppi" } CuSectionTitle { width: 224; text: "Detail"; foldable: true; summary: "As the Look sets it" } } }
                GalleryCell { name: "Label and fact rows"; Column { spacing: 16; CuLabelRow { width: 224; label: "Folder"; actionText: "Browse…" } CuLabelRow { width: 224; label: "Ran with"; value: "2×, Default look" } } }
                GalleryCell {
                    name: "Media rows: rest, hover, selected"
                    pad: 0
                    Column {
                        Repeater {
                            model: [{ s: "", sel: false }, { s: "hover", sel: false }, { s: "", sel: true }]
                            CuListRow {
                                required property var modelData
                                width: 256; kind: "media"; text: "Scene_Exterior_REV-C.png"; nameMiddle: true; meta: "3,840 × 2,400 px, 24 MB"
                                selected: modelData.sel; forcedState: modelData.s
                                leading: Rectangle { width: 36; height: 24; color: Tokens.checkB }
                                trailing: CuHoverWord { text: "Remove"; rowHovered: modelData.s === "hover" }
                            }
                        }
                    }
                }
                GalleryCell {
                    name: "Menu (on the stage)"
                    ground: "stage"
                    CuMenu { minWidth: 192; currentValue: "t"; highlighted: 0; model: [{ label: "PNG", value: "p" }, { label: "TIFF, 16-bit", value: "t" }, { separator: true }, { label: "Cancel batch…", value: "c", danger: true }] }
                }
                GalleryCell {
                    name: "Toasts at 224 (on the stage)"
                    ground: "stage"
                    Column {
                        spacing: 8
                        CuToast { width: 224; text: "Every waiting image set to 2×"; actions: [{ label: "Undo", value: "u" }] }
                        CuToast { width: 224; text: "1 image keeps the earlier settings"; detail: "It started before the change."; actions: [{ label: "Dismiss", value: "d" }] }
                    }
                }
            }
            Cells {
                GalleryCell { name: "Segmented on the stage"; ground: "stage"; CuSegmented { ground: "stage"; equalCells: false; currentValue: "fit"; model: [{ label: "Fit", value: "fit", sub: "31%" }, { label: "100%", value: "full" }] } }
                GalleryCell {
                    name: "Toggle tile: off, on, on and hovered"
                    ground: "stage"
                    Row {
                        spacing: 8
                        CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true }
                        CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; checked: true }
                        CuIconButton { text: "Protected areas"; swatch: Tokens.protectTint; checkable: true; checked: true; forcedState: "hover" }
                    }
                }
                GalleryCell { name: "Panels toggle, hover"; ground: "stage"; CuIconButton { iconName: "panels"; forcedState: "hover" } }
                GalleryCell { name: "Tile on the stage"; ground: "stage"; CuButton { variant: "tile"; text: "Try again"; ground: "stage" } }
                GalleryCell { name: "Well on the stage"; ground: "stage"; CuWell { width: 96; text: "328"; unit: "ppi"; ground: "stage" } }
                GalleryCell { name: "Tags"; ground: "stage"; Rectangle { width: 192; height: 64; color: Tokens.checkB; CuPlateLabel { x: 8; y: 64 - 8 - height; text: "Before" } } }
                GalleryCell { name: "Progress bar"; ground: "stage"; CuProgressBar { width: 224; ground: "stage"; segments: [1, 3]; value: 0.55 } }
            }
        }

        Section {
            key: "corners"
            title: "Corner A/B: radiusControl 0 and 2"
            note: ""
            visible: page.only === "corners"
            Repeater {
                model: [0, 2]
                Cells {
                    id: corRow
                    required property int modelData
                    readonly property int r: modelData
                    Repeater {
                        model: ["ink", "stage"]
                        GalleryCell {
                            id: corCell
                            required property string modelData
                            name: "radius " + corRow.r + " px, on " + modelData
                            ground: modelData
                            readonly property string g: modelData
                            Column {
                                spacing: 12
                                Rectangle {
                                    width: 224; height: 32; radius: corRow.r; antialiasing: radius > 0; color: Tokens.wellOn(corCell.g)
                                    CuText { x: 8; y: centredIn(32); text: "Warm evening light"; role: "body"; color: Tokens.text1 }
                                }
                                Rectangle {
                                    width: 224; height: 32; radius: corRow.r; antialiasing: radius > 0; color: Tokens.wellOn(corCell.g)
                                    Rectangle {
                                        x: 56 + Tokens.px(Tokens.devPx("inset", page.dpr), page.dpr); y: Tokens.px(Tokens.devPx("inset", page.dpr), page.dpr)
                                        width: 56 - 2 * Tokens.px(Tokens.devPx("inset", page.dpr), page.dpr); height: 32 - 2 * Tokens.px(Tokens.devPx("inset", page.dpr), page.dpr)
                                        radius: Math.max(0, corRow.r - Tokens.px(Tokens.devPx("inset", page.dpr), page.dpr)); antialiasing: radius > 0
                                        color: Tokens.raisedOn(corCell.g)
                                    }
                                    Repeater {
                                        model: ["2×", "4×", "6×", "8×"]
                                        CuText { required property string modelData; required property int index; x: index * 56 + Tokens.snap((56 - implicitWidth) / 2, page.dpr); y: centredIn(32); text: modelData; role: "body"; tabular: true; color: index === 1 ? Tokens.text1 : Tokens.text2 }
                                    }
                                }
                                Rectangle {
                                    width: 224; height: 32; radius: corRow.r; antialiasing: radius > 0; color: Tokens.wellOn(corCell.g)
                                    CuText { x: 8; y: centredIn(32); text: "TIFF, 16-bit"; role: "body"; color: Tokens.text1 }
                                    CuIcon { x: 224 - 24; y: 8; iconName: "chevronDown"; color: Tokens.text3 }
                                }
                                Row {
                                    spacing: 8
                                    Rectangle {
                                        width: 112; height: 32; radius: corRow.r; antialiasing: radius > 0; color: Tokens.tileOn(corCell.g)
                                        CuText { x: Tokens.snap((112 - implicitWidth) / 2, page.dpr); y: centredIn(32); text: "Queue again"; role: "body"; color: Tokens.text2 }
                                    }
                                    Rectangle {
                                        width: 16; height: 16; y: 8; radius: corRow.r; antialiasing: radius > 0; color: Tokens.wellOn(corCell.g)
                                        border.width: Tokens.px(1, page.dpr); border.color: Tokens.controlEdge
                                    }
                                }
                                Rectangle {
                                    width: 224; height: 40; radius: corRow.r; antialiasing: radius > 0; color: Tokens.white
                                    CuText { x: Tokens.snap((224 - implicitWidth) / 2, page.dpr); y: centredIn(40); text: "Upscale 4 images at 4×"; role: "title"; color: Tokens.inkOnWhite }
                                }
                            }
                        }
                    }
                }
            }
        }

        Section {
            key: "demibold"
            title: "Helvetica Neue at Font.Medium and Font.DemiBold, 13 px"
            note: ""
            visible: page.only === "demibold" || page.all
            Cells {
                Repeater {
                    model: [{ n: "Font.Normal", w: Font.Normal }, { n: "Font.Medium", w: Font.Medium }, { n: "Font.DemiBold", w: Font.DemiBold }, { n: "Font.Bold", w: Font.Bold }]
                    GalleryCell {
                        id: dbCell
                        required property var modelData
                        name: modelData.n
                        Column {
                            spacing: 4
                            Text {
                                id: dbText
                                objectName: "demibold-" + dbCell.modelData.n
                                text: "Remove noise, Re-render with AI 0123456789"
                                font.family: Tokens.sans
                                font.pixelSize: 13
                                font.weight: dbCell.modelData.w
                                font.hintingPreference: Tokens.hinting
                                renderType: Tokens.renderType
                                color: Tokens.text1
                            }
                            CuText { text: "advance " + Math.round(dbText.implicitWidth) + " px"; role: "meta"; tabular: true; color: Tokens.text3 }
                        }
                    }
                }
            }
        }
    }
}

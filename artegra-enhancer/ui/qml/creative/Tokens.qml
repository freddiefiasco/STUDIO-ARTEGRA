pragma Singleton
import QtQuick

QtObject {
    id: t

    readonly property FontLoader fontRegular: FontLoader { source: "fonts/InstrumentSans-Regular.ttf" }
    readonly property FontLoader fontMedium: FontLoader { source: "fonts/InstrumentSans-Medium.ttf" }
    readonly property var families: Qt.fontFamilies()
    readonly property string brandFamily: "Helvetica Neue"
    readonly property bool brandFace: families.indexOf(brandFamily) >= 0
    readonly property string fallbackSans: fontRegular.name !== "" ? fontRegular.name : "Instrument Sans"
    readonly property string sans: brandFace ? brandFamily : fallbackSans
    function familyFor(weight) {
        if (brandFace) {
            if (weight >= Font.Medium && families.indexOf(brandFamily + " Medium") >= 0) return brandFamily + " Medium"
            return brandFamily
        }
        if (weight >= Font.Medium && fontMedium.name !== "") return fontMedium.name
        return fallbackSans
    }
    readonly property int renderType: Text.NativeRendering
    readonly property int hinting: Font.PreferVerticalHinting

    readonly property color ink: "#181818"
    readonly property color stage: "#2E2E2E"
    readonly property color float: "#333333"
    readonly property color wellInk: "#0E0E0E"
    readonly property color wellStage: "#232323"
    readonly property color wellFloat: "#282828"
    readonly property color pressInk: "#1D1D1D"
    readonly property color pressStage: "#333333"
    readonly property color pressFloat: "#383838"
    readonly property color tileInk: "#232323"
    readonly property color tileStage: "#393939"
    readonly property color tileFloat: "#3E3E3E"
    readonly property color raisedInk: "#2E2E2E"
    readonly property color raisedStage: "#444444"
    readonly property color raisedFloat: "#494949"
    readonly property color white: "#F2F2F2"
    readonly property color whiteHover: "#FFFFFF"
    readonly property color whitePressed: "#D6D6D6"
    readonly property color dangerBody: "#3D2C27"
    readonly property color checkA: "#3A3A3A"
    readonly property color checkB: "#474747"
    readonly property color surroundMid: "#777777"
    readonly property color tag: "#CC181818"
    readonly property color scrim: "#B8181818"
    readonly property color fillOff: "#4A4A4A"
    readonly property color inkOnWhite: "#181818"
    function groundKey(g) { return g === "stage" || g === "opening" ? "stage" : (g === "float" || g === "plate" ? "float" : "ink") }
    function groundTone(g) { var k = groundKey(g); return k === "stage" ? stage : (k === "float" ? float : ink) }
    function wellOn(g) { var k = groundKey(g); return k === "stage" ? wellStage : (k === "float" ? wellFloat : wellInk) }
    function pressOn(g) { var k = groundKey(g); return k === "stage" ? pressStage : (k === "float" ? pressFloat : pressInk) }
    function tileOn(g) { var k = groundKey(g); return k === "stage" ? tileStage : (k === "float" ? tileFloat : tileInk) }
    function raisedOn(g) { var k = groundKey(g); return k === "stage" ? raisedStage : (k === "float" ? raisedFloat : raisedInk) }
    function trackOn(g) { return groundKey(g) === "stage" ? trackStage : trackInk }
    function ruleOn(g) { return groundKey(g) === "ink" ? rule : reveal }

    property bool surroundMidGrey: false
    property real clockSkewMs: 0
    function wallNow() { return Date.now() + clockSkewMs }

    readonly property color rule: "#2C2C2C"
    readonly property color reveal: "#474747"
    readonly property color trackInk: "#4A4A4A"
    readonly property color trackStage: "#5C5C5C"
    readonly property color controlEdge: "#808080"
    readonly property color pictureRing: "#1AF2F2F2"
    readonly property color liveOutline: "#F2F2F2"
    readonly property color liveOutlineHalo: "#73000000"
    readonly property color protectTint: "#E0694E"
    readonly property color protectFill: "#40E0694E"
    readonly property color protectEdge: "#B3E0694E"

    readonly property color text1: "#EDEDED"
    readonly property color text2: "#BABABA"
    readonly property color text3: "#999999"
    readonly property color text4: "#6E6E6E"
    readonly property color danger: "#F08C72"
    readonly property color focus: "#EDEDED"
    function onBody(tone, body) { return body && Qt.colorEqual(tone, text3) ? text2 : tone }
    function quietOn(g) { return groundKey(g) === "float" ? text2 : text3 }

    readonly property var type: ({
        "meta":          { size: 12, line: 16, weight: Font.Normal, track: 0.1 },
        "body":          { size: 13, line: 18, weight: Font.Normal, track: 0.05 },
        "bodyStrong":    { size: 13, line: 18, weight: Font.Medium, track: 0.05 },
        "title":         { size: 14, line: 20, weight: Font.Medium, track: 0 },
        "heading":       { size: 18, line: 24, weight: Font.Medium, track: -0.2 },
        "display":       { size: 18, line: 24, weight: Font.Medium, track: -0.2 },
        "dialog":        { size: 18, line: 24, weight: Font.Medium, track: -0.2 },
        "clock":         { size: 13, line: 18, weight: Font.Normal, track: 0.05 },
        "reading":       { size: 13, line: 18, weight: Font.Normal, track: 0.05 },
        "action":        { size: 14, line: 20, weight: Font.Medium, track: 0 },
        "label":         { size: 13, line: 18, weight: Font.Normal, track: 0.05 },
        "small":         { size: 12, line: 16, weight: Font.Normal, track: 0.1 },
        "micro":         { size: 12, line: 16, weight: Font.Normal, track: 0.1 },
        "mono":          { size: 13, line: 18, weight: Font.Normal, track: 0.05 },
        "trayTitle":     { size: 14, line: 20, weight: Font.Medium, track: 0 },
        "labelSm":       { size: 13, line: 18, weight: Font.Normal, track: 0.05 },
        "caption":       { size: 12, line: 16, weight: Font.Normal, track: 0.1 },
        "captionStrong": { size: 12, line: 16, weight: Font.Normal, track: 0.1 },
        "keycap":        { size: 12, line: 16, weight: Font.Normal, track: 0.1 },
        "control":       { size: 13, line: 18, weight: Font.Normal, track: 0.05 },
        "controlLg":     { size: 13, line: 18, weight: Font.Normal, track: 0.05 },
        "controlSm":     { size: 12, line: 16, weight: Font.Normal, track: 0.1 },
        "readingLg":     { size: 13, line: 18, weight: Font.Normal, track: 0.05 },
        "readingSm":     { size: 12, line: 16, weight: Font.Normal, track: 0.1 }
    })
    readonly property var typeSizes: [12, 13, 14, 18]
    readonly property var typeWeights: [400, 500]
    function isReadingRole(role) { return role === "readingSm" || role === "readingLg" }
    function toneFor(role) { return isReadingRole(role) ? readingTone : text1 }
    function sizeRole(px) { return px <= 12 ? "meta" : (px <= 13 ? "body" : (px <= 14 ? "title" : "heading")) }
    function controlRole(role) { var s = (type[role] || type.body).size; return s <= 12 ? "meta" : "body" }
    function readingRole(role) { return controlRole(role) }
    function lineOf(role) { return (type[role] || type.body).line }
    readonly property FontMetrics capMetrics: FontMetrics { font.hintingPreference: t.hinting }
    property var capCache: ({})
    function capHeightFor(f) {
        var k = f.family + "|" + f.pixelSize + "|" + f.weight + "|" + f.hintingPreference
        var v = capCache[k]
        if (v !== undefined) return v
        capMetrics.font = f
        v = capMetrics.tightBoundingRect("H").height
        if (!(v > 0)) v = f.pixelSize * 0.7
        capCache[k] = v
        return v
    }
    function fontFor(role, tabular) {
        var s = type[role] || type.body
        return Qt.font({ family: familyFor(s.weight), pixelSize: s.size, weight: s.weight,
                         letterSpacing: s.track, hintingPreference: hinting, features: { "tnum": tabular ? 1 : 0 } })
    }

    function nameParse(name) {
        var s = name || ""
        var dot = s.lastIndexOf(".")
        var stem = dot > 0 ? s.slice(0, dot) : s
        var ext = dot > 0 ? s.slice(dot) : ""
        var sfx = /_cu\d+x(?:_fast)?(?:_\d+)?$/.exec(stem)
        if (sfx && sfx.index > 0) { ext = stem.slice(sfx.index) + ext; stem = stem.slice(0, sfx.index) }
        var parts = stem.split(/([_ ])/)
        if (parts.length === 1 && stem.indexOf("-") > 0) parts = stem.split(/(-)/)
        var last = parts[parts.length - 1]
        var tails = []
        if (parts.length >= 5) tails.push(parts.slice(parts.length - 3).join(""))
        if (parts.length >= 3) tails.push(last)
        tails.push(stem.length > 8 ? stem.slice(stem.length - 8) : stem)
        var secondCode = parts.length >= 5 && (/\d/.test(parts[parts.length - 3]) || /^\d+$/.test(last))
        return { stem: stem, ext: ext, parts: parts, first: parts[0], last: last, tails: tails, secondCode: secondCode }
    }
    function nameFloors(name, metrics) {
        var w = function(x) { return metrics && typeof metrics.advanceWidth === "function" ? metrics.advanceWidth(x) : x.length * 7 }
        var s = name || ""
        var full = w(s)
        var p = nameParse(s)
        if (p.parts.length < 3) return { project: full, code: full }
        var proj
        if (p.secondCode) {
            proj = w(p.first + "…" + p.tails[0] + p.ext)
            return { project: Math.min(full, proj), code: Math.min(full, proj, w("…" + p.tails[0] + p.ext)) }
        }
        proj = w(p.first + "…" + p.last + p.ext)
        var re = /[a-z](?=[A-Z])/g, m
        while ((m = re.exec(p.last)) !== null) proj = Math.min(proj, w(p.first + "…" + p.last.slice(m.index + 1) + p.ext))
        proj = Math.min(full, proj)
        return { project: proj, code: proj }
    }
    function nameKeepsRule(full, shown, allowCodeWins) {
        if (shown === full) return true
        var p = nameParse(full)
        var head = shown.indexOf(p.first) === 0
        var code = p.secondCode ? p.tails[0] + p.ext : ""
        var hasCode = code === "" || (shown.length >= code.length && shown.slice(shown.length - code.length) === code)
        if (!p.secondCode) return head
        return hasCode && (head || allowCodeWins === true)
    }
    function elideName(name, width, metrics, allowCodeWins) {
        var s = name || ""
        var w = function(x) { return metrics && typeof metrics.advanceWidth === "function" ? metrics.advanceWidth(x) : x.length * 7 }
        if (s === "" || w(s) <= width) return s
        var np = nameParse(s)
        var stem = np.stem
        var ext = np.ext
        var parts = np.parts
        var first = np.first
        var last = np.last
        var tails = np.tails
        function withHead(tail) {
            var tt = tail + ext
            for (var n = stem.length - tail.length - 1; n >= first.length; --n) {
                var head = stem.slice(0, n)
                var cut = Math.max(head.lastIndexOf("_"), head.lastIndexOf(" "), head.lastIndexOf("-"))
                if (cut >= first.length && n - cut <= 4) head = head.slice(0, cut)
                var cand = head.replace(/[_ \-]+$/, "") + "…" + tt
                if (w(cand) <= width) return cand
            }
            return null
        }
        var secondCode = parts.length >= 5 && (/\d/.test(parts[parts.length - 3]) || /^\d+$/.test(last))
        var subs = []
        if (parts.length >= 3) {
            var re = /[a-z](?=[A-Z])/g, m
            while ((m = re.exec(last)) !== null) subs.push(last.slice(m.index + 1))
        }
        var order = []
        var i
        if (tails.length === 3) {
            order.push(["h", tails[0]])
            if (secondCode && allowCodeWins) order.push(["n", tails[0]])
            order.push(["h", tails[1]])
            for (i = 0; i < subs.length; ++i) order.push(["h", subs[i]])
            if (secondCode && !allowCodeWins) order.push(["n", tails[0]])
            order.push(["n", tails[1]])
            for (i = 0; i < subs.length; ++i) order.push(["n", subs[i]])
            order.push(["n", tails[2]])
        } else {
            for (i = 0; i < tails.length; ++i) order.push(["h", tails[i]])
            for (i = 0; i < tails.length; ++i) order.push(["n", tails[i]])
        }
        for (i = 0; i < order.length; ++i) {
            if (order[i][0] === "h") {
                var c = withHead(order[i][1])
                if (c !== null) return c
            } else if (w("…" + order[i][1] + ext) <= width) {
                return "…" + order[i][1] + ext
            }
        }
        return "…" + ext
    }
    function nameKeepsProject(full, shown) {
        var first = nameParse(full || "").first
        return shown === full || (first !== "" && (shown || "").indexOf(first) === 0)
    }

    function snap(v, dpr) { var d = dpr > 0 ? dpr : 1; return Math.floor(v * d + 0.001) / d }
    readonly property var devPxTable: ({
        "line":  [1, 1, 1, 1, 2],
        "beam":  [2, 2, 2, 2, 3],
        "bar":   [2, 2, 3, 3, 4],
        "tick":  [2, 2, 3, 3, 4],
        "check": [2, 2, 2, 2, 3],
        "inset": [2, 3, 3, 3, 4],
        "ring":  [2, 3, 3, 3, 4],
        "icon":  [1, 2, 2, 2, 3]
    })
    function scaleColumn(dpr) {
        var d = dpr > 0 ? dpr : 1
        return d >= 1.999 ? 4 : (d >= 1.749 ? 3 : (d >= 1.499 ? 2 : (d >= 1.249 ? 1 : 0)))
    }
    function devPx(mark, dpr) { var row = devPxTable[mark] || devPxTable.line; return row[scaleColumn(dpr)] }
    function px(n, dpr) { var d = dpr > 0 ? dpr : 1; return n / d }
    function devOf(v, dpr, min) { var d = dpr > 0 ? dpr : 1; return Math.max(min || 0, Math.floor(v * d + 0.001)) }
    function strokePx(dpr) { return devPx("icon", dpr) }
    function tickPx(dpr, thin) { return thin ? devPx("icon", dpr) : devPx("check", dpr) }

    readonly property int unit: 8
    readonly property int sp4: 4
    readonly property int sp8: 8
    readonly property int sp12: 12
    readonly property int sp16: 16
    readonly property int sp24: 24
    readonly property int sp32: 32
    readonly property int sp48: 48
    readonly property int sp64: 64
    readonly property int gapStack: 8
    readonly property int gapTitle: 12
    readonly property int gapUnit: 16
    readonly property int gapSection: 32
    readonly property int legInset: 16
    readonly property int openingInset: 24
    readonly property int blockAirMin: 24
    readonly property int dialogPad: 24
    readonly property int menuPad: 4
    readonly property int textInset: 8
    readonly property int legContentMin: 224
    readonly property int settingControl: 240
    readonly property int wellFigure: 96
    readonly property int pageColumn: 560
    function onGrid(v) { return Math.ceil(v / 4) * 4 }
    readonly property int hControl: 32
    readonly property int hCommit: 40
    readonly property int hBand: 48
    readonly property int hRowMedia: 48
    readonly property int hRow: 40
    readonly property int hRowSetting: 56
    readonly property int hGroupHead: 40
    readonly property int hMenuItem: 32
    readonly property int hTitleRow: 24
    readonly property int hLabelRow: 20
    readonly property int hFactRow: 24
    readonly property int hScaleRow: 16
    readonly property int hNamesRow: 16
    readonly property int hSliderName: 24
    readonly property int hSlider: 40
    readonly property int hLook: 32
    readonly property int hTag: 28
    readonly property int hToastOne: 40
    readonly property int hToastTwo: 56
    readonly property int toastAir: 10
    readonly property int hRowWord: 20
    readonly property int captionMin: 480
    readonly property int loupeSize: 200
    readonly property int hTipLine: 32
    readonly property int hFootSlot: 84
    readonly property int hFootStatus: 20
    readonly property int capSlot: 64
    readonly property int checkSize: 16
    readonly property int iconBox: 16
    readonly property int hitScale: 24
    readonly property int tickLong: 12
    readonly property int stopShort: 6
    readonly property int lookMark: 8
    readonly property int chevronCell: 32
    readonly property int tileGlyphPad: 12
    readonly property int textControlPad: 8
    readonly property int whitePadMin: 24
    readonly property int recessColumn: 400
    readonly property int menuMinWidth: 160
    readonly property int tooltipMaxWidth: 280
    readonly property int tooltipMaxLines: 3
    readonly property int dialogQuestion: 480
    readonly property int dialogForm: 560
    readonly property int detailsWidth: 320
    readonly property int keyBarWidth: 12
    readonly property int keyBarHeight: 3
    readonly property int overlayBarWidth: 4
    readonly property int panelsToggleSize: 32
    readonly property int brandUnit: 8
    readonly property int miniBoxWidth: 36
    readonly property int miniBoxHeight: 24
    readonly property int markSize: 8
    readonly property int markMinPx: 2
    readonly property int gripWidth: 3
    readonly property int gripHeight: 24
    function legWidth(w) { return w < 1240 ? 256 : (w < 1600 ? 280 : (w < 2200 ? 320 : 360)) }
    function settingsInset(w) { return 16 }
    readonly property string hiddenSpan: "window"

    readonly property real radiusControl: 2
    function innerRadius(r, inset) { return Math.max(0, r - inset) }

    readonly property url shadowFloat: Qt.resolvedUrl("assets/shadow-float.png")
    readonly property int shadowFloatMargin: 48
    readonly property int shadowFloatBorder: 72
    readonly property url shadowModal: Qt.resolvedUrl("assets/shadow-modal.png")
    readonly property int shadowModalMargin: 96
    readonly property int shadowModalBorder: 144

    property bool reduceMotion: false
    readonly property int durHoverIn: 0
    readonly property int durHoverOut: reduceMotion ? 120 : 150
    readonly property int durPress: 60
    readonly property int durChosen: reduceMotion ? 0 : 160
    readonly property int durSection: reduceMotion ? 0 : 200
    readonly property int durLegs: reduceMotion ? 0 : 240
    readonly property int durLegsIn: reduceMotion ? 0 : 200
    readonly property int durSheet: reduceMotion ? 120 : 200
    readonly property int durFloatIn: 120
    readonly property int durFloatOut: 80
    readonly property int durFill: reduceMotion ? 0 : 250
    readonly property int durReveal: reduceMotion ? 0 : 300
    readonly property int tooltipDelay: 500
    readonly property int tooltipPeerWindow: 400
    readonly property var easeEnter: [0.16, 1, 0.3, 1, 1, 1]
    readonly property var easeTravel: [0.65, 0, 0.35, 1, 1, 1]

    property double tipClosedAt: 0
    function tipDelay() { return (Date.now() - tipClosedAt) < tooltipPeerWindow ? 0 : tooltipDelay }
    property var tipsShown: []
    readonly property int tipsOpen: tipsShown.length
    function tipsLive(list, gone) {
        return list.filter(function(x) {
            try { return x !== gone && x !== null && x !== undefined && x.visible === true } catch (e) { return false }
        })
    }
    function tipShown(tp) { if (tp && tipsShown.indexOf(tp) < 0) tipsShown = tipsLive(tipsShown, null).concat([tp]) }
    function tipGone(tp) {
        var a = tipsLive(tipsShown, tp)
        if (a.length !== tipsShown.length) tipsShown = a
    }
    function dismissTips() {
        var a = tipsShown.slice()
        tipsShown = []
        for (var i = 0; i < a.length; ++i) {
            try { if (a[i]) a[i].dismiss() } catch (e) {}
        }
        return a.length
    }

    function keyTip(words, key) { return key ? words + "  " + key : words }
    function keyTipParts(text) {
        var m = /^(.*\S)  (\S{1,16})$/.exec(text || "")
        if (!m) return null
        var k = m[2]
        var keys = k === "+" ? ["+"] : k.split("+").filter(function(s) { return s !== "" })
        return keys.length > 0 ? { words: m[1], key: k, keys: keys } : null
    }

    readonly property var glyphs: ["add", "addFolder", "folder", "grid", "panels", "panelsOff",
                                   "chevronRight", "chevronDown", "chevronUp", "chevronLeft"]
    readonly property var glyphKinds: ({ "add": "add", "addFolder": "add folder", "folder": "open folder", "grid": "review results",
                                         "panels": "panels toggle", "panelsOff": "panels toggle", "chevronRight": "chevron",
                                         "chevronDown": "chevron", "chevronUp": "chevron", "chevronLeft": "chevron" })
    readonly property var glyphAliases: ({ "plus": "add", "inbox_import": "add", "add_folder": "addFolder", "folder_add": "addFolder",
                                           "folder_open": "folder", "folderOpen": "folder", "openFolder": "folder",
                                           "outputs_folder": "folder", "browse_folder": "folder", "logs_folder": "folder",
                                           "results": "grid", "reviewResults": "grid", "panels_hidden": "panelsOff",
                                           "chevron_right": "chevronRight", "chevron_down": "chevronDown",
                                           "chevron_up": "chevronUp", "chevron_left": "chevronLeft" })
    function glyphName(name) { return glyphAliases[name] !== undefined ? glyphAliases[name] : name }
    function isGlyph(name) { return glyphs.indexOf(glyphName(name)) >= 0 }
    readonly property var signs: glyphs
    function isSign(name) { return isGlyph(name) }

    readonly property url checkerTile: Qt.resolvedUrl("assets/checker-8.png")
    readonly property int checkerSize: 8
    readonly property url wordmark: Qt.resolvedUrl("assets/brand/SA_LOGO-03.svg")
    readonly property url brandmarkSvg: Qt.resolvedUrl("assets/brand/SA_BRANDMARK-01.svg")

    readonly property int revealMargin: 16
    function revealY(view, top, bottom) {
        var lo = view.originY - view.topMargin
        var hi = Math.max(lo, view.originY + view.contentHeight + view.bottomMargin - view.height)
        var y = view.contentY
        var m = revealMargin
        if (bottom - top > view.height - 2 * m) y = top - m
        else if (top < y + m) y = top - m
        else if (bottom > y + view.height - m) y = bottom - view.height + m
        return Math.round(Math.max(lo, Math.min(hi, y)))
    }

    readonly property color opening: "#2E2E2E"
    readonly property color surround: "#2E2E2E"
    readonly property color ground: "#2E2E2E"
    readonly property color panel: "#181818"
    readonly property color inset: "#181818"
    readonly property color panelClear: "#00181818"
    readonly property color groundClear: "#002E2E2E"
    readonly property color selected: "#2E2E2E"
    readonly property color active: "#2E2E2E"
    readonly property color field: "#0E0E0E"
    readonly property color fieldOp: "#232323"
    readonly property color raised: "#0E0E0E"
    readonly property color plate: "#333333"
    readonly property color overlay: "#333333"
    readonly property color rowHover: "#232323"
    readonly property color hoverInk: "#232323"
    readonly property color pressedInk: "#1D1D1D"
    readonly property color chosenInk: "#2E2E2E"
    readonly property color trackOp: "#393939"
    readonly property color hoverOp: "#393939"
    readonly property color pressedOp: "#333333"
    readonly property color chosenOp: "#444444"
    readonly property color trackPlate: "#3E3E3E"
    readonly property color hoverPlate: "#3E3E3E"
    readonly property color pressedPlate: "#383838"
    readonly property color chosenPlate: "#494949"
    readonly property color accentSubtle: "#2E2E2E"
    readonly property color segmentHighlight: "#2E2E2E"
    readonly property color overlayHover: "#3E3E3E"
    readonly property color overlayPressed: "#383838"
    readonly property color tagFill: "#CC181818"
    readonly property color plateLabel: "#CC181818"
    readonly property color plateChecker: "#474747"
    readonly property color printCornerTop: "#2E2E2E"
    readonly property color printCornerBottom: "#2E2E2E"
    readonly property color miniaturePlaceholder: "#0E0E0E"
    readonly property color primaryDisabledFill: "#232323"
    readonly property color warningSubtle: "#232323"
    readonly property color successSubtle: "#2E2E2E"
    readonly property color infoSubtle: "#2E2E2E"
    readonly property color dangerSubtle: "#3D2C27"
    readonly property color dangerSoft: "#3D2C27"
    readonly property color dropTint: "#00000000"
    readonly property color ruleOp: "#474747"
    readonly property color hairline: "#2C2C2C"
    readonly property color hairlineStrong: "#474747"
    readonly property color plateEdge: "#474747"
    readonly property color overlayLine: "#474747"
    readonly property color sliderTrack: "#4A4A4A"
    readonly property color tick: "#4A4A4A"
    readonly property color cellToCome: "#5C5C5C"
    readonly property color controlLine: "#808080"
    readonly property color warningLine: "#808080"
    readonly property color dangerLine: "#F08C72"
    readonly property color seamLine: "#F2F2F2"
    readonly property color seamHalo: "#66000000"
    readonly property color scrollThumbRest: "#4A4A4A"
    readonly property color scrollThumbRestOverlay: "#4A4A4A"
    readonly property color scrollThumbHover: "#999999"
    readonly property color scrollThumb: "#4A4A4A"
    readonly property color textDisabled: "#6E6E6E"
    readonly property color textPlaceholder: "#999999"
    readonly property color textTertiary: "#999999"
    readonly property color linkUnderline: "#999999"
    readonly property color textSelection: "#4A4A4A"
    readonly property color controlTone: "#BABABA"
    readonly property color readingTone: "#BABABA"
    readonly property color readingQuietTone: "#999999"
    readonly property color textOption: "#EDEDED"
    readonly property color selectionText: "#EDEDED"
    readonly property color selectText: "#EDEDED"
    readonly property color selectFill: "#EDEDED"
    readonly property color dangerText: "#F08C72"
    readonly property color warningText: "#999999"
    readonly property color successText: "#EDEDED"
    readonly property color thumbActive: "#EDEDED"
    readonly property color primary: "#F2F2F2"
    readonly property color primaryHover: "#FFFFFF"
    readonly property color primaryPressed: "#D6D6D6"
    readonly property color primaryHighlight: "#F2F2F2"
    readonly property color primaryDisabledText: "#6E6E6E"
    readonly property color inkOnPrimary: "#181818"
    readonly property color selectionMark: "#EDEDED"
    readonly property color inkOnSelectionMark: "#181818"
    readonly property color accent: "#EDEDED"
    readonly property color accentHover: "#FFFFFF"
    readonly property color inkOnAccent: "#181818"
    readonly property color accentFill: "#F2F2F2"
    readonly property color accentFillPressed: "#D6D6D6"
    readonly property color accentLine: "#EDEDED"
    readonly property color focusRing: "#EDEDED"
    readonly property color switchKnob: "#EDEDED"
    readonly property color warning: "#999999"
    readonly property color success: "#EDEDED"
    readonly property color info: "#EDEDED"
    readonly property color maskTint: "#E0694E"
    readonly property color shadowNear: "#40000000"
    readonly property color shadowFar: "#1F000000"
    readonly property color shadowDialog: "#55000000"
    readonly property color onAccent: inkOnWhite
    readonly property color onSelect: inkOnWhite
    readonly property bool lightFace: false
    readonly property int lightWeight: Font.Normal
    readonly property string mono: brandFace ? brandFamily : fallbackSans
    readonly property int sp2: 2
    readonly property int sp6: 6
    readonly property int sp20: 20
    readonly property int s1: 4
    readonly property int s2: 8
    readonly property int s3: 12
    readonly property int s4: 16
    readonly property int s5: 24
    readonly property int s6: 32
    readonly property int gutter: 0
    readonly property int trayPad: 16
    readonly property int sectionAbove: 32
    readonly property int sectionBelow: 12
    readonly property int sectionRuleGap: 16
    readonly property int controlGap: 8
    readonly property int iconGap: 8
    readonly property int textControlGap: 12
    readonly property int toggleGap: 8
    readonly property int toolGroupGap: 12
    readonly property int fieldPad: 8
    readonly property int textBleed: 8
    readonly property int tipGap: 8
    readonly property int tipGapSide: 8
    readonly property int focusAir: 24
    readonly property int blockAir: 24
    readonly property int pictureMargin: 24
    readonly property int legInsetNarrow: 16
    readonly property int settingsInsetWide: 16
    readonly property int groupAir: 24
    readonly property int trayTitleY: 12
    readonly property int hHeader: 48
    readonly property int hToolLine: 48
    readonly property int hTopBand: 48
    readonly property int hTrayHeader: 48
    readonly property int headerHeight: 48
    readonly property int hImageRow: 48
    readonly property int hTile: 32
    readonly property int hSegment: 32
    readonly property int hSegTrack: 32
    readonly property int hToolItem: 32
    readonly property int hIconButton: 32
    readonly property int hToggle: 32
    readonly property int controlHeight: 32
    readonly property int hControlSm: 32
    readonly property int wellHeight: 32
    readonly property int hWhite: 40
    readonly property int hPrimary: 40
    readonly property int primaryHeight: 40
    readonly property int hAddStrip: 40
    readonly property int hSectionRow: 40
    readonly property int hStepRow: 40
    readonly property int hSliderRow: 40
    readonly property int hCheckRow: 32
    readonly property int hToast: 40
    readonly property int hText: 32
    readonly property int hit: 32
    readonly property int sliderHit: 24
    readonly property int lookTickHeight: 12
    readonly property int tickWidth: 2
    readonly property int tagHeight: 28
    readonly property int hChip: 28
    readonly property int hBar: 2
    readonly property int hRowBar: 2
    readonly property int icon: 16
    readonly property int iconSign: 16
    readonly property int iconLarge: 16
    readonly property int thumb: 48
    readonly property int miniHeight: 24
    readonly property int miniMaxWidth: 36
    readonly property int miniMinSide: 4
    readonly property int tipPicture: 192
    readonly property int hFoot: 104
    readonly property int hDock: 104
    readonly property int hDockIdle: 104
    readonly property int hFooter: 104
    readonly property int hFooterTight: 104
    readonly property int hGroupHeading: 16
    readonly property int rulerRow: 16
    readonly property int hKeycap: 18
    readonly property int hKeycapSm: 18
    readonly property int wellWidth: 48
    readonly property int edgeFade: 16
    readonly property int sliderTickHeight: 12
    readonly property int sliderTickPressedHeight: 12
    readonly property int sliderMarkHeight: 8
    readonly property int lookStopHeight: 6
    readonly property int rulerCells: 30
    readonly property int rulerCellHeight: 3
    readonly property int rulerBarGap: 16
    readonly property int rulerLabelWidth: 56
    readonly property int headerTop: 7
    readonly property int headerGap: 1
    readonly property int textCaption: 12
    readonly property int textHelp: 13
    readonly property int textBody: 13
    readonly property int textTitle: 14
    readonly property int textDisplay: 18
    readonly property int rPanel: 0
    readonly property int rSheet: 0
    readonly property int rFloat: 0
    readonly property int rControl: 0
    readonly property int rTrack: 0
    readonly property int rSegment: 0
    readonly property int rRow: 0
    readonly property int rThumb: 0
    readonly property int rTip: 0
    readonly property int rChip: 0
    readonly property int rCheck: 0
    readonly property int rPicture: 0
    readonly property int rMiniature: 0
    readonly property int rText: 0
    readonly property int radiusChip: 0
    readonly property int radiusInput: 0
    readonly property int radiusPanel: 0
    readonly property bool printShadow: false
    readonly property int shadowPrintMargin: 72
    readonly property int shadowPrintBorder: 108
    readonly property int durState: reduceMotion ? 120 : 200
    readonly property int durMove: reduceMotion ? 0 : 160
    readonly property int durIndicator: reduceMotion ? 0 : 160
    readonly property int durOverlayIn: reduceMotion ? 0 : 120
    readonly property int durOverlayOut: reduceMotion ? 0 : 80
    readonly property int durOverlayMove: 0
    readonly property int durTooltipFade: 0
    readonly property int durSheetIn: reduceMotion ? 0 : 200
    readonly property int durSheetOut: reduceMotion ? 0 : 200
    readonly property int durSpinTurn: reduceMotion ? 3000 : 1000
    readonly property int durFieldFocus: 0
    readonly property int spinnerShowDelay: 200
    readonly property int spinnerMinHold: 400
    readonly property int durFast: 120
    readonly property int durBase: reduceMotion ? 0 : 200
    readonly property int durPanel: reduceMotion ? 0 : 240
    readonly property var easeOut: easeEnter
    function imageTrayWidth(w) { return legWidth(w) }
    function settingsTrayWidth(w) { return legWidth(w) }
    function settingsPad(w) { return settingsInset(w) }
}

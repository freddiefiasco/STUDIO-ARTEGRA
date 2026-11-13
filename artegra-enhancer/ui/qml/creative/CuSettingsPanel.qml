import QtQuick
import QtQuick.Window
import "format.js" as F

Rectangle {
    id: panel
    objectName: "settingsLeg"
    property var tab: null
    color: Tokens.ink
    readonly property bool tipBounds: true
    Accessible.role: Accessible.Pane
    Accessible.name: "Settings"

    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int pad: Tokens.legInset
    readonly property int cw: Math.max(0, width - 2 * pad)
    readonly property int winH: Window.window ? Window.window.height : height + Tokens.hBand
    readonly property bool tall: winH >= 1000
    readonly property real hs: Tokens.snap(height, dpr)
    readonly property real footY: hs - Tokens.hFootSlot
    readonly property real footTop: y + footY
    property Item detailsAnchor: null
    readonly property bool sheetOpen: tab !== null && tab.sheetOpen === true

    readonly property var b: tab ? tab.batch : ({ active: false })
    readonly property bool running: b.active === true
    readonly property var row: tab ? tab.selectedRow : null
    readonly property bool rowHasSize: row !== null && row.srcW > 0 && row.srcH > 0
    readonly property var input: rowHasSize && row.kind === "input" ? tab.inputFor(row.mediaId) : null
    readonly property string rowState: row ? String(row.status || "") : ""
    readonly property bool rowStopped: row !== null && row.kind === "job" && (rowState === "stopped" || rowState === "cancelled" || row.group === "stopped")
    readonly property bool rowFinished: row !== null && row.kind === "job" && rowState === "done"
    readonly property bool rowRan: row !== null && row.kind === "job" && ["stopped", "failed", "cancelled", "done"].indexOf(rowState) >= 0
    readonly property bool perImage: tab !== null && tab.perImageSettings === true
    readonly property int othersWaiting: {
        var n = 0
        for (var i = 0; i < waitingRows.length; ++i) if (!(rowStopped && row && waitingRows[i].key === row.key)) n += 1
        return n
    }
    readonly property string localScope: !running ? "selected"
                                       : !perImage ? "next"
                                       : rowStopped ? (othersWaiting > 0 ? "this+waiting" : "this")
                                       : (othersWaiting > 0 ? "waiting" : "next")
    readonly property string scope: {
        var s = tab ? tab.scope : undefined
        if (s === "none") return "selected"
        if (s === "waiting") return "waiting"
        if (s === "thisAndWaiting") return "this+waiting"
        if (s === "this") return "this"
        if (s === "next") return "next"
        return localScope
    }
    readonly property bool scopeShown: running && scope !== "selected"
    readonly property string scopeWords: scope === "this+waiting" ? "Changes apply to this image and the waiting ones."
                                       : scope === "this" ? "Changes apply to this image."
                                       : scope === "waiting" ? "Changes apply to the waiting images."
                                       : "Changes apply to the images you queue next."
    FontMetrics { id: bodyMetrics; font: Tokens.fontFor("body") }
    FontMetrics { id: metaMetrics; font: Tokens.fontFor("meta") }
    readonly property string scopeLines: {
        var t = scopeWords
        if (bodyMetrics.advanceWidth(t) <= cw) return t
        var at = t.indexOf(" and the waiting")
        if (at < 0) at = t.indexOf(" you queue")
        return at > 0 ? t.slice(0, at) + "\n" + t.slice(at + 1) : t
    }

    readonly property var allRows: {
        var out = []
        var m = tab ? tab.rowsByKey : null
        if (!m) return out
        for (var k in m) out.push(m[k])
        return out
    }
    readonly property var waitingRows: {
        var out = []
        for (var i = 0; i < allRows.length; ++i) {
            var r = allRows[i]
            if (r.kind === "input") { out.push(r); continue }
            if (r.kind !== "job") continue
            if (perImage && (r.status === "queued" || r.status === "interrupted")) out.push(r)
            else if (perImage && rowStopped && row && r.key === row.key) out.push(r)
        }
        return out
    }
    readonly property var scaleRefRows: {
        if (!running) return []
        if (waitingRows.length > 0) return waitingRows
        var out = []
        var ids = b.jobIds || []
        for (var i = 0; i < allRows.length; ++i)
            if (allRows[i].kind === "job" && ids.indexOf(allRows[i].jobId) >= 0) out.push(allRows[i])
        return out
    }
    onScaleRefRowsChanged: Qt.callLater(panel.planRefRows)
    function planRefRows() {
        if (!tab || typeof tab.ensurePlansForRow !== "function") return
        for (var i = 0; i < scaleRefRows.length; ++i)
            if (scaleRefRows[i].kind === "job") tab.ensurePlansForRow(scaleRefRows[i])
    }
    function rowTakes(r, s) {
        if (r.kind === "input") { var inp = tab.inputFor(r.mediaId); return inp ? tab.inputRefusal(inp, s) === "" : true }
        var p = tab.planFor(r.srcW, r.srcH, s)
        return p === null || p.ok !== false
    }
    function rowFactor(r) {
        if (r.kind === "input") return tab.scale
        if (r.effective && r.effective.scale) return Number(r.effective.scale)
        return Number(r.factor) || tab.scale
    }
    readonly property var waitingScales: {
        var out = []
        for (var i = 0; i < waitingRows.length; ++i) {
            var s = rowFactor(waitingRows[i])
            if (out.indexOf(s) < 0) out.push(s)
        }
        out.sort(function(a, c) { return a - c })
        return out
    }
    readonly property bool mixed: running && perImage && waitingScales.length > 1
    readonly property string mixedWords: {
        if (!mixed) return ""
        var w = waitingScales.map(function(s) { return F.scaleLabel(s) })
        return "Mixed: " + (w.length === 2 ? w[0] + " and " + w[1] : w.slice(0, -1).join(", ") + " and " + w[w.length - 1])
    }
    readonly property var scaleValue: mixed ? undefined
                                     : (running && perImage && waitingScales.length === 1 ? waitingScales[0] : (tab ? tab.scale : 2))

    property bool fastKnown: false
    property string fastReason: ""
    property string fastMessage: ""
    property var fastLooks: ["Light", "Default"]
    property int fastMaxFactor: 2
    readonly property var healthNow: tab ? tab.health : null
    function readFast() {
        var f = healthNow && healthNow.engine && healthNow.engine.fast ? healthNow.engine.fast : null
        if (f === null) return
        var on = f.available === true
        var why = on ? "" : String(f.reason || "")
        if (why !== fastReason) fastReason = why
        var msg = on ? "" : String(f.message || "")
        if (msg !== fastMessage) fastMessage = msg
        if (f.looks && f.looks.length > 0) {
            var l = []
            for (var i = 0; i < f.looks.length; ++i) l.push(String(f.looks[i]))
            if (l.join("|") !== fastLooks.join("|")) fastLooks = l
        }
        var mf = Number(f.max_factor)
        if (mf > 0 && mf !== fastMaxFactor) fastMaxFactor = mf
        var shown = on || why === "files_missing"
        if (shown !== fastKnown) fastKnown = shown
    }
    onHealthNowChanged: readFast()
    Component.onCompleted: readFast()
    readonly property bool modeShown: fastKnown && tab !== null && tab.mode !== undefined && typeof tab.setMode === "function"
    readonly property var modeList: {
        var list = tab && tab.controlsInfo && tab.controlsInfo.modes ? tab.controlsInfo.modes : []
        return list.length >= 2 ? list : [{ key: "standard", label: "Standard", text: "" }, { key: "fast", label: "Fast", text: "" }]
    }
    readonly property string fastText: {
        for (var i = 0; i < modeList.length; ++i) if (modeList[i].key === "fast") return String(modeList[i].text || "")
        return ""
    }
    readonly property bool fastUsable: modeShown && fastReason === ""
    function sizeRefusalOf(r) {
        if (!r || !tab) return null
        if (r.kind === "input") return typeof tab.fastSizeRefusal === "function" ? tab.fastSizeRefusal(tab.inputFor(r.mediaId)) : null
        var p = r.srcW > 0 && r.srcH > 0 ? tab.planFor(r.srcW, r.srcH, 2) : null
        var f = p && p.finish ? p.finish.fast_refusal : null
        return f && f.reason === "size" ? f : null
    }
    readonly property var modeTargets: {
        if (!tab) return []
        if (running) return waitingRows
        var out = []
        for (var i = 0; i < allRows.length; ++i) if (allRows[i].kind === "input") out.push(allRows[i])
        if (out.length === 0 && row !== null && row.kind === "job" && tab.footerMode === "again") out.push(row)
        return out
    }
    readonly property var sizeRefusals: {
        var out = []
        for (var i = 0; i < modeTargets.length; ++i) { var f = sizeRefusalOf(modeTargets[i]); if (f) out.push(f) }
        return out
    }
    readonly property bool fastSizeBlocked: modeTargets.length > 0 && sizeRefusals.length === modeTargets.length
    readonly property string fastSizeMessage: sizeRefusals.length > 0 ? String(sizeRefusals[0].message || "") : ""
    readonly property bool selectedTooLargeForFast: fastChosen && row !== null && sizeRefusalOf(row) !== null
    readonly property string fastHelper: !fastUsable ? (fastMessage || "Check the models folder to use Fast.")
                                       : selectedTooLargeForFast ? "Over 9 MP: runs in Standard."
                                       : "Quicker drafts. Use Standard for finals."
    readonly property var modeModel: {
        var out = []
        for (var i = 0; i < modeList.length; ++i) {
            var m = modeList[i]
            var isFast = m.key === "fast"
            out.push({ label: m.label, value: m.key, enabled: !isFast || (fastUsable && !fastSizeBlocked),
                       tip: !isFast ? "Standard mode, for finals."
                            : !fastUsable ? (fastMessage !== "" ? fastMessage : "Fast mode cannot be used now.")
                            : fastSizeBlocked ? (fastSizeMessage !== "" ? fastSizeMessage : "Fast mode works on images up to about 9 MP. Choose Standard for larger images.")
                            : (fastText !== "" ? fastText : "Quicker, with a slightly different look. Use Standard for finals.") })
        }
        return out
    }
    function rowMode(r) {
        if (r.kind === "input") return r.mode === "fast" || r.mode === "standard" ? String(r.mode) : tab.mode
        if (r.effective && r.effective.mode) return String(r.effective.mode)
        if (r.run && r.run.mode) return String(r.run.mode)
        return "standard"
    }
    readonly property var waitingModes: {
        var out = []
        if (!modeShown) return out
        for (var i = 0; i < waitingRows.length; ++i) {
            var m = rowMode(waitingRows[i])
            if (out.indexOf(m) < 0) out.push(m)
        }
        return out
    }
    readonly property bool modeMixed: running && perImage && waitingModes.length > 1
    readonly property string modeMixedWords: {
        if (!modeMixed) return ""
        var w = []
        for (var i = 0; i < modeList.length; ++i) if (waitingModes.indexOf(modeList[i].key) >= 0) w.push(modeList[i].label)
        return "Mixed: " + w.join(" and ")
    }
    readonly property var modeValue: modeMixed ? undefined
                                    : (running && perImage && waitingModes.length === 1 ? waitingModes[0]
                                       : (tab ? (tab.mode === "fast" && fastSizeBlocked ? "standard" : tab.mode) : "standard"))
    readonly property bool fastChosen: modeShown && modeValue === "fast"
    readonly property string fastScaleTip: {
        var list = tab && tab.controlsInfo && tab.controlsInfo.scales ? tab.controlsInfo.scales : [2, 4, 6, 8]
        var above = 0
        for (var i = 0; i < list.length; ++i) if (Number(list[i]) > fastMaxFactor && (above === 0 || Number(list[i]) < above)) above = Number(list[i])
        return F.scaleLabel(above > 0 ? above : fastMaxFactor * 2) + " and above are Standard only."
    }
    readonly property var standardOnlyLooks: {
        var out = []
        for (var i = 0; i < presetNames.length; ++i) if (fastLooks.indexOf(presetNames[i]) < 0) out.push(presetNames[i])
        return out
    }
    readonly property string fastLookTip: {
        var l = standardOnlyLooks
        if (l.length === 0) return ""
        var words = l.length === 1 ? l[0] : l.slice(0, l.length - 1).join(", ") + " and " + l[l.length - 1]
        return words + (l.length === 1 ? " is" : " are") + " Standard only."
    }
    readonly property string fastDefaultLook: fastLooks.indexOf("Default") >= 0 ? "Default" : fastLooks[fastLooks.length - 1]
    function chooseMode(m) {
        if (!tab) return
        if (m !== "fast") { tab.setMode(m); return }
        if (!fastUsable || fastSizeBlocked) return
        var before = typeof tab.settingsSnapshot === "function" ? tab.settingsSnapshot() : null
        var scaleMoved = tab.scale > fastMaxFactor
        var lookMoved = fastLooks.indexOf(tab.preset) < 0 || tab.custom === true
        if (scaleMoved) tab.setScale(fastMaxFactor)
        if (lookMoved) tab.applyPreset(fastLooks.indexOf(tab.preset) >= 0 ? tab.preset : fastDefaultLook)
        tab.setMode("fast")
        if ((scaleMoved || lookMoved) && before !== null && typeof tab.showToast === "function") {
            var sw = F.scaleLabel(fastMaxFactor)
            var lw = tab.preset
            var words = scaleMoved && lookMoved ? "Set to " + sw + " and " + lw + " for Fast"
                      : scaleMoved ? "Scale set to " + sw + " for Fast" : "Look set to " + lw + " for Fast"
            tab.showToast("undo", words, "", "", "Undo", { kind: "settings", prev: before })
        }
    }

    property bool fasterAvailable: tab !== null && tab.fasterAvailable === true
    property bool fasterOn: tab !== null && tab.fasterOn === true
    readonly property bool fasterApplies: fasterAvailable && fasterOn && !(modeShown && tab && tab.mode === "fast")
    readonly property real fasterFactor: 0.87
    readonly property bool spedUpNoteShown: modeShown && modeValue === "standard" && fasterAvailable && fasterOn
    function fasterMinutes(p) {
        if (!p || p.ok === false) return 0
        if (p.finish && p.finish.faster && isFinite(Number(p.finish.faster.minutes))) return Number(p.finish.faster.minutes)
        var std = tab.planMinutes(p)
        var stages = p.stages || []
        if (stages.length === 0) return std * fasterFactor
        var raw = 0
        for (var i = 0; i < stages.length; ++i) raw += Number(stages[i].minutes) || 0
        var first = raw > 0 ? std * (Number(stages[0].minutes) || 0) / raw : std
        var one = p.finish && p.finish.one_card && isFinite(Number(p.finish.one_card.minutes)) ? Number(p.finish.one_card.minutes) : std
        return Math.max(0, one - first * (1 - fasterFactor))
    }
    readonly property var splitNow: tab && tab.health && tab.health.engine && tab.health.engine.split ? tab.health.engine.split : null
    readonly property string fasterTime: {
        if (!fasterApplies || !tab || !tab.eligibleInputs) return ""
        var cards = tab.health && tab.health.engine && tab.health.engine.workers ? Math.max(1, tab.health.engine.workers.length) : 1
        if (cards > 1 && splitNow !== null && splitNow.on === true && tab.eligibleInputs.length < cards) return ""
        var lanes = []
        for (var c = 0; c < cards; ++c) lanes.push(0)
        var any = false
        var list = tab.eligibleInputs
        for (var j = 0; j < list.length; ++j) {
            var m = fasterMinutes(tab.planForInput(list[j], tab.inputFactor(list[j])))
            if (!(m > 0)) continue
            var first = 0
            for (var l = 1; l < lanes.length; ++l) if (lanes[l] < lanes[first]) first = l
            lanes[first] += m
            any = true
        }
        if (!any) return ""
        var minutes = 0
        for (var k = 0; k < lanes.length; ++k) minutes = Math.max(minutes, lanes[k])
        return F.capital(F.minutesText(minutes))
    }

    readonly property bool factShown: row !== null && (rowStopped || rowFinished) && ranWithText !== ""
    readonly property bool thisShown: factShown
    function effectiveOf(r) {
        if (!r) return null
        if (r.ranWith && typeof r.ranWith === "object") return r.ranWith
        if (r.effective) return r.effective
        var job = tab.jobFor(r.jobId)
        return job && job.effective ? job.effective : (r.factor ? { scale: r.factor, preset: "" } : null)
    }
    function settingsWords(e, r) {
        if (!e) return ""
        var s = Number(e.scale) || 0
        var custom = e.preset === "Custom" || e.custom === true
        var base = String(e.base_preset || (custom ? "" : e.preset) || "")
        var look = custom ? (base !== "" && base !== "Custom" ? "Custom from " + base : "Custom look") : (base !== "" ? base : "Default") + " look"
        var run = r && r.run ? r.run : null
        var mode = run && run.mode ? String(run.mode) : (e.mode ? String(e.mode) : "standard")
        var out = (s > 0 ? F.scaleLabel(s) + ", " : "") + look
        if (mode === "fast") out += ", Fast"
        else if (e.faster === true || (run && run.faster === true)) out += ", sped up"
        else if (run && run.match_earlier === true) out += ", matching earlier results"
        return out
    }
    readonly property string thisTail: ""
    readonly property string ranWithText: {
        var seam = tab ? tab.ranWith : undefined
        if (typeof seam === "string") return seam
        if (seam && typeof seam === "object") return settingsWords(seam, row)
        return row !== null && row.kind === "job" ? settingsWords(effectiveOf(row), row) : ""
    }
    readonly property bool rowRanFast: {
        if (row === null || row.kind !== "job" || !tab) return false
        if (row.run && row.run.mode) return row.run.mode === "fast"
        var e = effectiveOf(row)
        return e !== null && e !== undefined && e.mode === "fast"
    }
    readonly property string againLabel: {
        if (!tab) return ""
        if (modeShown && tab.footerMode === "again" && rowRanFast && tab.mode === "standard") return "Upscale again in Standard"
        return tab.primaryLabel
    }

    readonly property var scaleModel: {
        var out = []
        if (!tab) return out
        var list = tab.controlsInfo.scales || [2, 4, 6, 8]
        for (var i = 0; i < list.length; ++i) {
            var s = list[i]
            if (fastChosen && s > fastMaxFactor) {
                out.push({ label: F.scaleLabel(s), value: s, enabled: false, warn: false, tip: fastScaleTip })
                continue
            }
            if (running) {
                var ok = scaleRefRows.length === 0
                for (var j = 0; !ok && j < scaleRefRows.length; ++j) ok = rowTakes(scaleRefRows[j], s)
                out.push({ label: F.scaleLabel(s), value: s, enabled: ok, warn: false,
                           tip: ok ? passTip(s) : (waitingRows.length > 0 ? F.scaleLabel(s) + " is too large for every waiting image."
                                                                          : F.scaleLabel(s) + " is too large for every image in this batch.") })
                continue
            }
            var reason = input !== null ? tab.inputRefusal(input, s) : (rowHasSize ? tab.refusal(row.srcW, row.srcH, s) : "")
            var listOk = tab.someInputTakes(s)
            var onlyThis = tab.footerMode === "again" && tab.inputs.length === 0
            var usable = listOk && !(onlyThis && reason !== "")
            out.push({ label: F.scaleLabel(s), value: s, enabled: usable, warn: false,
                       tip: reason === "" ? (listOk ? passTip(s) : tab.listRefusalText(s))
                                          : reason + (listOk ? (usable ? " Other images can take it." : "")
                                                             : " No image in the list can take " + F.scaleLabel(s) + ".") })
        }
        return out
    }
    function passTip(s) {
        var passes = s <= 2 ? 1 : (s <= 4 ? 2 : 3)
        return F.scaleLabel(s) + ": each side " + (s === 2 ? "doubles" : "grows " + s + " times") + ", in "
               + (passes === 1 ? "one pass" : passes + " passes") + "."
    }
    readonly property bool noteForRow: row !== null && (input !== null || rowStopped || (rowFinished && !running))
    readonly property string sizeNote: {
        if (!tab || !noteForRow || !rowHasSize) return ""
        var s = tab.scale
        var w = 0, h = 0, refused = ""
        if (input !== null) {
            refused = tab.inputRefusal(input, s)
            var p = tab.planForInput(input, s)
            if (p && p.output_size && p.output_size[0] > 0) { w = p.output_size[0]; h = p.output_size[1] }
            else { w = input.width * s; h = input.height * s }
        } else {
            refused = tab.refusal(row.srcW, row.srcH, s)
            w = row.srcW * s; h = row.srcH * s
        }
        if (refused !== "" || !(w > 0 && h > 0)) return ""
        var longPx = Math.max(w, h)
        var sizes = [["A0", 1189], ["A1", 841], ["A2", 594], ["A3", 420]]
        var a = "A3", ppi = Math.round(longPx / (420 / 25.4))
        for (var k = 0; k < sizes.length; ++k) {
            var v = longPx / (sizes[k][1] / 25.4)
            if (v >= 200) { a = sizes[k][0]; ppi = Math.round(v); break }
        }
        return String(Math.max(1, Math.round(w * h / 1e6))) + " MP, " + a + " at " + ppi + " ppi"
    }
    readonly property string scaleNote: running ? (mixed ? mixedWords : (rowStopped ? sizeNote : "")) : sizeNote

    readonly property var presetNames: {
        var out = []
        var list = tab ? (tab.controlsInfo.presets || []) : []
        for (var i = 0; i < list.length; ++i) out.push(list[i].name)
        return out
    }
    readonly property var presetVals: tab ? tab.presetValues(tab.preset) : null
    readonly property bool lookCustom: tab !== null && tab.custom === true
    readonly property string lookText: tab ? tab.presetText(tab.preset) : ""
    readonly property bool lookHelperShown: {
        if (!tab || presetNames.length === 0) return false
        for (var i = 0; i < presetNames.length; ++i)
            if (metaMetrics.advanceWidth(tab.presetText(presetNames[i])) > cw) return false
        return true
    }
    readonly property var lookLimited: {
        var out = []
        if (!fastChosen) return out
        for (var i = 0; i < presetNames.length; ++i) if (fastLooks.indexOf(presetNames[i]) < 0) out.push(i)
        return out
    }

    readonly property var sliderKeys: ["creativity", "resemblance", "restoration"]
    readonly property var changedValues: {
        var out = []
        if (!tab || !presetVals) return out
        for (var i = 0; i < sliderKeys.length; ++i) {
            var k = sliderKeys[i]
            if (Math.round(tab[k]) !== Math.round(presetVals[k])) out.push({ label: tab.sliderInfo(k).label, value: Math.round(tab[k]) })
        }
        return out
    }
    readonly property bool detailChanged: changedValues.length > 0
    FontMetrics { id: titleMetrics; font: Tokens.fontFor("title") }
    function summaryRoom(title) { return cw - Math.ceil(titleMetrics.advanceWidth(title)) - Tokens.sp8 - Tokens.iconBox - Tokens.sp8 }
    readonly property string detailSummary: {
        if (changedValues.length === 0)
            return tab && tab.extraPrompt.trim() !== "" ? "With an extra description" : "As the Look sets it"
        var room = summaryRoom("Detail")
        var full = changedValues.map(function(v) { return v.label + " " + v.value }).join(", ")
        if (metaMetrics.advanceWidth(full) <= room) return full
        var names = changedValues.map(function(v) { return v.label })
        var joined = names.length === 1 ? names[0] : names.length === 2 ? names[0] + " and " + names[1]
                   : names.slice(0, -1).join(", ") + " and " + names[names.length - 1]
        if (metaMetrics.advanceWidth(joined) <= room) return joined
        return names[0] + " and " + (names.length - 1) + " more"
    }

    readonly property string protectSummary: {
        if (!tab) return ""
        if (tab.quickProtect !== "") return "All but people and planting"
        var keys = tab.effectiveProtect || []
        if (keys.length === 0) return "Off"
        var cats = tab.controlsInfo.protect || []
        var first = keys[0]
        for (var j = 0; j < cats.length; ++j) if (cats[j].key === keys[0]) first = cats[j].label
        if (keys.length === cats.length && cats.length > 1) return "Everything"
        return keys.length === 1 ? first : first + " and " + (keys.length - 1) + " more"
    }
    readonly property string protectLine: {
        if (!tab) return ""
        if (tab.quickProtect !== "") return "Set by the option above"
        var s = protectSummary
        return s === "Off" ? "Nothing is protected" : s
    }
    readonly property string quickHint: "People and planting still get new detail. Indoors, almost the whole room is kept."
    function quickTitle(q) { return q.key === "architecture_only_people_vegetation" ? "Protect architecture" : String(q.label) }
    function quickLine(q) { return q.key === "architecture_only_people_vegetation" ? "Only people and planting change." : "" }
    readonly property bool maskStale: {
        if (row === null || !tab) return false
        var m = tab.maskFor(row.mediaId)
        return m !== null && m.signature !== tab.protectSignature
    }

    readonly property string formatShort: ({ png8: "PNG", png16: "PNG 16-bit", tiff16: "TIFF 16-bit", jpeg: "JPEG" })[tab ? tab.outputFormat : "png8"] || "PNG"
    readonly property string formatExt: ({ png8: "png", png16: "png", tiff16: "tif", jpeg: "jpg" })[tab ? tab.outputFormat : "png8"] || "png"
    readonly property string fileNote: "Saved as name_cu" + (tab ? tab.scale : 2) + "x" + (fastChosen ? "_fast" : "") + "." + formatExt
    readonly property string outputSummary: {
        if (!tab) return ""
        if (tab.outputDirError !== "") return "Choose a folder"
        if (tab.outputDir === "") return formatShort
        var room = summaryRoom("Output")
        var head = formatShort + ", "
        var fits = function(t) { return metaMetrics.advanceWidth(head + t) <= room }
        var sp = F.shortPath(tab.outputDir, fits)
        if (fits(sp)) return head + sp
        var last = F.basename(tab.outputDir)
        return fits("…\\" + last) ? head + "…\\" + last : formatShort
    }

    property int detailUser: -1
    property bool protectOpen: false
    property bool protectChange: false
    property bool outputOpen: false
    readonly property bool detailOpen: detailUser < 0 ? tall : detailUser === 1
    function toggleSection(name) {
        if (name === "detail") detailUser = detailOpen ? 0 : 1
        else if (name === "protect") protectOpen = !protectOpen
        else if (name === "output") outputOpen = !outputOpen
    }
    function showOutput() { outputOpen = true; Qt.callLater(function() { scroll.reveal(outputBody, outputSection.rowItem) }) }
    function showFineTune() { detailUser = 1; Qt.callLater(function() { scroll.reveal(detailBody, detailSection.rowItem) }) }
    readonly property var refusedFolder: tab ? tab.outputDirRefused : null
    onRefusedFolderChanged: { if (refusedFolder !== null) { outputOpen = true; Qt.callLater(function() { scroll.reveal(refusedNote) }) } }

    readonly property bool resultsOpen: tab !== null && tab.resultsOpen === true
    readonly property bool hasImages: tab !== null && ((tab.inputs && tab.inputs.length > 0) || (tab.imageCount || 0) > 0)
    readonly property string engineKind: {
        if (!tab) return ""
        if (typeof tab.engineLineKind === "string") return tab.engineLineKind
        if (tab.engineState === "problem") return "problem"
        if (tab.engineState === "starting") return tab.reconnecting ? "reconnecting" : "starting"
        return ""
    }
    readonly property bool engineDown: engineKind === "problem" || engineKind === "starting" || engineKind === "reconnecting"
    property bool stopPressed: false
    onRunningChanged: { if (!running) stopPressed = false }
    readonly property string seamStopping: tab && typeof tab.stoppingLine === "string" ? tab.stoppingLine : ""
    readonly property bool stopping: running && (stopPressed || seamStopping !== "")
    readonly property bool againTile: !running && tab !== null && tab.inputs.length === 0
                                      && (tab.footerMode === "again" || tab.footerMode === "cancelled")
    readonly property string localFootState: {
        if (!tab) return "empty"
        if (running) return stopping ? "stopping" : "running"
        if (engineDown) return hasImages ? "engine" : "empty"
        if (tab.inputs.length > 0) return "start"
        if (againTile && !resultsOpen) return "again"
        if ((tab.imageCount || 0) > 0) return "results"
        return "empty"
    }
    readonly property string footState: {
        var s = tab ? tab.footState : undefined
        return typeof s === "string" && s !== "" ? s : localFootState
    }
    readonly property string bandMode: footState
    property double now: Tokens.wallNow()
    function setClockSkew(ms) { Tokens.clockSkewMs = Number(ms) || 0; now = Tokens.wallNow() }
    Timer { interval: 20000; repeat: true; running: panel.running; triggeredOnStart: true; onTriggered: panel.now = Tokens.wallNow() }
    function hhmm(ms) {
        var d = new Date(ms)
        var h = d.getHours(), m = d.getMinutes()
        return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m
    }
    readonly property real etaS: running && b.etaS !== undefined ? Number(b.etaS) : -1
    readonly property string finishClock: {
        if (!(etaS > 0)) return ""
        var step = 5 * 60 * 1000
        return hhmm(Math.round((now + etaS * 1000) / step) * step)
    }
    readonly property string startedClock: {
        if (!running || !tab) return ""
        var first = 0
        for (var i = 0; i < tab.jobs.length; ++i) {
            var j = tab.jobs[i]
            if ((b.runIds && b.runIds.length ? b.runIds : (b.jobIds || [])).indexOf(j.id) < 0) continue
            var t = Date.parse(j.created)
            if (isFinite(t) && (first === 0 || t < first)) first = t
        }
        return first > 0 ? hhmm(first) : ""
    }
    readonly property string clockTip: {
        var left = etaS > 0 ? F.minutesText(etaS / 60).replace(/^about /, "") + " left" : ""
        var parts = []
        if (left !== "") parts.push(F.capital(left))
        if (startedClock !== "") parts.push((parts.length ? "started " : "Started ") + startedClock)
        return parts.join(", ")
    }
    readonly property var workingNames: {
        var out = []
        for (var i = 0; i < allRows.length; ++i)
            if (allRows[i].kind === "job" && F.contains(F.BUSY_ITEM_STATES, allRows[i].status)) out.push(allRows[i].name)
        return out
    }
    readonly property var queuedRows: {
        var out = []
        for (var i = 0; i < allRows.length; ++i)
            if (allRows[i].kind === "job" && (allRows[i].status === "queued" || allRows[i].status === "interrupted")) out.push(allRows[i])
        return out
    }
    readonly property string batchCount: running ? F.doneOf(Number(b.done) || 0, Number(b.total) || 0) : ""
    readonly property string stopTip: Tokens.keyTip(tab && tab.stopImageSupported === false
                                                     ? "Finishes the images in progress, then stops. Waiting images are cancelled."
                                                     : "Finishes the images in progress, then stops. Waiting images move to Stopped.", "Ctrl+.")
    readonly property string stopAfterTip: stopTip
    readonly property string floorWords: tab && tab.status && typeof tab.status.floorMessage === "string"
                                         ? String(tab.status.floorMessage).replace(/\.$/, "") : ""
    function stopAfterCurrent() {
        if (!tab) return
        stopPressed = true
        if (typeof tab.stopAfterCurrent === "function") { tab.stopAfterCurrent(); return }
        var rows = queuedRows.slice()
        var n = rows.length
        if (n === 0) return
        tab.confirmDialog.ask("Stop after current?",
                              (workingNames.length === 1 ? "The image in progress finishes. " : "The images in progress finish. ")
                              + (n === 1 ? "The waiting image is not started." : "The " + n + " waiting images are not started.")
                              + " Finished images stay in the output folder.",
                              "Stop after current", "Keep working", function() {
                                  for (var i = 0; i < rows.length; ++i) tab.cancelItem(rows[i])
                              })
    }
    function firstSentence(t) {
        var s = String(t || "")
        var i = s.indexOf(". ")
        return i > 0 ? s.slice(0, i + 1) : s
    }
    readonly property string engineWords: {
        if (!tab) return ""
        if (typeof tab.engineLine === "string" && tab.engineLine !== "") return tab.engineLine
        if (tab.engineState === "problem") {
            if (typeof tab.problemTitle === "string" && tab.problemTitle !== "") return tab.problemTitle.replace(/\.?$/, ".")
            var p = tab.problems && tab.problems.length ? tab.problems[0] : ""
            return firstSentence(typeof p === "string" ? p : (p && p.message ? p.message : ""))
        }
        var secs = Math.max(0, Math.round(tab.startingSeconds || 0))
        return (tab.reconnecting ? "Reconnecting to the engine" : "Starting the engine") + (secs > 0 ? " (" + secs + " s)" : "")
    }
    readonly property bool engineProblem: engineKind === "problem"
    readonly property string engineActionWords: {
        if (tab && typeof tab.engineAction === "string" && tab.engineAction !== "") return tab.engineAction
        return tab && tab.problemKind === "output" && engineProblem ? "Choose a folder…" : "Try again"
    }
    function openDetails(item) {
        detailsAnchor = item
        if (!tab) return
        if (tab.detailsAnchor !== undefined) tab.detailsAnchor = item
        if (typeof tab.showEngineDetails === "function") tab.showEngineDetails(item)
        else if (typeof tab.openEngineDetails === "function") tab.openEngineDetails(item)
    }

    property real viewCut: -1
    function measureCut() {
        var room = Math.max(0, footY - Tokens.sp24 - scroll.y)
        if (content.height <= room + 0.5) { if (viewCut !== -1) viewCut = -1; return }
        var best = -1
        var kids = content.children
        for (var i = 0; i < kids.length; ++i) {
            var k = kids[i]
            if (!k.visible || k.height <= 0) continue
            var t = k.y - Tokens.sp16
            if (t > 0 && t <= room && t > best) best = t
        }
        var bodies = [[detailSection, detailBody], [protectSection, protectBody], [outputSection, outputBody]]
        for (var b = 0; b < bodies.length; ++b) {
            var sec = bodies[b][0], body = bodies[b][1]
            if (!sec.open) continue
            var units = body.children
            var spans = []
            for (var u = 0; u < units.length; ++u) {
                if (!units[u].visible || units[u].height <= 0) continue
                var top = sec.y + Tokens.hTitleRow + Tokens.gapTitle + units[u].y
                var t2 = top - Tokens.sp8
                if (units[u].y > 0 && t2 > 0 && t2 <= room && t2 > best) best = t2
                spans.push({ top: top, bottom: top + units[u].height })
            }
            spans.sort(function(p, q) { return p.top - q.top })
            for (var v = 0; v < spans.length; ++v) {
                var next = v + 1 < spans.length ? spans[v + 1].top : sec.y + sec.height
                if (spans[v].bottom > room || next < spans[v].bottom) continue
                var t3 = Math.min(room, spans[v].bottom + Math.min(Tokens.sp8, (next - spans[v].bottom) / 2))
                if (t3 > best) best = t3
            }
        }
        var cut = best > 0 ? Tokens.snap(best, dpr) : -1
        if (cut !== viewCut) viewCut = cut
    }
    Timer { id: cutTimer; interval: 0; onTriggered: panel.measureCut() }
    onFootYChanged: cutTimer.restart()

    CuScrollArea {
        id: scroll
        objectName: "settingsScroll"
        x: 0
        y: Tokens.sp4
        width: panel.width
        property bool atTop: true
        function syncTop() { var t = contentY <= minY + 0.5; if (t !== atTop) atTop = t }
        onContentYChanged: Qt.callLater(syncTop)
        height: panel.viewCut > 0 && atTop ? panel.viewCut : Math.max(0, panel.footY - Tokens.sp24 - y)
        onHeightChanged: if (contentY > maxY + 0.5) contentY = maxY
        ground: "ink"
        visible: !panel.sheetOpen
        regionHovered: legHover.hovered

        Column {
            id: content
            objectName: "settingsContent"
            x: panel.pad
            width: panel.cw
            topPadding: Tokens.sp8
            onHeightChanged: cutTimer.restart()

            Item {
                id: scopeRow
                objectName: "settingsScope"
                visible: panel.scopeShown
                width: parent.width
                readonly property int lines: panel.scopeLines.indexOf("\n") >= 0 ? 2 : 1
                readonly property int rowH: lines === 1 ? Tokens.hTitleRow : 2 * scopeText.lineBox + Tokens.sp4
                height: rowH + (panel.factShown ? Tokens.sp4 : Tokens.gapSection)
                CuText {
                    id: scopeText
                    objectName: "settingsScopeWords"
                    x: 0
                    y: Tokens.snap((scopeRow.rowH - scopeRow.lines * lineBox) / 2, panel.dpr)
                    width: parent.width
                    text: panel.scopeLines
                    role: "body"
                    color: Tokens.text2
                    Accessible.role: Accessible.StaticText
                    Accessible.name: panel.scopeWords
                }
            }

            Item {
                id: factBlock
                objectName: "settingsRanWithBlock"
                visible: panel.factShown
                width: parent.width
                height: ranWithRow.implicitHeight + Tokens.gapSection
                CuLabelRow {
                    id: ranWithRow
                    objectName: "settingsRanWith"
                    x: 0
                    y: 0
                    width: parent.width
                    label: "Ran with"
                    value: panel.ranWithText
                    Accessible.role: Accessible.StaticText
                    Accessible.name: "Ran with " + panel.ranWithText
                }
            }

            Item {
                id: modeBlock
                objectName: "modeBlock"
                property Item sectionHeading: modeTitle
                visible: panel.modeShown
                width: parent.width
                readonly property bool helper: panel.fastChosen || (panel.modeShown && !panel.fastUsable)
                height: Tokens.hTitleRow + Tokens.gapTitle + Tokens.hControl + (helper ? Tokens.sp8 + modeLine.lineBox : 0) + Tokens.gapSection
                Accessible.role: Accessible.Grouping
                Accessible.name: "Mode"
                CuSectionTitle {
                    id: modeTitle
                    objectName: "modeTitle"
                    x: 0
                    y: 0
                    width: parent.width
                    text: "Mode"
                    note: panel.modeMixed ? panel.modeMixedWords : (panel.spedUpNoteShown ? "Sped up" : "")
                }
                Item {
                    objectName: "modeNoteTipArea"
                    visible: panel.spedUpNoteShown && !panel.modeMixed
                    x: Tokens.snap(parent.width - Math.ceil(metaMetrics.advanceWidth("Sped up")), panel.dpr)
                    y: 0
                    width: parent.width - x
                    height: Tokens.hTitleRow
                    HoverHandler { id: spedHover }
                    CuHoverTip { shown: spedHover.hovered; text: "Speed up upscaling is on in Settings. About 13% quicker at 2×." }
                }
                CuSegmented {
                    id: modeControl
                    objectName: "modeControl"
                    x: 0
                    y: Tokens.hTitleRow + Tokens.gapTitle
                    width: parent.width
                    ground: "ink"
                    equalCells: true
                    model: panel.modeModel
                    currentValue: panel.modeValue
                    accessibleName: "Mode"
                    onActivated: (value) => panel.chooseMode(value)
                }
                CuText {
                    id: modeLine
                    objectName: "modeLine"
                    visible: modeBlock.helper
                    x: 0
                    y: modeControl.y + Tokens.hControl + Tokens.sp8
                    width: parent.width
                    elide: Text.ElideRight
                    text: panel.fastHelper
                    role: "meta"
                    color: Tokens.text3
                }
            }

            Item {
                id: scaleBlock
                objectName: "scaleBlock"
                property Item sectionHeading: scaleTitle
                width: parent.width
                height: Tokens.hTitleRow + Tokens.gapTitle + Tokens.hControl + Tokens.gapSection
                CuSectionTitle {
                    id: scaleTitle
                    objectName: "upscaleTitle"
                    x: 0
                    y: 0
                    width: parent.width
                    text: "Scale"
                    note: panel.scaleNote
                }
                CuSegmented {
                    objectName: "scaleControl"
                    x: 0
                    y: Tokens.hTitleRow + Tokens.gapTitle
                    width: parent.width
                    ground: "ink"
                    equalCells: true
                    model: panel.scaleModel
                    currentValue: panel.scaleValue
                    accessibleName: "Scale"
                    onActivated: (value) => panel.tab.setScale(value, panel.mixed)
                }
            }

            Item {
                id: lookBlock
                objectName: "lookBlock"
                property Item sectionHeading: lookTitle
                width: parent.width
                height: Tokens.hTitleRow + Tokens.gapTitle + Tokens.hLook
                        + (panel.lookHelperShown ? Tokens.sp8 + lookHelper.lineBox : 0) + Tokens.gapSection
                CuSectionTitle {
                    id: lookTitle
                    objectName: "lookTitle"
                    x: 0
                    y: 0
                    width: parent.width
                    text: "Look"
                    note: panel.lookCustom ? "Custom, from " + (panel.tab ? panel.tab.preset : "") : ""
                }
                Item {
                    objectName: "lookTitleTipArea"
                    x: lookTitle.titleItem.x
                    y: 0
                    width: lookTitle.titleItem.width
                    height: Tokens.hTitleRow
                    HoverHandler { id: lookTitleHover }
                    CuHoverTip { shown: lookTitleHover.hovered && !panel.lookHelperShown; text: panel.lookText }
                }
                Item {
                    objectName: "presetCustom"
                    visible: panel.lookCustom
                    x: Tokens.snap(parent.width - Math.ceil(metaMetrics.advanceWidth(lookTitle.note)), panel.dpr)
                    y: 0
                    width: parent.width - x
                    height: Tokens.hTitleRow
                    readonly property string words: lookTitle.note
                    HoverHandler { id: customHover }
                    CuHoverTip {
                        shown: customHover.hovered
                        text: panel.presetVals ? "Choose " + panel.tab.preset + " on the scale to go back to Creativity "
                                                 + panel.presetVals.creativity + ", Resemblance " + panel.presetVals.resemblance
                                                 + ", Restoration " + panel.presetVals.restoration + "." : ""
                    }
                }
                CuStopScale {
                    objectName: "presetControl"
                    x: 0
                    y: Tokens.hTitleRow + Tokens.gapTitle
                    width: parent.width
                    names: panel.presetNames
                    currentIndex: panel.tab ? panel.presetNames.indexOf(panel.tab.preset) : -1
                    custom: panel.lookCustom
                    limited: panel.lookLimited
                    limitTip: panel.fastLookTip
                    onActivated: (index) => panel.tab.applyPreset(panel.presetNames[index])
                }
                CuText {
                    id: lookHelper
                    objectName: "presetDescription"
                    visible: panel.lookHelperShown
                    x: 0
                    y: Tokens.hTitleRow + Tokens.gapTitle + Tokens.hLook + Tokens.sp8
                    width: parent.width
                    elide: Text.ElideRight
                    text: panel.lookText
                    role: "meta"
                    color: Tokens.text3
                }
            }

            CuSettingsSection {
                id: detailSection
                objectName: "sectionDetail"
                name: "detail"
                title: "Detail"
                open: panel.detailOpen
                summary: panel.detailSummary
                onToggled: panel.toggleSection("detail")
                Column {
                    id: detailBody
                    width: parent.width
                    spacing: Tokens.gapUnit
                    CuText {
                        objectName: "detailFastNote"
                        visible: panel.fastChosen
                        width: parent.width
                        elide: Text.ElideRight
                        text: "Fine-tuning is Standard only."
                        role: "meta"
                        color: Tokens.text3
                    }
                    CuSlider {
                        objectName: "slider-creativity"
                        readonly property var info: panel.tab ? panel.tab.sliderInfo("creativity") : ({})
                        width: parent.width
                        enabled: !panel.fastChosen
                        ground: "ink"
                        label: info.label || "Creativity"
                        description: info.text || ""
                        lowLabel: info.low || ""
                        highLabel: info.high || ""
                        value: panel.tab ? panel.tab.creativity : 0
                        resetValue: panel.presetVals ? panel.presetVals.creativity : value
                        resetName: panel.tab ? panel.tab.preset : ""
                        onMoved: (v) => panel.tab.setSlider("creativity", v)
                    }
                    CuSlider {
                        objectName: "slider-resemblance"
                        readonly property var info: panel.tab ? panel.tab.sliderInfo("resemblance") : ({})
                        width: parent.width
                        enabled: !panel.fastChosen
                        ground: "ink"
                        label: info.label || "Resemblance"
                        description: info.text || ""
                        lowLabel: info.low || ""
                        highLabel: info.high || ""
                        value: panel.tab ? panel.tab.resemblance : 0
                        resetValue: panel.presetVals ? panel.presetVals.resemblance : value
                        resetName: panel.tab ? panel.tab.preset : ""
                        onMoved: (v) => panel.tab.setSlider("resemblance", v)
                    }
                    CuSlider {
                        objectName: "slider-restoration"
                        readonly property var info: panel.tab ? panel.tab.sliderInfo("restoration") : ({})
                        width: parent.width
                        enabled: !panel.fastChosen
                        ground: "ink"
                        label: info.label || "Restoration"
                        description: info.text || ""
                        lowLabel: info.low || ""
                        highLabel: info.high || ""
                        value: panel.tab ? panel.tab.restoration : 0
                        resetValue: panel.presetVals ? panel.presetVals.restoration : value
                        resetName: panel.tab ? panel.tab.preset : ""
                        onMoved: (v) => panel.tab.setSlider("restoration", v)
                    }
                    Item {
                        objectName: "seedUnit"
                        width: parent.width
                        height: Tokens.hLabelRow + Tokens.sp4 + Tokens.hControl + (seedField.errorText !== "" ? Tokens.sp4 + Tokens.type.meta.line : 0)
                        CuLabelRow {
                            x: 0
                            y: 0
                            width: parent.width
                            label: "Variation number"
                            actionText: "New number"
                            actionTip: "The same number with the same settings makes the same result. A new number makes a new version."
                            onActionClicked: panel.tab.newSeed()
                        }
                        CuTextField {
                            id: seedField
                            objectName: "seedField"
                            x: 0
                            y: Tokens.hLabelRow + Tokens.sp4
                            width: parent.width
                            ground: "ink"
                            digitsOnly: true
                            maximumLength: 19
                            text: panel.tab ? panel.tab.seed : ""
                            placeholderText: panel.tab ? String(panel.tab.controlsInfo.default_seed || "") : ""
                            accessibleName: "Variation number"
                            error: panel.tab !== null && panel.tab.seedError !== ""
                            errorText: panel.tab ? panel.tab.seedError : ""
                            onEdited: (t) => panel.tab.setSeed(t)
                        }
                    }
                    Item {
                        objectName: "promptUnit"
                        width: parent.width
                        height: Tokens.hLabelRow + Tokens.sp4 + Tokens.hControl
                        CuLabelRow {
                            x: 0
                            y: 0
                            width: parent.width
                            label: "Extra description"
                        }
                        CuTextField {
                            id: promptField
                            objectName: "promptField"
                            x: 0
                            y: Tokens.hLabelRow + Tokens.sp4
                            width: parent.width
                            ground: "ink"
                            maximumLength: 400
                            text: panel.tab ? panel.tab.extraPrompt : ""
                            placeholderText: "Polished concrete, oak floor…"
                            accessibleName: "Extra description"
                            onEdited: (t) => panel.tab.extraPrompt = t
                            HoverHandler { id: promptHover }
                            CuHoverTip {
                                shown: promptHover.hovered && !promptField.editing
                                text: "Describe materials, not objects. Naming objects can make new ones appear."
                            }
                        }
                    }
                }
            }

            CuSettingsSection {
                id: protectSection
                objectName: "sectionProtect"
                name: "protect"
                title: "Protect"
                open: panel.protectOpen
                summary: panel.protectSummary
                onToggled: panel.toggleSection("protect")
                CuButton {
                    id: previewBtn
                    objectName: "previewMask"
                    parent: protectSection.rowItem
                    visible: protectSection.open && panel.row !== null
                    x: Tokens.snap(protectSection.width - Tokens.iconBox - Tokens.sp8 - width, panel.dpr)
                    y: protectSection.rowItem.onBaseline(labelItem.y + labelItem.baselineOffset)
                    variant: "text"
                    ground: "ink"
                    text: panel.maskStale ? "Preview again" : "Preview"
                    busy: panel.tab ? panel.tab.maskBusy : false
                    enabled: panel.tab ? panel.tab.engineWorks : false
                    tooltip: panel.maskStale ? "Your choices changed after this preview. Preview again to update it."
                                             : Tokens.keyTip("Tint the protected areas on the selected image", "M")
                    onClicked: panel.tab.previewMask()
                }
                Column {
                    id: protectBody
                    width: parent.width
                    Repeater {
                        model: panel.tab ? (panel.tab.controlsInfo.quick_protect || []) : []
                        CuCheckBox {
                            id: quickBox
                            required property var modelData
                            objectName: "quick-" + modelData.key
                            width: protectBody.width
                            ground: "ink"
                            text: panel.quickTitle(modelData)
                            hint: panel.quickLine(modelData)
                            checked: panel.tab.quickProtect === modelData.key
                            onToggled: (on) => panel.tab.setQuickProtect(modelData.key, on)
                            Accessible.description: modelData.label + ". " + panel.quickHint
                            CuHoverTip {
                                objectName: "quickHintTip"
                                shown: quickBox.hovered || quickBox.visualFocus
                                text: quickBox.modelData.label + "."
                                detail: panel.quickHint
                            }
                        }
                    }
                    Item { width: 1; height: Tokens.gapUnit }
                    CuLabelRow {
                        objectName: "protectLine"
                        width: protectBody.width
                        label: panel.protectLine
                        actionText: panel.protectChange ? "Done" : "Change"
                        actionTip: panel.protectChange ? "Fold the list" : "Choose what keeps its shapes and materials"
                        onActionClicked: panel.protectChange = !panel.protectChange
                    }
                    Item { width: 1; height: panel.protectChange ? Tokens.sp4 : 0 }
                    Column {
                        objectName: "protectRows"
                        visible: panel.protectChange
                        width: protectBody.width
                        Repeater {
                            model: panel.tab ? (panel.tab.controlsInfo.protect || []) : []
                            CuCheckBox {
                                id: protectBox
                                required property var modelData
                                objectName: "protect-" + modelData.key
                                width: protectBody.width
                                ground: "ink"
                                text: modelData.label
                                checked: panel.tab.effectiveProtect.indexOf(modelData.key) >= 0
                                locked: panel.tab.quickProtect !== ""
                                lockedReason: "Set by the option above. Untick it to choose these yourself."
                                onToggled: (on) => panel.tab.setProtect(modelData.key, on)
                                CuHoverTip {
                                    shown: !protectBox.locked && (protectBox.hovered || protectBox.visualFocus)
                                    text: protectBox.modelData.hint
                                }
                            }
                        }
                    }
                    CuText {
                        objectName: "maskStaleNote"
                        visible: panel.maskStale && panel.tab.maskVisible
                        width: parent.width
                        topPadding: Tokens.sp8
                        elide: Text.ElideRight
                        text: "The tint shows your earlier choices."
                        role: "meta"
                        color: Tokens.text3
                    }
                }
            }

            CuSettingsSection {
                id: outputSection
                objectName: "sectionOutput"
                name: "output"
                title: "Output"
                open: panel.outputOpen
                summary: panel.outputSummary
                trail: 0
                onToggled: panel.toggleSection("output")
                Column {
                    id: outputBody
                    width: parent.width
                    CuLabelRow {
                        objectName: "outputFolderRow"
                        width: outputBody.width
                        label: "Folder"
                        actionText: panel.tab && panel.tab.savingOutputDir ? "Saving…" : "Browse…"
                        actionTip: panel.tab && panel.tab.connected ? "Choose the output folder" : "Opens once the engine is ready"
                        onActionClicked: { if (panel.tab && panel.tab.connected && !panel.tab.savingOutputDir) panel.tab.openOutputDialog() }
                    }
                    Item { width: 1; height: Tokens.sp4 }
                    CuTextField {
                        objectName: "outputFolderField"
                        width: outputBody.width
                        ground: "ink"
                        readOnly: true
                        pathMode: true
                        text: panel.tab ? panel.tab.outputDir : ""
                        placeholderText: panel.tab && panel.tab.connected ? "No folder chosen" : "Waiting for the engine…"
                        accessibleName: "Output folder"
                        error: panel.tab !== null && panel.tab.outputDirError !== ""
                        errorText: panel.tab && panel.tab.outputDirError !== "" ? F.outputFieldError(panel.tab.outputDirError) : ""
                    }
                    Item { width: 1; height: panel.tab && panel.tab.outputDirError !== "" ? Tokens.sp4 + Tokens.type.meta.line : 0 }
                    Item { width: 1; height: Tokens.sp8 }
                    Item {
                        width: outputBody.width
                        height: Tokens.hControl
                        CuButton {
                            objectName: "outputOpen"
                            x: 0
                            y: 0
                            variant: "text"
                            ground: "ink"
                            text: "Open folder"
                            tooltip: "Open the output folder in Explorer"
                            enabled: panel.tab !== null && panel.tab.connected && panel.tab.outputDir !== ""
                            onClicked: panel.tab.openPath(panel.tab.outputDir, "output folder")
                        }
                    }
                    Column {
                        id: refusedNote
                        objectName: "outputFolderRefused"
                        width: outputBody.width
                        visible: panel.tab !== null && panel.tab.outputDirRefused !== null
                        topPadding: Tokens.sp8
                        readonly property var refused: panel.tab ? panel.tab.outputDirRefused : null
                        Accessible.role: Accessible.AlertMessage
                        Accessible.name: refused ? "Not used: " + refused.path + ". " + F.splitPath(refused.reason).text : ""
                        CuText {
                            id: refusedPath
                            objectName: "notePath"
                            width: parent.width
                            text: refusedNote.refused ? "Not used: " + F.shortPath(refusedNote.refused.path, function(t) {
                                return refusedMetrics.advanceWidth("Not used: " + t) <= refusedPath.width - 2 }) : ""
                            elide: Text.ElideMiddle
                            role: "meta"
                            color: Tokens.text1
                            FontMetrics { id: refusedMetrics; font: refusedPath.font }
                        }
                        CuText {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: refusedNote.refused ? F.splitPath(refusedNote.refused.reason).text : ""
                            role: "meta"
                            color: Tokens.text2
                        }
                        Item {
                            width: parent.width
                            height: Tokens.hControl
                            CuButton {
                                objectName: "noteDismiss"
                                x: 0
                                y: 0
                                variant: "text"
                                ground: "ink"
                                text: "Dismiss"
                                onClicked: panel.tab.dismissOutputDirRefused()
                            }
                        }
                    }
                    Item { width: 1; height: Tokens.gapUnit }
                    CuLabelRow {
                        objectName: "formatRow"
                        width: outputBody.width
                        label: "Format"
                        note: panel.fileNote
                    }
                    Item { width: 1; height: Tokens.sp4 }
                    CuComboBox {
                        id: formatCombo
                        objectName: "formatCombo"
                        width: outputBody.width
                        ground: "ink"
                        accessibleName: "Output format"
                        model: {
                            var out = []
                            var list = panel.tab ? (panel.tab.controlsInfo.output_formats || []) : []
                            for (var i = 0; i < list.length; ++i) out.push({ label: list[i].label, value: list[i].key })
                            return out
                        }
                        currentValue: panel.tab ? panel.tab.outputFormat : "png8"
                        onActivated: (value) => panel.tab.setOutputFormat(value)
                        CuHoverTip {
                            shown: formatCombo.hovered && !formatCombo.open
                            text: "Existing files are never overwritten."
                        }
                    }
                }
            }
        }
    }
    HoverHandler { id: legHover }

    CuSettingsFoot {
        id: foot
        x: panel.pad
        y: panel.footY
        width: panel.cw
        footState: panel.footState
        line: {
            var s = panel.footState
            if (!panel.tab) return ""
            if (s === "running") {
                if (panel.engineKind === "reconnecting" || panel.engineKind === "starting") return panel.engineWords
                if (typeof panel.tab.batchLineCount === "string" && panel.tab.batchLineCount !== "") return panel.tab.batchLineCount
                return panel.finishClock !== "" ? panel.batchCount + ", finishes about " : panel.batchCount
            }
            if (s === "stopping") {
                if (panel.seamStopping !== "") return panel.seamStopping
                var n = panel.workingNames.length
                return n > 0 ? "Stopping after " + F.plural(n, "image", "images") + " in progress" : "Stopping"
            }
            if (s === "start") {
                if (panel.tab.submitting || panel.tab.canStart) return panel.fasterTime !== "" ? panel.fasterTime : panel.tab.footerTime
                return panel.tab.primaryReason
            }
            if (s === "again") return panel.tab.footerTime
            if (s === "results") return "No images are waiting."
            if (s === "engine") return panel.engineProblem ? "" : panel.engineWords
            return ""
        }
        lineValue: footState !== "running" || panel.engineKind === "reconnecting" || panel.engineKind === "starting" ? ""
                   : (panel.tab && typeof panel.tab.batchLineCount === "string" && panel.tab.batchLineCount !== ""
                      ? String(panel.tab.batchLineTime || "") : panel.finishClock)
        lineDanger: (footState === "engine" || panel.running) && panel.engineProblem ? panel.engineWords : ""
        lineTip: footState === "running" ? [panel.clockTip, panel.floorWords].filter(function(t) { return t !== "" }).join(". ") : ""
        detailsText: (footState === "engine" || panel.running) && panel.engineProblem ? "Details" : ""
        whiteText: {
            if (!panel.tab) return ""
            if (panel.tab.submitting) {
                var n = panel.tab.eligibleInputs ? panel.tab.eligibleInputs.length : 0
                return n > 0 ? "Starting " + F.plural(n, "image", "images") + "…" : "Starting…"
            }
            return panel.tab.primaryLabel
        }
        whiteEnabled: panel.tab !== null && (panel.tab.canStart || panel.tab.submitting)
        whiteBusy: panel.tab !== null && panel.tab.submitting
        whiteTip: Tokens.keyTip("Start the batch", "Ctrl+Enter")
        whiteDescription: panel.tab ? panel.tab.footerTime : ""
        tileText: footState === "engine" ? panel.engineActionWords : panel.againLabel
        tileEnabled: footState === "engine" ? true : (panel.tab !== null && panel.tab.canStart)
        tileBusy: footState === "again" && panel.tab !== null && panel.tab.submitting
        tileTip: footState === "engine" ? (panel.engineActionWords === "Try again" ? "Start the engine again" : "Choose the output folder")
                 : (panel.tab && panel.tab.footerMode === "cancelled" ? Tokens.keyTip("With the current settings, as a new batch", "Ctrl+Enter")
                                                                      : Tokens.keyTip("With the current settings", "Ctrl+Enter"))
        stopEnabled: panel.queuedRows.length > 0 || (panel.tab !== null && typeof panel.tab.stopAfterCurrent === "function")
        stopTip: panel.stopTip
        cancelTip: Tokens.keyTip("Cancel the batch", "Esc")
        onStartClicked: panel.tab.startUpscale()
        onTileClicked: {
            if (footState === "engine") {
                if (panel.engineActionWords === "Try again") panel.tab.retryEngine()
                else panel.tab.openOutputDialog()
            }
            else if (panel.againLabel === "Upscale again in Standard" && typeof panel.tab.upscaleAgainStandard === "function") panel.tab.upscaleAgainStandard(panel.row)
            else panel.tab.startUpscale()
        }
        onStopClicked: panel.stopAfterCurrent()
        onCancelClicked: panel.tab.requestCancelBatch()
        onDetailsClicked: (item) => panel.openDetails(item)
    }
}

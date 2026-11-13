import QtQuick
import QtQuick.Window
import QtQuick.Dialogs
import "format.js" as F
import "Defaults.js" as D

Rectangle {
    id: root
    objectName: "creativeUpscalerTab"
    color: Tokens.opening
    focus: true

    property var appBridge: null
    property string hostLogFolder: ""

    readonly property int gutter: 0
    readonly property int legWidth: Tokens.legWidth(width)
    readonly property int railWidth: legWidth
    readonly property int settingsWidth: legWidth
    readonly property bool fontsLoaded: Tokens.fontRegular.status === FontLoader.Ready && Tokens.fontMedium.status === FontLoader.Ready

    property bool panelsShown: true
    property double lastActivityMs: 0
    HoverHandler {
        id: activityHover
        onPointChanged: root.lastActivityMs = Date.now()
        onHoveredChanged: root.lastActivityMs = Date.now()
    }
    signal panelsToggleRequested()
    readonly property bool focusMode: !panelsShown
    property real traySlide: 0
    readonly property bool traysAway: focusMode && traySlide >= 0.999
    readonly property bool panelsHidden: traysAway
    readonly property string panelsKey: "Tab"
    function togglePanels() { panelsToggleRequested() }
    function toggleFocusMode() { togglePanels() }
    function setFocusMode(on) { if ((!!on) !== focusMode) togglePanels() }
    onPanelsShownChanged: {
        var on = !panelsShown
        slideAnim.stop()
        var ms = on ? Tokens.durLegs : Tokens.durSheetOut
        if (ms <= 0) {
            traySlide = on ? 1 : 0
        } else {
            slideAnim.from = traySlide
            slideAnim.to = on ? 1 : 0
            slideAnim.duration = ms
            slideAnim.easing.bezierCurve = on ? Tokens.easeTravel : Tokens.easeEnter
            slideAnim.start()
        }
        log("info", "focus_mode", on ? "Panels hidden" : "Panels shown", null, true)
        announce(on ? "Panels hidden" : "Panels shown")
    }
    NumberAnimation {
        id: slideAnim
        target: root
        property: "traySlide"
        easing.type: Easing.BezierSpline
        easing.bezierCurve: Tokens.easeTravel
    }

    LoggingCategory {
        id: logCategory
        name: "creative.upscaler"
        defaultLogLevel: LoggingCategory.Info
    }
    property var tabLog: []
    property int _tabLogSeq: 0

    function log(level, event, message, data, quiet) {
        message = String(message).replace(/([?&]token=)[^&\s"\']+/g, "$1[redacted]")
        if (data !== undefined && data !== null) data = JSON.parse(JSON.stringify(data).replace(/([?&]token=)[^&\s"\']+/g, "$1[redacted]"))
        var line = "[" + level + "] " + event + ": " + message
        if (data !== undefined && data !== null) {
            try { line += " " + JSON.stringify(data) } catch (e) { line += " (unprintable data)" }
        }
        if (level === "debug") console.debug(logCategory, line)
        else if (level === "exception") console.warn(logCategory, line)
        else console.info(logCategory, line)
        if (level === "debug" || quiet === true) return
        var next = tabLog.slice(Math.max(0, tabLog.length - 199))
        _tabLogSeq += 1
        next.push({ seq: _tabLogSeq, ts: Tokens.wallNow(), level: level === "exception" ? "error" : level, msg: message, source: "tab",
                    job: data && data.job ? data.job : "" })
        tabLog = next
    }

    CuApi {
        id: api
        hostEndpoint: root.appBridge ? root.appBridge.endpoint : ""
        hostToken: root.appBridge ? root.appBridge.token : ""
        logger: root.log
    }
    property alias service: api
    readonly property int servicePort: api.port
    readonly property int pendingRequests: api._pending.length

    CuPrefs {
        id: prefs
        logger: root.log
    }

    readonly property bool connected: api.connected
    property var health: null
    property int healthFailures: 0
    property bool launchTried: false
    property bool launchFailed: false
    property double firstAttemptAt: 0
    property bool everConnected: false
    readonly property bool startupTimedOut: !connected && firstAttemptAt > 0 && (clock.now - firstAttemptAt) > 90000
    readonly property var problems: {
        if (connected && health && health.problems && health.problems.length) return health.problems
        if (!connected && launchFailed) return ["The engine could not start. Open Settings to check your folders, then try again."]
        if (startupTimedOut) return [everConnected
            ? "The connection to the engine was lost and it has not come back. Choose Try again; if it keeps happening, restart Artegra Enhancer."
            : "The engine did not start. Open Settings to check your folders, then try again."]
        return []
    }
    readonly property string engineState: {
        if (problems.length > 0) return "problem"
        if (!connected) return "starting"
        if (health && health.ok === false) return "starting"
        if (batch.active && batch.busy) return "working"
        return "ready"
    }
    readonly property bool engineUsable: connected && engineState !== "problem" && engineState !== "starting"
    readonly property string problemKind: problems.length > 0 ? F.problemKind(problems[0]) : ""
    readonly property string problemTitle: problems.length > 0 ? F.problemTitle(problems[0]) : ""
    readonly property bool reconnecting: !connected && everConnected && engineState === "starting"
    readonly property bool engineWorks: connected && engineState !== "starting" && (engineState !== "problem" || problemKind === "output")
    onEngineStateChanged: log(engineState === "problem" ? "warning" : "info", "engine_state",
                              engineState === "problem" ? (problems[0] || "The engine has a problem.")
                              : engineState === "starting" ? (!connected && everConnected ? "Reconnecting to the engine" : "Waiting for the engine to start")
                              : engineState === "working" ? "The engine is working" : "The engine is ready", { state: engineState, problems: problems },
                              engineState === "ready" || engineState === "working")
    readonly property real startingSeconds: engineState === "starting" && firstAttemptAt > 0 ? Math.max(0, (clock.now - firstAttemptAt) / 1000) : 0

    readonly property var features: health !== null && health.features !== undefined && health.features !== null ? health.features : ({})
    readonly property bool perImageSettings: features.item_settings === true
    readonly property bool stopImageSupported: features.stop_image === true
    readonly property bool requeueSupported: features.requeue === true
    readonly property bool fastAvailable: health !== null && health.engine !== undefined && health.engine !== null
                                          && health.engine.fast !== undefined && health.engine.fast !== null
                                          && health.engine.fast.available === true
    readonly property bool engineInBackground: health !== null && health.lifecycle !== undefined && health.lifecycle !== null
                                               && health.lifecycle.in_background === true
    readonly property bool splitKey: true

    readonly property string engineLogFolder: root.appBridge ? root.appBridge.logFolder : ""

    function openLogFolder() {
        var ok = false
        try {
            ok = Qt.openUrlExternally(F.fileUrlFromPath(engineLogFolder))
        } catch (e) {
            log("error", "open_logs_exception", "Opening the log folder failed: " + e, null)
        }
        if (ok) log("info", "open_logs", "Opened the log folder " + engineLogFolder, null)
        else showError("Could not open the log folder.", "Open " + engineLogFolder + " in Explorer yourself.", "")
    }

    function engineDetails() {
        var out = ["Creative Upscaler engine: " + engineState]
        for (var i = 0; i < problems.length; ++i) out.push("Problem: " + problems[i])
        if (health && health.version !== undefined) out.push("Engine version " + health.version + (servicePort > 0 ? ", port " + servicePort : ""))
        if (health && health.checked_at) out.push("Checked at " + health.checked_at)
        out.push("Engine logs: " + engineLogFolder)
        if (hostLogFolder !== "") out.push("Artegra Enhancer logs: " + hostLogFolder)
        return out.join("\n")
    }

    QtObject {
        id: clock
        property double now: Date.now()
    }
    Timer {
        interval: 1000
        repeat: true
        running: (root.visible && (!root.connected || root.engineState === "starting")) || root.batch.active
        onTriggered: clock.now = Date.now()
    }

    function startDiscovery() {
        if (api.discovering || connected) return
        if (firstAttemptAt === 0) firstAttemptAt = Date.now()
        api.discover(function(port, h) {
            if (port > 0) {
                onConnected(h)
            }
        })
    }

    function retryEngine() {
        log("info", "engine_retry", "Trying the engine again", null)
        launchTried = false
        launchFailed = false
        firstAttemptAt = Date.now()
        clock.now = Date.now()
        if (connected) {
            api.post("/api/engine/retry", {}, function(err, data) {
                if (err) { log("warning", "engine_retry_failed", "The engine could not retry: " + err.message, { log_ref: err.log_ref }); refreshHealth(); return }
                if (data && api.isHealth(data)) health = data
                else refreshHealth()
            })
        } else {
            startDiscovery()
        }
    }

    function onConnected(h) {
        if (everConnected) log("info", "service_back", "Connected to the engine again", null)
        health = h
        healthFailures = 0
        everConnected = true
        _pollWarned = false
        launchFailed = false
        loadControls()
        loadSettings()
        loadHistory()
    }

    property bool historyLoaded: false
    Timer {
        interval: 3000
        repeat: true
        running: root.visible && root.connected && (!root.controlsFromService || !root.settingsLoaded || !root.historyLoaded)
        onTriggered: {
            if (!root.controlsFromService) root.loadControls()
            if (!root.settingsLoaded) root.loadSettings()
            if (!root.historyLoaded) root.loadHistory()
        }
    }

    function refreshHealth() {
        api.get("/health", function(err, data) {
            if (err) {
                healthFailures += 1
                if (healthFailures >= 2) {
                    log("warning", "service_lost", "Lost the connection to the engine; looking for it again.", { error: err.message })
                    api.abortAll()
                    api.port = 0
                    health = null
                    firstAttemptAt = Date.now()
                    launchTried = false
                    launchFailed = false
                    startDiscovery()
                }
                return
            }
            healthFailures = 0
            health = data
        }, { quiet: true, timeoutMs: 4000 })
    }

    Timer {
        id: discoveryTimer
        interval: 2000
        repeat: true
        triggeredOnStart: true
        running: root.visible && !root.connected
        onTriggered: root.startDiscovery()
    }
    Timer {
        interval: 3000
        repeat: true
        running: (root.visible || root.batch.active) && root.connected
        onTriggered: root.refreshHealth()
    }

    property var controlsInfo: D.controls
    property bool controlsFromService: false

    property bool _controlsPending: false
    function loadControls() {
        if (_controlsPending) return
        _controlsPending = true
        api.get("/api/controls", function(err, data) {
            _controlsPending = false
            if (err) { log("warning", "controls_failed", "Could not load the control descriptions yet (will retry): " + err.message, { log_ref: err.log_ref }); return }
            if (!data || !data.presets || !data.sliders) { log("error", "controls_invalid", "The engine sent incomplete control descriptions.", null); return }
            controlsInfo = data
            controlsFromService = true
            log("info", "controls_loaded", "Controls loaded (" + data.contract + ")", null, true)
        })
    }

    function presetValues(name) {
        var list = controlsInfo.presets || []
        for (var i = 0; i < list.length; ++i) if (list[i].name === name) return list[i].values
        return null
    }
    function presetText(name) {
        var list = controlsInfo.presets || []
        for (var i = 0; i < list.length; ++i) if (list[i].name === name) return list[i].text
        return ""
    }
    function sliderInfo(key) {
        var list = controlsInfo.sliders || []
        for (var i = 0; i < list.length; ++i) if (list[i].key === key) return list[i]
        return { key: key, label: key, low: "", high: "", text: "" }
    }

    property string preset: "Default"
    property bool custom: false
    property real creativity: 50
    property real resemblance: 60
    property real restoration: 35
    property int scale: 2
    property var protect: ["people", "furniture", "vehicles", "windows"]
    property string quickProtect: ""
    property string outputFormat: "png8"
    property string seed: "20261102"
    property string extraPrompt: ""
    property string mode: "standard"
    function setMode(m) {
        if ((m !== "standard" && m !== "fast") || mode === m) return
        if (m === "fast" && !fastAvailable) return
        mode = m
        log("info", "mode", "Mode set to " + (m === "fast" ? "Fast" : "Standard"), null)
        rebuildQueue()
        _waitingModeTouched = true
        waitingChanged()
    }
    property double _fastRefusedMs: 0
    function fastRefused(err) {
        if (!err || err.code !== "fast_unavailable") return
        _fastRefusedMs = Date.now()
        refreshHealth()
    }
    onFastAvailableChanged: if (!fastAvailable && health !== null && mode !== "standard") {
        mode = "standard"
        rebuildQueue()
        var fm = health.engine && health.engine.fast ? String(health.engine.fast.message || "") : ""
        log("warning", "mode", "Mode set to Standard: Fast cannot be used now", { message: fm })
        if (Date.now() - _fastRefusedMs > 10000) showToast("notice", "Mode set to Standard", fm, "", "", null, "", "")
    }
    property string outputDir: ""
    property bool outputDirOk: false
    property string outputDirError: ""
    property var outputDirRefused: null
    property bool settingsLoaded: false
    property bool savingOutputDir: false
    property bool restoringPrefs: false

    function applyPreset(name) {
        var v = presetValues(name)
        if (!v) return
        preset = name
        custom = false
        creativity = v.creativity
        resemblance = v.resemblance
        restoration = v.restoration
        log("info", "preset", "Preset " + name + ": Creativity " + v.creativity + ", Resemblance " + v.resemblance + ", Restoration " + v.restoration, null)
        savePrefs()
        waitingChanged()
    }

    function setSlider(key, value) {
        var v = Math.max(0, Math.min(100, Math.round(value)))
        if (key === "creativity") creativity = v
        else if (key === "resemblance") resemblance = v
        else if (key === "restoration") restoration = v
        var p = presetValues(preset)
        custom = !p || p.creativity !== creativity || p.resemblance !== resemblance || p.restoration !== restoration
        savePrefs()
        waitingChanged()
    }

    function resetToPreset() { applyPreset(preset) }

    function setScale(s, force) {
        if (scale === s && force !== true) return
        var mixedBefore = force === true || waitingFactorsMixed()
        var undo = mixedBefore ? waitingSnapshot() : null
        scale = s
        log("info", "scale", "Upscale set to " + F.scaleLabel(s), null)
        if (inputFactorCount() > 0) inputFactors = ({})
        rebuildQueue()
        ensurePlansForInputs()
        savePrefs()
        _waitingScaleTouched = true
        waitingChanged()
        if (undo !== null && undo.length > 0)
            showToast("undo", "Every waiting image set to " + F.scaleLabel(s), "", "", "Undo", { kind: "waiting", items: undo })
    }

    function setProtect(key, on) {
        var next = []
        var cats = controlsInfo.protect || []
        for (var i = 0; i < cats.length; ++i) {
            var k = cats[i].key
            if ((k === key && on) || (k !== key && protect.indexOf(k) >= 0)) next.push(k)
        }
        protect = next
        savePrefs()
        waitingChanged()
    }

    function quickInfo(key) {
        var list = controlsInfo.quick_protect || []
        for (var i = 0; i < list.length; ++i) if (list[i].key === key) return list[i]
        return null
    }

    function setQuickProtect(key, on) {
        quickProtect = on ? key : ""
        savePrefs()
        waitingChanged()
    }

    readonly property var effectiveProtect: {
        var q = quickInfo(quickProtect)
        return q ? q.categories : protect
    }
    readonly property string protectSignature: quickProtect !== "" ? "quick:" + quickProtect : protect.join(",")

    function setOutputFormat(f) { outputFormat = f; savePrefs(); waitingChanged() }
    function setSeed(s) { seed = s; waitingChanged() }
    function randomSeed() { return String(Math.floor(Math.random() * 2147483646) + 1) }
    function newSeed() {
        seed = randomSeed()
        log("info", "seed", "New variation number " + seed, null)
        waitingChanged()
    }
    onExtraPromptChanged: waitingChanged()

    function currentSettings() {
        var s = { preset: preset, scale: scale, output_format: outputFormat, seed: seed.trim(), prompt: extraPrompt.trim() }
        if (mode === "fast" && fastAvailable && fastSettingsOk(scale)) s.mode = "fast"
        if (custom) {
            s.custom = true
            s.creativity = creativity
            s.resemblance = resemblance
            s.restoration = restoration
        }
        if (quickProtect !== "") s.quick_protect = quickProtect
        else s.protect = protect.slice()
        return s
    }

    readonly property string seedError: {
        var t = seed.trim()
        if (t === "") return ""
        if (!/^\d{1,19}$/.test(t)) return "Use a whole number of up to 19 digits."
        if (t.length === 19 && t > "9223372036854775807") return "Use a number up to 9223372036854775807."
        return ""
    }

    property bool _settingsPending: false
    function loadSettings() {
        if (_settingsPending) return
        _settingsPending = true
        api.get("/api/settings", function(err, data) {
            _settingsPending = false
            if (err) { log("warning", "settings_failed", "Could not read the output folder setting yet (will retry): " + err.message, { log_ref: err.log_ref }); return }
            settingsLoaded = true
            outputDir = data.output_dir || ""
            var w = data.output_dir_writable
            outputDirOk = (w === undefined || w === null) ? outputDir !== "" : !!w
            outputDirError = outputDirOk ? "" : (data.output_dir_problem || (outputDir === "" ? "Choose an output folder." : "This folder cannot be written to. Choose another folder."))
            log("info", "settings_loaded", "Output folder " + outputDir + (outputDirOk ? "" : " (not writable)"), null)
        })
    }

    function chooseOutputDir(path) {
        if (!path) return
        savingOutputDir = true
        api.post("/api/settings", { output_dir: path }, function(err, data) {
            savingOutputDir = false
            if (err) {
                outputDirRefused = { path: path, reason: err.message }
                log("warning", "output_dir_rejected", "Output folder " + path + " was not accepted: " + err.message, { log_ref: err.log_ref })
                return
            }
            outputDir = (data && data.output_dir) || path
            outputDirOk = true
            outputDirError = ""
            outputDirRefused = null
            log("info", "output_dir", "Output folder set to " + outputDir, null)
            if (engineState === "problem" && problemKind === "output") refreshHealth()
        })
    }
    function dismissOutputDirRefused() { outputDirRefused = null }

    function openPath(path, what) {
        if (!path) return
        api.post("/api/open", { path: path }, function(err) {
            if (err) showError("Could not open the " + (what || "folder") + ".", err.message, err.log_ref, err.detail)
        })
    }

    property var dismissedJobs: ({})
    property bool activityOpen: false
    property real activityShare: 0.4

    function savePrefs() {
        if (restoringPrefs) return
        prefs.write("settings", { preset: preset, custom: custom, creativity: creativity, resemblance: resemblance,
                                  restoration: restoration, scale: scale, protect: protect, quickProtect: quickProtect,
                                  outputFormat: outputFormat })
    }

    function restorePrefs() {
        prefs.open()
        restoringPrefs = true
        var s = prefs.read("settings", null)
        if (s && typeof s === "object") {
            if (presetValues(s.preset)) preset = s.preset
            var p = presetValues(preset)
            custom = !!s.custom
            creativity = custom && isFinite(s.creativity) ? s.creativity : p.creativity
            resemblance = custom && isFinite(s.resemblance) ? s.resemblance : p.resemblance
            restoration = custom && isFinite(s.restoration) ? s.restoration : p.restoration
            if ([2, 4, 6, 8].indexOf(s.scale) >= 0) scale = s.scale
            if (s.protect && s.protect.length !== undefined) protect = s.protect
            quickProtect = s.quickProtect || ""
            if (s.outputFormat) outputFormat = s.outputFormat
        }
        dismissedJobs = prefs.read("dismissedJobs", {}) || {}
        Tokens.reduceMotion = !!prefs.read("reduceMotion", false)
        Tokens.surroundMidGrey = String(prefs.read("pictureSurround", "charcoal")) === "midGrey"
        activityOpen = false
        var share = Number(prefs.read("activityShare", 0.4))
        activityShare = isFinite(share) && share > 0 && share <= 0.6 ? share : 0.4
        restoringPrefs = false
    }

    function setActivityShare(v) {
        var share = Number(v)
        if (!isFinite(share) || share <= 0) return
        activityShare = Math.min(0.6, share)
        prefs.write("activityShare", activityShare)
    }

    function setReduceMotion(on) {
        Tokens.reduceMotion = on
        prefs.write("reduceMotion", on)
    }

    property var _activityOpener: null
    function setActivityOpen(on) {
        on = !!on
        if (on === activityOpen) return
        if (on) {
            var w = Window.window
            _activityOpener = w ? w.activeFocusItem : null
            if (shortcutsSheet.opened) shortcutsSheet.close()
            activityOpen = true
            refreshLogs()
            Qt.callLater(function() { if (root.activityOpen) activityLog.focusFirst() })
        } else {
            activityOpen = false
            var back = _activityOpener
            _activityOpener = null
            if (back && back.visible) back.forceActiveFocus()
            else root.forceActiveFocus()
        }
    }
    function setPictureSurround(value) {
        Tokens.surroundMidGrey = value === "midGrey"
        prefs.write("pictureSurround", value === "midGrey" ? "midGrey" : "charcoal")
    }
    readonly property string pictureSurround: Tokens.surroundMidGrey ? "midGrey" : "charcoal"

    property var inputs: []
    property var jobs: []
    property var rejected: []
    property bool adding: false
    property string selectedKey: ""
    property var rowsByKey: ({})
    property var lastSubmit: null
    property bool submitting: false
    property var _jobPolling: ({})

    ListModel { id: queueModel }
    property alias queue: queueModel
    signal queueAboutToChange()
    signal queuePatched()

    function inputKey(mediaId) { return "in:" + mediaId }
    function itemKey(jobId, itemId) { return "job:" + jobId + ":" + itemId }

    function addUrls(urls) {
        var paths = []
        for (var i = 0; i < urls.length; ++i) paths.push(F.localPathFromUrl(urls[i].toString()))
        addPaths(paths)
    }

    readonly property bool canAddImages: connected && !(engineState === "problem" && problemKind !== "output")
    function addPaths(paths) { addPathsAt(paths, null) }
    property real _inputOrder: 0
    function inputInsertAt(list, order) {
        var k = list.length
        while (k > 0 && !(list[k - 1].order <= order)) --k
        return k
    }
    function addPathsAt(paths, restore) {
        if (!paths || paths.length === 0) return
        var lineKey = restore && restore.removedKey ? restore.removedKey : ""
        if (!connected) {
            var why = reconnecting ? "The engine is reconnecting." : "The engine is still starting."
            if (lineKey !== "") { undoFailed(lineKey, "Could not be put back. " + why + " Try Undo again in a moment.", null); return }
            showError("Images cannot be added yet.", why + " Try again in a moment.", "")
            return
        }
        adding = true
        log("info", "inputs_add", "Adding " + F.plural(paths.length, "file or folder", "files or folders"), null, true)
        api.post("/api/inputs", { paths: paths }, function(err, data) {
            adding = false
            if (err) {
                if (lineKey !== "") {
                    var cause = err.status === 503 || err.code === "timeout" ? "The engine is busy. Try Undo again in a moment."
                              : err.status === 0 ? "The engine is reconnecting. Try Undo again in a moment."
                              : err.message
                    undoFailed(lineKey, "Could not be put back. " + cause, err)
                    return
                }
                showError("The images could not be added.", err.message, err.log_ref, err.detail)
                return
            }
            var added = []
            var items = (data && data.items) || []
            var rl = (data && data.rejected) || []
            if (lineKey !== "" && items.length === 0) {
                undoFailed(lineKey, "Could not be put back. " + (rl.length > 0 && rl[0].reason ? rl[0].reason : "Try Undo again in a moment."), null)
                return
            }
            var next = inputs.slice()
            var keep = restore && isFinite(restore.order)
            var listed = {}
            for (var n0 = 0; n0 < next.length; ++n0) listed[next[n0].mediaId] = true
            var already = []
            for (var i = 0; i < items.length; ++i) {
                var rec = F.normalizeInput(items[i])
                if (listed[rec.mediaId]) { already.push(rec.name); continue }
                listed[rec.mediaId] = true
                if (keep) rec.order = restore.order + i / 1000
                else { _inputOrder += 1; rec.order = _inputOrder }
                next.splice(inputInsertAt(next, rec.order), 0, rec)
                added.push(rec)
            }
            inputs = next
            if (lineKey !== "") dropRemovedLine(lineKey)
            var rej = []
            for (var j = 0; j < rl.length; ++j) rej.push({ name: F.basename(rl[j].path), path: rl[j].path, reason: rl[j].reason || "Not supported." })
            if (lineKey === "" || rej.length > 0) rejected = rej
            rebuildQueue()
            ensurePlansForInputs()
            if (added.length > 0 && ((restore && restore.select) || selectedKey === "" || !rowsByKey[selectedKey]))
                selectKey(inputKey(added[0].mediaId))
            var msg = lineKey !== "" && added.length > 0 ? added[0].name + " is back in the list"
                    : added.length > 0 ? "Added " + F.plural(added.length, "image", "images")
                    : already.length === 1 ? already[0] + " is already in the list"
                    : already.length > 1 ? F.plural(already.length, "image is", "images are") + " already in the list"
                    : "No images were added"
            if (rej.length > 0) msg += "; " + F.plural(rej.length, "file was", "files were") + " not added"
            announce(msg)
            log("info", "inputs_added", msg, { rejected: rej })
        }, { timeoutMs: 60000 })
    }

    property var removedLines: []
    function removeInput(mediaId, withUndo) {
        var rec = null
        var at = -1
        var next = []
        for (var i = 0; i < inputs.length; ++i) {
            if (inputs[i].mediaId === mediaId) { rec = inputs[i]; at = i }
            else next.push(inputs[i])
        }
        if (!rec) return
        var wasSelected = selectedKey === inputKey(mediaId)
        var pick = ""
        if (wasSelected) {
            var keys = []
            for (var q = 0; q < queueModel.count; ++q) {
                var r = queueModel.get(q)
                if (r.kind === "input" || r.kind === "job") keys.push(r.key)
            }
            var me = keys.indexOf(inputKey(mediaId))
            pick = me >= 0 && me + 1 < keys.length ? keys[me + 1] : (me > 0 ? keys[me - 1] : "")
        }
        inputs = next
        if (withUndo !== false) {
            var lines = removedLines.slice()
            lines.push({ key: "rm:" + mediaId, rec: rec, select: wasSelected, state: "", text: "" })
            removedLines = lines
        }
        if (wasSelected) selectedKey = pick
        rebuildQueue()
        api.del("/api/inputs/" + encodeURIComponent(mediaId), function(err) {
            if (err && err.status !== 404) log("warning", "input_remove_failed", "The engine could not forget " + rec.name + ": " + err.message, { log_ref: err.log_ref })
        })
        log("info", "input_removed", "Removed " + rec.name, null)
        if (withUndo !== false) announce("Removed " + rec.name + ". Undo puts it back.")
    }
    function removedLineAt(key) {
        for (var i = 0; i < removedLines.length; ++i) if (removedLines[i].key === key) return i
        return -1
    }
    function setRemovedLine(key, state, text) {
        var i = removedLineAt(key)
        if (i < 0) return
        var lines = removedLines.slice()
        lines[i] = Object.assign({}, lines[i], { state: state, text: text })
        removedLines = lines
    }
    function dropRemovedLine(key) {
        var i = removedLineAt(key)
        if (i < 0) return
        var lines = removedLines.slice()
        lines.splice(i, 1)
        removedLines = lines
    }
    function undoRemoval(key) {
        var i = removedLineAt(key)
        if (i < 0 || removedLines[i].state === "busy") return
        var line = removedLines[i]
        setRemovedLine(key, "busy", "")
        rebuildQueue()
        addPathsAt([line.rec.path], { order: line.rec.order, select: line.select, removedKey: key })
    }
    function undoLatest() {
        for (var i = removedLines.length - 1; i >= 0; --i) {
            if (removedLines[i].state !== "busy") { undoRemoval(removedLines[i].key); return }
        }
        if (clearedLine !== null) undoClearFinished()
    }
    function undoFailed(key, text, err) {
        var i = removedLineAt(key)
        var name = i >= 0 ? removedLines[i].rec.name : ""
        setRemovedLine(key, "failed", text)
        rebuildQueue()
        log("warning", "undo_failed", name + ": " + text, err ? { log_ref: err.log_ref || "", detail: err.detail || "" } : null)
        announce(name + ". " + text)
    }

    property var clearedLine: null
    function clearFinished() {
        var d = Object.assign({}, dismissedJobs)
        var n = 0
        var images = 0
        for (var i = 0; i < jobs.length; ++i) {
            if (!F.isActiveJob(jobs[i]) && !d[jobs[i].id]) { d[jobs[i].id] = true; n += 1; images += jobs[i].items.length }
        }
        if (n === 0) return
        clearedLine = { count: (clearedLine ? clearedLine.count : 0) + images, prev: clearedLine ? clearedLine.prev : dismissedJobs }
        dismissedJobs = d
        prefs.write("dismissedJobs", d)
        rebuildQueue()
        log("info", "history_cleared", "Hid " + F.plural(n, "finished batch", "finished batches") + " from the list", null)
        announce(F.plural(images, "finished image", "finished images") + " cleared. Undo shows them again.")
    }
    function undoClearFinished() {
        if (clearedLine === null) return
        dismissedJobs = clearedLine.prev
        prefs.write("dismissedJobs", dismissedJobs)
        clearedLine = null
        rebuildQueue()
        log("info", "history_restored", "Showed the finished batches in the list again", null)
    }
    function collapseRemoved() {
        var keep = []
        for (var i = 0; i < removedLines.length; ++i) if (removedLines[i].state === "busy") keep.push(removedLines[i])
        if (keep.length === removedLines.length && clearedLine === null) return
        removedLines = keep
        clearedLine = null
        rebuildQueue()
    }
    property int removedLineMs: 20000
    Timer {
        id: removedTimer
        interval: root.removedLineMs
        running: (root.removedLines.length > 0 || root.clearedLine !== null) && !rail.attention
        onTriggered: root.collapseRemoved()
    }

    function planMinutes(p, m, single) {
        var want = m === "fast" || m === "standard" ? m : (mode === "fast" && fastAvailable ? "fast" : "standard")
        return F.planMinutes(p, want, single === true)
    }
    function fastSizeRefusal(inp) {
        if (!inp) return null
        var p = planForInput(inp, 2)
        var r = p && p.finish ? p.finish.fast_refusal : null
        return r && r.reason === "size" ? r : null
    }
    function fastLooks() {
        var f = health && health.engine && health.engine.fast && health.engine.fast.looks ? health.engine.fast.looks : null
        return f && f.length > 0 ? f : ["Light", "Default"]
    }
    function fastMaxFactor() {
        var f = health && health.engine && health.engine.fast ? Number(health.engine.fast.max_factor) : 0
        return f > 0 ? f : 2
    }
    function fastSettingsOk(factor) {
        return factor <= fastMaxFactor() && !custom && fastLooks().indexOf(preset) >= 0
    }
    readonly property bool anyInputFast: {
        if (!(mode === "fast" && fastAvailable)) return false
        for (var i = 0; i < inputs.length; ++i) if (inputMode(inputs[i]) === "fast") return true
        return false
    }
    function inputMode(inp, factor) {
        if (!(mode === "fast" && fastAvailable)) return "standard"
        if (!fastSettingsOk(factor > 0 ? factor : inputFactor(inp))) return "standard"
        return fastSizeRefusal(inp) !== null ? "standard" : "fast"
    }
    property var inputFactors: ({})
    function inputFactor(inp) {
        var f = inp ? Number(inputFactors[inp.mediaId]) : 0
        return f > 0 ? f : scale
    }
    function inputFactorCount() { var n = 0; for (var k in inputFactors) n += 1; return n }
    function transparencyFor(alpha, fmt) {
        if (!alpha) return "none"
        if (fmt === "jpeg") return "not_kept"
        return features.alpha_kept === true ? "kept" : "not_kept"
    }
    function formatOfName(name) {
        var m = /\.([A-Za-z0-9]+)$/.exec(String(name || ""))
        var e = m ? m[1].toLowerCase() : ""
        return e === "jpg" || e === "jpeg" ? "JPEG" : e === "png" ? "PNG" : e === "tif" || e === "tiff" ? "TIFF"
             : e === "webp" ? "WebP" : e === "bmp" ? "BMP" : ""
    }

    function planKey(w, h, s) { return w + "x" + h + "@" + s }
    property var plans: ({})
    property var _planPending: ({})

    function planFor(w, h, s) {
        return plans[planKey(w, h, s)] || null
    }

    function ensurePlan(w, h, s) {
        if (!(w > 0 && h > 0) || !connected) return
        var k = planKey(w, h, s)
        if (plans[k] || _planPending[k]) return
        _planPending[k] = true
        api.post("/api/plan", { width: w, height: h, scale: s }, function(err, data) {
            delete _planPending[k]
            if (err) { log("warning", "plan_failed", "Could not plan " + w + "x" + h + " at " + s + "x: " + err.message, { log_ref: err.log_ref }); return }
            var next = Object.assign({}, plans)
            next[k] = data
            plans = next
            rebuildQueue()
        }, { quiet: true })
    }

    function ensurePlansForInputs() {
        for (var i = 0; i < inputs.length; ++i) {
            if (!inputs[i].scales) ensurePlan(inputs[i].width, inputs[i].height, inputFactor(inputs[i]))
        }
        var row = selectedRow
        if (row && row.kind === "input") {
            var inp = inputFor(row.mediaId)
            if (inp && !inp.scales) {
                var scales = controlsInfo.scales || [2, 4, 6, 8]
                for (var j = 0; j < scales.length; ++j) ensurePlan(row.srcW, row.srcH, scales[j])
            }
        }
    }

    function inputFor(mediaId) {
        for (var i = 0; i < inputs.length; ++i) if (inputs[i].mediaId === mediaId) return inputs[i]
        return null
    }

    readonly property string finishBasis: {
        var sp = health !== null && health.engine !== undefined && health.engine !== null ? health.engine.speed : null
        return (sp && sp.match_earlier === true ? "match" : "stack") + (fastAvailable ? "+fast" : "")
    }
    property string _finishBasisSeen: "stack"
    onFinishBasisChanged: {
        if (health === null) return
        if (_finishBasisSeen === finishBasis) return
        _finishBasisSeen = finishBasis
        refreshInputPlans()
    }
    function refreshInputPlans() {
        plans = ({})
        if (!connected) return
        api.get("/api/inputs", function(err, data) {
            if (err) { log("warning", "inputs_refresh_failed", "Could not read the images' plans again: " + err.message, { log_ref: err.log_ref }, true); return }
            var list = data && data.items ? data.items : []
            var byId = {}
            for (var i = 0; i < list.length; ++i) byId[String(list[i].id !== undefined ? list[i].id : list[i].media_id)] = list[i]
            var next = []
            var changed = false
            for (var j = 0; j < inputs.length; ++j) {
                var fresh = byId[inputs[j].mediaId]
                if (fresh && fresh.scales) { next.push(Object.assign({}, inputs[j], { scales: fresh.scales })); changed = true }
                else next.push(inputs[j])
            }
            if (changed) inputs = next
            rebuildQueue()
            ensurePlansForInputs()
            if (selectedRow && selectedRow.kind === "job") ensurePlansForRow(selectedRow)
        }, { quiet: true })
    }

    function planForInput(inp, s) {
        if (!inp) return null
        return F.planFromScales(inp.scales, s) || planFor(inp.width, inp.height, s)
    }

    function refusalText(p, s) {
        if (!p || p.ok !== false) return ""
        var m = F.limitMp(p.reason || "")
        var os = p.output_size || [0, 0]
        if (m !== "" && os[0] > 0 && os[1] > 0) return F.overLimitText(s, os[0], os[1], m)
        return p.reason || "This image is too large for " + F.scaleLabel(s) + "."
    }

    function inputRefusal(inp, s) {
        return refusalText(planForInput(inp, s), s)
    }

    function refusal(w, h, s) {
        return refusalText(planFor(w, h, s), s)
    }

    function someInputTakes(s) {
        if (inputs.length === 0) return true
        for (var i = 0; i < inputs.length; ++i) if (inputRefusal(inputs[i], s) === "") return true
        return false
    }
    function listRefusalText(s) {
        var m = ""
        for (var i = 0; i < inputs.length && m === ""; ++i) m = F.limitMp((planForInput(inputs[i], s) || {}).reason || "")
        return m !== "" ? F.scaleLabel(s) + " is over the " + m + " MP limit for every image in the list."
                        : F.scaleLabel(s) + " is too large for every image in the list."
    }

    property bool _historyPending: false
    function loadHistory() {
        if (_historyPending) return
        _historyPending = true
        api.get("/api/jobs", function(err, data) {
            _historyPending = false
            if (err) { log("warning", "history_failed", "Could not load earlier batches yet (will retry): " + err.message, { log_ref: err.log_ref }); return }
            historyLoaded = true
            var list = F.jobsFromResponse(data)
            log("info", "history_received", "Received " + F.plural(list.length, "earlier job", "earlier jobs") + " from the engine", null, true)
            var norm = []
            for (var i = 0; i < list.length; ++i) norm.push(F.normalizeJob(list[i]))
            norm.sort(function(a, b) { return a.created < b.created ? -1 : (a.created > b.created ? 1 : 0) })
            var hadJobs = jobs.length > 0
            jobs = norm
            rebuildQueue()
            var told = Number(prefs.read("restartTold", 0)) || 0
            var restartAt = 0, resumed = 0
            for (var j0 = 0; j0 < norm.length; ++j0) {
                if (dismissedJobs[norm[j0].id]) continue
                for (var k0 = 0; k0 < norm[j0].items.length; ++k0) {
                    var it0 = norm[j0].items[k0]
                    if (!(it0.resumedAt > 0) || !F.contains(F.ACTIVE_ITEM_STATES, it0.state)) continue
                    restartAt = Math.max(restartAt, it0.resumedAt)
                    if (it0.resumedAt > told) resumed += 1
                }
            }
            if (restartAt > told) prefs.write("restartTold", restartAt)
            if (!hadJobs && norm.length > 0) {
                var toFinish = 0, finished = 0
                for (var j = 0; j < norm.length; ++j) {
                    if (dismissedJobs[norm[j].id]) continue
                    for (var k = 0; k < norm[j].items.length; ++k) {
                        var st = norm[j].items[k].state
                        if (F.contains(F.ACTIVE_ITEM_STATES, st)) toFinish += 1
                        else if (st === "done") finished += 1
                    }
                }
                var bg = prefs.read("background", null)
                if (bg && typeof bg === "object" && bg.ids && bg.ids.length !== undefined) {
                    prefs.write("background", null)
                    var doneNow = 0, known = []
                    for (var b0 = 0; b0 < norm.length; ++b0) {
                        if (bg.ids.indexOf(norm[b0].id) < 0) continue
                        known.push(norm[b0].id)
                        for (var b1 = 0; b1 < norm[b0].items.length; ++b1) if (norm[b0].items[b1].state === "done") doneNow += 1
                    }
                    if (known.length > 0) {
                        runJobIds = known
                        _runActive = batch.active
                        rebuildQueue()
                        var since = Math.max(0, doneNow - (Number(bg.done) || 0))
                        showToast("notice", "Kept running while the window was closed, " + F.hhmm(Number(bg.at)) + " to " + F.hhmm(Tokens.wallNow()),
                                  since > 0 ? F.plural(since, "image", "images") + " finished" : "", "", "", null)
                    }
                } else if (resumed > 0) {
                    showToast("notice", "Resumed " + F.plural(resumed, "image", "images") + " after the restart", "Finished passes are kept.", "", "", null)
                }
                log("info", "history_loaded", "Earlier work loaded: " + F.plural(toFinish, "image", "images") + " to finish, " + finished + " finished", { jobs: norm.length, resumed_after_restart: resumed })
                if (selectedKey === "" && batch.runningKey !== "") selectKey(batch.runningKey)
                else if (batch.runningKey !== "" && batch.active && bg) selectKey(batch.runningKey)
            }
        })
    }

    function pollActiveJobs() {
        for (var i = 0; i < jobs.length; ++i) {
            if (F.isActiveJob(jobs[i])) refreshJob(jobs[i].id)
        }
    }

    property bool _pollWarned: false
    property var _jobTouched: ({})
    property var _jobHeld: ({})
    function jobHeld(id) { return _jobHeld[id] !== undefined && Date.now() - _jobHeld[id] < 8000 }
    function refreshJob(id) {
        if (_jobPolling[id]) return
        _jobPolling[id] = true
        var asked = Date.now()
        api.get("/api/jobs/" + encodeURIComponent(id), function(err, data, status, same) {
            delete _jobPolling[id]
            if (!err && (jobHeld(id) || (_jobTouched[id] !== undefined && asked < _jobTouched[id]))) { api.forget("job:" + id); return }
            if (same) { _pollWarned = false; return }
            if (err) {
                var quiet = err.code === "timeout" || err.code === "aborted" || _pollWarned
                log("warning", "job_poll_failed", "Could not check the progress of the running images: " + err.message,
                    { job: id, code: err.code, log_ref: err.log_ref }, quiet)
                if (!quiet) _pollWarned = true
                return
            }
            _pollWarned = false
            mergeJob(F.normalizeJob(data))
        }, { quiet: true, timeoutMs: 5000, sameKey: "job:" + id })
    }
    function forgetJobAnswer(id) {
        var sigs = _jobSigs
        delete sigs[id]
        _jobTouched[id] = Date.now()
        api.forget("job:" + id)
    }

    property var _jobSigs: ({})
    function mergeJob(nj) {
        var sig = JSON.stringify(nj)
        if (_jobSigs[nj.id] === sig) return
        _jobSigs[nj.id] = sig
        var prev = null
        var next = []
        var found = false
        for (var i = 0; i < jobs.length; ++i) {
            if (jobs[i].id === nj.id) { prev = jobs[i]; next.push(nj); found = true }
            else next.push(jobs[i])
        }
        if (!found) next.push(nj)
        jobs = next
        reportTransitions(prev, nj)
        rebuildQueue()
    }

    function reportTransitions(prev, nj) {
        var before = {}
        if (prev) for (var i = 0; i < prev.items.length; ++i) before[prev.items[i].itemId] = prev.items[i].state
        var failedNow = []
        for (var j = 0; j < nj.items.length; ++j) {
            var it = nj.items[j]
            var was = before[it.itemId]
            if (was === it.state) continue
            log("info", "item_state", it.name + ": " + (was || "new") + " -> " + it.state, { job: nj.id, item: it.itemId }, true)
            if (it.state === "failed" && was !== undefined) {
                log("error", "item_failed", it.name + " could not be upscaled. " + (it.errorText || "The engine stopped on this image."),
                    { job: nj.id, item: it.itemId, log_ref: it.logRef })
                failedNow.push({ key: itemKey(nj.id, it.itemId), name: it.name, text: it.errorText || "The engine stopped on this image.", logRef: it.logRef })
            }
        }
        if (failedNow.length > 0)
            announce(failedNow.length === 1 ? failedNow[0].name + " could not be upscaled." : failedNow.length + " images could not be upscaled.")
        if (prev && F.isActiveJob(prev) && !F.isActiveJob(nj)) {
            var done = 0, failed = 0, cancelled = 0, stopped = 0
            for (var k = 0; k < nj.items.length; ++k) {
                if (nj.items[k].state === "done") done += 1
                else if (nj.items[k].state === "failed") failed += 1
                else if (nj.items[k].state === "cancelled") cancelled += 1
                else if (nj.items[k].state === "stopped") stopped += 1
            }
            var parts = [F.plural(done, "image", "images") + " upscaled"]
            if (failed) parts.push(failed + " failed")
            if (stopped) parts.push(stopped + " stopped")
            if (cancelled) parts.push(cancelled + " cancelled")
            log("info", "job_finished", "Batch finished: " + parts.join(", "), { job: nj.id, state: nj.state })
            announce(F.plural(done, "image", "images") + " finished" + (failed ? ", " + failed + " failed" : "")
                     + (stopped ? ", " + stopped + " stopped" : "") + (cancelled ? ", " + cancelled + " cancelled" : ""))
        }
    }

    property var _rowSigs: ({})
    property string _allRowsSig: ""
    property bool earlierOpen: false
    property var groupCounts: ({ working: 0, failed: 0, stopped: 0, next: 0, done: 0, cancelled: 0, ready: 0, refused: 0, last: 0, earlier: 0 })
    property var groupLines: ({ working: 0, failed: 0, stopped: 0, next: 0, done: 0, cancelled: 0, ready: 0, refused: 0, cleared: 0, last: 0, earlier: 0 })
    property var runJobIds: []
    property bool _runActive: false
    property var liveThumbs: ({})
    property bool wantsLastFrames: false
    readonly property int imageCount: {
        var n = 0
        for (var k in groupCounts) n += groupCounts[k]
        return n
    }
    property int activeJobCount: 0
    property string refusedNote: ""

    function flatRow(r) {
        var out = {}
        for (var k in r) {
            var t = typeof r[k]
            if (t === "string" || t === "number" || t === "boolean") out[k] = r[k]
        }
        return out
    }
    function jobRows(job, group, places) {
        var out = []
        for (var j = 0; j < job.items.length; ++j) {
            var it = job.items[j]
            var key = itemKey(job.id, it.itemId)
            var eff = it.effective || job.effective || null
            var fct = eff && eff.scale ? Number(eff.scale) : (it.outW && it.width ? Math.round(it.outW / it.width) : 2)
            var live = liveThumbs[key] || null
            var halted = it.state === "stopped" || it.state === "failed" || it.state === "cancelled"
            out.push({
                key: key, kind: "job", group: group, place: places[key] || 0,
                mediaId: it.mediaId, jobId: job.id, itemId: it.itemId,
                name: it.name, path: it.path, srcW: it.width, srcH: it.height,
                outW: it.outW || it.width * fct, outH: it.outH || it.height * fct, factor: fct,
                status: it.state, progress: it.progress, stage: it.stage, stages: it.stages, stageProgress: it.stageProgress,
                etaS: it.etaS, minutes: F.itemMinutes(it), message: it.message, output: it.output,
                errorText: it.errorText, logRef: it.logRef, thumbUrl: it.thumbUrl, proxyUrl: it.proxyUrl,
                resultProxyUrl: it.resultProxyUrl, resultRegionUrl: it.resultRegionUrl, resultReady: it.resultReady,
                duplicate: false, refusedReason: "", maxFactor: 0, notes: it.notes, tookS: it.tookS, alpha: it.alpha === true,
                removedState: "", removedText: "",
                gpu: it.gpu, cardsText: F.cardsLabel(it.cards), ownFactor: false,
                liveThumbUrl: live && !halted ? live.thumb : "", lastFrameUrl: live && halted ? live.canvas : "",
                livePass: live && !halted && live.pass ? live.pass : "",
                mode: eff && eff.mode ? String(eff.mode) : "standard",
                settingsChanged: it.settingsChanged === true,
                transparency: it.transparency !== "" ? it.transparency : transparencyFor(it.alpha === true, eff ? String(eff.output_format || "") : ""),
                outputBytes: it.outputBytes, bytes: it.bytes, format: formatOfName(it.name), finishedAt: it.finishedAt,
                queueRank: it.queueRank,
                cards: it.cards, run: it.run, effective: eff, ranWith: it.ranWith, at: it.at
            })
        }
        return out
    }

    function longestRunInOrder(keys, newAt) {
        var tails = [], tailAt = [], prev = []
        for (var i = 0; i < keys.length; ++i) {
            var v = newAt[keys[i]]
            var lo = 0, hi = tails.length
            while (lo < hi) {
                var mid = (lo + hi) >> 1
                if (tails[mid] < v) lo = mid + 1
                else hi = mid
            }
            tails[lo] = v
            tailAt[lo] = i
            prev[i] = lo > 0 ? tailAt[lo - 1] : -1
        }
        var out = {}
        for (var k = tails.length > 0 ? tailAt[tails.length - 1] : -1; k >= 0; k = prev[k]) out[keys[k]] = true
        return out
    }

    function rebuildQueue() {
        var shown = []
        for (var i = 0; i < jobs.length; ++i) {
            if (dismissedJobs[jobs[i].id] && !F.isActiveJob(jobs[i])) continue
            shown.push(jobs[i])
        }
        var liveIds = []
        for (var r0 = 0; r0 < jobs.length; ++r0) if (F.isActiveJob(jobs[r0])) liveIds.push(jobs[r0].id)
        if (liveIds.length > 0) {
            var runIds = _runActive ? runJobIds.slice() : []
            for (var r1 = 0; r1 < liveIds.length; ++r1) if (runIds.indexOf(liveIds[r1]) < 0) runIds.push(liveIds[r1])
            if (JSON.stringify(runIds) !== JSON.stringify(runJobIds)) runJobIds = runIds
            _runActive = true
        } else {
            _runActive = false
        }
        var inRun = {}
        for (var r2 = 0; r2 < runJobIds.length; ++r2) inRun[runJobIds[r2]] = true
        var places = {}
        var waiting = 0
        var active = []
        var finished = []
        for (var a0 = 0; a0 < shown.length; ++a0) {
            if (F.isActiveJob(shown[a0]) || (_runActive && inRun[shown[a0].id])) active.push(shown[a0])
            else finished.push(shown[a0])
        }
        var waitList = []
        for (var a1 = 0; a1 < active.length; ++a1) {
            for (var a2 = 0; a2 < active[a1].items.length; ++a2) {
                var wit = active[a1].items[a2]
                if (wit.state === "queued" || wit.state === "interrupted")
                    waitList.push({ key: itemKey(active[a1].id, wit.itemId), rank: Number(wit.queueRank) || 0, order: waitList.length })
            }
        }
        waitList.sort(function(x, y) {
            var rx = x.rank > 0 ? x.rank : 1e9, ry = y.rank > 0 ? y.rank : 1e9
            return rx !== ry ? rx - ry : x.order - y.order
        })
        for (var a3 = 0; a3 < waitList.length; ++a3) places[waitList[a3].key] = ++waiting
        var rows = []
        var now = { working: [], failed: [], stopped: [], next: [], done: [], cancelled: [] }
        var halts = false
        for (var n = 0; n < active.length; ++n) {
            var jr = jobRows(active[n], "next", places)
            for (var t = 0; t < jr.length; ++t) {
                var st = jr[t].status
                jr[t].group = st === "queued" || st === "interrupted" ? "next" : st === "done" ? "done"
                            : st === "failed" ? "failed" : st === "stopped" ? "stopped" : st === "cancelled" ? "cancelled" : "working"
                if (st === "failed" || st === "stopped" || st === "cancelled") halts = true
                now[jr[t].group].push(jr[t])
            }
        }
        now.next.sort(function(x, y) { return (places[x.key] || 0) - (places[y.key] || 0) })
        if (now.next.length > 1) {
            var tally = {}, common = 0, most = 0
            for (var t1 = 0; t1 < now.next.length; ++t1) {
                var ff = now.next[t1].factor
                tally[ff] = (tally[ff] || 0) + 1
                if (tally[ff] > most) { most = tally[ff]; common = ff }
            }
            for (var t2 = 0; t2 < now.next.length; ++t2) now.next[t2].ownFactor = now.next[t2].factor !== common
        }
        rows = rows.concat(now.working, now.failed, now.stopped, now.next, now.done, now.cancelled)
        var refusedRows = []
        var note = ""
        var waitingLines = []
        for (var k0 = 0; k0 < inputs.length; ++k0) waitingLines.push({ rec: inputs[k0], line: null })
        for (var k1 = 0; k1 < removedLines.length; ++k1)
            waitingLines.splice(inputInsertAt(waitingLines.map(function(x) { return x.rec }), removedLines[k1].rec.order), 0,
                                { rec: removedLines[k1].rec, line: removedLines[k1] })
        for (var k = 0; k < waitingLines.length; ++k) {
            var inp = waitingLines[k].rec
            var gone = waitingLines[k].line
            var fct = inputFactor(inp)
            var reason = inputRefusal(inp, fct)
            var plan = planForInput(inp, fct)
            var row = {
                key: gone ? gone.key : inputKey(inp.mediaId), kind: gone ? "removed" : "input",
                group: reason !== "" ? "refused" : "ready", place: 0,
                mediaId: inp.mediaId, jobId: "", itemId: "",
                name: inp.name, path: inp.path, srcW: inp.width, srcH: inp.height,
                outW: inp.width * fct, outH: inp.height * fct, factor: fct,
                status: gone ? "removed" : (reason !== "" ? "refused" : "ready"), progress: 0, stage: 0,
                stages: plan && plan.stages ? plan.stages.length : 0, stageProgress: 0, etaS: -1,
                minutes: plan ? planMinutes(plan, gone ? "" : inputMode(inp)) : 0, message: "", output: "",
                mode: gone ? "" : inputMode(inp),
                errorText: "", logRef: "", thumbUrl: gone ? "" : inp.thumbUrl, proxyUrl: gone ? "" : inp.proxyUrl, resultProxyUrl: "",
                resultRegionUrl: "", resultReady: false,
                duplicate: gone ? false : inp.duplicate, refusedReason: gone ? "" : reason,
                maxFactor: reason !== "" && !gone ? largestFactor(inp) : 0,
                notes: gone ? "" : (inp.notes || ""), tookS: -1, alpha: inp.alpha === true,
                removedState: gone ? gone.state : "", removedText: gone ? gone.text : "",
                gpu: -1, cardsText: "", ownFactor: !gone && fct !== scale, liveThumbUrl: "", lastFrameUrl: "",
                settingsChanged: false, transparency: transparencyFor(inp.alpha === true, outputFormat),
                outputBytes: 0, bytes: gone ? 0 : (inp.bytes || 0), format: inp.format !== "" && inp.format !== undefined ? inp.format : formatOfName(inp.name),
                finishedAt: "", queueRank: 0,
                cards: [], run: null, effective: null, ranWith: null, at: null
            }
            if (reason === "") { rows.push(row); continue }
            refusedRows.push(row)
            if (note === "") {
                var m = F.limitMp((planForInput(inp, fct) || {}).reason || "")
                note = m !== "" ? "Over the " + m + " MP limit." : reason
            }
        }
        rows = rows.concat(refusedRows)
        if (clearedLine !== null) {
            rows.push({
                key: "cleared", kind: "cleared", group: "cleared", place: 0, mediaId: "", jobId: "", itemId: "",
                name: "", path: "", srcW: 0, srcH: 0, outW: 0, outH: 0, factor: scale, status: "cleared", progress: 0, stage: 0,
                stages: 0, stageProgress: 0, etaS: -1, minutes: 0, message: "", output: "", errorText: "", logRef: "",
                thumbUrl: "", proxyUrl: "", resultProxyUrl: "", resultRegionUrl: "", resultReady: false, duplicate: false,
                refusedReason: "", maxFactor: 0, notes: "", tookS: -1, alpha: false, removedState: "", removedText: "",
                gpu: -1, cardsText: "", ownFactor: false, liveThumbUrl: "", lastFrameUrl: "", settingsChanged: false,
                transparency: "none", outputBytes: 0, bytes: 0, format: "", finishedAt: "", queueRank: 0,
                cards: [], run: null, effective: null, ranWith: null, at: null
            })
        }
        var lastIds = {}
        var anyRun = false
        for (var f0 = 0; f0 < finished.length; ++f0) if (!_runActive && inRun[finished[f0].id]) { lastIds[finished[f0].id] = true; anyRun = true }
        if (!anyRun && finished.length > 0 && !_runActive) lastIds[finished[finished.length - 1].id] = true
        for (var f = 0; f < finished.length; ++f) {
            if (!lastIds[finished[f].id]) continue
            var lastRows = jobRows(finished[f], "last", places)
            for (var f1 = 0; f1 < lastRows.length; ++f1)
                if (lastRows[f1].status === "failed" || lastRows[f1].status === "stopped" || lastRows[f1].status === "cancelled") halts = true
            rows = rows.concat(lastRows)
        }
        for (var f2 = finished.length - 1; f2 >= 0; --f2)
            if (!lastIds[finished[f2].id]) rows = rows.concat(jobRows(finished[f2], "earlier", places))
        if (wantsLastFrames !== halts) wantsLastFrames = halts

        var byKey = {}
        var rowSigs = []
        var counts = { working: 0, failed: 0, stopped: 0, next: 0, done: 0, cancelled: 0, ready: 0, refused: 0, last: 0, earlier: 0 }
        var lines = { working: 0, failed: 0, stopped: 0, next: 0, done: 0, cancelled: 0, ready: 0, refused: 0, cleared: 0, last: 0, earlier: 0 }
        for (var r = 0; r < rows.length; ++r) {
            byKey[rows[r].key] = rows[r]
            rowSigs.push(JSON.stringify(rows[r]))
            if (rows[r].kind === "input" || rows[r].kind === "job") counts[rows[r].group] += 1
            lines[rows[r].group] += 1
        }
        var all = rowSigs.join("|")
        var changing = all !== _allRowsSig || JSON.stringify(counts) !== JSON.stringify(groupCounts)
                       || JSON.stringify(lines) !== JSON.stringify(groupLines) || note !== refusedNote
        if (changing) queueAboutToChange()
        if (note !== refusedNote) refusedNote = note
        if (JSON.stringify(counts) !== JSON.stringify(groupCounts)) groupCounts = counts
        if (JSON.stringify(lines) !== JSON.stringify(groupLines)) groupLines = lines
        if (activeJobCount !== active.length) activeJobCount = active.length
        if (changing) {
            var newAt = {}
            for (var w0 = 0; w0 < rows.length; ++w0) newAt[rows[w0].key] = w0
            for (var d0 = queueModel.count - 1; d0 >= 0; --d0) if (newAt[queueModel.get(d0).key] === undefined) queueModel.remove(d0)
            var keys = []
            for (var e0 = 0; e0 < queueModel.count; ++e0) keys.push(queueModel.get(e0).key)
            var stay = longestRunInOrder(keys, newAt)
            var inserted = {}
            for (var m = rows.length - 1; m >= 0; --m) {
                var key = rows[m].key
                var at = keys.indexOf(key)
                if (at >= 0 && stay[key]) continue
                var target = m === rows.length - 1 ? keys.length : keys.indexOf(rows[m + 1].key)
                if (at < 0) {
                    queueModel.insert(target, flatRow(rows[m]))
                    keys.splice(target, 0, key)
                    inserted[key] = true
                    continue
                }
                var to = at < target ? target - 1 : target
                if (to !== at) {
                    queueModel.move(at, to, 1)
                    keys.splice(at, 1)
                    keys.splice(to, 0, key)
                }
            }
            for (var u = 0; u < rows.length; ++u)
                if (!inserted[rows[u].key] && _rowSigs[rows[u].key] !== rowSigs[u]) queueModel.set(u, flatRow(rows[u]))
        }
        var sigMap = {}
        for (var c = 0; c < rows.length; ++c) sigMap[rows[c].key] = rowSigs[c]
        _rowSigs = sigMap
        if (all !== _allRowsSig) {
            _allRowsSig = all
            rowsByKey = byKey
        }
        if (changing) queuePatched()
        var again = []
        for (var g = 0; g < rows.length; ++g) {
            if (rows[g].group === "last" && rows[g].status === "cancelled" && rows[g].srcW > 0) {
                again.push(rows[g])
                ensurePlan(rows[g].srcW, rows[g].srcH, scale)
            }
        }
        if (JSON.stringify(again) !== JSON.stringify(cancelledRows)) cancelledRows = again
        var sel = selectedRow
        if (sel && sel.kind === "job" && sel.srcW > 0) ensurePlansForRow(sel)
        var nb = computeBatch()
        if (JSON.stringify(nb) !== JSON.stringify(batch)) batch = nb
        if (selectedKey !== "" && !byKey[selectedKey]) selectedKey = ""
        if (selectedKey === "" && rows.length > 0) {
            var pick = batch.runningKey
            var firstImage = ""
            for (var q = 0; pick === "" && q < rows.length; ++q) {
                if (rows[q].kind !== "input" && rows[q].kind !== "job") continue
                if (firstImage === "") firstImage = rows[q].key
                if (rows[q].group !== "earlier") pick = rows[q].key
            }
            selectedKey = pick !== "" ? pick : firstImage
        }
    }

    function groupTitle(group) {
        var n = groupCounts[group] || 0
        if (group === "cleared") return F.plural(clearedLine ? clearedLine.count : 0, "finished image", "finished images") + " cleared"
        var gone = (groupLines[group] || 0) - n
        if (n === 0 && gone > 0) return "Removed, " + F.plural(gone, "image", "images")
        var count = F.plural(n, "image", "images")
        if (group === "working") return "Working, " + count
        if (group === "failed") return "Failed, " + count
        if (group === "stopped") return "Stopped, " + count
        if (group === "next") return "Next, " + count
        if (group === "done") return "Done, " + count
        if (group === "cancelled") return "Cancelled, " + count
        if (group === "ready") return "Ready to upscale, " + count
        if (group === "refused") return "Too large for " + F.scaleLabel(scale) + ", " + count
        if (group === "last") return "Last batch, " + count
        return "Earlier, " + count
    }
    readonly property int groupsShown: {
        var n = 0
        for (var k in groupLines) if (groupLines[k] > 0) n += 1
        return n
    }

    function largestFactor(inp) {
        var list = controlsInfo.scales || [2, 4, 6, 8]
        var best = 0
        for (var i = 0; i < list.length; ++i) if (list[i] > best && inputRefusal(inp, list[i]) === "") best = list[i]
        return best
    }
    function syncLiveThumbs() {
        var items = viewer.liveFeed.items
        var out = {}
        for (var k in items) {
            var it = items[k]
            var halted = it.state === "stopped" || it.state === "failed"
            out[itemKey(it.job_id, it.item_id)] = { thumb: it.thumb_url ? api.mediaUrl(String(it.thumb_url)) : "",
                                                    canvas: halted && it.canvas_url ? api.mediaUrl(String(it.canvas_url)) : "",
                                                    pass: it.state === "sampling" && it.pass ? String(it.pass) : "" }
        }
        if (JSON.stringify(out) === JSON.stringify(liveThumbs)) return
        liveThumbs = out
        rebuildQueue()
    }
    readonly property int stuckMinutes: {
        if (!batch.active) return 0
        var items = viewer.liveFeed.items
        var worst = 0
        for (var k in items) {
            var t = items[k].timing
            if (!t || items[k].state !== "sampling") continue
            var pace = Math.max(Number(t.tile_s) || 0, 0)
            var age = Number(t.last_tile_age_s) || 0
            if (pace > 0 && age > Math.max(60, 3 * pace)) worst = Math.max(worst, Math.floor(age / 60))
        }
        return worst
    }

    readonly property var selectedRow: selectedKey !== "" && rowsByKey[selectedKey] ? rowsByKey[selectedKey] : null
    onSelectedRowChanged: {
        if (selectedRow && selectedRow.kind === "input") ensurePlansForInputs()
        else if (selectedRow && selectedRow.kind === "job" && selectedRow.srcW > 0) ensurePlansForRow(selectedRow)
    }
    function ensurePlansForRow(row) {
        if (!row || !(row.srcW > 0 && row.srcH > 0)) return
        var list = controlsInfo.scales || [2, 4, 6, 8]
        for (var i = 0; i < list.length; ++i) ensurePlan(row.srcW, row.srcH, list[i])
    }
    onConnectedChanged: { if (connected && selectedRow && selectedRow.kind === "job") ensurePlansForRow(selectedRow) }
    onSelectedKeyChanged: acknowledgeFailure(selectedKey)

    function jobFor(id) {
        for (var i = 0; i < jobs.length; ++i) if (jobs[i].id === id) return jobs[i]
        return null
    }

    function selectFirstFailed() {
        var fallback = ""
        for (var i = 0; i < queueModel.count; ++i) {
            var r = queueModel.get(i)
            if (r.status !== "failed") continue
            if (batch.active && batch.jobIds.indexOf(r.jobId) >= 0) { selectKey(r.key); return }
            if (fallback === "") fallback = r.key
        }
        if (fallback !== "") selectKey(fallback)
    }

    function selectKey(key) {
        if (key === selectedKey) return
        var r = rowsByKey[key]
        if (r && r.group === "earlier" && !earlierOpen) earlierOpen = true
        selectedKey = key
        log("debug", "select", "Selected " + key, null)
    }

    property var batch: ({ active: false, busy: false, preparing: false, total: 0, index: 0, done: 0, failed: 0, cancelled: 0, stopped: 0,
                          progress: 0, etaS: -1, stage: 0, stages: 0, factor: 0, runningKey: "", runningName: "", jobIds: [], runIds: [],
                          startedAt: "", last: null, wait: "", outputWait: "", outputWaitMessage: "", working: [] })
    readonly property bool outputWaiting: batch.active && batch.outputWait !== ""

    function computeBatch() {
        var active = []
        var ids = []
        var anyActive = false
        var started = ""
        for (var i = 0; i < jobs.length; ++i) {
            var live = F.isActiveJob(jobs[i])
            if (live) { ids.push(jobs[i].id); anyActive = true }
            if (live || (_runActive && runJobIds.indexOf(jobs[i].id) >= 0)) {
                active.push(jobs[i])
                if (jobs[i].created !== "" && (started === "" || jobs[i].created < started)) started = jobs[i].created
            }
        }
        if (!anyActive) active = []
        var b = { active: active.length > 0, busy: false, preparing: false, total: 0, index: 0, done: 0, failed: 0, cancelled: 0, stopped: 0,
                  progress: 0, etaS: 0, stage: 0, stages: 0, factor: 0, runningKey: "", runningName: "", jobIds: ids,
                  runIds: active.length > 0 ? runJobIds.slice() : [], startedAt: active.length > 0 ? started : "", last: null, wait: "",
                  outputWait: "", outputWaitMessage: "", working: [] }
        var queuedWait = ""
        if (active.length === 0) {
            var lastJobs = []
            for (var l0 = 0; l0 < jobs.length; ++l0)
                if (runJobIds.indexOf(jobs[l0].id) >= 0 && !dismissedJobs[jobs[l0].id]) lastJobs.push(jobs[l0])
            if (lastJobs.length === 0) {
                for (var l = jobs.length - 1; l >= 0; --l) {
                    if (dismissedJobs[jobs[l].id]) continue
                    lastJobs.push(jobs[l])
                    break
                }
            }
            if (lastJobs.length > 0) {
                var newest = lastJobs[lastJobs.length - 1]
                var s = { id: newest.id, ids: [], state: newest.state, total: 0, done: 0, failed: 0, cancelled: 0, stopped: 0,
                          outputDir: newest.outputDir, startedAt: "", finishedAt: "", durationS: -1 }
                for (var l1 = 0; l1 < lastJobs.length; ++l1) {
                    var lj = lastJobs[l1]
                    s.ids.push(lj.id)
                    s.total += lj.items.length
                    if (lj.created !== "" && (s.startedAt === "" || lj.created < s.startedAt)) s.startedAt = lj.created
                    for (var m = 0; m < lj.items.length; ++m) {
                        var ls = lj.items[m].state
                        if (ls === "done") s.done += 1
                        else if (ls === "failed") s.failed += 1
                        else if (ls === "cancelled") s.cancelled += 1
                        else if (ls === "stopped") s.stopped += 1
                        if (lj.items[m].finishedAt !== "" && Date.parse(lj.items[m].finishedAt) > (s.finishedAt === "" ? 0 : Date.parse(s.finishedAt)))
                            s.finishedAt = lj.items[m].finishedAt
                    }
                }
                if (s.finishedAt !== "" && isFinite(Date.parse(s.startedAt)))
                    s.durationS = Math.max(0, (Date.parse(s.finishedAt) - Date.parse(s.startedAt)) / 1000)
                b.last = s
            }
            b.etaS = -1
            return b
        }
        var sum = 0
        var position = 0
        var eta = 0
        for (var j = 0; j < active.length; ++j) {
            var jobEta = 0
            for (var k = 0; k < active[j].items.length; ++k) {
                var it = active[j].items[k]
                b.total += 1
                position += 1
                if (b.outputWait === "" && it.state === "finishing" && F.waitingWords(it.message) === "Waiting for the output folder") {
                    b.outputWait = active[j].outputDir || outputDir
                    b.outputWaitMessage = it.message
                }
                if (it.state === "done") { b.done += 1; sum += 1 }
                else if (it.state === "failed") { b.failed += 1; sum += 1 }
                else if (it.state === "cancelled") { b.cancelled += 1; sum += 1 }
                else if (it.state === "stopped") { b.stopped += 1; sum += 1 }
                else if (F.contains(F.BUSY_ITEM_STATES, it.state)) {
                    sum += it.progress
                    b.working.push(position)
                    if (!b.busy) {
                        b.busy = true
                        b.preparing = it.state === "preparing"
                        b.index = position
                        b.stage = it.stage
                        b.stages = it.stages
                        b.factor = it.effective && it.effective.scale ? Number(it.effective.scale)
                                   : (it.outW && it.width ? Math.round(it.outW / it.width) : 0)
                        b.runningKey = itemKey(active[j].id, it.itemId)
                        b.runningName = it.name
                        b.wait = F.waitingWords(it.message)
                    }
                    jobEta += it.etaS >= 0 ? it.etaS : Math.max(0, F.itemMinutes(it) * 60 * (1 - it.progress))
                } else {
                    sum += it.progress
                    jobEta += F.itemMinutes(it) * 60
                    if (queuedWait === "") queuedWait = F.waitingWords(it.message)
                }
            }
            eta += active[j].etaS >= 0 ? active[j].etaS : jobEta
        }
        if (!b.busy) {
            b.index = Math.min(b.total, b.done + b.failed + b.cancelled + b.stopped + 1)
            b.wait = queuedWait
        }
        b.progress = b.total > 0 ? sum / b.total : 0
        b.etaS = eta
        return b
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.connected && root.batch.active
        onTriggered: root.pollActiveJobs()
    }

    property bool unseenEnd: false
    onVisibleChanged: {
        if (visible) { unseenEnd = false; Qt.callLater(root.takeKeysBack) }
        else viewer.holdBefore = false
    }
    readonly property bool _batchActive: batch.active
    on_BatchActiveChanged: {
        if (_batchActive) { unseenEnd = false; return }
        if (_cancelAsked && confirm.opened) { _cancelAsked = false; confirm.close() }
        stopRequested = false
        if (!visible && batch.last !== null && batch.last !== undefined && batch.last.done > 0) unseenEnd = true
        Qt.callLater(root.toastBatchEnd)
    }
    property bool stopRequested: false
    function durationWords(sec) {
        if (!(sec > 0)) return ""
        var m = Math.round(sec / 60)
        if (m < 1) return "under\u00a0a\u00a0minute"
        if (m < 60) return m + "\u00a0min"
        return Math.floor(m / 60) + "\u00a0h" + (m % 60 ? "\u00a0" + (m % 60) + "\u00a0min" : "")
    }
    property string _toastedEnd: ""
    onInputsChanged: if (inputs.length === 0 && !batch.active) Qt.callLater(root.toastBatchEnd)
    function toastBatchEnd() {
        var last = batch.last
        if (batch.active || !last || inputs.length > 0) return
        var key = String(last.id || "") + ":" + (last.finishedAt || "")
        if (key === _toastedEnd) return
        if ((last.done + last.failed + (last.cancelled || 0) + (last.stopped || 0)) <= 0) return
        _toastedEnd = key
        var head = last.state === "cancelled" ? "Batch cancelled" : "Batch done"
        var d = durationWords(last.durationS !== undefined ? Number(last.durationS) : -1)
        var tail = []
        if (last.state === "cancelled" && last.done > 0) tail.push(last.done + " finished")
        if (last.failed > 0) tail.push(last.failed + " failed")
        if ((last.stopped || 0) > 0) tail.push(last.stopped + " stopped")
        var words = head + (d !== "" && last.state !== "cancelled" ? " in " + d : "") + (tail.length ? ", " + tail.join(", ") : "")
        showToast("done", words, "", "", last.done > 0 ? "Review results" : "", null)
    }
    property int _stuckToastId: -1
    onStuckMinutesChanged: {
        if (stuckMinutes > 0) {
            var words = "No new tile for " + stuckMinutes + " min."
            for (var i = 0; i < toastModel.count; ++i) {
                if (toastModel.get(i).toastId === _stuckToastId) { toastModel.setProperty(i, "title", words); return }
            }
            _stuckToastId = showToast("stuck", words, "The engine is still running.", "", "", null)
        } else if (_stuckToastId >= 0) {
            dismissToast(_stuckToastId)
            _stuckToastId = -1
        }
    }
    readonly property var runSlot: {
        if (batch.active && batch.total > 0) {
            var words = statusBar.batchCount
            var line = statusBar.batchLine !== "" ? statusBar.batchLine : words
            if (engineLineKind === "problem" && engineLine !== "")
                return { text: engineLine, tip: engineLine + " " + F.capital(line) + ".", danger: true,
                         fraction: Math.max(0, Math.min(1, Number(batch.progress) || 0)), started: true, title: words }
            return { text: words, tip: line,
                     fraction: Math.max(0, Math.min(1, Number(batch.progress) || 0)), started: true, title: words }
        }
        return null
    }
    FontMetrics { id: laneNameMetrics; font: Tokens.fontFor("small") }
    readonly property var gpuLanes: {
        var out = []
        if (!batch.active) return out
        var lanes = statusBar.lanes
        for (var i = 0; i < lanes.length; ++i) {
            var r = lanes[i].row
            if (!r) continue
            var share = Math.max(0, Math.min(1, Number(r.progress) || 0))
            out.push({ gpu: lanes[i].label, name: Tokens.elideName(r.name, 160, laneNameMetrics, true),
                       figure: Math.round(share * 100) + "%", fraction: share })
        }
        return out
    }

    readonly property var eligibleInputs: {
        var out = []
        for (var i = 0; i < inputs.length; ++i) if (inputRefusal(inputs[i], inputFactor(inputs[i])) === "") out.push(inputs[i])
        return out
    }
    readonly property bool plansPending: {
        for (var i = 0; i < inputs.length; ++i) if (!planForInput(inputs[i], inputFactor(inputs[i]))) return true
        return false
    }
    readonly property var startFactors: {
        var seen = []
        for (var i = 0; i < eligibleInputs.length; ++i) {
            var f = inputFactor(eligibleInputs[i])
            if (seen.indexOf(f) < 0) seen.push(f)
        }
        seen.sort(function(a, b) { return a - b })
        return seen
    }
    readonly property string startFactorWords: startFactors.length === 1 ? " at " + F.scaleLabel(startFactors[0]) : ""

    property var cancelledRows: []
    readonly property var againRows: {
        var out = []
        for (var i = 0; i < cancelledRows.length; ++i) {
            var p = planFor(cancelledRows[i].srcW, cancelledRows[i].srcH, scale)
            if (p && p.ok !== false) out.push(cancelledRows[i])
        }
        return out
    }
    readonly property var againRow: {
        var r = selectedRow
        if (batch.active || inputs.length > 0 || !r || r.kind !== "job" || r.status !== "done") return null
        var p = planFor(r.srcW, r.srcH, scale)
        return p && p.ok !== false ? r : null
    }
    readonly property bool againMode: againRow !== null
    readonly property bool againDone: againMode
    function sameAsUsed(e) {
        if (!e) return false
        if ((e.mode || "standard") !== (mode === "fast" && fastAvailable ? "fast" : "standard")) return false
        if (Number(e.scale) !== scale) return false
        if (Number(e.creativity) !== creativity || Number(e.resemblance) !== resemblance || Number(e.restoration) !== restoration) return false
        var q = e.quick_protect || ""
        if (q !== quickProtect) return false
        if (q === "" && (e.protect || []).slice().sort().join(",") !== protect.slice().sort().join(",")) return false
        var s = seed.trim() !== "" ? seed.trim() : String(controlsInfo.default_seed || "")
        if (String(e.seed) !== s) return false
        return (e.prompt_extra || "") === extraPrompt.trim()
    }
    readonly property bool againSame: {
        if (!againDone) return false
        var job = jobFor(againRow.jobId)
        return sameAsUsed(againRow.effective ? againRow.effective : (job ? job.effective : null))
    }
    property string againSeed: ""
    readonly property string againSeedKey: againSame ? againRow.key : ""
    onAgainSeedKeyChanged: { if (againSeedKey !== "") againSeed = randomSeed() }
    readonly property bool offerCancelledAgain: !batch.active && inputs.length === 0 && againRows.length > 0 && !againMode
    readonly property string cancelledAgainLabel: "Upscale " + F.plural(againRows.length, "image", "images") + " again"
    readonly property string footerMode: againMode ? "again" : offerCancelledAgain ? "cancelled" : "start"

    readonly property string startBlockReason: {
        if (engineState === "problem") return problemKind === "output" ? "Choose an output folder that can be reached." : "Solve the problem shown in the viewer first."
        if (reconnecting) return "Reconnecting to the engine…"
        if (!connected || engineState === "starting") return "The engine is starting…"
        if (inputs.length === 0 && footerMode === "start") return "Add images to start."
        if (inputs.length > 0 && eligibleInputs.length === 0) return inputs.length === 1 ? "This image is too large for " + scale + "×. Choose a smaller scale."
                                                                                         : "These images are too large for " + scale + "×. Choose a smaller scale."
        if (settingsLoaded && !outputDirOk) return "Choose an output folder you can write to."
        if (seedError !== "") return "Fix the variation number in Advanced."
        if (extraPrompt.length > 400) return "Shorten the extra description to 400 characters."
        return ""
    }
    readonly property string primaryReason: {
        if (engineState === "problem" || reconnecting || !connected || engineState === "starting") return ""
        if (inputs.length === 0 && footerMode === "start") return ""
        return startBlockReason
    }
    readonly property bool canStart: startBlockReason === "" && !submitting
    readonly property bool primaryShown: !(batch.active && inputs.length === 0)
                                         && !(footerMode === "start" && inputs.length === 0 && selectedRow !== null
                                              && selectedRow.kind === "job" && selectedRow.status === "failed")
    readonly property string primaryLabel: {
        if (footerMode === "again") return (againSame ? "Make another version at " : "Upscale again at ") + F.scaleLabel(scale)
        if (footerMode === "cancelled") return cancelledAgainLabel
        if (batch.active) return eligibleInputs.length > 0 ? "Queue " + F.plural(eligibleInputs.length, "image", "images") + startFactorWords : "Add to queue"
        if (eligibleInputs.length === 0) return "Upscale"
        return "Upscale " + F.plural(eligibleInputs.length, "image", "images") + startFactorWords
    }
    readonly property string footerTime: {
        var plans = []
        var modes = []
        if (footerMode === "again") plans.push(planFor(againRow.srcW, againRow.srcH, scale))
        else if (footerMode === "cancelled") for (var c = 0; c < againRows.length; ++c) plans.push(planFor(againRows[c].srcW, againRows[c].srcH, scale))
        else for (var j = 0; j < eligibleInputs.length; ++j) {
            plans.push(planForInput(eligibleInputs[j], inputFactor(eligibleInputs[j])))
            modes.push(inputMode(eligibleInputs[j]))
        }
        var single = plans.length === 1 && !batch.active
        var cardsInUse = health && health.engine && health.engine.workers ? Math.max(1, health.engine.workers.length) : 1
        var lanes = []
        for (var c0 = 0; c0 < cardsInUse; ++c0) lanes.push(0)
        var any = false
        for (var k = 0; k < plans.length; ++k) {
            var p = plans[k]
            if (!p || p.ok === false) continue
            var first = 0
            for (var l0 = 1; l0 < lanes.length; ++l0) if (lanes[l0] < lanes[first]) first = l0
            lanes[first] += planMinutes(p, modes.length > k ? modes[k] : "", single)
            any = true
        }
        if (!any) return ""
        var minutes = 0
        for (var l1 = 0; l1 < lanes.length; ++l1) minutes = Math.max(minutes, lanes[l1])
        return F.capital(F.minutesText(minutes)) + (batch.active ? ", after the current batch" : "")
    }
    readonly property string againFolder: {
        if (!againDone) return ""
        var job = jobFor(againRow.jobId)
        return (job && job.outputDir) || outputDir
    }

    function minutesFor(rows, m) {
        var t = 0
        for (var i = 0; i < rows.length; ++i) {
            var p = planFor(rows[i].srcW, rows[i].srcH, scale)
            if (p && p.ok !== false) t += planMinutes(p, m, rows.length === 1)
        }
        return t
    }
    function confirmAgain(rows, modeOverride) {
        if (!rows || rows.length === 0) return
        var inMode = modeOverride === "standard" || modeOverride === "fast" ? modeOverride : ""
        var minutes = minutesFor(rows, inMode)
        if (minutes < 30) { upscaleAgain(rows, inMode); return }
        var recipe = (custom ? "Custom" : preset) + ", " + F.scaleLabel(scale)
        var another = inMode === "" && againSame && rows.length === 1 && rows[0].key === againRow.key
        var again = inMode === "standard" ? "again in Standard" : "again"
        var title = another ? "Make another version of " + rows[0].name + "?"
                  : rows.length === 1 ? "Upscale " + rows[0].name + " " + again + "?" : "Upscale the " + rows.length + " stopped images " + again + "?"
        var body = another ? "This uses a new variation number and takes " + F.minutesText(minutes) + "."
                           : "This takes " + F.minutesText(minutes) + " with the current settings (" + recipe + ")."
        body += rows.length === 1 && rows[0].status === "done" ? " The earlier result stays in the output folder; the new one gets its own name." : ""
        confirm.ask(title, body, another ? "Make another version" : "Upscale " + again, "Not now", function() { upscaleAgain(rows, inMode) }, "go")
    }
    function upscaleCancelledAgain() { confirmAgain(againRows) }

    function requestRedo(row) {
        if (!row || !row.mediaId) return
        var job = jobFor(row.jobId)
        var e = job && job.effective ? job.effective : null
        var minutes = row.minutes || 0
        if (minutes < 30) { retryItem(row); return }
        var recipe = e ? String(e.preset || preset) + ", " + F.scaleLabel(e.scale || row.factor) : F.scaleLabel(row.factor)
        confirm.ask("Upscale " + row.name + " again?",
                    "This takes " + F.minutesText(minutes) + " with the settings it was started with (" + recipe + ").",
                    "Upscale again", "Not now", function() { retryItem(row) }, "go")
    }

    function startInputAt(mediaId, factor) {
        var inp = inputFor(mediaId)
        if (!inp || !(factor > 0) || !engineUsable || submitting) return
        var settings = currentSettings()
        settings.scale = factor
        if (inputMode(inp, factor) === "fast") settings.mode = "fast"
        else delete settings.mode
        var body = { client_request_id: F.randomHex(32), media_ids: [mediaId], settings: settings, output_dir: outputDir }
        submitting = true
        log("info", "job_one", "Upscaling " + inp.name + " on its own at " + F.scaleLabel(factor), { settings: settings })
        api.post("/api/jobs", body, function(err, data) {
            submitting = false
            if (err) { fastRefused(err); showError("Could not upscale " + inp.name + ".", err.message, err.log_ref, err.detail); return }
            var left = []
            for (var k = 0; k < inputs.length; ++k) if (inputs[k].mediaId !== mediaId) left.push(inputs[k])
            inputs = left
            collapseRemoved()
            var nj = F.normalizeJob(data)
            mergeJob(nj)
            if (nj.items.length > 0) selectKey(itemKey(nj.id, nj.items[0].itemId))
            announce("Started " + inp.name + " at " + F.scaleLabel(factor))
        }, { timeoutMs: 30000 })
    }

    function startUpscale() {
        if (!canStart) {
            log("info", "start_blocked", "Start not possible: " + startBlockReason, null)
            return
        }
        if (footerMode === "again") { confirmAgain([againRow]); return }
        if (footerMode === "cancelled") { upscaleCancelledAgain(); return }
        rejected = []
        var groups = []
        var byFactor = {}
        for (var i = 0; i < eligibleInputs.length; ++i) {
            var f = inputFactor(eligibleInputs[i])
            var im = inputMode(eligibleInputs[i])
            var gk = f + ":" + im
            if (byFactor[gk] === undefined) { byFactor[gk] = { factor: f, mode: im, media: [] }; groups.push(byFactor[gk]) }
            byFactor[gk].media.push(eligibleInputs[i].mediaId)
        }
        groups.sort(function(a, b) {
            if (a.factor !== b.factor) return a.factor === scale ? -1 : (b.factor === scale ? 1 : a.factor - b.factor)
            return a.mode === b.mode ? 0 : (a.mode === "fast" ? -1 : 1)
        })
        var bodies = []
        for (var g = 0; g < groups.length; ++g) {
            var settings = currentSettings()
            settings.scale = groups[g].factor
            if (groups[g].mode === "fast") settings.mode = "fast"
            else delete settings.mode
            bodies.push({ media_ids: groups[g].media, settings: settings, output_dir: outputDir })
        }
        var signature = JSON.stringify(bodies)
        var ids = lastSubmit && lastSubmit.signature === signature ? lastSubmit.ids : []
        for (var q = ids.length; q < bodies.length; ++q) ids.push(F.randomHex(32))
        lastSubmit = { id: ids[0], ids: ids, signature: signature }
        submitting = true
        var total = eligibleInputs.length
        var wasActive = batch.active
        var first = ""
        log("info", "job_submit", "Starting " + F.plural(total, "image", "images") + startFactorWords, { client_request_ids: ids, settings: bodies[0].settings }, true)
        function send(n) {
            if (n >= bodies.length) {
                submitting = false
                lastSubmit = null
                collapseRemoved()
                if (first !== "") selectKey(first)
                announce((wasActive ? "Queued " : "Started ") + F.plural(total, "image", "images"))
                return
            }
            var body = bodies[n]
            body.client_request_id = ids[n]
            api.post("/api/jobs", body, function(err, data) {
                if (err) {
                    submitting = false
                    fastRefused(err)
                    showError("The upscale could not start.", err.message, err.log_ref, err.detail)
                    return
                }
                var job = F.normalizeJob(data)
                var sent = {}
                for (var j = 0; j < body.media_ids.length; ++j) sent[body.media_ids[j]] = true
                var left = []
                var own = Object.assign({}, inputFactors)
                for (var k = 0; k < inputs.length; ++k) {
                    if (!sent[inputs[k].mediaId]) left.push(inputs[k])
                    else delete own[inputs[k].mediaId]
                }
                inputs = left
                inputFactors = own
                mergeJob(job)
                if (first === "" && job.items.length > 0) first = itemKey(job.id, job.items[0].itemId)
                log("info", "job_started", (wasActive ? "Queued " : "Started ") + F.plural(job.items.length, "image", "images")
                    + " at " + F.scaleLabel(body.settings.scale), { job: job.id })
                send(n + 1)
            }, { timeoutMs: 30000 })
        }
        send(0)
    }

    function stopImage(row) {
        if (!row || row.kind !== "job") return
        log("info", "item_stop", "Stopping " + row.name, { job: row.jobId, item: row.itemId }, true)
        api.stopImage(row.mediaId, row.jobId, row.itemId, function(err, data) {
            if (err) { showError("This image did not stop.", err.message, err.log_ref, err.detail); return }
            if (data && data.job && data.job.id) mergeJob(F.normalizeJob(data.job)); else refreshJob(row.jobId)
            log("info", "item_stopped", "Stopped " + row.name, { job: row.jobId, item: row.itemId })
            announce("Stopped " + row.name + ". The rest of the batch carries on.")
        })
    }
    function queueAgain(rows, asBefore, done) {
        if (!rows || rows.length === 0) return
        var list = []
        for (var i = 0; i < rows.length; ++i) if (rows[i] && rows[i].kind === "job") list.push(rows[i])
        if (list.length === 0) return
        if (!requeueSupported) {
            if (list.length === 1) requestRedo(list[0]); else confirmAgain(list)
            return
        }
        var answered = 0, taken = []
        for (var j = list.length - 1; j >= 0; --j) {
            (function(row) {
                api.requeue(row.jobId, row.itemId, asBefore === true ? { as_before: true, front: true } : { front: true }, function(err, data) {
                    answered += 1
                    if (err) showError("This image was not queued again.", err.message, err.log_ref, err.detail)
                    else {
                        taken.push(row.name)
                        forgetJobAnswer(row.jobId)
                        if (data && data.id && data.items) mergeJob(F.normalizeJob(data)); else refreshJob(row.jobId)
                        log("info", "item_requeued", "Queued " + row.name + " again" + (asBefore === true ? " as before" : ""), { job: row.jobId, item: row.itemId })
                    }
                    if (answered === list.length && taken.length > 0)
                        announce(taken.length === 1 ? "Queued " + taken[0] + " again" : "Queued " + taken.length + " images again")
                    if (typeof done === "function") done(!err, row)
                })
            })(list[j])
        }
    }
    function requeueImage(row, asBefore) { queueAgain([row], asBefore) }
    function useFactorFor(rows, factor) {
        if (!rows || !(factor > 0)) return
        var media = []
        for (var i = 0; i < rows.length; ++i) if (rows[i] && rows[i].kind === "input") media.push(rows[i].mediaId)
        if (media.length === 0) return
        if (batch.active) { startInputsAt(media, factor); return }
        var next = Object.assign({}, inputFactors)
        for (var j = 0; j < media.length; ++j) next[media[j]] = factor
        inputFactors = next
        rebuildQueue()
        ensurePlansForInputs()
        log("info", "factor_own", F.plural(media.length, "image", "images") + " set to " + F.scaleLabel(factor), null)
        announce(F.plural(media.length, "image", "images") + " set to " + F.scaleLabel(factor))
    }
    function startInputsAt(media, factor) {
        if (!engineUsable || submitting || media.length === 0) return
        var settings = currentSettings()
        settings.scale = factor
        var body = { client_request_id: F.randomHex(32), media_ids: media, settings: settings, output_dir: outputDir }
        submitting = true
        log("info", "job_factor", "Queueing " + F.plural(media.length, "image", "images") + " at " + F.scaleLabel(factor), { settings: settings }, true)
        api.post("/api/jobs", body, function(err, data) {
            submitting = false
            if (err) {
                fastRefused(err)
                showError("The images could not be queued.", err.message, err.log_ref, err.detail)
                return
            }
            var sent = {}
            for (var j = 0; j < media.length; ++j) sent[media[j]] = true
            var left = []
            for (var k = 0; k < inputs.length; ++k) if (!sent[inputs[k].mediaId]) left.push(inputs[k])
            inputs = left
            mergeJob(F.normalizeJob(data))
            log("info", "job_started", "Queued " + F.plural(media.length, "image", "images") + " at " + F.scaleLabel(factor), null)
            announce("Queued " + F.plural(media.length, "image", "images") + " at " + F.scaleLabel(factor))
        }, { timeoutMs: 30000 })
    }
    function queueLater(rows) { startUpscale() }

    function stopAfterCurrent() {
        if (!batch.active) return
        var waitingItems = []
        for (var i = 0; i < jobs.length; ++i) {
            if (!F.isActiveJob(jobs[i])) continue
            for (var j = 0; j < jobs[i].items.length; ++j) {
                var it = jobs[i].items[j]
                if (it.state === "queued" || it.state === "interrupted") waitingItems.push(it)
            }
        }
        if (waitingItems.length === 0) { announce("No images are waiting. The images in progress finish."); return }
        if (!stopImageSupported) {
            confirm.ask("Stop after current?",
                        "The " + F.plural(waitingItems.length, "waiting image is", "waiting images are").replace(/^\d+ /, "") + " cancelled. Finished images stay in the output folder.",
                        "Stop after current", "Keep working", function() {
                            for (var c = 0; c < waitingItems.length; ++c)
                                cancelItem({ name: waitingItems[c].name, jobId: waitingItems[c].jobId, itemId: waitingItems[c].itemId })
                        })
            return
        }
        log("info", "stop_after_current", "Stopping after the images in progress; " + F.plural(waitingItems.length, "waiting image", "waiting images") + " moved to Stopped", null)
        stopRequested = true
        var touched = {}
        for (var k = 0; k < waitingItems.length; ++k) {
            (function(it) {
                touched[it.jobId] = true
                api.stopImage(it.mediaId, it.jobId, it.itemId, function(err, data) {
                    if (err && err.status !== 409) { showError("The waiting images could not be stopped.", err.message, err.log_ref, err.detail); return }
                    if (data && data.job && data.job.id) mergeJob(F.normalizeJob(data.job)); else refreshJob(it.jobId)
                })
            })(waitingItems[k])
        }
        announce("Stopping after the images in progress")
    }

    property bool _applyingRecord: false
    function waitingTargets() {
        var out = []
        for (var i = 0; i < jobs.length; ++i) {
            if (!F.isActiveJob(jobs[i])) continue
            for (var j = 0; j < jobs[i].items.length; ++j) {
                var it = jobs[i].items[j]
                if (it.state === "queued" || it.state === "interrupted") out.push({ job_id: jobs[i].id, item_id: it.itemId })
            }
        }
        var sel = selectedRow
        if (sel && sel.kind === "job" && sel.status === "stopped") out.push({ job_id: sel.jobId, item_id: sel.itemId })
        return out
    }
    function waitingSnapshot() {
        var t = waitingTargets()
        var out = []
        for (var i = 0; i < t.length; ++i) {
            var job = jobFor(t[i].job_id)
            if (!job) continue
            for (var j = 0; j < job.items.length; ++j) {
                if (job.items[j].itemId !== t[i].item_id) continue
                var req = Object.assign({}, job.items[j].ownSettings || job.settings || {})
                if (job.items[j].effective && job.items[j].effective.scale) req.scale = Number(job.items[j].effective.scale)
                out.push({ job_id: t[i].job_id, item_id: t[i].item_id, settings: req })
            }
        }
        return out
    }
    function waitingFactorsMixed() {
        if (!batch.active || !perImageSettings) return false
        var t = waitingTargets()
        var seen = -1
        for (var i = 0; i < t.length; ++i) {
            var r = rowsByKey[itemKey(t[i].job_id, t[i].item_id)]
            if (!r) continue
            if (seen < 0) seen = r.factor
            else if (r.factor !== seen) return true
        }
        return false
    }
    function effectiveFromControls(base, keepScale, keepMode) {
        var e = Object.assign({}, base || {})
        e.preset = custom ? "Custom" : preset
        e.base_preset = preset
        e.creativity = creativity
        e.resemblance = resemblance
        e.restoration = restoration
        e.scale = keepScale === true && base && Number(base.scale) > 0 ? Number(base.scale) : scale
        e.quick_protect = quickProtect !== "" ? quickProtect : null
        e.protect = effectiveProtect.slice()
        e.output_format = outputFormat
        if (seed.trim() !== "") e.seed = seed.trim()
        e.prompt_extra = extraPrompt.trim()
        var tabMode = mode === "fast" && fastAvailable ? "fast" : "standard"
        e.mode = keepMode === true && base && (base.mode === "fast" || base.mode === "standard") ? String(base.mode) : tabMode
        if (e.mode === "fast" && !fastAvailable) e.mode = "standard"
        return e
    }
    function sameEffective(a, b) {
        if (!a || !b) return false
        return Number(a.scale) === Number(b.scale) && Number(a.creativity) === Number(b.creativity)
            && Number(a.resemblance) === Number(b.resemblance) && Number(a.restoration) === Number(b.restoration)
            && (a.quick_protect || "") === (b.quick_protect || "")
            && (a.protect || []).slice().sort().join(",") === (b.protect || []).slice().sort().join(",")
            && String(a.seed) === String(b.seed) && (a.prompt_extra || "") === (b.prompt_extra || "")
            && (a.mode || "standard") === (b.mode || "standard") && (a.output_format || "") === (b.output_format || "")
    }
    function waitingChanged() {
        if (restoringPrefs || _applyingRecord || !batch.active || !perImageSettings) { _waitingScaleTouched = false; _waitingModeTouched = false; return }
        var targets = waitingTargets()
        if (targets.length === 0) { _waitingScaleTouched = false; _waitingModeTouched = false; return }
        var hit = {}
        for (var t = 0; t < targets.length; ++t) hit[targets[t].job_id + ":" + targets[t].item_id] = true
        var next = []
        for (var i = 0; i < jobs.length; ++i) {
            var job = jobs[i]
            var changed = false
            var items = []
            for (var j = 0; j < job.items.length; ++j) {
                var it = job.items[j]
                if (!hit[job.id + ":" + it.itemId]) { items.push(it); continue }
                var e = effectiveFromControls(it.effective, !_waitingScaleTouched, !_waitingModeTouched)
                var copy = Object.assign({}, it, { effective: e })
                if (it.width > 0 && Number(e.scale) > 0 && (!it.effective || Number(it.effective.scale) !== Number(e.scale))) {
                    copy.outW = it.width * Number(e.scale)
                    copy.outH = it.height * Number(e.scale)
                }
                if (it.state === "stopped" && it.ranWith) copy.settingsChanged = !sameEffective(e, it.ranWith)
                items.push(copy)
                changed = true
            }
            if (changed) { next.push(Object.assign({}, job, { items: items })); forgetJobAnswer(job.id); _jobHeld[job.id] = Date.now() }
            else next.push(job)
        }
        jobs = next
        rebuildQueue()
        waitingTimer.restart()
    }
    Timer {
        id: waitingTimer
        interval: 250
        onTriggered: root.postWaitingNow()
    }
    property bool _waitingScaleTouched: false
    property bool _waitingModeTouched: false
    function postWaitingNow() {
        var targets = waitingTargets()
        var s = currentSettings()
        var allScale = _waitingScaleTouched, allMode = _waitingModeTouched
        _waitingScaleTouched = false
        _waitingModeTouched = false
        var tabMode = s.mode === "fast" ? "fast" : "standard"
        var groups = {}, order = []
        for (var i = 0; i < targets.length; ++i) {
            var job = jobFor(targets[i].job_id)
            var f = scale, m = tabMode
            if (job) for (var j = 0; j < job.items.length; ++j) {
                var it = job.items[j]
                if (it.itemId !== targets[i].item_id || !it.effective) continue
                if (!allScale && Number(it.effective.scale) > 0) f = Number(it.effective.scale)
                if (!allMode && (it.effective.mode === "fast" || it.effective.mode === "standard")) m = String(it.effective.mode)
            }
            if (m === "fast" && !fastAvailable) m = "standard"
            var gk = f + ":" + m
            if (groups[gk] === undefined) { groups[gk] = { factor: f, mode: m, items: [] }; order.push(gk) }
            groups[gk].items.push(targets[i])
        }
        for (var k = 0; k < order.length; ++k) {
            var gs = Object.assign({}, s, { scale: groups[order[k]].factor })
            if (groups[order[k]].mode === "fast") gs.mode = "fast"
            else delete gs.mode
            postWaiting(groups[order[k]].items, gs, "")
        }
    }
    function stillHalted(ref) {
        var job = ref ? jobFor(ref.job_id) : null
        if (!job) return false
        for (var i = 0; i < job.items.length; ++i)
            if (job.items[i].itemId === ref.item_id)
                return ["stopped", "cancelled", "failed"].indexOf(String(job.items[i].state)) >= 0
        return false
    }
    function postWaiting(items, settings, undone) {
        if (!items || items.length === 0 || !connected) return
        api.itemSettings(items, settings, function(err, data) {
            var seen = {}
            for (var i = 0; i < items.length; ++i) {
                if (seen[items[i].job_id]) continue
                seen[items[i].job_id] = true
                delete _jobHeld[items[i].job_id]
                forgetJobAnswer(items[i].job_id)
                refreshJob(items[i].job_id)
            }
            if (err) { showError("The waiting images could not be changed.", err.message, err.log_ref, err.detail); return }
            var refused = data && data.refused ? data.refused : []
            var kept = 0, why = ""
            for (var r = 0; r < refused.length; ++r) {
                if (refused[r].code === "started" && !stillHalted(refused[r])) continue
                kept += 1
                if (why === "" && refused[r].reason) why = String(refused[r].reason)
            }
            if (kept > 0) showToast("notice", F.plural(kept, "image keeps", "images keep") + " the earlier settings", why, "", "", null)
            log("info", "items_settings", (undone !== "" ? undone : "Changed the settings of " + F.plural(items.length - refused.length, "waiting image", "waiting images")),
                { refused: refused.length }, undone === "")
        })
    }
    function undoWaiting(list) {
        var bySettings = {}
        var order = []
        for (var i = 0; i < list.length; ++i) {
            var k = JSON.stringify(list[i].settings)
            if (bySettings[k] === undefined) { bySettings[k] = []; order.push(k) }
            bySettings[k].push({ job_id: list[i].job_id, item_id: list[i].item_id })
        }
        for (var j = 0; j < order.length; ++j) postWaiting(bySettings[order[j]], JSON.parse(order[j]), "Put the waiting images' own factors back")
    }

    function settingsSnapshot() {
        return { preset: preset, custom: custom, creativity: creativity, resemblance: resemblance, restoration: restoration,
                 scale: scale, protect: protect.slice(), quickProtect: quickProtect, outputFormat: outputFormat, seed: seed,
                 extraPrompt: extraPrompt, mode: mode }
    }
    function restoreSettingsSnapshot(p) {
        if (!p) return
        var scaleMoved = Number(p.scale) !== Number(scale)
        _applyingRecord = true
        preset = p.preset; custom = !!p.custom
        creativity = p.creativity; resemblance = p.resemblance; restoration = p.restoration
        scale = p.scale; protect = p.protect || []; quickProtect = p.quickProtect || ""
        outputFormat = p.outputFormat; seed = p.seed; extraPrompt = p.extraPrompt || ""
        mode = p.mode === "fast" && fastAvailable ? "fast" : "standard"
        _applyingRecord = false
        savePrefs()
        rebuildQueue()
        ensurePlansForInputs()
        if (scaleMoved) _waitingScaleTouched = true
        waitingChanged()
    }
    function useSettingsFrom(row) {
        if (!row || row.kind !== "job") return
        var job = jobFor(row.jobId)
        var e = row.effective || (job ? job.effective : null)
        if (!e) return
        var before = settingsSnapshot()
        var base = e.base_preset !== undefined && presetValues(e.base_preset) ? e.base_preset : e.preset
        var p = presetValues(base)
        restoreSettingsSnapshot({
            preset: p ? base : preset, custom: false,
            creativity: Number(e.creativity), resemblance: Number(e.resemblance), restoration: Number(e.restoration),
            scale: [2, 4, 6, 8].indexOf(Number(e.scale)) >= 0 ? Number(e.scale) : scale,
            protect: e.protect && e.protect.length !== undefined ? e.protect.slice() : protect, quickProtect: e.quick_protect || "",
            outputFormat: e.output_format || outputFormat, seed: e.seed !== undefined && e.seed !== null ? String(e.seed) : seed,
            extraPrompt: e.prompt_extra || "", mode: e.mode || "standard" })
        var pv = presetValues(preset)
        custom = !pv || pv.creativity !== creativity || pv.resemblance !== resemblance || pv.restoration !== restoration
        savePrefs()
        log("info", "settings_from", "Settings set to what " + row.name + " was made with", null)
        showToast("undo", "Settings set to what this image was made with", "", "", "Undo", { kind: "settings", prev: before })
    }
    function upscaleAgainStandard(row) {
        if (!row || row.kind !== "job") return
        confirmAgain([row], "standard")
    }

    property bool resultsOpen: false
    function setResultsOpen(on) {
        on = !!on
        if (on && (batch.active || batch.last === null || batch.last === undefined)) return
        if (resultsOpen === on) return
        resultsOpen = on
        log("info", "results", on ? "Opened the results" : "Closed the results", null, true)
    }
    readonly property bool resultsAvailable: !batch.active && batch.last !== null && batch.last !== undefined
    onResultsAvailableChanged: if (!resultsAvailable && resultsOpen) resultsOpen = false

    function retryItem(row, scaleOverride) {
        if (!row || !row.mediaId) return
        var job = jobFor(row.jobId)
        var own = null
        if (job) for (var oi = 0; oi < job.items.length; ++oi) if (job.items[oi].itemId === row.itemId && job.items[oi].ownSettings) own = job.items[oi].ownSettings
        var settings = Object.assign({}, own || (job && job.settings ? job.settings : currentSettings()))
        if (scaleOverride) settings.scale = scaleOverride
        var body = { client_request_id: F.randomHex(32), media_ids: [row.mediaId], settings: settings, output_dir: (job && job.outputDir) || outputDir }
        log("info", "item_retry", "Trying " + row.name + " again" + (scaleOverride ? " at " + F.scaleLabel(scaleOverride) : ""), { job: row.jobId, item: row.itemId })
        api.post("/api/jobs", body, function(err, data) {
            if (err) { showError("Could not try " + row.name + " again.", err.message, err.log_ref, err.detail); return }
            var nj = F.normalizeJob(data)
            mergeJob(nj)
            if (nj.items.length > 0) selectKey(itemKey(nj.id, nj.items[0].itemId))
        })
    }

    function upscaleAgain(rows, modeOverride) {
        var media = []
        var names = []
        for (var i = 0; i < rows.length; ++i) if (rows[i] && rows[i].mediaId) { media.push(rows[i].mediaId); names.push(rows[i].name) }
        if (media.length === 0) return
        var inMode = modeOverride === "standard" || modeOverride === "fast" ? modeOverride : ""
        if (inMode === "" && againSame && rows.length === 1 && rows[0].key === againRow.key && againSeed !== "") {
            seed = againSeed
            log("info", "seed", "New variation number " + seed + " for another version", null)
        }
        var settings = currentSettings()
        if (inMode === "standard") delete settings.mode
        else if (inMode === "fast" && fastAvailable) settings.mode = "fast"
        var body = { client_request_id: F.randomHex(32), media_ids: media, settings: settings, output_dir: outputDir }
        submitting = true
        log("info", "job_again", "Upscaling " + (media.length === 1 ? names[0] : F.plural(media.length, "image", "images")) + " again at " + F.scaleLabel(scale)
            + (inMode === "standard" ? " in Standard" : ""), { settings: settings })
        api.post("/api/jobs", body, function(err, data) {
            submitting = false
            if (err) { showError(media.length === 1 ? "Could not upscale " + names[0] + " again." : "The images could not be upscaled again.", err.message, err.log_ref, err.detail); return }
            var nj = F.normalizeJob(data)
            mergeJob(nj)
            if (nj.items.length > 0) selectKey(itemKey(nj.id, nj.items[0].itemId))
            announce("Started " + F.plural(nj.items.length, "image", "images") + " again")
        }, { timeoutMs: 30000 })
    }

    function requestCancelBatch() {
        if (!batch.active) return
        confirm.ask("Cancel this batch?",
                    "The image being upscaled now stops and images still waiting are cancelled. Finished images stay in the output folder.",
                    "Cancel batch", "Keep working", function() { if (batch.active) cancelBatch() })
        _cancelAsked = true
    }
    property bool _cancelAsked: false
    Connections {
        target: confirm
        function onClosed() { root._cancelAsked = false }
    }

    function cancelBatch() {
        var ids = batch.jobIds.slice()
        log("info", "batch_cancel", "Cancelling the batch", { jobs: ids })
        for (var i = 0; i < ids.length; ++i) {
            (function(id) {
                api.post("/api/jobs/" + encodeURIComponent(id) + "/cancel", {}, function(err, data) {
                    if (err) { showError("The batch could not be cancelled.", err.message, err.log_ref, err.detail); return }
                    if (data && data.id) mergeJob(F.normalizeJob(data)); else refreshJob(id)
                })
            })(ids[i])
        }
        announce("Cancelling the batch")
    }

    function requestCancelItem(row) {
        if (!row || row.kind !== "job") return
        var running = F.contains(F.BUSY_ITEM_STATES, row.status)
        if (stopImageSupported) { stopImage(row); return }
        confirm.ask(running ? "Stop upscaling " + row.name + "?" : "Cancel " + row.name + "?",
                    running ? "Work on this image stops now and its partial files are removed. The rest of the batch carries on."
                            : "This image will not be upscaled. The rest of the batch carries on.",
                    running ? "Stop image" : "Cancel image", "Keep it", function() { cancelItem(row) })
    }

    function cancelItem(row) {
        log("info", "item_cancel", "Cancelling " + row.name, { job: row.jobId, item: row.itemId })
        api.post("/api/jobs/" + encodeURIComponent(row.jobId) + "/items/" + encodeURIComponent(row.itemId) + "/cancel", {}, function(err, data) {
            if (err) { showError("Could not cancel " + row.name + ".", err.message, err.log_ref, err.detail); return }
            if (data && data.id && data.items) mergeJob(F.normalizeJob(data)); else refreshJob(row.jobId)
        })
    }

    property var _closeProceed: null
    readonly property bool closePromptOpen: confirm.opened && confirm.purpose === "close"
    function holdAppClose(proceed) {
        if (!(connected && batch.active)) return false
        if (_closeProceed !== null) return true
        _closeProceed = typeof proceed === "function" ? proceed : null
        if (_closeProceed === null) _closeProceed = function() {}
        log("info", "close_prompt_shown", "Asked what to do with the running batch before Artegra Enhancer closes",
            { done: batch.done, total: batch.total })
        Qt.callLater(openClosePrompt)
        return true
    }
    readonly property string closePromptBody: batch.done + " of " + batch.total
        + " done. Closing stops the engine. Unfinished images resume when you next open Artegra Enhancer."
    function openClosePrompt() {
        if (_closeProceed === null) return
        confirm.askChoice("Images are still upscaling", closePromptBody,
                          "Keep open", "", null,
                          "Stop and close", function() { closeChoice("stop") }, "danger",
                          function() { closeChoice("keep") }, "close")
    }
    function closeChoice(choice) {
        var proceed = _closeProceed
        _closeProceed = null
        log("info", "close_choice", choice === "stop" ? "Chose Stop and close" : choice === "finish" ? "Chose Finish in the background"
                                                                                                    : "Chose Keep open", { choice: choice })
        if (choice === "keep" || proceed === null) return
        if (choice === "finish") prefs.write("background", { at: Tokens.wallNow(), done: batch.done, ids: batch.runIds })
        var called = false
        function go() {
            if (called) return
            called = true
            proceed()
        }
        api.post("/api/lifecycle/close", { choice: choice }, function(err) {
            if (err) log("warning", "close_choice_failed", "The engine did not answer before closing. Unfinished work is kept for the next launch.",
                         { error: err.message, log_ref: err.log_ref || "", choice: choice })
            go()
        }, { timeoutMs: 5000 })
    }

    property var masks: ({})
    property bool maskBusy: false
    property bool maskVisible: false

    function maskFor(mediaId) { return masks[mediaId] || null }

    function previewMask() {
        var row = selectedRow
        if (!row || !row.mediaId) return
        maskBusy = true
        var body = { media_id: row.mediaId, protect: effectiveProtect.slice(), quick_protect: quickProtect !== "" ? quickProtect : null }
        var signature = protectSignature
        log("info", "mask_preview", "Previewing protected areas for " + row.name, { protect: body.protect, quick_protect: body.quick_protect })
        api.post("/api/mask-preview", body, function(err, data) {
            maskBusy = false
            if (err) { showError("The protected areas could not be previewed.", err.message, err.log_ref, err.detail); return }
            if (!data || !data.mask_url) { showError("The protected areas could not be previewed.", "The engine did not return a mask.", ""); return }
            var next = Object.assign({}, masks)
            next[row.mediaId] = { url: api.mediaUrl(data.mask_url), signature: signature }
            masks = next
            maskVisible = true
            announce("Protected areas shown on the image")
        }, { timeoutMs: 180000 })
    }

    property var serviceLog: []
    property string logsError: ""

    function refreshLogs() {
        if (!connected) return
        var path = "/api/logs?limit=200"
        api.get(path, function(err, data, status, same) {
            if (err) {
                if (logsError === "") log("warning", "logs_failed", "Could not refresh the engine log; retrying every 2 s: " + err.message, { log_ref: err.log_ref })
                logsError = "Could not refresh the engine log; retrying."
                return
            }
            if (logsError !== "") log("info", "logs_recovered", "The engine log is refreshing again", null)
            logsError = ""
            if (same) return
            serviceLog = data && data.lines ? data.lines : (data && data.length !== undefined ? data : [])
        }, { quiet: true, sameKey: "logs" })
    }
    Timer {
        interval: 2000
        repeat: true
        running: root.visible && root.connected && root.activityOpen
        onTriggered: root.refreshLogs()
    }

    ListModel { id: toastModel }
    property alias toasts: toastModel
    property int _toastSeq: 0

    function showToast(kind, title, body, logRef, actionLabel, payload, name, detail) {
        _toastSeq += 1
        toastModel.append({ toastId: _toastSeq, kind: kind, title: title, name: name || "", body: body || "", logRef: logRef || "",
                            detail: detail || "",
                            actionLabel: actionLabel || "", payload: payload ? JSON.stringify(payload) : "" })
        while (toastModel.count > 4) {
            var removed = false
            for (var i = 0; i < toastModel.count; ++i) {
                if (toastModel.get(i).kind !== "error") { toastModel.remove(i); removed = true; break }
            }
            if (!removed) toastModel.remove(0)
        }
        return _toastSeq
    }

    function showError(title, body, logRef, detail) {
        log("error", "user_error", title + " " + body, logRef || detail ? { log_ref: logRef || "", detail: detail || "" } : null)
        showToast("error", title, body, logRef, "", null, "", detail)
        announce(title)
    }

    function dismissToast(toastId) {
        if (toastId === _failToastId) { _failToastId = -1; _failPending = [] }
        for (var i = 0; i < toastModel.count; ++i) if (toastModel.get(i).toastId === toastId) { toastModel.remove(i); return }
    }

    property var _failPending: []
    property int _failToastId: -1
    function acknowledgeFailure(key) { }

    function toastAction(toastId) {
        for (var i = 0; i < toastModel.count; ++i) {
            var t = toastModel.get(i)
            if (t.toastId !== toastId) continue
            var payload = t.payload ? JSON.parse(t.payload) : {}
            var action = t.actionLabel
            if (toastId === _failToastId) { _failToastId = -1; _failPending = [] }
            toastModel.remove(i)
            if (action === "Open folder" && payload.path) openPath(payload.path, "output folder")
            else if (action === "Show" && payload.key) selectKey(payload.key)
            else if (action === "Undo" && payload.kind === "settings") { restoreSettingsSnapshot(payload.prev); log("info", "settings_undo", "Put the settings back", null) }
            else if (action === "Undo" && payload.kind === "waiting") undoWaiting(payload.items || [])
            else if (action === "Review results") setResultsOpen(true)
            return
        }
    }

    property string lastAnnouncement: ""
    function announce(message) {
        lastAnnouncement = message
        try {
            root.Accessible.announce(message)
        } catch (e) {
            log("debug", "announce_unavailable", String(e), null)
        }
    }

    TextEdit { id: clipboardHelper; visible: false }
    function copyText(text) {
        clipboardHelper.text = text
        clipboardHelper.selectAll()
        clipboardHelper.copy()
        clipboardHelper.text = ""
        showToast("info", "Copied", "", "", "", null)
    }

    FileDialog {
        id: fileDialog
        title: "Choose images to upscale"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Images (*.png *.jpg *.jpeg *.tif *.tiff *.webp *.bmp)", "All files (*.*)"]
        onAccepted: root.addUrls(selectedFiles)
    }
    FolderDialog {
        id: folderDialog
        title: "Choose a folder of images"
        onAccepted: root.addUrls([selectedFolder])
    }
    FolderDialog {
        id: outputDialog
        title: "Choose the output folder"
        onAccepted: root.chooseOutputDir(F.localPathFromUrl(selectedFolder.toString()))
    }
    function openFileDialog() { fileDialog.open() }
    function openFolderDialog() { folderDialog.open() }
    function openOutputDialog() {
        if (outputDir !== "") outputDialog.currentFolder = F.fileUrlFromPath(outputDir)
        outputDialog.open()
    }

    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property real hs: Tokens.snap(height, dpr)
    readonly property real regionLeft: legWidth
    readonly property real regionRight: width - legWidth
    property string hiddenSpan: Tokens.hiddenSpan
    readonly property bool windowSpan: panelsHidden && hiddenSpan === "window"
    readonly property real contentLeft: !panelsHidden ? legWidth + Tokens.openingInset : (windowSpan ? Tokens.openingInset : legWidth)
    readonly property real contentRight: !panelsHidden ? width - legWidth - Tokens.openingInset
                                                       : (windowSpan ? width - Tokens.openingInset : width - legWidth)
    readonly property rect pictureBlockRect: Qt.rect(contentLeft, Tokens.hBand, Math.max(0, contentRight - contentLeft),
                                                     Math.max(0, (windowSpan ? hs - 80 : hs) - Tokens.hBand))
    readonly property string navigatorPlace: windowSpan ? "floating" : "leg"
    readonly property bool batchRunning: batch.active === true
    readonly property string inViewKey: !resultsOpen && viewer.hasRow && (viewer.captionSaysState === true || viewer.readingA !== "")
                                        ? selectedKey : ""
    readonly property bool dropActive: dropZone.dragging === true

    CuViewer {
        id: viewer
        objectName: "creativeViewer"
        tab: root
        x: root.regionLeft
        width: Math.max(0, root.regionRight - root.regionLeft)
        y: 0
        height: root.height
        reserveBottom: 0
        dropping: dropZone.dropState !== undefined ? dropZone.dropState === "recess" : dropZone.dragging
    }
    property alias viewerItem: viewer
    readonly property string readingKey: !resultsOpen && viewer.hasRow && viewer.readingA !== "" ? selectedKey : ""
    property rect printRect: Qt.rect(0, 0, 0, 0)
    function syncPrintRect() {
        var pr = viewer.pictureRect
        var r = pr.width > 0 ? Qt.rect(viewer.x + pr.x, viewer.y + pr.y, pr.width, pr.height) : Qt.rect(0, 0, 0, 0)
        if (r.x !== printRect.x || r.y !== printRect.y || r.width !== printRect.width || r.height !== printRect.height) printRect = r
    }
    Timer { id: printRectTimer; interval: 0; onTriggered: root.syncPrintRect() }
    function tipKeepClearRect() {
        var pr = viewer.pictureRect
        return pr.width > 0 && pr.height > 0 ? Qt.rect(viewer.x + pr.x, viewer.y + pr.y, pr.width, pr.height) : Qt.rect(0, 0, 0, 0)
    }
    function tipCanvasRect() {
        return panelsHidden ? Qt.rect(0, 0, width, height) : Qt.rect(regionLeft, 0, Math.max(0, regionRight - regionLeft), height)
    }
    function tipKeepClearRects() {
        var out = []
        var own = viewer.tipKeepClearRects()
        for (var i = 0; i < own.length; ++i) out.push(Qt.rect(viewer.x + own[i].x, viewer.y + own[i].y, own[i].width, own[i].height))
        if (navigator.visible) out.push(Qt.rect(navigator.x, navigator.y, navigator.width, navigator.height))
        if (toastHost.count > 0) out.push(Qt.rect(toastHost.x, toastHost.y, toastHost.width, toastHost.height))
        return out
    }
    Connections {
        target: viewer
        function onPictureRectChanged() { printRectTimer.restart() }
        function onXChanged() { printRectTimer.restart() }
        function onYChanged() { printRectTimer.restart() }
    }
    Connections {
        target: viewer.liveFeed
        function onItemsChanged() { root.syncLiveThumbs() }
    }
    property alias settingsItem: settingsPanel

    CuStatusBar {
        id: statusBar
        tab: root
    }
    property alias dockItem: statusBar
    property alias status: statusBar
    readonly property string engineLine: statusBar.engineLine
    readonly property string engineLineKind: statusBar.engineKind
    readonly property string engineAction: statusBar.engineAction
    readonly property string engineRecessTitle: statusBar.engineRecessTitle
    readonly property string engineRecessText: statusBar.engineRecessText
    readonly property string batchLine: statusBar.batchLine
    readonly property string batchLineCount: statusBar.batchLineCount
    readonly property string batchLineTime: statusBar.batchLineTime
    readonly property string stoppingLine: statusBar.stoppingLine
    readonly property int waitingCount: {
        var n = inputs.length
        for (var k in rowsByKey) {
            var w = rowsByKey[k]
            if (w && w.kind === "job" && (w.status === "queued" || w.status === "interrupted")) n += 1
        }
        return n
    }
    readonly property string scope: {
        if (!batch.active) return "none"
        if (!perImageSettings) return ""
        var r = selectedRow
        var stopped = r !== null && r.kind === "job" && (r.status === "stopped" || r.status === "cancelled" || r.group === "stopped")
        if (stopped) return waitingCount > 0 ? "thisAndWaiting" : "this"
        return waitingCount > 0 ? "waiting" : "next"
    }
    readonly property var speedInfo: health !== null && health.engine !== undefined && health.engine !== null ? health.engine.speed : null
    readonly property bool fasterAvailable: (speedInfo !== null && speedInfo !== undefined && speedInfo.faster_available === true)
                                            || (health !== null && health.engine !== undefined && health.engine !== null
                                                && health.engine.faster !== undefined && health.engine.faster !== null
                                                && health.engine.faster.available === true)
    readonly property bool fasterOn: fasterAvailable && ((speedInfo !== null && speedInfo !== undefined && speedInfo.faster === true)
                                                         || (health !== null && health.engine !== undefined && health.engine !== null
                                                             && health.engine.faster !== undefined && health.engine.faster !== null
                                                             && health.engine.faster.on === true))

    CuResultsSheet {
        id: resultsSheet
        tab: root
        shown: root.resultsOpen
        onCloseRequested: root.setResultsOpen(false)
        x: root.regionLeft
        y: 0
        width: Math.max(0, root.regionRight - root.regionLeft)
        height: root.height
    }
    property alias resultsItem: resultsSheet

    CuQueueRail {
        id: rail
        tab: root
        x: 0
        y: 0
        height: root.height
        width: root.legWidth
        visible: !root.traysAway
        footReserve: root.stackEmpty ? 0 : Math.max(0, root.hs - root.stackTop + Tokens.sp8)
        transform: Translate { x: -(rail.width + Tokens.sp8) * root.traySlide }
    }
    property alias railItem: rail

    readonly property real stackLeft: Tokens.legInset
    readonly property real stackWidth: Math.max(0, legWidth - 2 * Tokens.legInset)
    readonly property bool navigatorInStack: navigator.visible
    readonly property real toastFoot: navigatorInStack ? navigator.y + navigator.boxTop - Tokens.sp8 : hs - Tokens.sp16
    readonly property bool stackEmpty: !navigatorInStack && toastHost.count === 0
    readonly property real stackTop: Tokens.snap(toastHost.count > 0 ? toastHost.y
                                                 : (navigatorInStack ? navigator.y + navigator.boxTop : hs), dpr)

    CuNavigator {
        id: navigator
        objectName: "legNavigator"
        viewer: viewer
        readonly property real boxTop: 0
        visible: viewer.navigatorShown && root.navigatorPlace === "leg"
        x: 0
        width: root.legWidth
        height: implicitHeight
        y: Tokens.snap(root.hs - height, root.dpr)
        z: 10
    }

    CuSettingsPanel {
        id: settingsPanel
        tab: root
        x: root.width - width
        y: 0
        height: root.height
        width: root.legWidth
        visible: !root.traysAway
        transform: Translate { x: (settingsPanel.width + Tokens.sp8) * root.traySlide }
    }
    readonly property real footTop: settingsPanel.footTop !== undefined ? Number(settingsPanel.footTop) : hs - Tokens.hFootSlot

    CuToasts {
        id: toastHost
        tab: root
        z: 10
        x: root.stackLeft
        width: root.stackWidth
        y: Tokens.snap(root.toastFoot - height, root.dpr)
    }
    property alias toastsItem: toastHost

    readonly property bool shortcutsOpen: shortcutsSheet.opened
    readonly property bool sheetOpen: activityOpen || shortcutsOpen
    Item {
        id: sheetHost
        objectName: "sheetHost"
        z: 20
        x: root.width - root.legWidth
        y: 0
        width: root.legWidth
        height: Math.max(0, Tokens.snap(root.footTop - Tokens.sp24, root.dpr))
        visible: !root.traysAway && root.sheetOpen
        transform: Translate { x: (sheetHost.width + Tokens.sp8) * root.traySlide }
        CuActivityLog {
            id: activityLog
            objectName: "activityDrawer"
            anchors.fill: parent
            tab: root
            visible: root.activityOpen
            live: root.activityOpen
            onCloseRequested: root.setActivityOpen(false)
        }
        CuShortcutsSheet {
            id: shortcutsSheet
            anchors.fill: parent
            tab: root
            onOpenedChanged: { if (opened && root.activityOpen) root.setActivityOpen(false) }
        }
    }
    property alias activityItem: activityLog

    CuDropZone {
        id: dropZone
        anchors.fill: parent
        tab: root
        labelArea: viewer
        z: 50
    }

    CuEngineChip {
        id: engineChip
        tab: root
        status: statusBar
    }
    property Item detailsAnchor: null
    onDetailsAnchorChanged: { if (detailsAnchor !== null) engineChip.openAt(detailsAnchor) }
    readonly property bool engineDetailsOpen: engineChip.popupOpen
    function openEngineDetails(anchor) {
        engineChip.openAt(anchor || null)
    }
    function closeEngineDetails() { engineChip.close() }
    onEngineDetailsOpenChanged: { if (!engineDetailsOpen) detailsAnchor = null }

    CuConfirmDialog { id: confirm; tab: root; onOpenedChanged: { if (opened) engineChip.close() } }
    property alias confirmDialog: confirm
    property alias shortcuts: shortcutsSheet

    Text {
        visible: false
        text: root.lastAnnouncement
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }

    readonly property var focusItem: Window.window ? Window.window.activeFocusItem : null
    readonly property bool textEditing: focusItem !== null && (focusItem instanceof TextInput || focusItem instanceof TextEdit)
    readonly property bool overlayOpen: confirm.opened
    readonly property bool keysActive: visible && !textEditing && !overlayOpen
    readonly property bool pictureKeys: keysActive && !resultsOpen

    Shortcut { sequence: "Ctrl+O"; enabled: root.visible && !root.overlayOpen && root.canAddImages; onActivated: root.openFileDialog() }
    Shortcut {
        sequence: "Ctrl+Z"
        enabled: root.keysActive && (root.removedLines.length > 0 || root.clearedLine !== null)
        onActivated: root.undoLatest()
    }
    Shortcut { sequences: ["Ctrl+Return", "Ctrl+Enter"]; enabled: root.visible && !root.overlayOpen; onActivated: root.startUpscale() }
    Shortcut { sequence: "B"; enabled: root.pictureKeys; onActivated: viewer.toggleBeforeAfter() }
    Shortcut { sequences: ["+", "="]; enabled: root.pictureKeys; onActivated: viewer.zoomBy(1.25) }
    Shortcut { sequence: "-"; enabled: root.pictureKeys; onActivated: viewer.zoomBy(0.8) }
    Shortcut { sequence: "0"; enabled: root.pictureKeys; onActivated: viewer.fit() }
    Shortcut { sequence: "1"; enabled: root.pictureKeys; onActivated: viewer.actualSize() }
    Shortcut { sequence: "M"; enabled: root.pictureKeys; onActivated: root.maskVisible = !root.maskVisible }
    Shortcut { sequence: "?"; enabled: root.keysActive; onActivated: shortcutsSheet.opened ? shortcutsSheet.close() : shortcutsSheet.openAt("shortcuts") }
    Shortcut { sequence: "R"; enabled: root.keysActive && root.resultsAvailable; onActivated: root.setResultsOpen(!root.resultsOpen) }
    Shortcut { sequence: "Ctrl+."; enabled: root.visible && !root.overlayOpen && root.batch.active; onActivated: root.stopAfterCurrent() }
    Shortcut {
        sequence: "Delete"
        enabled: root.keysActive && root.selectedRow !== null && root.selectedRow.kind === "input"
        onActivated: root.removeInput(root.selectedRow.mediaId)
    }
    Shortcut {
        sequence: "Escape"
        enabled: root.keysActive && Tokens.tipsOpen === 0 && !root.engineDetailsOpen
                 && (root.batch.active || root.activityOpen || root.shortcutsOpen || root.resultsOpen)
        onActivated: root.activityOpen ? root.setActivityOpen(false)
                     : (root.shortcutsOpen ? shortcutsSheet.close()
                        : (root.resultsOpen ? root.setResultsOpen(false) : root.requestCancelBatch()))
    }
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space && !event.isAutoRepeat && pictureKeys) { viewer.holdBefore = true; event.accepted = true }
    }
    Keys.onReleased: (event) => {
        if (event.key === Qt.Key_Space && !event.isAutoRepeat) { viewer.holdBefore = false; event.accepted = true }
    }
    function focusInside() {
        var w = Window.window
        if (!w) return false
        for (var p = w.activeFocusItem; p !== null && p !== undefined; p = p.parent) if (p === root) return true
        return false
    }
    onActiveFocusChanged: { if (!activeFocus) Qt.callLater(function() { if (!root.focusInside()) viewer.holdBefore = false }) }
    readonly property bool windowActive: Window.window !== null && Window.window.active === true
    onWindowActiveChanged: { if (!windowActive) viewer.holdBefore = false }
    onKeysActiveChanged: { if (!keysActive) viewer.holdBefore = false }
    function takeKeysBack() {
        if (!visible || !Window.window) return
        if (!focusInside()) root.forceActiveFocus()
    }

    function keyRegions() {
        var out = []
        if (!panelsHidden) out.push({ name: "images", item: rail })
        out.push(resultsOpen ? { name: "results", item: resultsSheet } : { name: "picture", item: viewer })
        if (!panelsHidden) out.push({ name: "settings", item: sheetOpen ? sheetHost : settingsPanel })
        return out
    }
    function firstControlIn(region) {
        if (!region || !region.visible || region.width <= 0 || region.height <= 0) return null
        var found = null
        function walk(it) {
            if (found !== null || !it || !it.visible || it.enabled === false) return
            if (it !== region && it.activeFocusOnTab === true) { found = it; return }
            var ch = it.children || []
            for (var i = 0; i < ch.length && found === null; ++i) walk(ch[i])
        }
        walk(region)
        return found
    }
    function keyRegionName() {
        var w = Window.window
        var regions = keyRegions()
        for (var p = w ? w.activeFocusItem : null; p !== null && p !== undefined; p = p.parent)
            for (var i = 0; i < regions.length; ++i) if (regions[i].item === p) return regions[i].name
        return ""
    }
    function focusRegion(step) {
        var regions = keyRegions()
        var n = regions.length
        var now = keyRegionName()
        var cur = -1
        for (var i = 0; i < n; ++i) if (regions[i].name === now) cur = i
        for (var k = 1; k <= n; ++k) {
            var at = cur < 0 ? (step > 0 ? k - 1 : n - k) : (((cur + step * k) % n) + n) % n
            var c = firstControlIn(regions[at].item)
            if (c !== null) {
                c.forceActiveFocus(Qt.TabFocusReason)
                return regions[at].name
            }
        }
        return ""
    }
    Shortcut { sequence: "F6"; enabled: root.keysActive; onActivated: root.focusRegion(1) }
    Shortcut { sequence: "Shift+F6"; enabled: root.keysActive; onActivated: root.focusRegion(-1) }

    Component.onCompleted: {
        restorePrefs()
        traySlide = panelsShown ? 0 : 1
        log("info", "tab_open", "Creative Upscaler opened; looking for the engine", null)
        rebuildQueue()
        Qt.callLater(root.takeKeysBack)
    }
    Component.onDestruction: api.end()
}

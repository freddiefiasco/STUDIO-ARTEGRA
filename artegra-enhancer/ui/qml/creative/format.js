.pragma library

var ACTIVE_JOB_STATES = ["queued", "preparing", "running", "finishing"]
var ACTIVE_ITEM_STATES = ["queued", "preparing", "running", "finishing", "interrupted"]
var BUSY_ITEM_STATES = ["preparing", "running", "finishing"]

function thousands(n) {
    if (n === undefined || n === null || !isFinite(n)) return ""
    var s = String(Math.round(n))
    return s.replace(/\B(?=(\d{3})+(?!\d))/g, ",")
}

function dims(w, h) {
    if (!(w > 0) || !(h > 0)) return ""
    return thousands(w) + " × " + thousands(h)
}

function megapixels(w, h) {
    if (!(w > 0) || !(h > 0)) return ""
    return Math.max(1, Math.round(w * h / 1e6)) + "\u00a0MP"
}

function resultDims(w, h) {
    var d = dims(w, h)
    return d === "" ? "" : "\u2192\u00a0" + d
}

function overLimitText(scale, w, h, mp) {
    return scaleLabel(scale) + " would make " + dims(w, h) + "\u00a0px, over the " + mp + "\u00a0MP limit."
}

function scaleLabel(s) {
    return s + "×"
}

function planLine(plan) {
    if (!plan || plan.ok === false || !plan.output_size) return ""
    var w = plan.output_size[0], h = plan.output_size[1]
    var passes = plan.stages ? plan.stages.length : 0
    var time = minutesText(plan.minutes)
    var head = "Becomes " + dims(w, h) + " px (" + megapixels(w, h) + ")"
    if (passes > 1) return head + " in " + passes + " passes" + (time !== "" ? ", " + time : "")
    return head + (time !== "" ? " in " + time : "")
}

function minutesText(min) {
    if (min === undefined || min === null || !isFinite(min) || min < 0) return ""
    if (min < 1) return "under a minute"
    var m = Math.round(min)
    if (m >= 360) {
        var hours = Math.round(m / 60)
        return "about " + hours + " hours"
    }
    if (m >= 180) m = Math.round(m / 30) * 30
    else if (m >= 60) m = Math.round(m / 15) * 15
    else if (m >= 20) m = Math.round(m / 5) * 5
    if (m < 60) return "about " + m + " min"
    var h = Math.floor(m / 60)
    var r = m % 60
    return "about " + h + " h" + (r ? " " + r + " min" : "")
}

function capital(text) {
    var t = String(text || "")
    return t === "" ? t : t.charAt(0).toUpperCase() + t.slice(1)
}

function secondsLeftText(sec) {
    if (sec === undefined || sec === null || !isFinite(sec) || sec < 0) return ""
    if (sec < 60) return "less than a minute left"
    return minutesText(sec / 60) + " left"
}

function elapsedText(sec) {
    if (!isFinite(sec) || sec < 0) return ""
    var s = Math.round(sec)
    if (s < 60) return s + " s"
    var m = Math.floor(s / 60)
    if (m < 10) return m + " min " + (s % 60) + " s"
    if (m < 60) return m + " min"
    return Math.floor(m / 60) + " h " + (m % 60) + " min"
}

function ordinal(n) {
    var v = Math.round(n)
    var t = v % 100
    var suffix = (t >= 11 && t <= 13) ? "th" : (v % 10 === 1 ? "st" : v % 10 === 2 ? "nd" : v % 10 === 3 ? "rd" : "th")
    return v + suffix
}

function passText(stage, stages) {
    return stages > 1 ? "pass " + (stage + 1) + " of " + stages : ""
}

function shortPath(path, fits) {
    var p = String(path || "")
    if (p === "" || fits(p)) return p
    var unc = p.indexOf("\\\\") === 0
    var parts = p.replace(/^\\\\/, "").split("\\").filter(function(x) { return x !== "" })
    if (parts.length < 2) return p
    var lead = unc ? "\\\\" : ""
    var headCount = unc && parts.length > 2 ? 2 : 1
    var last = parts[parts.length - 1]
    for (var keep = parts.length - 2; keep >= headCount; --keep) {
        var c = lead + parts.slice(0, keep).join("\\") + "\\\u2026\\" + last
        if (fits(c)) return c
    }
    return "\u2026\\" + last
}

function limitMp(reason) {
    var all = String(reason || "").match(/\d[\d,]*\s?MP\b/g)
    if (!all || all.length < 2 && !/limit|largest/.test(String(reason))) return ""
    return all[all.length - 1].replace(/\s?MP$/, "")
}

function problemKind(text) {
    var t = String(text || "")
    if (/^The output folder\b/.test(t)) return "output"
    if (/^The models folder\b/.test(t)) return "models"
    return "engine"
}

function problemTitle(text) {
    var t = String(text || "")
    var kind = problemKind(t)
    if (kind === "output") return /read-only|cannot be written/.test(t) ? "The output folder cannot be written to" : "The output folder cannot be reached"
    if (kind === "models") return "The upscaler's own files cannot be reached"
    if (/did not start|could not start/.test(t)) return "The engine did not start"
    if (/connection to the engine was lost/.test(t)) return "The engine stopped answering"
    return "The engine has a problem"
}

function problemBody(text) {
    var parts = splitPath(text)
    var t = parts.text
    var kind = problemKind(text)
    if (/is not reachable/.test(t) && kind === "output")
        t = driveAdvice(parts.path) + ", or choose another folder."
    else if (kind === "models") {
        var drive = /^([A-Za-z]:)/.exec(parts.path)
        if (/is not reachable/.test(t))
            t = "Connect the network drive" + (drive ? " (" + drive[1].toUpperCase() + ")" : "") + ", then choose Try again."
        return { text: t, path: "" }
    }
    else if (kind === "output" && /read-only|cannot be written/.test(t))
        t = "Make it writable, or choose another folder."
    else {
        var m = t.match(/^[^.]*\b(did not start|could not start|was lost)\b[^.]*\.\s+(\S[\s\S]*)$/)
        if (m) t = m[2]
    }
    return { text: t, path: parts.path }
}

function driveAdvice(path) {
    var p = String(path || "")
    if (/^\\\\/.test(p) || /^[Aa]:/.test(p)) return "Connect the network drive"
    var d = /^([A-Za-z]):/.exec(p)
    if (d && d[1].toUpperCase() !== "C") return "Connect the drive (" + d[1].toUpperCase() + ":)"
    return "Check that the folder still exists"
}

function outputWaitInfo(message, path) {
    var m = String(message || "")
    if (/not enough free space/.test(m))
        return { title: "The output folder is full", text: "Free some space in it. The finished image is kept and saved as soon as there is room." }
    if (/cannot be written|read-only/.test(m))
        return { title: "The output folder cannot be written to", text: "Make it writable. The finished image is kept and saved as soon as it can be." }
    return { title: "The output folder cannot be reached",
             text: driveAdvice(path) + ". The finished image is kept and saved as soon as the folder is back." }
}

function outputFieldError(text) {
    var t = String(text || "")
    if (problemKind(t) !== "output") return splitPath(t).text
    return /read-only|cannot be written/.test(t) ? "This folder cannot be written to." : "This folder cannot be reached."
}

function plural(n, one, many) {
    return n + " " + (n === 1 ? one : many)
}

function basename(path) {
    if (!path) return ""
    var s = String(path).replace(/\\/g, "/")
    var i = s.lastIndexOf("/")
    return i >= 0 ? s.substring(i + 1) : s
}

function localPathFromUrl(url) {
    var s = String(url)
    if (s.indexOf("file:") !== 0) return s
    s = s.replace(/^file:\/\/\/(?=[A-Za-z]:)/, "").replace(/^file:/, "")
    try {
        s = decodeURIComponent(s)
    } catch (e) {
    }
    if (/^\/\/[^\/]/.test(s)) return s.replace(/\//g, "\\")
    return s.replace(/^\/(?=[A-Za-z]:)/, "").replace(/\//g, "\\")
}

function fileUrlFromPath(path) {
    var n = String(path).replace(/\\/g, "/")
    return (n.indexOf("//") === 0 ? "file:" : "file:///") + encodeURI(n).replace(/#/g, "%23").replace(/\?/g, "%3F")
}

function randomHex(n) {
    var out = ""
    for (var i = 0; i < n; ++i) out += Math.floor(Math.random() * 16).toString(16)
    return out
}

function nowClock() {
    var d = new Date()
    function p(v) { return v < 10 ? "0" + v : String(v) }
    return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds())
}

function clockFromTs(ts) {
    if (ts === undefined || ts === null || ts === "") return ""
    var d = typeof ts === "number" ? new Date(ts > 1e12 ? ts : ts * 1000) : new Date(ts)
    if (isNaN(d.getTime())) return String(ts).substring(11, 19)
    function p(v) { return v < 10 ? "0" + v : String(v) }
    return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds())
}

function contains(list, value) {
    return list && list.indexOf(value) >= 0
}

function pair(v, fallbackW, fallbackH) {
    if (v && v.length === 2 && v[0] > 0 && v[1] > 0) return [Number(v[0]), Number(v[1])]
    if (fallbackW > 0 && fallbackH > 0) return [Number(fallbackW), Number(fallbackH)]
    return [0, 0]
}

function errorText(e) {
    if (!e) return ""
    if (typeof e === "string") return e
    return e.text || e.message || ""
}

function notesText(notes) {
    if (!notes || notes.length === undefined) return ""
    var out = []
    for (var i = 0; i < notes.length; ++i) {
        var n = String(notes[i] || "").trim()
        if (n !== "" && n.indexOf("identical to another image") < 0 && out.indexOf(n) < 0) out.push(n)
    }
    return out.join("\n")
}

function waitingWords(message) {
    var m = String(message || "")
    if (/^Waiting for the output folder|^Saved; waiting for the output folder/.test(m)) return "Waiting for the output folder"
    if (/^Waiting to save/.test(m)) return "Waiting to save"
    if (/^Waiting for memory/.test(m)) return "Waiting for memory"
    if (/^Waiting for the engine/.test(m)) return "Waiting for the engine"
    return ""
}

function secondsBetween(a, b) {
    if (!a || !b) return -1
    var t0 = Date.parse(a), t1 = Date.parse(b)
    return isNaN(t0) || isNaN(t1) || t1 < t0 ? -1 : (t1 - t0) / 1000
}

function normalizeInput(r) {
    var size = pair(r.size, r.width, r.height)
    var id = r.id !== undefined ? r.id : r.media_id
    return {
        mediaId: String(id),
        name: r.name || basename(r.path || r.source),
        path: r.path || r.source || "",
        width: size[0], height: size[1],
        alpha: !!r.alpha,
        duplicate: !!r.duplicate,
        notes: notesText(r.notes),
        thumbUrl: r.thumb_url || "",
        proxyUrl: r.proxy_url || "",
        scales: r.scales || null,
        bytes: Number(r.bytes) > 0 ? Number(r.bytes) : 0,
        format: r.format ? String(r.format) : ""
    }
}

function planFromScales(scales, s) {
    if (!scales) return null
    var v = scales[String(s)]
    if (!v) return null
    var st = []
    for (var i = 0; i < (v.passes || 0); ++i) st.push(i)
    return { ok: v.ok !== false, output_size: v.output_size || [0, 0], minutes: v.minutes || 0, stages: st,
             reason: v.reason || "", suggestions: v.suggestions || [], text: v.text || "",
             finish: v.finish || null }
}

function normalizeItem(it, job) {
    var plan = it.plan || null
    var size = pair(it.size, it.width, it.height)
    if (!(size[0] > 0) && plan) size = pair(plan.input_size)
    var out = plan ? pair(plan.output_size) : [0, 0]
    var stages = typeof it.stages === "number" ? it.stages : (plan && plan.stages ? plan.stages.length : 0)
    var err = it.error || null
    var mediaId = it.media_id !== undefined ? it.media_id : (it.media !== undefined ? it.media : "")
    return {
        jobId: String(job.id),
        itemId: String(it.id),
        mediaId: String(mediaId),
        name: it.name || basename(it.source || it.path),
        path: it.source || it.path || "",
        width: size[0], height: size[1],
        alpha: !!it.alpha,
        outW: out[0], outH: out[1],
        state: String(it.state || "queued"),
        progress: Math.max(0, Math.min(1, Number(it.progress) || 0)),
        stage: Math.max(0, Number(it.stage) || 0),
        stages: stages,
        stageProgress: Math.max(0, Math.min(1, Number(it.stage_progress) || 0)),
        etaS: (it.eta_s === undefined || it.eta_s === null) ? -1 : Number(it.eta_s),
        minutes: plan && plan.minutes ? Number(plan.minutes) : 0,
        message: it.message || "",
        output: it.output || "",
        errorText: errorText(err),
        logRef: err && err.log_ref ? String(err.log_ref) : "",
        thumbUrl: it.thumb_url || "",
        proxyUrl: it.proxy_url || "",
        resultProxyUrl: it.result_proxy_url || "",
        resultRegionUrl: it.result_region_url || "",
        resultReady: it.result_ready === undefined || it.result_ready === null ? true : !!it.result_ready,
        notes: notesText(it.notes),
        tookS: it.timings ? secondsBetween(it.timings.started, it.timings.finished) : -1,
        finishedAt: it.timings && it.timings.finished ? String(it.timings.finished) : "",
        gpu: (it.gpu === undefined || it.gpu === null) ? -1 : Number(it.gpu),
        cards: it.cards || [],
        run: it.run || null,
        ownSettings: it.settings || null,
        effective: it.effective || job.effective || null,
        ranWith: it.ran_with || null,
        settingsChanged: it.settings_changed === true,
        at: it.at || null,
        transparency: it.transparency ? String(it.transparency) : "",
        queueRank: (it.queue_rank === undefined || it.queue_rank === null) ? 0 : Number(it.queue_rank),
        outputBytes: it.output_info && Number(it.output_info.bytes) > 0 ? Number(it.output_info.bytes) : 0,
        outputAlpha: !!(it.output_info && (it.output_info.alpha === true || it.output_info.alpha === "kept")),
        bytes: Number(it.bytes) > 0 ? Number(it.bytes) : 0,
        resumedAt: resumedAtMs(it.history)
    }
}

function resumedAtMs(history) {
    var at = 0
    var h = history || []
    for (var i = 1; i < h.length; ++i) {
        if (!h[i] || !h[i - 1] || h[i - 1].state !== "interrupted" || h[i].state !== "queued") continue
        var t = Date.parse(h[i].ts)
        if (isFinite(t) && t > at) at = t
    }
    return at
}

function planMinutes(plan, mode, single) {
    if (!plan) return 0
    var fin = plan.finish || null
    var want = mode === "fast" ? "fast" : "standard"
    var sets = single === true && fin && fin.single ? [fin.single, fin] : (fin ? [fin] : [])
    for (var i = 0; i < sets.length; ++i) {
        var f = sets[i][want]
        if (!(f && isFinite(Number(f.minutes))) && want === "fast") f = sets[i].standard
        if (f && isFinite(Number(f.minutes))) return Number(f.minutes)
    }
    return Number(plan.minutes) || 0
}

function itemMinutes(it) {
    if (it && it.run && isFinite(Number(it.run.minutes)) && Number(it.run.minutes) > 0) return Number(it.run.minutes)
    return it ? Number(it.minutes) || 0 : 0
}

function cardsLabel(cards) {
    var out = []
    for (var i = 0; i < (cards || []).length; ++i) out.push("GPU " + (Number(cards[i]) + 1))
    return out.join(" + ")
}

function hhmm(ts) {
    if (ts === undefined || ts === null || ts === "") return ""
    var d = typeof ts === "number" ? new Date(ts) : new Date(Date.parse(ts))
    if (isNaN(d.getTime())) return ""
    function p(v) { return v < 10 ? "0" + v : String(v) }
    return p(d.getHours()) + ":" + p(d.getMinutes())
}

function normalizeJob(j) {
    var job = {
        id: String(j.id),
        state: String(j.state || "queued"),
        created: j.created || j.created_at || "",
        settings: j.settings || null,
        effective: j.effective || null,
        outputDir: j.output_dir || "",
        etaS: j.summary && typeof j.summary.eta_s === "number" ? j.summary.eta_s : -1,
        items: []
    }
    var items = j.items || []
    for (var i = 0; i < items.length; ++i) job.items.push(normalizeItem(items[i], job))
    return job
}

function jobsFromResponse(data) {
    if (!data) return []
    if (data.length !== undefined) return data
    return data.jobs || data.items || []
}

function isActiveJob(job) {
    return contains(ACTIVE_JOB_STATES, job.state)
}

function stateInfo(state, progress, scale, message) {
    if (state === "finishing" && waitingWords(message) !== "") return { word: "Waiting", icon: "pause", tone: "plain" }
    switch (state) {
    case "ready": return { word: "", icon: "", tone: "plain" }
    case "refused": return { word: "Too large", icon: "warning", tone: "warning" }
    case "queued": return { word: "Queued", icon: "queue", tone: "plain" }
    case "preparing": return { word: "Starting", icon: "loading", tone: "plain" }
    case "running": return { word: "Working", icon: "loading", tone: "plain" }
    case "finishing": return { word: "Saving", icon: "loading", tone: "plain" }
    case "done": return { word: "Done", icon: "check", tone: "success" }
    case "failed": return { word: "Failed", icon: "error", tone: "danger" }
    case "cancelled": return { word: "Cancelled", icon: "slash", tone: "muted" }
    case "interrupted": return { word: "Resuming", icon: "retry", tone: "plain" }
    default: return { word: state ? state.charAt(0).toUpperCase() + state.slice(1) : "", icon: "info", tone: "neutral" }
    }
}

function protectText(keys, categories) {
    if (!keys || keys.length === 0) return "Nothing"
    var names = []
    for (var i = 0; i < keys.length; ++i) {
        var label = keys[i]
        for (var j = 0; j < (categories || []).length; ++j) if (categories[j].key === keys[i]) label = categories[j].label
        names.push(names.length === 0 ? label : label.charAt(0).toLowerCase() + label.slice(1))
    }
    return names.join(", ")
}

function recipeRows(effective, categories) {
    if (!effective) return []
    var rows = []
    var preset = String(effective.preset || "")
    if (preset !== "") rows.push({ label: "Preset", value: preset })
    var names = [["creativity", "Creativity"], ["resemblance", "Resemblance"], ["restoration", "Restoration"]]
    for (var i = 0; i < names.length; ++i) {
        var v = effective[names[i][0]]
        if (v !== undefined && v !== null && v !== "") rows.push({ label: names[i][1], value: String(Math.round(Number(v))) })
    }
    rows.push({ label: "Protected", value: protectText(effective.protect || [], categories) })
    if (effective.seed !== undefined && effective.seed !== null && String(effective.seed) !== "") rows.push({ label: "Variation number", value: String(effective.seed) })
    if (effective.prompt_extra) rows.push({ label: "Extra description", value: String(effective.prompt_extra) })
    return rows
}

var PATH_BEFORE_VERB = /\b(folder|file) ((?:[A-Za-z]:\\|\\\\)[^()]*?) (is|are|was|cannot|could|does|has)\b/
var PATH_AFTER_NOUN = /\b(folder|file) ((?:[A-Za-z]:\\|\\\\)[^\s()]+?)([.,;:]?)(\s|$)/
var PATH_IN_BRACKETS = / \(((?:[A-Za-z]:\\|\\\\)[^()]+)\)/
function splitPath(text) {
    var s = String(text || "")
    var m = s.match(PATH_BEFORE_VERB)
    if (m) return { text: s.replace(m[0], m[1] + " " + m[3]), path: m[2] }
    m = s.match(PATH_AFTER_NOUN)
    if (m) return { text: s.replace(m[0], m[1] + m[3] + m[4]), path: m[2] }
    m = s.match(PATH_IN_BRACKETS)
    if (m) return { text: s.replace(m[0], ""), path: m[1] }
    return { text: s, path: "" }
}

function smallerScale(s, scales) {
    var best = 0
    var list = scales || [2, 4, 6, 8]
    for (var i = 0; i < list.length; ++i) if (list[i] < s && list[i] > best) best = list[i]
    return best
}

function size(w, h) {
    var d = dims(w, h)
    return d === "" ? "" : d + "\u00a0px"
}

function sizePair(w1, h1, w2, h2) {
    var a = dims(w1, h1), b = dims(w2, h2)
    if (a === "" || b === "") return a !== "" ? size(w1, h1) : size(w2, h2)
    return a + " \u2192 " + b + "\u00a0px"
}

function factor(s) {
    return scaleLabel(s)
}

function percent(v) {
    if (v === undefined || v === null || !isFinite(v)) return ""
    return Math.round(v) + "%"
}

function bytesText(n) {
    if (!(n > 0)) return ""
    if (n >= 1e9) return (n / 1e9 >= 10 ? String(Math.round(n / 1e9)) : (n / 1e9).toFixed(1)) + "\u00a0GB"
    if (n >= 1e6) return (n / 1e6 >= 10 ? String(Math.round(n / 1e6)) : (n / 1e6).toFixed(1)) + "\u00a0MB"
    return Math.max(1, Math.round(n / 1e3)) + "\u00a0KB"
}

function printText(paper, ppi) {
    if (!paper || !(ppi > 0)) return ""
    return paper + " at " + Math.round(ppi) + "\u00a0ppi"
}

function facts(parts) {
    var out = []
    for (var i = 0; i < (parts || []).length; ++i) {
        var p = parts[i]
        if (p !== undefined && p !== null && String(p) !== "") out.push(String(p))
    }
    return out.join(", ")
}

function doneOf(done, total) {
    return Math.round(done) + " of " + Math.round(total) + " done"
}

function imageCount(n) {
    return plural(n, "image", "images")
}

function stepOf(step, steps) {
    return "step " + Math.round(step) + " of " + Math.round(steps)
}

function aboutText(min) {
    return capital(minutesText(min))
}

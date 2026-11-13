import QtQuick
import "format.js" as F

Item {
    id: api
    visible: false

    property string hostEndpoint: ""
    property string hostToken: ""
    property int port: 0
    readonly property string base: port > 0 ? hostEndpoint : ""
    readonly property bool connected: port > 0
    property bool discovering: false
    property int defaultTimeoutMs: 8000
    property var logger: null
    property var _pending: []

    function _log(level, event, message, data, quiet) {
        if (logger) logger(level, event, message, data, quiet === true)
    }

    function baseNow() { return /^http:\/\/127\.0\.0\.1:189[56][0-9]$/.test(hostEndpoint) ? hostEndpoint : "" }
    function url(path) {
        if (!path || !baseNow() || !hostToken) return ""
        var value = String(path)
        if (/^[a-z]+:/i.test(value)) return isEngineAddress(value) ? value : ""
        return baseNow() + (value.charAt(0) === "/" ? value : "/" + value)
    }
    function isEngineAddress(u) {
        return !!baseNow() && String(u || "").indexOf(baseNow() + "/") === 0
    }
    function mediaUrl(path) {
        var value = url(path)
        if (!value) return ""
        return value + (value.indexOf("?") >= 0 ? "&" : "?") + "token=" + encodeURIComponent(hostToken)
    }
    onHostEndpointChanged: {
        abortAll()
        port = 0
        _lastText = ({})
    }

    readonly property string notAccepted: "The engine did not accept the request. Try again, or copy the details."
    function _errorFor(status, data, timedOut) {
        if (timedOut) return { code: "timeout", status: 0, log_ref: "", message: "The engine did not answer in time. It may be busy; the tab will keep trying." }
        if (status === 0) return { code: "unreachable", status: 0, log_ref: "", message: "The Creative Upscaler engine is not answering." }
        if (data && data.error) {
            var e = data.error
            return { code: String(e.code || ("http_" + status)), status: status, log_ref: e.log_ref ? String(e.log_ref) : "",
                     message: e.message ? String(e.message) : api.notAccepted, detail: "HTTP " + status }
        }
        return { code: "http_" + status, status: status, log_ref: "", message: api.notAccepted, detail: "HTTP " + status }
    }

    property var _lastText: ({})
    function send(method, fullUrl, body, callback, options) {
        if (api.ended)
            return { done: true, xhr: null, method: method, url: fullUrl, finish: function() {} }
        var opts = options || {}
        var timeoutMs = opts.timeoutMs || defaultTimeoutMs
        var xhr = new XMLHttpRequest()
        var rec = { xhr: xhr, deadline: Date.now() + timeoutMs, done: false, method: method, url: fullUrl, callback: callback, quiet: !!opts.quiet }
        function finish(err, data, status, same) {
            if (rec.done) return
            rec.done = true
            var i = api._pending.indexOf(rec)
            if (i >= 0) { var p = api._pending.slice(); p.splice(i, 1); api._pending = p }
            if (err && !rec.quiet) api._log("warning", "http_failed", method + " " + fullUrl.replace(api.base, "") + ": " + err.message, { code: err.code, status: err.status, log_ref: err.log_ref, detail: err.detail || "" }, true)
            if (callback) {
                try {
                    callback(err, data, status, same === true)
                } catch (e) {
                    api._log("exception", "callback_exception", "Internal error while handling " + method + " " + fullUrl + ": " + e, { stack: e.stack || "" })
                }
            }
        }
        rec.finish = finish
        if (!isEngineAddress(fullUrl)) {
            api._log("warning", "request_refused", "A request was not sent: its address is not the engine's (" + method + " " + String(fullUrl).slice(0, 80) + ")", null, true)
            finish({ code: "not_connected", status: 0, log_ref: "", message: "The engine is not connected yet." }, null, 0)
            return rec
        }
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE || rec.done) return
            var status = xhr.status
            var data = null
            var text = xhr.responseText
            var key = opts.sameKey
            if (key && status >= 200 && status < 300 && api._lastText[key] === text) { finish(null, null, status, true); return }
            if (text && text.length > 0) {
                try {
                    data = JSON.parse(text)
                } catch (e) {
                    if (status >= 200 && status < 300) {
                        finish({ code: "bad_json", status: status, log_ref: "", message: "The engine sent an answer the tab could not read." }, null, status)
                        return
                    }
                }
            }
            if (status >= 200 && status < 300) {
                if (key) api._lastText[key] = text
                finish(null, data, status)
            }
            else finish(api._errorFor(status, data, false), data, status)
        }
        api._pending = api._pending.concat([rec])
        try {
            xhr.open(method, fullUrl)
            xhr.setRequestHeader("Authorization", "Bearer " + hostToken)
            if (body !== undefined && body !== null) {
                xhr.setRequestHeader("Content-Type", "application/json")
                xhr.send(JSON.stringify(body))
            } else {
                xhr.send()
            }
        } catch (e) {
            finish({ code: "request_failed", status: 0, log_ref: "", message: api.notAccepted, detail: String(e) }, null, 0)
        }
        if (!rec.quiet && method !== "GET") api._log("info", "http_request", method + " " + fullUrl.replace(api.base, ""), body && body.client_request_id ? { client_request_id: body.client_request_id } : null, true)
        return rec
    }

    function request(method, path, body, callback, options) {
        if (!(port > 0)) {
            var err = { code: "not_connected", status: 0, log_ref: "", message: "The engine is not connected yet." }
            if (callback) callback(err, null, 0)
            return null
        }
        return send(method, url(path), body, callback, options)
    }

    function get(path, callback, options) { return request("GET", path, null, callback, options) }
    function post(path, body, callback, options) { return request("POST", path, body || {}, callback, options) }
    function del(path, callback, options) { return request("DELETE", path, null, callback, options) }

    function stopImage(mediaId, jobId, itemId, callback) {
        var q = "/api/cancel?image=" + encodeURIComponent(mediaId)
        if (jobId) q += "&job=" + encodeURIComponent(jobId)
        if (itemId) q += "&item=" + encodeURIComponent(itemId)
        return post(q, {}, callback, { timeoutMs: 15000 })
    }
    function requeue(jobId, itemId, body, callback) {
        return post("/api/jobs/" + encodeURIComponent(jobId) + "/items/" + encodeURIComponent(itemId) + "/requeue", body || {}, callback,
                    { timeoutMs: 15000 })
    }
    function itemSettings(items, settings, callback) {
        return post("/api/items/settings", { items: items, settings: settings }, callback, { timeoutMs: 15000 })
    }
    function live(callback) { return get("/api/live", callback, { quiet: true, sameKey: "live", timeoutMs: 4000 }) }
    function readSettings(callback) { return get("/api/settings", callback) }
    function writeSettings(values, callback) { return post("/api/settings", values, callback) }
    function forget(key) {
        if (_lastText[key] !== undefined) delete _lastText[key]
    }

    property bool ended: false
    function end() {
        ended = true
        abortAll()
    }
    Component.onDestruction: end()

    function abortAll() {
        var list = _pending.slice()
        for (var i = 0; i < list.length; ++i) {
            list[i].finish({ code: "aborted", status: 0, log_ref: "", message: "The connection to the engine was lost. Try again in a moment." }, null, 0)
            try { list[i].xhr.abort() } catch (e) { _log("debug", "abort_failed", String(e), null) }
        }
    }

    function isHealth(data) {
        return data !== null && typeof data === "object" && data.ok !== undefined && data.engine !== undefined
    }
    function isClosing(data) {
        return isHealth(data) && data.lifecycle !== undefined && data.lifecycle !== null && data.lifecycle.closing === true
    }

    function discover(callback) {
        if (discovering || !baseNow() || !hostToken) return
        discovering = true
        send("GET", url("/health"), null, function(err, data) {
            discovering = false
            if (!err && api.isHealth(data) && !api.isClosing(data)) {
                api.port = Number(hostEndpoint.split(":").pop())
                callback(api.port, data)
            } else callback(0, null)
        }, { quiet: true, timeoutMs: 2500 })
    }

    Timer {
        interval: 250
        repeat: true
        running: api._pending.length > 0
        onTriggered: {
            var now = Date.now()
            var list = api._pending.slice()
            for (var i = 0; i < list.length; ++i) {
                if (list[i].deadline < now) {
                    list[i].finish(api._errorFor(0, null, true), null, 0)
                    try { list[i].xhr.abort() } catch (e) { api._log("debug", "abort_failed", String(e), null) }
                }
            }
        }
    }
}

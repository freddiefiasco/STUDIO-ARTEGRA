import QtQuick

Item {
    id: feed
    property var tab: null
    property bool busy: false
    property bool wantedQuiet: false
    property var _items: ({})
    property var _detailed: null
    readonly property var _none: ({})
    readonly property bool wanted: busy || wantedQuiet
    readonly property bool available: featureOn && supported
    readonly property var items: wanted && available ? _items : _none
    readonly property var detailed: wanted && available ? _detailed : null
    property int seq: 0
    property bool supported: true
    property double lastOk: 0
    readonly property bool featureOn: {
        if (!tab || !tab.health || !tab.health.features) return true
        return tab.health.features.live !== false
    }
    readonly property bool connected: tab !== null && tab.connected === true
    readonly property bool running: connected && available && wanted
    property bool _inFlight: false

    visible: false
    width: 0
    height: 0

    function key(jobId, itemId) { return String(jobId) + ":" + String(itemId) }
    function itemFor(row) {
        if (!row || row.kind !== "job") return null
        return items[key(row.jobId, row.itemId)] || null
    }
    function canvasUrl(item) {
        if (!item || !item.canvas_url || !tab || !tab.service) return ""
        return tab.service.mediaUrl(item.canvas_url)
    }
    function thumbUrl(row) {
        var it = itemFor(row)
        if (!it || !it.thumb_url || !tab || !tab.service) return ""
        return tab.service.mediaUrl(it.thumb_url)
    }

    function poll() {
        if (!running || _inFlight || !tab.service) return
        _inFlight = true
        tab.service.get("/api/live", function(err, data, status, same) {
            feed._inFlight = false
            if (err) {
                if (status === 404 || status === 405) {
                    feed.supported = false
                    retry.restart()
                    if (typeof feed.tab.log === "function")
                        feed.tab.log("info", "live_unavailable", "The engine does not send live frames; the picture shows the source while it works.", null, true)
                }
                return
            }
            feed.lastOk = Date.now()
            if (same) return
            var out = {}
            var list = data && data.items ? data.items : []
            for (var i = 0; i < list.length; ++i) {
                var it = list[i]
                if (it && it.job_id !== undefined && it.item_id !== undefined) out[feed.key(it.job_id, it.item_id)] = it
            }
            feed._items = out
            feed._detailed = data && data.detailed ? data.detailed : null
            feed.seq = data && typeof data.seq === "number" ? data.seq : feed.seq + 1
        }, { quiet: true, sameKey: "live", timeoutMs: 4000 })
    }

    Timer {
        id: ticker
        interval: feed.busy ? 500 : 3000
        repeat: true
        triggeredOnStart: true
        running: feed.running
        onTriggered: feed.poll()
    }
    Timer {
        id: retry
        interval: 60000
        onTriggered: feed.supported = true
    }
}

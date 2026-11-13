import QtQuick

Item {
    id: live
    property string url: ""
    property real naturalW: 0
    property real naturalH: 0
    property string alphaUrl: ""
    readonly property bool useAlpha: alphaUrl !== ""
    property size decodeSize: Qt.size(0, 0)
    readonly property bool decodeAtDrawn: decodeSize.width > 0 && decodeSize.height > 0
                                          && (naturalW <= 0 || (2 * decodeSize.width <= naturalW + 0.5 && 2 * decodeSize.height <= naturalH + 0.5))
    readonly property var wantedSize: decodeAtDrawn ? Qt.size(2 * decodeSize.width, 2 * decodeSize.height) : undefined
    property bool current: true
    property var heldSize: undefined
    onWantedSizeChanged: { if (url !== "" && current) heldSize = wantedSize }
    onCurrentChanged: {
        if (current && url !== "") heldSize = wantedSize
        else abortLoads()
    }
    readonly property var frameSize: url !== "" && current ? wantedSize : heldSize
    function abortLoads() {
        if (a.status === Image.Loading && !(front === 0 && a.implicitWidth > 0)) a.source = ""
        if (b.status === Image.Loading && !(front === 1 && b.implicitWidth > 0)) b.source = ""
    }
    readonly property bool ready: url !== "" && (useAlpha ? canvas.drawnUrl !== "" : holds(front === 0 ? a : b))
    function holds(img) { return img.status === Image.Ready || (img.status === Image.Loading && img.implicitWidth > 0) }
    property int front: 0
    property string _wantedUrl: ""
    property string _ident: ""
    function ident(u) {
        var i = u.indexOf("?")
        var p = i >= 0 ? u.slice(0, i) : u
        var j = p.lastIndexOf("/")
        return j > 0 ? p.slice(0, j) : p
    }
    readonly property Item frontImage: front === 0 ? a : b
    Component.onCompleted: load()

    onUrlChanged: load()
    onAlphaUrlChanged: load()
    function load() {
        _wantedUrl = url
        if (url !== "" && current) heldSize = wantedSize
        if (url === "") {
            abortLoads()
            letGo.restart()
            return
        }
        letGo.stop()
        var id = ident(url)
        if (id !== _ident) {
            _ident = id
            a.source = ""
            b.source = ""
            canvas.forget()
        }
        if (useAlpha) { canvas.want(url); return }
        var back = front === 0 ? b : a
        var shown = front === 0 ? a : b
        if (shown.source.toString() === url && shown.status === Image.Ready) return
        back.source = url
        if (back.status === Image.Ready) swapTo(front === 0 ? 1 : 0)
    }

    function swapTo(i) {
        front = i
        Qt.callLater(function() {
            if (live.front === 0 && b.source.toString() !== live._wantedUrl) b.source = ""
            else if (live.front === 1 && a.source.toString() !== live._wantedUrl) a.source = ""
        })
    }

    Timer {
        id: letGo
        interval: 3000
        onTriggered: {
            if (live.url !== "") return
            live._ident = ""
            a.source = ""
            b.source = ""
            canvas.forget()
        }
    }

    Image {
        id: a
        objectName: "liveFrameA"
        anchors.fill: parent
        visible: !live.useAlpha && live.front === 0 && live.holds(a)
        asynchronous: true
        cache: false
        retainWhileLoading: true
        smooth: true
        mipmap: false
        fillMode: Image.Stretch
        sourceSize: live.frameSize
        onStatusChanged: { if (status === Image.Ready && live.front === 1 && source.toString() === live._wantedUrl) live.swapTo(0) }
    }
    Image {
        id: b
        objectName: "liveFrameB"
        anchors.fill: parent
        visible: !live.useAlpha && live.front === 1 && live.holds(b)
        asynchronous: true
        cache: false
        retainWhileLoading: true
        smooth: true
        mipmap: false
        fillMode: Image.Stretch
        sourceSize: live.frameSize
        onStatusChanged: { if (status === Image.Ready && live.front === 0 && source.toString() === live._wantedUrl) live.swapTo(1) }
    }

    Canvas {
        id: canvas
        objectName: "liveAlphaCanvas"
        visible: live.useAlpha && drawnUrl !== ""
        width: Math.max(1, Math.round(live.naturalW > 0 ? Math.min(live.width, live.naturalW) : live.width))
        height: Math.max(1, Math.round(live.naturalH > 0 ? Math.min(live.height, live.naturalH) : live.height))
        transform: Scale {
            xScale: live.width / Math.max(1, canvas.width)
            yScale: live.height / Math.max(1, canvas.height)
        }
        property string pendingUrl: ""
        property string drawnUrl: ""
        property string drawnAlpha: ""
        property int tries: 0
        function forget() {
            poller.stop()
            if (drawnUrl !== "") unloadImage(drawnUrl)
            if (pendingUrl !== "" && pendingUrl !== drawnUrl) unloadImage(pendingUrl)
            if (drawnAlpha !== "" && drawnAlpha !== live.alphaUrl) unloadImage(drawnAlpha)
            pendingUrl = ""
            drawnUrl = ""
            drawnAlpha = ""
        }
        function want(u) {
            if (pendingUrl !== "" && pendingUrl !== u && pendingUrl !== drawnUrl) unloadImage(pendingUrl)
            pendingUrl = u
            loadImage(u)
            if (live.alphaUrl !== "") loadImage(live.alphaUrl)
            tries = 0
            poller.restart()
        }
        function bothLoaded() {
            return pendingUrl !== "" && isImageLoaded(pendingUrl) && (live.alphaUrl === "" || isImageLoaded(live.alphaUrl))
        }
        onImageLoaded: { if (bothLoaded()) requestPaint() }
        onWidthChanged: { if (drawnUrl !== "") { pendingUrl = pendingUrl !== "" ? pendingUrl : drawnUrl; requestPaint() } }
        onHeightChanged: { if (drawnUrl !== "") { pendingUrl = pendingUrl !== "" ? pendingUrl : drawnUrl; requestPaint() } }
        onPaint: {
            var u = pendingUrl !== "" ? pendingUrl : drawnUrl
            if (u === "" || !isImageLoaded(u) || (live.alphaUrl !== "" && !isImageLoaded(live.alphaUrl))) return
            var ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            ctx.globalCompositeOperation = "source-over"
            ctx.drawImage(u, 0, 0, width, height)
            if (live.alphaUrl !== "") {
                ctx.globalCompositeOperation = "destination-in"
                ctx.drawImage(live.alphaUrl, 0, 0, width, height)
                ctx.globalCompositeOperation = "source-over"
            }
            var old = drawnUrl
            drawnUrl = u
            drawnAlpha = live.alphaUrl
            if (pendingUrl === u) pendingUrl = ""
            if (old !== "" && old !== u) unloadImage(old)
        }
    }
    Timer {
        id: poller
        interval: 40
        repeat: true
        onTriggered: {
            canvas.tries += 1
            if (canvas.bothLoaded()) { stop(); canvas.requestPaint() }
            else if (canvas.tries > 150) stop()
        }
    }
}

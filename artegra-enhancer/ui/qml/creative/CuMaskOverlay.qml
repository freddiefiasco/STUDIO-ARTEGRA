import QtQuick

Item {
    id: overlay

    property string maskUrl: ""
    property color tint: Tokens.protectTint
    property real strength: Tokens.protectFill.a
    property int edgeAlpha: Math.round(Tokens.protectEdge.a * 255)
    property string drawnUrl: ""

    property string loadedUrl: ""
    onMaskUrlChanged: {
        if (loadedUrl !== "" && loadedUrl !== maskUrl) { canvas.unloadImage(loadedUrl); loadedUrl = "" }
        drawnUrl = ""
        canvas.requestPaint()
    }

    Image {
        id: probe
        visible: false
        asynchronous: true
        cache: true
        source: overlay.maskUrl
        onStatusChanged: {
            if (status === Image.Ready) {
                canvas.loadImage(overlay.maskUrl)
                overlay.loadedUrl = overlay.maskUrl
                waitLoaded.tries = 0
                waitLoaded.start()
            }
        }
    }

    Timer {
        id: waitLoaded
        property int tries: 0
        interval: 60
        repeat: true
        onTriggered: {
            tries += 1
            if (canvas.isImageLoaded(overlay.maskUrl)) { stop(); canvas.requestPaint() }
            else if (tries > 100) stop()
        }
    }

    Canvas {
        id: canvas
        width: Math.max(1, probe.implicitWidth)
        height: Math.max(1, probe.implicitHeight)
        visible: overlay.maskUrl !== "" && overlay.drawnUrl === overlay.maskUrl
        transform: Scale {
            xScale: overlay.width / Math.max(1, canvas.width)
            yScale: overlay.height / Math.max(1, canvas.height)
        }
        onImageLoaded: requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var url = overlay.maskUrl
            if (url === "" || !isImageLoaded(url)) return
            var srcImage = ctx.createImageData(url)
            var src = srcImage.data
            var w = srcImage.width, h = srcImage.height
            if (w < 2 || h < 2) return
            var r = Math.round(overlay.tint.r * 255), g = Math.round(overlay.tint.g * 255), b = Math.round(overlay.tint.b * 255)
            var count = w * h
            var lum = new Uint8Array(count)
            for (var p = 0; p < count; ++p) lum[p] = src[p * 4]
            var out = srcImage
            var d = src
            var k = Math.max(1, Math.min(6, Math.round(w / Math.max(1, overlay.width))))
            for (var q = 0; q < count; ++q) {
                var v = lum[q]
                var cx = q % w
                var edge = v > 127 && ((cx >= k && lum[q - k] <= 127) || (cx < w - k && lum[q + k] <= 127)
                                       || (q >= k * w && lum[q - k * w] <= 127) || (q + k * w < count && lum[q + k * w] <= 127)
                                       || (cx > 0 && lum[q - 1] <= 127) || (cx < w - 1 && lum[q + 1] <= 127)
                                       || (q >= w && lum[q - w] <= 127) || (q + w < count && lum[q + w] <= 127))
                var i = q * 4
                d[i] = r
                d[i + 1] = g
                d[i + 2] = b
                d[i + 3] = edge ? overlay.edgeAlpha : Math.round(v * overlay.strength)
            }
            ctx.drawImage(out, 0, 0, width, height)
            overlay.drawnUrl = url
        }
    }
}

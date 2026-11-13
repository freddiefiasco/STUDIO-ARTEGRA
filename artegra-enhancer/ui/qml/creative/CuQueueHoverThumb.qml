import QtQuick
import QtQuick.Window
import "format.js" as F

CuPlate {
    id: plate
    objectName: "queueHoverThumb"
    property Item rail: null
    property Item row: null
    property real picW: 0
    property real picH: 0
    property bool above: false
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int pad: Tokens.sp8
    readonly property int lineH: Tokens.type.meta.line
    function need(h, r) { return h + 3 * pad + lineH * (folderOf(r === undefined ? row : r) !== "" ? 2 : 1) }
    function folderOf(r) {
        var p = r ? String(r.path || "") : ""
        var i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"))
        return i > 0 ? p.slice(0, i) : ""
    }
    readonly property string folder: folderOf(row)
    function shortFolder(p, fits) {
        if (p === "" || fits(p)) return p
        var unc = p.indexOf("\\\\") === 0
        var parts = p.replace(/^\\\\/, "").split(/[\\\/]/).filter(function(x) { return x !== "" })
        if (parts.length < 3) return F.shortPath(p, fits)
        var lead = (unc ? "\\\\" : "") + parts.slice(0, unc ? 3 : 2).join("\\")
        var best = ""
        for (var k = 1; k <= parts.length - (unc ? 4 : 3); ++k) {
            var c = lead + "\\…\\" + parts.slice(parts.length - k).join("\\")
            if (fits(c)) best = c
            else break
        }
        return best !== "" ? best : F.shortPath(p, fits)
    }
    readonly property real innerW: Math.max(0, width - 2 * pad)

    visible: opacity > 0
    opacity: row !== null ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: plate.row !== null ? Tokens.durFloatIn : Tokens.durFloatOut } }
    x: rail ? rail.inset : Tokens.legInset
    width: rail ? Math.max(0, rail.width - 2 * rail.inset) : 0
    Accessible.ignored: true

    function openFor(r) {
        if (!rail || !r || !r.isImage || r.aspect <= 0) { close(); return }
        var a = r.aspect
        var h0 = Math.round(innerW / a)
        var top = r.mapToItem(rail, 0, r.bodyTop).y
        var bottom = top + r.rowHeight
        var below = rail.plateBottom - (bottom + Tokens.sp4)
        var over = (top - Tokens.sp4) - rail.plateTop
        var whole = need(h0, r)
        var down = below >= whole || (over < whole && below >= over)
        var room = down ? below : over
        var ph = Math.min(h0, room - need(0, r))
        if (ph < Tokens.sp48) { close(); return }
        picH = Math.floor(ph)
        picW = Math.min(innerW, Math.round(picH * a))
        height = need(picH, r)
        y = Tokens.snap(down ? bottom + Tokens.sp4 : top - Tokens.sp4 - height, dpr)
        above = !down
        row = r
    }
    function close() { row = null }

    readonly property real edgeIn: edgeWidth
    readonly property string source: row ? (row.proxySource !== "" ? row.proxySource : row.thumbSource) : ""
    readonly property real picX: Tokens.snap(pad - edgeIn + (innerW - picW) / 2, dpr)
    readonly property real picY: pad - edgeIn
    Image {
        objectName: "queueHoverChecker"
        visible: plate.row !== null && plate.row.alpha
        x: plate.picX
        y: plate.picY
        width: plate.picW
        height: plate.picH
        source: plate.row !== null && plate.row.alpha ? Tokens.checkerTile : ""
        fillMode: Image.Tile
        smooth: false
    }
    Rectangle {
        visible: picture.status !== Image.Ready && plate.row !== null
        x: plate.picX
        y: plate.picY
        width: plate.picW
        height: plate.picH
        color: Tokens.wellFloat
    }
    Image {
        objectName: "queueHoverStandIn"
        visible: picture.status !== Image.Ready && plate.row !== null
        x: plate.picX
        y: plate.picY
        width: plate.picW
        height: plate.picH
        source: plate.row !== null ? plate.row.thumbSource : ""
        asynchronous: true
        cache: true
        smooth: true
        fillMode: Image.PreserveAspectCrop
        sourceSize: Qt.size(Math.ceil(plate.picW * plate.dpr), Math.ceil(plate.picH * plate.dpr))
    }
    Image {
        id: picture
        objectName: "queueHoverPicture"
        x: plate.picX
        y: plate.picY
        width: plate.picW
        height: plate.picH
        source: plate.source
        asynchronous: true
        cache: true
        smooth: true
        mipmap: false
        fillMode: Image.PreserveAspectCrop
        sourceSize: Qt.size(Math.ceil(plate.picW * plate.dpr), Math.ceil(plate.picH * plate.dpr))
    }

    readonly property string format: {
        var f = row ? String(row.role("format", "")) : ""
        if (f !== "") return f
        var n = row ? String(row.name || "").toLowerCase() : ""
        var ext = n.slice(n.lastIndexOf(".") + 1)
        return ext === "jpg" || ext === "jpeg" ? "JPEG" : ext === "png" ? "PNG" : ext === "tif" || ext === "tiff" ? "TIFF"
             : ext === "webp" ? "WebP" : ext === "bmp" ? "BMP" : ext.toUpperCase()
    }
    CuText {
        objectName: "queueHoverSizes"
        x: plate.pad - plate.edgeIn
        y: plate.picY + plate.picH + plate.pad
        width: plate.innerW
        role: "meta"
        color: Tokens.text2
        tabular: true
        elide: Text.ElideRight
        text: plate.row ? F.facts([F.size(plate.row.srcW, plate.row.srcH), plate.format,
                                   F.bytesText(Number(plate.row.role("bytes", 0)))]) : ""
    }
    FontMetrics { id: folderMetrics; font: folderText.font }
    CuText {
        id: folderText
        objectName: "queueHoverPath"
        visible: plate.folder !== ""
        x: plate.pad - plate.edgeIn
        y: plate.picY + plate.picH + plate.pad + plate.lineH
        width: plate.innerW
        role: "meta"
        color: Tokens.text3
        elide: Text.ElideMiddle
        text: plate.shortFolder(plate.folder, function(t) { return folderMetrics.advanceWidth(t) <= plate.innerW })
    }
}

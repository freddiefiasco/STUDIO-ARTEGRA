import QtQuick
import QtQuick.Window

FocusScope {
    id: sheet
    objectName: "shortcutsSheet"
    property var tab: null
    property var returnFocus: null
    property bool opened: false
    property string view: "shortcuts"
    readonly property string title: "Shortcuts"
    readonly property string startAt: "shortcuts"
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    readonly property int inset: Tokens.legInset
    readonly property int pitch: Tokens.hControl
    signal closed()
    visible: opened || fade.running
    opacity: opened ? 1 : 0
    Behavior on opacity { NumberAnimation { id: fade; duration: Tokens.durSheet; easing.type: Easing.BezierSpline; easing.bezierCurve: Tokens.easeEnter } }

    function open() { openAt("shortcuts") }
    function openAt(section) {
        view = "shortcuts"
        if (opened) return
        var w = tab ? tab.Window.window : null
        returnFocus = w ? w.activeFocusItem : null
        opened = true
        frame.area.contentY = frame.area.minY
        Qt.callLater(function() { frame.closeButton.forceActiveFocus() })
    }
    function close() {
        if (!opened) return
        opened = false
        var back = returnFocus
        returnFocus = null
        if (back && back.visible) back.forceActiveFocus()
        else if (tab) tab.forceActiveFocus()
        closed()
    }

    readonly property var keys: [
        { keys: "Ctrl O", d: "Add images" },
        { keys: "Ctrl Enter", d: "Start upscaling" },
        { keys: "Delete", d: "Remove the selected image", tip: "Remove the selected waiting image. Undo puts it back." },
        { keys: "Ctrl Z", d: "Put back a removed image", needs: "removedLines" },
        { keys: "B", d: "Before or After", tip: "Switch between Before and After" },
        { keys: "S", d: "Split the picture", needs: "splitKey" },
        { keys: "Y", d: "Side by side", tip: "Put Before and After side by side", needs: "splitKey" },
        { keys: "L", d: "Loupe", tip: "Show or hide the loupe, which magnifies the picture under the pointer", needs: "splitKey" },
        { keys: "Hold Space", d: "Show the original", tip: "Show the original while held" },
        { keys: "+ or −", d: "Zoom in or out" },
        { keys: "0 or 1", d: "Fit or 100%", tip: "Fit to window, or 100%" },
        { keys: "M", d: "Protected areas", tip: "Show or hide the protected areas" },
        { keys: "← or →", d: "Move the divider", tip: "Move the divider when it has focus" },
        { keys: sheet.tab && sheet.tab.panelsKey ? sheet.tab.panelsKey : "Tab", d: "Hide or show the panels", needs: "focusMode" },
        { keys: "F6", d: "Next part of the window", needs: "focusRegion",
          tip: "Go to the next part of the window: the image list, the picture, the settings" },
        { keys: "Ctrl .", d: "Stop after current", needs: "stopAfterCurrent",
          tip: "Finishes the images in progress, then stops. Waiting images move to Stopped." },
        { keys: "Ctrl Shift .", d: "Stop this image", needs: "stopImage" },
        { keys: "R", d: "Review results", tip: "Review the results of the last batch", needs: "resultsOpen" },
        { keys: "Esc", d: "Close, or cancel the batch", tip: "Close a tooltip or a dialog, or ask to cancel the running batch" }
    ]
    readonly property var shownKeys: keys.filter(function(k) { return !k.needs || (sheet.tab && sheet.tab[k.needs] !== undefined) })

    CuSheet {
        id: frame
        objectName: "shortcutsFrame"
        anchors.fill: parent
        title: sheet.title
        ground: "ink"
        onCloseRequested: sheet.close()
        Component.onCompleted: { closeButton.objectName = "shortcutsClose"; area.objectName = "shortcutsScroll"; area.bar.objectName = "shortcutsScrollBar" }

        Column {
            id: rows
            objectName: "shortcutsRows"
            x: sheet.inset
            y: 0
            width: Math.max(0, frame.width - 2 * sheet.inset)
            Repeater {
                model: sheet.shownKeys
                Item {
                    id: keyRow
                    objectName: "shortcutRow"
                    required property var modelData
                    width: rows.width
                    height: sheet.pitch
                    Accessible.role: Accessible.StaticText
                    Accessible.name: modelData.keys + ": " + (modelData.tip || modelData.d)
                    CuText {
                        id: keysText
                        objectName: "shortcutKeys"
                        x: Tokens.snap(keyRow.width - width, sheet.dpr)
                        y: centredIn(sheet.pitch)
                        width: Math.ceil(implicitWidth)
                        text: keyRow.modelData.keys
                        role: "body"
                        tabular: true
                        color: Tokens.text1
                    }
                    CuText {
                        id: words
                        objectName: "shortcutWords"
                        x: 0
                        y: centredIn(sheet.pitch)
                        width: Math.min(Math.ceil(implicitWidth), Math.max(0, keysText.x - Tokens.sp16))
                        text: keyRow.modelData.d
                        role: "body"
                        elide: Text.ElideRight
                        color: Tokens.text2
                    }
                    HoverHandler { id: rowHover }
                    CuHoverTip {
                        shown: rowHover.hovered && (!!keyRow.modelData.tip || words.truncated)
                        text: keyRow.modelData.tip || keyRow.modelData.d
                        placement: "below"
                    }
                }
            }
            Item { width: 1; height: Tokens.sp24 }
        }
    }
}

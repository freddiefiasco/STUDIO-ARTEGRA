import QtQuick
import QtQuick.Window

Item {
    id: slot
    property string status: ""
    property string statusValue: ""
    property bool statusDanger: false
    property string statusTip: ""
    readonly property alias statusItem: statusLine
    readonly property alias statusTextItem: countText
    property string detailsText: ""
    property string detailsTip: ""
    property string ground: "ink"
    property bool ruleShown: false
    property string forcedState: ""
    default property alias row: commitRow.data
    readonly property alias commitItem: commitRow
    readonly property alias detailsItem: detailsButton
    readonly property real dpr: Screen.devicePixelRatio > 0 ? Screen.devicePixelRatio : 1
    signal details()

    implicitWidth: Tokens.legContentMin
    implicitHeight: Tokens.hFootSlot
    height: Tokens.hFootSlot
    objectName: "footSlot"

    CuSettingsRule {
        visible: slot.ruleShown
        x: -Tokens.legInset
        y: -Tokens.sp24
        width: slot.width + 2 * Tokens.legInset
        ground: slot.ground
    }
    property var statusForms: []
    readonly property var forms: {
        var out = [{ status: slot.status, value: slot.statusDanger ? "" : slot.statusValue }]
        var more = slot.statusDanger ? [] : (slot.statusForms || [])
        for (var i = 0; i < more.length && out.length < 3; ++i)
            if (more[i] && String(more[i].status || "") !== "") out.push({ status: String(more[i].status), value: String(more[i].value || "") })
        return out
    }
    readonly property real lineRoom: Math.max(0, slot.width - (detailsButton.visible ? detailsButton.width + Tokens.sp16 : 0))
    function formNeed(c, v, f) { return Math.ceil(c.implicitWidth) + (f.value !== "" ? Math.ceil(v.implicitWidth) : 0) }
    readonly property int formIndex: {
        var needs = [formNeed(m0c, m0v, forms[0]), forms.length > 1 ? formNeed(m1c, m1v, forms[1]) : -1,
                     forms.length > 2 ? formNeed(m2c, m2v, forms[2]) : -1]
        for (var i = 0; i < forms.length; ++i) if (needs[i] >= 0 && needs[i] <= lineRoom + 0.5) return i
        return forms.length - 1
    }
    readonly property var form: forms[Math.max(0, Math.min(formIndex, forms.length - 1))]
    Item {
        visible: false
        CuText { id: m0c; text: slot.forms[0].status; role: "body"; tabular: !slot.statusDanger }
        CuText { id: m0v; text: slot.forms[0].value; role: "body"; tabular: true }
        CuText { id: m1c; text: slot.forms.length > 1 ? slot.forms[1].status : ""; role: "body"; tabular: true }
        CuText { id: m1v; text: slot.forms.length > 1 ? slot.forms[1].value : ""; role: "body"; tabular: true }
        CuText { id: m2c; text: slot.forms.length > 2 ? slot.forms[2].status : ""; role: "body"; tabular: true }
        CuText { id: m2v; text: slot.forms.length > 2 ? slot.forms[2].value : ""; role: "body"; tabular: true }
    }
    Item {
        id: statusLine
        objectName: "footStatus"
        x: 0
        y: 0
        width: slot.width
        height: Tokens.hFootStatus
        CuText {
            id: countText
            objectName: slot.statusDanger ? "footProblem" : "footStatusText"
            x: 0
            y: centredIn(Tokens.hFootStatus)
            width: Math.min(Math.ceil(implicitWidth), Math.max(0, slot.lineRoom - (valueText.visible ? Math.ceil(valueText.implicitWidth) : 0)))
            text: slot.form.status
            role: "body"
            tabular: !slot.statusDanger
            elide: Text.ElideRight
            color: slot.statusDanger ? Tokens.danger : Tokens.text2
        }
        CuText {
            id: valueText
            objectName: "footStatusValue"
            x: countText.x + countText.width
            y: countText.y
            visible: slot.form.value !== "" && !slot.statusDanger
            width: Math.ceil(implicitWidth)
            text: slot.form.value
            role: "body"
            tabular: true
            color: Tokens.text1
        }
        CuButton {
            id: detailsButton
            objectName: "footDetails"
            visible: slot.detailsText !== ""
            variant: "text"
            ground: slot.ground
            text: slot.detailsText
            tooltip: slot.detailsTip
            forcedState: slot.forcedState
            x: Tokens.snap(statusLine.width - width, slot.dpr)
            y: Tokens.snap(countText.y + countText.baselineOffset - (labelItem.y + labelItem.baselineOffset), slot.dpr)
            onClicked: slot.details()
        }
        Item {
            objectName: "footStatusTipArea"
            x: 0
            y: 0
            width: detailsButton.visible ? Math.max(0, statusLine.width - detailsButton.width - Tokens.sp16) : statusLine.width
            height: Tokens.hFootStatus
            readonly property bool shortened: slot.formIndex > 0 || countText.truncated
            readonly property string whole: slot.status + (slot.statusDanger ? "" : slot.statusValue)
            readonly property string tip: shortened ? whole + (slot.statusTip !== "" ? ". " + slot.statusTip : "")
                                                    : slot.statusTip
            visible: tip !== ""
            HoverHandler { id: statusHover }
            CuHoverTip { shown: statusHover.hovered; text: parent.tip; placement: "above" }
        }
    }
    Item {
        id: commitRow
        objectName: "footCommitRow"
        x: 0
        y: Tokens.hFootStatus + Tokens.sp8
        width: slot.width
        height: Tokens.hCommit
    }
}

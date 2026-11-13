import QtQuick
import QtCore

QtObject {
    id: prefs

    property var logger: null
    property var _settings: null
    property bool available: false
    property string location: ""

    function _log(level, event, message) {
        if (logger) logger(level, event, message, null)
    }

    function _defaultLocation() {
        if (typeof cuPrefsLocation !== "undefined" && cuPrefsLocation)
            return String(cuPrefsLocation)
        var dir = StandardPaths.writableLocation(StandardPaths.AppConfigLocation)
        return String(dir) + "/creative-upscaler-tab.ini"
    }

    function open() {
        try {
            location = _defaultLocation()
            _settings = Qt.createQmlObject('import QtCore; Settings { category: "CreativeUpscalerTab" }', prefs, "CuPrefsSettings")
            _settings.location = location
            _settings.value("schema", "1")
            available = true
        } catch (e) {
            available = false
            _log("warning", "prefs_unavailable", "Saved preferences are unavailable; using defaults (" + e + ").")
        }
    }

    function read(key, fallback) {
        if (!available) return fallback
        try {
            var raw = _settings.value(key, "")
            if (raw === undefined || raw === null || raw === "") return fallback
            return JSON.parse(String(raw))
        } catch (e) {
            _log("warning", "prefs_read_failed", "Could not read preference " + key + " (" + e + ").")
            return fallback
        }
    }

    function write(key, value) {
        if (!available) return
        try {
            _settings.setValue(key, JSON.stringify(value))
            _settings.sync()
        } catch (e) {
            _log("warning", "prefs_write_failed", "Could not save preference " + key + " (" + e + ").")
        }
    }
}

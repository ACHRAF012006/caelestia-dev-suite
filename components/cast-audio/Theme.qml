import QtQuick
import Quickshell
import Quickshell.Io
import Caelestia.Services

QtObject {
    id: root
    // The settings process has no host Colours singleton. Read its current
    // scheme too, and use KDE's Qt palette if no Caelestia scheme is available.
    readonly property var palette: PaletteManager.tPalette
    property var scheme: ({})
    property SystemPalette system: SystemPalette { colorGroup: SystemPalette.Active }
    property FileView schemeFile: FileView {
        path: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/caelestia/scheme.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try { root.scheme = JSON.parse(text()).colours || {}; }
            catch (error) { root.scheme = {}; }
        }
        onLoadFailed: root.scheme = ({})
    }
    function role(name, fallback) {
        const live = palette["m3" + name];
        if (live !== undefined && live !== null) return live;
        const saved = scheme[name];
        if (typeof saved === "string" && /^#?[0-9a-fA-F]{6}$/.test(saved))
            return saved.startsWith("#") ? saved : "#" + saved;
        return fallback;
    }
    readonly property color surface: role("surface", system.window)
    readonly property color card: role("surfaceContainerLow", system.alternateBase)
    readonly property color raised: role("surfaceContainerHighest", system.button)
    readonly property color selected: role("secondaryContainer", system.highlight)
    readonly property color selectedText: role("onSecondaryContainer", system.highlightedText)
    readonly property color foreground: role("onSurface", system.windowText)
    readonly property color secondary: role("onSurfaceVariant", system.text)
    readonly property color accent: role("primary", system.highlight)
    readonly property color accentText: role("onPrimary", system.highlightedText)
    readonly property color outline: role("outlineVariant", system.mid)
    readonly property color error: role("error", system.text)
}

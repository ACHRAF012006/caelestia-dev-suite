import QtQuick
import Caelestia.Services

QtObject {
    // Verified C++ singleton; external plugins cannot rely on qs.* root imports.
    readonly property var palette: PaletteManager.tPalette
    readonly property color surface: palette.m3surface || "#171b23"
    readonly property color card: palette.m3surfaceContainerHighest || "#303644"
    readonly property color selected: palette.m3secondaryContainer || "#354260"
    readonly property color foreground: palette.m3onSurface || "#e0e5ef"
    readonly property color secondary: palette.m3onSurfaceVariant || "#b5bdce"
    readonly property color accent: palette.m3primary || "#b4c4f6"
}

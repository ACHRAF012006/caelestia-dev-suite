import QtQuick
import QtQuick.Controls
import Caelestia.Config
import qs.services

TextField {
    id: root
    font: Tokens.font.body.small
    color: Colours.palette.m3onSurface
    placeholderTextColor: Colours.palette.m3onSurfaceVariant
    selectionColor: Colours.palette.m3primary
    selectedTextColor: Colours.palette.m3onPrimary
    padding: Tokens.padding.medium
    selectByMouse: true
    background: Rectangle {
        radius: Tokens.rounding.small
        color: Colours.palette.m3surfaceContainer
        border.width: root.activeFocus ? 1 : 0
        border.color: Colours.palette.m3primary
    }
}

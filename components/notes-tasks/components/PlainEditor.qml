import QtQuick
import QtQuick.Controls
import Caelestia.Config
import qs.services

TextArea {
    id: root
    textFormat: TextEdit.PlainText
    font: Tokens.font.body.small
    color: Colours.palette.m3onSurface
    placeholderTextColor: Colours.palette.m3onSurfaceVariant
    selectionColor: Colours.palette.m3primary
    selectedTextColor: Colours.palette.m3onPrimary
    wrapMode: TextEdit.Wrap
    selectByMouse: true
    padding: Tokens.padding.medium
    background: Rectangle { radius: Tokens.rounding.large; color: Colours.tPalette.m3surfaceContainerHigh }
}

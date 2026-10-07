import QtQuick
import Caelestia.Config

Text {
    property Theme theme: Theme {}
    textFormat: Text.PlainText
    renderType: Text.NativeRendering
    color: theme.foreground
    font: Tokens.font.body.small
}

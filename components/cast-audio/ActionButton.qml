import QtQuick
import QtQuick.Controls
import Caelestia.Config

Button {
    id: root
    property Theme theme: Theme {}
    implicitHeight: 44
    implicitWidth: Math.max(44, contentItem.implicitWidth + 28)
    padding: 12
    contentItem: CastText {
        text: root.text
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        opacity: root.enabled ? 1 : 0.45
    }
    background: Rectangle {
        radius: Tokens.rounding.large
        color: root.down ? root.theme.selected : root.theme.card
        opacity: root.enabled ? (root.hovered ? 1 : 0.85) : 0.4
        Behavior on color { ColorAnimation { duration: 100 } }
    }
}

import QtQuick
import QtQuick.Controls
import Caelestia.Config

Button {
    id: root
    property Theme theme: Theme {}
    property bool primary: false
    property bool active: false
    property string subtitle: ""
    font: Tokens.font.body.small
    implicitHeight: Math.max(44, root.implicitContentHeight + root.topPadding + root.bottomPadding)
    implicitWidth: Math.max(44, root.implicitContentWidth + root.leftPadding + root.rightPadding)
    padding: 12
    hoverEnabled: true
    contentItem: Item {
        implicitWidth: Math.max(label.implicitWidth, subtitleLabel.implicitWidth)
        implicitHeight: label.implicitHeight + (subtitleLabel.visible ? subtitleLabel.implicitHeight + 3 : 0)
        opacity: root.enabled || root.active ? 1 : 0.45
        CastText {
            id: label
            objectName: "castAudioButtonText"
            font: root.font
            anchors.left: parent.left
            anchors.right: parent.right
            y: root.subtitle ? (parent.height - parent.implicitHeight) / 2 : (parent.height - height) / 2
            text: root.text
            color: root.primary ? root.theme.accentText : root.active ? root.theme.selectedText : root.theme.foreground
            elide: Text.ElideRight
            horizontalAlignment: root.subtitle ? Text.AlignLeft : Text.AlignHCenter
        }
        CastText {
            id: subtitleLabel
            anchors.left: parent.left
            anchors.right: parent.right
            y: label.y + label.height + 3
            visible: root.subtitle.length > 0
            text: root.subtitle
            color: root.active ? root.theme.selectedText : root.theme.secondary
            font.pixelSize: 11
            elide: Text.ElideRight
        }
    }
    background: Rectangle {
        radius: Tokens.rounding.large
        color: root.primary ? root.theme.accent : root.active || root.down ? root.theme.selected : root.flat && !root.hovered ? "transparent" : root.theme.raised
        opacity: root.enabled || root.active ? (root.hovered || root.down ? 1 : 0.9) : 0.4
        border.width: root.visualFocus ? 2 : 0
        border.color: root.theme.accent
        Behavior on color { ColorAnimation { duration: 150 } }
    }
}

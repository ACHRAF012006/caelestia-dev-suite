pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Caelestia.Config
import qs.components
import qs.services

Button {
    id: root
    property string symbol: ""
    property bool selected: false
    property bool motion: true
    property bool destructive: false
    property string description: text
    implicitHeight: label.implicitHeight + Tokens.padding.small * 2
    implicitWidth: label.implicitWidth + Tokens.padding.small * 2
    padding: Tokens.padding.small
    hoverEnabled: true
    Accessible.name: description
    ToolTip.visible: hovered && description.length > 0
    ToolTip.text: description
    contentItem: Row {
        id: label
        spacing: Tokens.spacing.extraSmall
        MaterialIcon { visible: !!root.symbol; text: root.symbol; color: root.destructive ? Colours.palette.m3error : root.selected ? Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant; fontStyle: Tokens.font.icon.small }
        StyledText { visible: !!root.text; text: root.text; font: Tokens.font.body.small; color: root.selected ? Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant }
    }
    background: StyledRect {
        radius: Tokens.rounding.full
        color: root.selected ? Qt.alpha(Colours.palette.m3primary, 0.13) : root.hovered || root.down ? Colours.tPalette.m3surfaceContainerHighest : "transparent"
        border.width: root.activeFocus ? 1 : 0
        border.color: Colours.palette.m3primary
        opacity: root.enabled ? 1 : 0.5
        Behavior on color { ColorAnimation { duration: root.motion ? Math.min(160, Tokens.anim.durations.small) : 0 } }
    }
}

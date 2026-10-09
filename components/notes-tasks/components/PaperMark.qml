import QtQuick
import Caelestia.Config
import qs.components
import qs.services

Item {
    id: root
    property bool active: false
    property bool motion: true
    property bool secondary: false
    implicitWidth: Tokens.padding.large * 4
    implicitHeight: implicitWidth
    Rectangle {
        anchors.centerIn: parent
        width: parent.width * 0.85; height: width
        radius: width * 0.38
        rotation: root.active ? 18 : -12
        color: root.secondary ? Colours.palette.m3secondaryContainer : Colours.palette.m3primaryContainer
        opacity: 0.55
        Behavior on rotation { Anim { duration: root.motion ? Math.min(200, Tokens.anim.durations.small) : 0; type: Anim.FastSpatial } }
    }
    StyledRect {
        anchors.centerIn: parent
        width: parent.width * 0.52; height: parent.height * 0.64
        radius: Tokens.rounding.small
        rotation: root.active ? -6 : 8
        color: Colours.tPalette.m3surfaceContainerHighest
        Behavior on rotation { Anim { duration: root.motion ? Math.min(180, Tokens.anim.durations.small) : 0; type: Anim.FastSpatial } }
        MaterialIcon { anchors.centerIn: parent; text: "stylus_note"; fontStyle: Tokens.font.icon.large; color: root.secondary ? Colours.palette.m3secondary : Colours.palette.m3primary }
    }
    Rectangle { x: root.width * 0.86; y: root.height * 0.24; width: Tokens.padding.extraSmall; height: width; radius: width / 2; color: Colours.palette.m3secondary }
    Rectangle { x: root.width * 0.08; y: root.height * 0.8; width: Tokens.padding.extraSmall / 2; height: width; radius: width / 2; color: Colours.palette.m3primary }
}

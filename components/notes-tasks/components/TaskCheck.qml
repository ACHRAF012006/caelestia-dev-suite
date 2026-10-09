pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Caelestia.Config
import qs.components
import qs.services

Button {
    id: root
    property bool completed: false
    property bool motion: true
    property string description: completed ? qsTr("Mark incomplete") : qsTr("Complete task")
    implicitWidth: Math.max(Tokens.padding.large * 2, glyph.implicitHeight + Tokens.padding.small)
    implicitHeight: implicitWidth
    padding: 0
    hoverEnabled: true
    Accessible.role: Accessible.CheckBox
    Accessible.checkable: true
    Accessible.checked: completed
    Accessible.name: description
    ToolTip.visible: hovered
    ToolTip.text: description
    HoverHandler { cursorShape: Qt.PointingHandCursor }
    contentItem: Item {
        MaterialIcon {
            id: glyph
            objectName: "notesTasksCheckGlyph"
            anchors.centerIn: parent
            text: "check"
            fontStyle: Tokens.font.icon.small
            color: Colours.palette.m3primary
            scale: 0.75
            opacity: root.completed ? 1 : 0
            Behavior on opacity { Anim { duration: root.motion ? Math.min(160, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } }
        }
    }
    background: Item {
        StyledRect {
            objectName: "notesTasksCheckCircle"
            anchors.centerIn: parent
            width: parent.width - Tokens.padding.small
            height: width
            radius: width / 2
            color: root.completed || root.hovered || root.down ? Qt.alpha(Colours.palette.m3primary, 0.13) : "transparent"
            border.width: root.activeFocus ? 2 : 1
            border.color: root.completed || root.activeFocus ? Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant
            Behavior on color { ColorAnimation { duration: root.motion ? Math.min(160, Tokens.anim.durations.small) : 0 } }
        }
    }
}

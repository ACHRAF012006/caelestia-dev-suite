pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

Rectangle {
    id: root
    required property var entry
    required property var controller
    signal editRequested(string recordId)
    implicitHeight: body.implicitHeight + Tokens.padding.small * 2
    radius: Tokens.rounding.small
    color: Colours.palette.m3surfaceContainer
    RowLayout {
        id: body
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: Tokens.padding.small
        spacing: Tokens.spacing.small
        ActionButton {
            objectName: "notesTasksComplete"
            symbol: root.entry.completed ? "check_circle" : "radio_button_unchecked"
            description: root.entry.completed ? qsTr("Mark incomplete") : qsTr("Complete task")
            selected: root.entry.completed; motion: root.controller.motion
            onClicked: root.controller.edit("tasks", root.entry.id, {completed: !root.entry.completed})
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.extraSmall
            opacity: root.entry.completed ? 0.55 : 1
            Behavior on opacity { Anim { duration: root.controller.motion ? Tokens.anim.durations.small : 0; type: Anim.FastEffects } }
            StyledText {
                Layout.fillWidth: true
                text: root.entry.title || qsTr("Untitled task")
                font.strikeout: root.entry.completed
                maximumLineCount: root.controller.settings.compact ? 1 : 2
                wrapMode: Text.Wrap; elide: Text.ElideRight
            }
            StyledText {
                visible: !root.controller.settings.compact && (!!root.entry.due.date || root.entry.priority > 0 || root.entry.subtasks.length > 0)
                Layout.fillWidth: true
                text: [root.entry.due.date + (root.entry.due.time ? " · " + root.entry.due.time : ""), root.entry.priority ? ["", qsTr("Low"), qsTr("Medium"), qsTr("High")][root.entry.priority] : "", root.entry.subtasks.length ? root.entry.subtasks.filter(s => s.completed).length + "/" + root.entry.subtasks.length + " " + qsTr("subtasks") : ""].filter(part => part).join("  ·  ")
                elide: Text.ElideRight; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.label.small
            }
        }
        ActionButton { symbol: "chevron_right"; description: qsTr("Edit task and details"); motion: root.controller.motion; onClicked: root.editRequested(root.entry.id) }
    }
}

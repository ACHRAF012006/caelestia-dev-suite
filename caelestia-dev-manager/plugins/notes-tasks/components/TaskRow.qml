pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

StyledRect {
    id: root
    required property var entry
    required property var controller
    signal editRequested(string recordId)
    implicitHeight: body.implicitHeight + Tokens.padding.small * 2
    radius: Tokens.rounding.large
    color: hover.hovered ? Colours.tPalette.m3surfaceContainerHigh : "transparent"
    readonly property real titleLineHeight: taskTitle.implicitHeight / Math.max(1, taskTitle.lineCount)
    HoverHandler { id: hover }
    Behavior on color { ColorAnimation { duration: root.controller.motion ? Math.min(160, Tokens.anim.durations.small) : 0 } }
    RowLayout {
        id: body
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: Tokens.padding.small
        spacing: Tokens.spacing.small
        TaskCheck {
            id: complete
            objectName: "notesTasksComplete"
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: Math.max(0, (root.titleLineHeight - implicitHeight) / 2)
            completed: root.entry.completed
            motion: root.controller.motion
            onClicked: root.controller.edit("tasks", root.entry.id, {completed: !root.entry.completed})
        }
        ColumnLayout {
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: Math.max(0, (complete.implicitHeight - root.titleLineHeight) / 2)
            Layout.fillWidth: true; Layout.minimumWidth: 0
            spacing: Tokens.spacing.extraSmall
            opacity: root.entry.completed ? 0.5 : 1
            Behavior on opacity { Anim { duration: root.controller.motion ? Math.min(160, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } }
            StyledText {
                id: taskTitle
                Layout.fillWidth: true
                objectName: "notesTasksTaskTitle"
                text: root.entry.title || qsTr("Untitled task")
                font.strikeout: root.entry.completed
                maximumLineCount: root.controller.settings.compact ? 1 : 2
                wrapMode: Text.Wrap; elide: Text.ElideRight
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.editRequested(root.entry.id) }
            }
            StyledText {
                visible: !root.controller.settings.compact && (!!root.entry.due.date || root.entry.priority > 0 || root.entry.subtasks.length > 0)
                Layout.fillWidth: true
                text: [root.entry.due.date + (root.entry.due.time ? " · " + root.entry.due.time : ""), root.entry.priority ? ["", qsTr("Low"), qsTr("Medium"), qsTr("High")][root.entry.priority] : "", root.entry.subtasks.length ? root.entry.subtasks.filter(s => s.completed).length + "/" + root.entry.subtasks.length : ""].filter(part => part).join(" · ")
                elide: Text.ElideRight; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.label.small
            }
        }
        ActionButton { Layout.alignment: Qt.AlignTop; Layout.topMargin: (Math.max(complete.implicitHeight, root.titleLineHeight) - implicitHeight) / 2; symbol: "arrow_outward"; description: qsTr("Edit task and details"); opacity: hover.hovered || activeFocus ? 1 : 0.35; motion: root.controller.motion; onClicked: root.editRequested(root.entry.id) }
    }
}

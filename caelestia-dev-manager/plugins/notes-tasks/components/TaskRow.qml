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
    HoverHandler { id: hover }
    Behavior on color { ColorAnimation { duration: root.controller.motion ? Math.min(160, Tokens.anim.durations.small) : 0 } }
    RowLayout {
        id: body
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: Tokens.padding.small
        spacing: Tokens.spacing.small
        Item {
            implicitWidth: complete.implicitWidth; implicitHeight: complete.implicitHeight
            CircularProgress { anchors.centerIn: parent; implicitSize: parent.width - Tokens.padding.extraSmall; value: root.entry.completed ? 1 : 0; strokeWidth: 2; spacing: 0; wavePaused: true; bgColour: Colours.palette.m3onSurfaceVariant; fgColour: Colours.palette.m3secondary; Behavior on clampedVal { Anim { duration: root.controller.motion ? Math.min(160, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } } }
            ActionButton {
                id: complete
                objectName: "notesTasksComplete"
                symbol: root.entry.completed ? "check" : ""
                implicitWidth: Tokens.padding.large * 1.5
                description: root.entry.completed ? qsTr("Mark incomplete") : qsTr("Complete task")
                motion: root.controller.motion
                onClicked: root.controller.edit("tasks", root.entry.id, {completed: !root.entry.completed})
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0
            spacing: Tokens.spacing.extraSmall
            opacity: root.entry.completed ? 0.5 : 1
            Behavior on opacity { Anim { duration: root.controller.motion ? Math.min(160, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } }
            StyledText {
                Layout.fillWidth: true
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
        ActionButton { symbol: "arrow_outward"; description: qsTr("Edit task and details"); opacity: hover.hovered || activeFocus ? 1 : 0.35; motion: root.controller.motion; onClicked: root.editRequested(root.entry.id) }
    }
}

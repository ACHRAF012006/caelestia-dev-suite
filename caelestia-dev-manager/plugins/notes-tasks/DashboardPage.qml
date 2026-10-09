pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services
import "components"

Rectangle {
    id: root
    objectName: "notesTasksPage"
    required property var controller
    property bool presentationActive: true
    property string section: controller.settings.defaultSection
    property bool settingsOpen: false
    property string pendingDeleteKind: ""
    property string pendingDeleteId: ""
    readonly property bool narrow: width < Tokens.sizes.dashboard.mediaSectionWidth * 2
    implicitWidth: Tokens.sizes.dashboard.mediaTabWidth
    implicitHeight: Tokens.sizes.dashboard.mediaTabHeight
    radius: Tokens.rounding.large
    color: Colours.palette.m3surfaceContainerLow
    function requestDelete(kind, id) {
        if (controller.settings.confirmDelete) { pendingDeleteKind = kind; pendingDeleteId = id; }
        else controller.send({action: "delete", kind: kind, id: id});
    }
    function captured(kind, id) {
        if (section !== "both") section = kind;
        if (kind === "notes") notes.openRecord(id);
    }
    onPresentationActiveChanged: if (!presentationActive) { settingsOpen = false; capture.visible = false; pendingDeleteId = ""; }
    Keys.onPressed: event => {
        if (event.modifiers & Qt.ControlModifier) {
            if (event.key === Qt.Key_F) { search.focusSearch(); event.accepted = true; }
            else if (event.key === Qt.Key_N) { capture.open(event.modifiers & Qt.ShiftModifier ? "tasks" : "notes"); event.accepted = true; }
        } else if (event.key === Qt.Key_Escape) { settingsOpen = false; capture.visible = false; pendingDeleteId = ""; event.accepted = true; }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.small
        GridLayout {
            Layout.fillWidth: true
            columns: root.narrow ? 1 : 2
            rowSpacing: Tokens.spacing.small
            RowLayout {
                Layout.fillWidth: true
                StyledText { text: qsTr("Notes & Tasks"); font: Tokens.font.body.medium; Layout.fillWidth: true; elide: Text.ElideRight }
                ActionButton { symbol: "settings"; description: qsTr("Settings"); motion: root.controller.motion; selected: root.settingsOpen; enabled: root.controller.healthy; onClicked: root.settingsOpen = !root.settingsOpen }
                ActionButton { objectName: "notesTasksAdd"; symbol: "add"; description: qsTr("Quick capture · Ctrl+N / Ctrl+Shift+N"); selected: capture.visible; motion: root.controller.motion; enabled: root.controller.healthy; onClicked: { if (capture.visible) capture.visible = false; else capture.open(root.section === "notes" ? "notes" : "tasks"); } }
            }
            SearchBar { id: search; Layout.fillWidth: true }
        }
        Reveal {
            Layout.fillWidth: true
            expanded: capture.visible
            motion: root.controller.motion
            QuickCapture { id: capture; controller: root.controller; width: parent.width; onCaptured: (kind, id) => root.captured(kind, id); onCloseRequested: visible = false }
        }
        StyledText {
            visible: !!root.controller.error
            Layout.fillWidth: true
            text: root.controller.error
            color: Colours.palette.m3error
            wrapMode: Text.Wrap
        }
        RowLayout {
            visible: !!root.pendingDeleteId
            Layout.fillWidth: true
            StyledText { Layout.fillWidth: true; text: qsTr("Permanently delete this item?"); wrapMode: Text.Wrap }
            ActionButton { text: qsTr("Cancel"); motion: root.controller.motion; onClicked: root.pendingDeleteId = "" }
            ActionButton { text: qsTr("Delete"); destructive: true; motion: root.controller.motion; onClicked: { root.controller.send({action: "delete", kind: root.pendingDeleteKind, id: root.pendingDeleteId}); root.pendingDeleteId = ""; } }
        }
        RowLayout {
            visible: !root.settingsOpen
            Layout.fillWidth: true
            ActionButton { text: qsTr("Both"); selected: root.section === "both"; motion: root.controller.motion; onClicked: root.section = "both" }
            ActionButton { text: qsTr("Notes"); selected: root.section === "notes"; motion: root.controller.motion; onClicked: root.section = "notes" }
            ActionButton { text: qsTr("Tasks"); selected: root.section === "tasks"; motion: root.controller.motion; onClicked: root.section = "tasks" }
            Item { Layout.fillWidth: true }
            StyledText { text: root.controller.saving ? qsTr("Saving…") : qsTr("Saved locally"); visible: root.controller.healthy; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
        }
        GridLayout {
            visible: !root.settingsOpen
            enabled: root.controller.healthy
            Layout.fillWidth: true; Layout.fillHeight: true
            columns: root.narrow ? 1 : 2
            columnSpacing: Tokens.spacing.large
            rowSpacing: Tokens.spacing.medium
            NotesPane {
                id: notes
                objectName: "notesTasksNotesPane"
                visible: root.section !== "tasks"
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.preferredWidth: 1; Layout.preferredHeight: 1
                controller: root.controller; query: search.text
                onDeleteRequested: (kind, id) => root.requestDelete(kind, id)
            }
            TasksPane {
                id: tasks
                objectName: "notesTasksTasksPane"
                visible: root.section !== "notes"
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.preferredWidth: 1; Layout.preferredHeight: 1
                controller: root.controller; query: search.text; presentationActive: root.presentationActive
                onDeleteRequested: (kind, id) => root.requestDelete(kind, id)
            }
        }
        SettingsPane { visible: root.settingsOpen; Layout.fillWidth: true; Layout.fillHeight: true; controller: root.controller; onCloseRequested: root.settingsOpen = false }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services
import "components"

Item {
    id: root
    objectName: "notesTasksPage"
    required property var controller
    property bool presentationActive: true
    property string section: controller.settings.defaultSection
    property string selectedTag: ""
    readonly property bool narrow: width < Tokens.padding.large * 36
    implicitWidth: Tokens.sizes.dashboard.mediaTabWidth
    implicitHeight: Tokens.sizes.dashboard.mediaTabHeight * 2
    opacity: presentationActive ? 1 : 0
    Behavior on opacity { Anim { duration: root.controller.motion ? Math.min(160, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } }
    function requestDelete(kind, id) {
        controller.send({action: "delete", kind: kind, id: id});
    }
    function captured(kind, id) {
        if (section !== "both") section = kind;
        if (kind === "notes") { selectedTag = ""; notes.archived = false; notes.openRecord(id); }
    }
    onPresentationActiveChanged: if (!presentationActive) { capture.close(); }
    Keys.onPressed: event => {
        if (event.modifiers & Qt.ControlModifier) {
            if (event.key === Qt.Key_F) { search.focusSearch(); event.accepted = true; }
            else if (event.key === Qt.Key_N) { capture.open(event.modifiers & Qt.ShiftModifier ? "tasks" : "notes"); event.accepted = true; }
        } else if (event.key === Qt.Key_Escape) { capture.close(); event.accepted = true; }
    }
    ScrollView {
        id: scroll
        anchors.fill: parent; clip: true
        contentWidth: availableWidth
        ColumnLayout {
            id: composition
            width: scroll.availableWidth
            spacing: Tokens.spacing.medium
            QuickCapture {
                id: capture
                Layout.fillWidth: true
                controller: root.controller
                trailingWidth: utilities.width
                onCaptured: (kind, id) => root.captured(kind, id)
                RowLayout {
                    id: utilities
                    anchors.top: parent.top; anchors.right: parent.right; anchors.margins: Tokens.padding.large
                    spacing: Tokens.spacing.extraSmall
                    SearchBar { id: search; motion: root.controller.motion; availableWidth: Math.max(Tokens.padding.large * 6, Math.min(Tokens.padding.large * 20, root.width - Tokens.padding.large * 9)); onExpandedChanged: if (expanded && root.narrow) capture.expanded = true }
                    ActionButton { objectName: "notesTasksAdd"; symbol: "add"; description: qsTr("Quick capture · Ctrl+N / Ctrl+Shift+N"); selected: capture.expanded; motion: root.controller.motion; enabled: root.controller.healthy; onClicked: capture.open(root.section === "tasks" ? "tasks" : "notes") }
                }
            }
            StyledText { visible: !!root.controller.error; Layout.fillWidth: true; text: root.controller.error; color: Colours.palette.m3error; wrapMode: Text.Wrap }
            RowLayout {
                Layout.fillWidth: true
                ActionButton { objectName: "notesTasksAllSection"; text: qsTr("All"); selected: root.section === "both"; motion: root.controller.motion; onClicked: root.section = "both" }
                ActionButton { text: qsTr("Notes"); selected: root.section === "notes"; motion: root.controller.motion; onClicked: root.section = "notes" }
                ActionButton { text: qsTr("Tasks"); selected: root.section === "tasks"; motion: root.controller.motion; onClicked: root.section = "tasks" }
                Item { Layout.fillWidth: true }
                StyledText { text: root.controller.saving ? qsTr("Saving…") : qsTr("On this device"); visible: root.controller.healthy; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
            }
            GridLayout {
                id: widgets
                enabled: root.controller.healthy
                Layout.fillWidth: true
                columns: root.narrow || root.section !== "both" ? 1 : 3
                columnSpacing: Tokens.spacing.medium; rowSpacing: Tokens.spacing.medium
                NotesPane {
                    id: notes
                    objectName: "notesTasksNotesPane"
                    visible: root.section !== "tasks"
                    Layout.columnSpan: widgets.columns === 3 ? 2 : 1
                    Layout.fillWidth: true; Layout.preferredWidth: 2
                    Layout.preferredHeight: root.narrow ? Tokens.padding.large * 23 : Math.max(Tokens.padding.large * 27, root.height - capture.implicitHeight - Tokens.padding.large * 4)
                    controller: root.controller; query: search.query; tag: root.selectedTag
                    onDeleteRequested: (kind, id) => root.requestDelete(kind, id)
                    onCaptureRequested: capture.open("notes")
                    onTagRequested: tag => root.selectedTag = tag
                }
                ColumnLayout {
                    visible: root.section !== "notes"
                    Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignTop
                    spacing: Tokens.spacing.medium
                    TasksPane {
                        id: tasks
                        objectName: "notesTasksTasksPane"
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.max(Tokens.padding.large * 22, notes.Layout.preferredHeight - tags.implicitHeight - Tokens.spacing.medium)
                        controller: root.controller; query: search.query; presentationActive: root.presentationActive
                        onDeleteRequested: (kind, id) => root.requestDelete(kind, id)
                        onCaptureRequested: capture.open("tasks")
                    }
                    TagsCard { id: tags; Layout.fillWidth: true; controller: root.controller; selectedTag: root.selectedTag; onTagRequested: tag => { root.selectedTag = tag; if (root.section === "tasks") root.section = "both"; notes.selectedId = ""; } }
                }
            }
        }
    }
}

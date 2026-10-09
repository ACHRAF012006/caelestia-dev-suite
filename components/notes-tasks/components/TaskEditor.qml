pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

ColumnLayout {
    id: root
    objectName: "notesTasksTaskEditor"
    required property var controller
    property string recordId: ""
    property var entry: null
    property bool advanced: false
    signal closeRequested()
    signal deleteRequested(string kind, string recordId)
    signal moveRequested(string recordId, int direction)
    function focusTitle() { title.forceActiveFocus(); }
    function load() {
        entry = controller.record("tasks", recordId);
        if (!entry) { closeRequested(); return; }
        if (!title.activeFocus) title.text = entry.title;
        if (!details.activeFocus) details.text = entry.details;
        if (!tags.activeFocus) tags.text = entry.tags.join(", ");
        if (!dueDate.activeFocus) dueDate.text = entry.due.date;
        if (!dueTime.activeFocus) dueTime.text = entry.due.time;
        priority.currentIndex = entry.priority;
    }
    function subtask(action, id, value) { controller.send({action: action, kind: "tasks", id: recordId, subtaskId: id, title: value ?? ""}); }
    onRecordIdChanged: { title.focus = false; details.focus = false; tags.focus = false; dueDate.focus = false; dueTime.focus = false; load(); }
    spacing: Tokens.spacing.small
    RowLayout {
        Layout.fillWidth: true
        ActionButton { symbol: "arrow_back"; description: qsTr("Back to tasks"); motion: root.controller.motion; onClicked: root.closeRequested() }
        StyledText { Layout.fillWidth: true; text: qsTr("Edit task"); font: Tokens.font.body.medium }
        TaskCheck { objectName: "notesTasksEditorComplete"; completed: root.entry?.completed ?? false; motion: root.controller.motion; onClicked: root.controller.edit("tasks", root.recordId, {completed: !root.entry.completed}) }
        ActionButton { objectName: "notesTasksDeleteTask"; symbol: "delete"; description: qsTr("Delete task"); destructive: true; motion: root.controller.motion; onClicked: root.deleteRequested("tasks", root.recordId) }
    }
    ScrollView {
        Layout.fillWidth: true; Layout.fillHeight: true
        clip: true
        ColumnLayout {
            width: parent.width
            spacing: Tokens.spacing.small
            InputField { id: title; Layout.fillWidth: true; placeholderText: qsTr("Task title"); onTextEdited: root.controller.edit("tasks", root.recordId, {title: text}) }
            ActionButton { text: qsTr("Details & properties"); symbol: root.advanced ? "expand_less" : "expand_more"; selected: root.advanced; motion: root.controller.motion; onClicked: root.advanced = !root.advanced }
            Reveal {
                expanded: root.advanced
                motion: root.controller.motion
                Layout.fillWidth: true
                ColumnLayout {
                width: parent.width
                spacing: Tokens.spacing.small
                PlainEditor { id: details; Layout.fillWidth: true; Layout.preferredHeight: Tokens.padding.large * 5; placeholderText: qsTr("Details (optional)"); onTextChanged: if (activeFocus) root.controller.edit("tasks", root.recordId, {details: text}) }
                InputField { id: tags; Layout.fillWidth: true; placeholderText: qsTr("Tags, separated by commas"); onTextEdited: root.controller.edit("tasks", root.recordId, {tags: root.controller.tags(text)}) }
                GridLayout {
                    Layout.fillWidth: true
                    columns: width < Tokens.padding.large * 20 ? 1 : 2
                    InputField { id: dueDate; Layout.fillWidth: true; placeholderText: qsTr("Due date: YYYY-MM-DD"); onEditingFinished: if (root.entry) root.controller.edit("tasks", root.recordId, {due: {date: text, time: text ? dueTime.text : ""}}) }
                    InputField { id: dueTime; Layout.fillWidth: true; enabled: !!dueDate.text; placeholderText: qsTr("Time: HH:MM (optional)"); onEditingFinished: if (root.entry) root.controller.edit("tasks", root.recordId, {due: {date: dueDate.text, time: text}}) }
                }
                RowLayout {
                    Layout.fillWidth: true
                    StyledText { text: qsTr("Priority") }
                    ChoiceBox { id: priority; Layout.fillWidth: true; model: [qsTr("None"), qsTr("Low"), qsTr("Medium"), qsTr("High")]; onActivated: root.controller.edit("tasks", root.recordId, {priority: currentIndex}) }
                }
                RowLayout {
                    Layout.fillWidth: true
                    ActionButton { symbol: "arrow_upward"; text: qsTr("Move up"); motion: root.controller.motion; onClicked: root.moveRequested(root.recordId, -1) }
                    ActionButton { symbol: "arrow_downward"; text: qsTr("Move down"); motion: root.controller.motion; onClicked: root.moveRequested(root.recordId, 1) }
                }
            }
            }
            StyledText { text: qsTr("Subtasks"); color: Colours.palette.m3onSurfaceVariant }
            Repeater {
                model: root.entry?.subtasks ?? []
                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    TaskCheck { completed: parent.modelData.completed; description: qsTr("Toggle subtask"); motion: root.controller.motion; onClicked: root.subtask("subtask-toggle", parent.modelData.id) }
                    InputField { Layout.fillWidth: true; text: parent.modelData.title; onEditingFinished: root.subtask("subtask-edit", parent.modelData.id, text) }
                    ActionButton { symbol: "close"; description: qsTr("Remove subtask"); motion: root.controller.motion; onClicked: root.subtask("subtask-delete", parent.modelData.id) }
                }
            }
            InputField {
                Layout.fillWidth: true
                placeholderText: qsTr("Add subtask · Enter")
                onAccepted: { if (text.trim()) root.subtask("subtask-create", "", text.trim()); text = ""; }
            }
        }
    }
    Connections {
        target: root.controller
        function onChanged(kind, id, entry) { if (kind === "tasks" && id === root.recordId) root.load(); }
    }
}

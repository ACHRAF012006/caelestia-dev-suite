pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

ColumnLayout {
    id: root
    required property var controller
    property string recordId: ""
    property var entry: null
    signal closeRequested()
    signal deleteRequested(string kind, string recordId)
    function load() {
        entry = controller.record("notes", recordId);
        if (!entry) { closeRequested(); return; }
        if (!title.activeFocus) title.text = entry.title;
        if (!tags.activeFocus) tags.text = entry.tags.join(", ");
        if (!body.activeFocus) body.text = entry.text;
    }
    onRecordIdChanged: { title.focus = false; tags.focus = false; body.focus = false; load(); }
    spacing: Tokens.spacing.small
    RowLayout {
        Layout.fillWidth: true
        ActionButton { symbol: "arrow_back"; description: qsTr("Back to notes"); motion: root.controller.motion; onClicked: root.closeRequested() }
        StyledText { Layout.fillWidth: true; text: qsTr("Edit note"); font: Tokens.font.body.medium }
        ActionButton { symbol: root.entry?.pinned ? "keep" : "keep_off"; description: qsTr("Pin / unpin"); selected: root.entry?.pinned ?? false; motion: root.controller.motion; onClicked: root.controller.edit("notes", root.recordId, {pinned: !root.entry.pinned}) }
        ActionButton { symbol: "archive"; description: root.entry?.archived ? qsTr("Unarchive") : qsTr("Archive"); motion: root.controller.motion; onClicked: { root.controller.edit("notes", root.recordId, {archived: !root.entry.archived}); root.closeRequested(); } }
        ActionButton { symbol: "delete"; description: qsTr("Delete note"); destructive: true; motion: root.controller.motion; onClicked: root.deleteRequested("notes", root.recordId) }
    }
    InputField {
        id: title
        Layout.fillWidth: true
        placeholderText: qsTr("Title (optional)")
        onTextEdited: root.controller.edit("notes", root.recordId, {title: text})
    }
    InputField {
        id: tags
        Layout.fillWidth: true
        placeholderText: qsTr("Tags, separated by commas")
        onTextEdited: root.controller.edit("notes", root.recordId, {tags: root.controller.tags(text)})
    }
    ScrollView {
        Layout.fillWidth: true; Layout.fillHeight: true
        clip: true
        PlainEditor {
            id: body
            objectName: "notesTasksNoteBody"
            width: parent.width
            placeholderText: qsTr("Write a note…")
            onTextChanged: if (activeFocus) root.controller.edit("notes", root.recordId, {text: text})
        }
    }
    StyledText {
        Layout.fillWidth: true
        text: root.entry ? qsTr("Created ") + new Date(root.entry.createdAt).toLocaleString(Qt.locale(), Locale.ShortFormat) + " · " + qsTr("Edited ") + new Date(root.entry.updatedAt).toLocaleString(Qt.locale(), Locale.ShortFormat) : ""
        elide: Text.ElideRight; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant
    }
    Connections {
        target: root.controller
        function onChanged(kind, id, entry) { if (kind === "notes" && id === root.recordId) root.load(); }
    }
}

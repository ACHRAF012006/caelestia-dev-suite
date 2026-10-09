pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

StyledRect {
    id: root
    required property var controller
    property string recordId: ""
    property var entry: null
    property bool propertiesOpen: false
    signal closeRequested()
    signal deleteRequested(string kind, string recordId)
    function focusBody() { body.forceActiveFocus(); }
    function done(event) { if (event.key === Qt.Key_Return && event.modifiers & Qt.ControlModifier) { root.closeRequested(); event.accepted = true; } }
    function load() {
        entry = controller.record("notes", recordId);
        if (!entry) { closeRequested(); return; }
        if (!title.activeFocus) title.text = entry.title;
        if (!tags.activeFocus) tags.text = entry.tags.join(", ");
        if (!body.activeFocus) body.text = entry.text;
    }
    onRecordIdChanged: { title.focus = false; tags.focus = false; body.focus = false; propertiesOpen = false; load(); }
    color: Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.extraLarge
    Keys.onPressed: event => root.done(event)
    ColumnLayout {
        anchors.fill: parent; anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.small
        RowLayout {
            Layout.fillWidth: true
            MaterialIcon { text: "stylus_note"; color: Colours.palette.m3primary; fontStyle: Tokens.font.icon.small }
            StyledText { Layout.fillWidth: true; text: root.entry?.pinned ? qsTr("Pinned thought") : qsTr("A little space to think"); font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant; elide: Text.ElideRight }
            ActionButton { symbol: root.entry?.pinned ? "keep" : "keep_off"; description: qsTr("Pin / unpin"); selected: root.entry?.pinned ?? false; motion: root.controller.motion; onClicked: root.controller.edit("notes", root.recordId, {pinned: !root.entry.pinned}) }
            ActionButton { objectName: "notesTasksNoteActions"; symbol: "more_horiz"; description: qsTr("Note actions and tags"); selected: root.propertiesOpen; motion: root.controller.motion; onClicked: root.propertiesOpen = !root.propertiesOpen }
        }
        InputField { id: title; objectName: "notesTasksNoteTitle"; Layout.fillWidth: true; padding: 0; font: Tokens.font.title.large; placeholderText: qsTr("Title, if you like"); background: null; Keys.onPressed: event => root.done(event); onTextEdited: root.controller.edit("notes", root.recordId, {title: text}) }
        ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            PlainEditor { id: body; objectName: "notesTasksNoteBody"; width: parent.width; padding: 0; background: null; placeholderText: qsTr("Let the idea unfold…"); Keys.onPressed: event => root.done(event); onTextChanged: if (activeFocus) root.controller.edit("notes", root.recordId, {text: text}) }
        }
        Reveal {
            expanded: root.propertiesOpen; motion: root.controller.motion; Layout.fillWidth: true
            ColumnLayout {
                width: parent.width; spacing: Tokens.spacing.small
                InputField { id: tags; objectName: "notesTasksNoteTags"; Layout.fillWidth: true; placeholderText: qsTr("Tags, separated by commas"); onTextEdited: root.controller.edit("notes", root.recordId, {tags: root.controller.tags(text)}) }
                Flow {
                    Layout.fillWidth: true; spacing: Tokens.spacing.small
                    ActionButton { text: qsTr("Duplicate"); symbol: "content_copy"; motion: root.controller.motion; onClicked: root.controller.send({action: "duplicate", kind: "notes", id: root.recordId}) }
                    ActionButton { text: root.entry?.archived ? qsTr("Unarchive") : qsTr("Archive"); symbol: "archive"; motion: root.controller.motion; onClicked: { root.controller.edit("notes", root.recordId, {archived: !root.entry.archived}); root.closeRequested(); } }
                    ActionButton { objectName: "notesTasksDeleteNote"; text: qsTr("Delete"); symbol: "delete"; destructive: true; motion: root.controller.motion; onClicked: root.deleteRequested("notes", root.recordId) }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            StyledText { Layout.fillWidth: true; text: root.entry ? qsTr("Updated ") + new Date(root.entry.updatedAt).toLocaleTimeString(Qt.locale(), Locale.ShortFormat) : ""; elide: Text.ElideRight; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
            ActionButton { objectName: "notesTasksNoteDone"; text: qsTr("Done"); symbol: "check"; selected: true; description: qsTr("Done · Ctrl+Enter"); motion: root.controller.motion; onClicked: root.closeRequested() }
        }
    }
    Connections { target: root.controller; function onChanged(kind, id, entry) { if (kind === "notes" && id === root.recordId) root.load(); } }
}

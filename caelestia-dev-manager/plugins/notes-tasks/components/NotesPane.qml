pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services
import "../models" as Models

ColumnLayout {
    id: root
    required property var controller
    property string query: ""
    property string tag: ""
    property string selectedId: ""
    property bool archived: false
    signal deleteRequested(string kind, string recordId)
    signal captureRequested()
    signal tagRequested(string tag)
    function openRecord(id) { selectedId = id; editor.focusBody(); }
    Layout.minimumWidth: 0
    spacing: Tokens.spacing.medium
    RowLayout {
        Layout.fillWidth: true
        StyledText { text: qsTr("Your notes"); font: Tokens.font.title.medium }
        StyledText { text: notes.model.count.toString(); font: Tokens.font.label.medium; color: Colours.palette.m3primary }
        Item { Layout.fillWidth: true }
        ActionButton { visible: !!root.tag; text: "#" + root.tag; symbol: "close"; selected: true; motion: root.controller.motion; onClicked: root.tagRequested("") }
        ActionButton { text: root.archived ? qsTr("Archived") : ""; symbol: "archive"; description: qsTr("Show archived notes"); selected: root.archived; motion: root.controller.motion; onClicked: { root.archived = !root.archived; root.selectedId = ""; } }
    }
    FontMetrics { id: metrics; font: Tokens.font.body.small }
    Models.FilteredModel { id: notes; controller: root.controller; kind: "notes"; query: root.query; tag: root.tag; filter: root.archived ? "archived" : "active" }
    GridView {
        id: list
        objectName: "notesTasksNotesList"
        visible: !root.selectedId
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumWidth: 0
        clip: true; model: notes.model
        cellWidth: width / Math.max(1, Math.floor(width / (Tokens.padding.large * 14)))
        cellHeight: Math.max(Tokens.padding.large * (root.controller.settings.compact ? 8 : 11), metrics.height * (root.controller.settings.compact ? 5 : 7) + Tokens.padding.large * 2 + Tokens.spacing.medium)
        boundsBehavior: Flickable.StopAtBounds
        reuseItems: true
        ScrollBar.vertical: ScrollBar {}
        delegate: Item {
            id: tile
            required property string recordId
            required property int index
            width: list.cellWidth; height: list.cellHeight
            GridView.onReused: { opacity = 1; scale = 1; }
            NoteCard {
                id: card
                entry: root.controller.record("notes", tile.recordId)
                width: parent.width - Tokens.spacing.medium; height: implicitHeight
                tall: tile.index % 3 === 0
                controller: root.controller
                onEditRequested: id => root.selectedId = id
                onDeleteRequested: (kind, id) => root.deleteRequested(kind, id)
                Connections { target: root.controller; function onReset() { if (root.controller.record("notes", tile.recordId)) card.entry = Qt.binding(() => root.controller.record("notes", tile.recordId)); } function onChanged(kind, id, entry) { if (kind === "notes" && id === tile.recordId && entry) card.entry = Qt.binding(() => root.controller.record("notes", tile.recordId)); } }
            }
        }
        add: Transition { Anim { properties: "opacity"; from: 0; to: 1; duration: root.controller.motion ? Math.min(160, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } Anim { properties: "scale"; from: 0.97; to: 1; duration: root.controller.motion ? Math.min(180, Tokens.anim.durations.small) : 0; type: Anim.FastSpatial } }
        remove: Transition { Anim { properties: "opacity"; to: 0; duration: root.controller.motion ? Math.min(150, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } Anim { properties: "scale"; to: 0.97; duration: root.controller.motion ? Math.min(150, Tokens.anim.durations.small) : 0; type: Anim.FastSpatial } }
        NotesEmptyState {
            anchors.centerIn: parent; width: Math.min(parent.width - Tokens.padding.medium * 2, Tokens.padding.large * 20)
            visible: notes.model.count === 0
            motion: root.controller.motion
            title: root.query || root.tag ? qsTr("No matching notes") : root.archived ? qsTr("Archive is clear") : qsTr("Nothing captured yet")
            message: root.query || root.tag ? qsTr("Try another word or tag.") : root.archived ? qsTr("Archived notes will live here.") : qsTr("Write something before it disappears.")
            canCreate: !root.query && !root.tag && !root.archived
            onCreateRequested: root.captureRequested()
        }
    }
    NoteEditor { id: editor; visible: !!root.selectedId; Layout.fillWidth: true; Layout.fillHeight: true; controller: root.controller; recordId: root.selectedId; onCloseRequested: root.selectedId = ""; onDeleteRequested: (kind, id) => root.deleteRequested(kind, id) }
}

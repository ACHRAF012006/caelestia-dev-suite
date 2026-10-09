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
    property string selectedId: ""
    property bool archived: false
    signal deleteRequested(string kind, string recordId)
    function openRecord(id) { selectedId = id; }
    Layout.minimumWidth: 0
    spacing: Tokens.spacing.small
    RowLayout {
        Layout.fillWidth: true
        StyledText { text: qsTr("NOTES"); font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
        StyledText { text: notes.model.count.toString(); font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
        Item { Layout.fillWidth: true }
        ActionButton { text: root.archived ? qsTr("Archived") : qsTr("Active"); symbol: "archive"; selected: root.archived; motion: root.controller.motion; onClicked: { root.archived = !root.archived; root.selectedId = ""; } }
    }
    Models.FilteredModel { id: notes; controller: root.controller; kind: "notes"; query: root.query; filter: root.archived ? "archived" : "active" }
    ListView {
        id: list
        objectName: "notesTasksNotesList"
        visible: !root.selectedId
        Layout.fillWidth: true; Layout.fillHeight: true
        clip: true
        model: notes.model
        spacing: Tokens.spacing.small
        boundsBehavior: Flickable.StopAtBounds
        reuseItems: true
        ScrollBar.vertical: ScrollBar {}
        delegate: NoteCard {
            required property var model
            entry: model.entry
            required property string recordId
            width: list.width
            height: implicitHeight
            ListView.onReused: { height = Qt.binding(() => implicitHeight); opacity = 1; }
            controller: root.controller
            onEditRequested: id => root.selectedId = id
            onDeleteRequested: (kind, id) => root.deleteRequested(kind, id)
        }
        add: Transition { Anim { properties: "opacity"; from: 0; to: 1; duration: root.controller.motion ? Tokens.anim.durations.small : 0; type: Anim.FastEffects } }
        remove: Transition { Anim { properties: "opacity,height"; to: 0; duration: root.controller.motion ? Tokens.anim.durations.small : 0; type: Anim.FastEffects } }
        displaced: Transition { Anim { properties: "y"; duration: root.controller.motion ? Tokens.anim.durations.small : 0; type: Anim.FastSpatial } }
        StyledText { anchors.centerIn: parent; width: parent.width - Tokens.padding.large * 2; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; visible: notes.model.count === 0; text: root.query ? qsTr("No matching notes") : root.archived ? qsTr("No archived notes") : qsTr("A place for your thoughts.\nUse + to write your first note."); color: Colours.palette.m3onSurfaceVariant }
    }
    NoteEditor {
        visible: !!root.selectedId
        Layout.fillWidth: true; Layout.fillHeight: true
        controller: root.controller
        recordId: root.selectedId
        onCloseRequested: root.selectedId = ""
        onDeleteRequested: (kind, id) => root.deleteRequested(kind, id)
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services
import "../models" as Models
import "../models/Query.js" as Query

ColumnLayout {
    id: root
    required property var controller
    property string query: ""
    property string selectedId: ""
    property string filter: "active"
    property bool presentationActive: true
    signal deleteRequested(string kind, string recordId)
    function openRecord(id) { selectedId = id; }
    function moveRecord(id, direction) {
        // Manual order remains global across Today/Upcoming/filter boundaries.
        const ordered = Object.values(controller.tasks).sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
        const i = ordered.findIndex(row => row.id === id);
        if (direction < 0 && i > 0) controller.send({action: "reorder", kind: "tasks", id: id, before: ordered[i - 1].id});
        else if (direction > 0 && i < ordered.length - 1) controller.send({action: "reorder", kind: "tasks", id: id, before: ordered[i + 2]?.id ?? null});
    }
    Layout.minimumWidth: 0
    spacing: Tokens.spacing.small
    RowLayout {
        Layout.fillWidth: true
        StyledText { text: qsTr("TASKS"); font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
        StyledText { text: tasks.model.count.toString(); font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
        Item { Layout.fillWidth: true }
        ChoiceBox {
            id: filters
            objectName: "notesTasksTaskFilter"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredWidth: Tokens.padding.large * 10
            model: [qsTr("Open tasks"), qsTr("Today"), qsTr("Upcoming"), qsTr("Completed"), qsTr("All Tasks")]
            onActivated: { root.filter = ["active", "today", "upcoming", "completed", "all"][currentIndex]; root.selectedId = ""; }
        }
    }
    Models.FilteredModel { id: tasks; controller: root.controller; kind: "tasks"; query: root.query; filter: root.filter }
    // One event at the next midnight; never a repeating idle poll.
    Timer {
        id: midnight
        repeat: false
        function schedule() { const next = new Date(); next.setHours(24, 0, 0, 0); interval = Math.max(1, next.getTime() - Date.now()); restart(); }
        onTriggered: { tasks.day = Query.today(); schedule(); }
        Component.onCompleted: schedule()
    }
    onPresentationActiveChanged: if (presentationActive) tasks.day = Query.today()
    ListView {
        id: list
        objectName: "notesTasksTasksList"
        visible: !root.selectedId
        Layout.fillWidth: true; Layout.fillHeight: true
        model: tasks.model
        clip: true; spacing: Tokens.spacing.small
        boundsBehavior: Flickable.StopAtBounds
        reuseItems: true
        ScrollBar.vertical: ScrollBar {}
        section.property: "group"
        section.delegate: StyledText { required property string section; width: list.width; text: section; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant; topPadding: Tokens.padding.medium; bottomPadding: Tokens.padding.small }
        delegate: TaskRow {
            required property var model
            entry: model.entry
            required property string recordId
            width: list.width
            height: implicitHeight
            ListView.onReused: { height = Qt.binding(() => implicitHeight); opacity = 1; }
            controller: root.controller
            onEditRequested: id => root.selectedId = id
        }
        add: Transition { Anim { properties: "opacity"; from: 0; to: 1; duration: root.controller.motion ? Tokens.anim.durations.small : 0; type: Anim.FastEffects } }
        remove: Transition { Anim { properties: "opacity,height"; to: 0; duration: root.controller.motion ? Tokens.anim.durations.small : 0; type: Anim.FastEffects } }
        displaced: Transition { Anim { properties: "y"; duration: root.controller.motion ? Tokens.anim.durations.small : 0; type: Anim.FastSpatial } }
        StyledText { anchors.centerIn: parent; width: parent.width - Tokens.padding.large * 2; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; visible: tasks.model.count === 0; text: root.query ? qsTr("No matching tasks") : qsTr("Nothing here yet.\nUse + to capture a task."); color: Colours.palette.m3onSurfaceVariant }
    }
    TaskEditor {
        visible: !!root.selectedId
        Layout.fillWidth: true; Layout.fillHeight: true
        controller: root.controller
        recordId: root.selectedId
        onCloseRequested: root.selectedId = ""
        onDeleteRequested: (kind, id) => root.deleteRequested(kind, id)
        onMoveRequested: (id, direction) => root.moveRecord(id, direction)
    }
}

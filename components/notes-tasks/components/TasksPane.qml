pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services
import "../models" as Models
import "../models/Query.js" as Query

StyledRect {
    id: root
    required property var controller
    property string query: ""
    property string selectedId: ""
    property string filter: "active"
    property bool presentationActive: true
    property var known: ({})
    property int todayTotal: 0
    property int todayDone: 0
    signal deleteRequested(string kind, string recordId)
    signal captureRequested()
    function counts(entry) {
        if (!entry?.due.date || entry.due.date > tasks.day) return false;
        if (!entry.completed || entry.due.date === tasks.day) return true;
        const done = new Date(entry.completedAt);
        const completedDay = done.getFullYear() + "-" + ("0" + (done.getMonth() + 1)).slice(-2) + "-" + ("0" + done.getDate()).slice(-2);
        return completedDay === tasks.day;
    }
    function resetStats() {
        known = {}; todayTotal = 0; todayDone = 0;
        for (const entry of Object.values(controller.tasks)) updateStats(entry.id, entry);
    }
    function updateStats(id, entry) {
        const old = known[id];
        if (counts(old)) { --todayTotal; if (old.completed) --todayDone; }
        if (entry) known[id] = entry; else delete known[id];
        if (counts(entry)) { ++todayTotal; if (entry.completed) ++todayDone; }
    }
    function openRecord(id) { selectedId = id; editor.focusTitle(); }
    function moveRecord(id, direction) {
        const ordered = Object.values(controller.tasks).sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
        const i = ordered.findIndex(row => row.id === id);
        if (direction < 0 && i > 0) controller.send({action: "reorder", kind: "tasks", id: id, before: ordered[i - 1].id});
        else if (direction > 0 && i < ordered.length - 1) controller.send({action: "reorder", kind: "tasks", id: id, before: ordered[i + 2]?.id ?? null});
    }
    color: Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.extraLarge
    Models.FilteredModel { id: tasks; controller: root.controller; kind: "tasks"; query: root.query; filter: root.filter; completionDelay: root.controller.motion ? Math.min(180, Tokens.anim.durations.small) : 0; onDayChanged: root.resetStats() }
    Connections {
        target: root.controller
        function onReset() { root.resetStats(); }
        function onChanged(kind, id, entry) { if (kind === "tasks") root.updateStats(id, entry); }
    }
    Component.onCompleted: resetStats()
    Timer {
        id: midnight
        repeat: false
        function schedule() { const next = new Date(); next.setHours(24, 0, 0, 0); interval = Math.max(1, next.getTime() - Date.now()); restart(); }
        onTriggered: { tasks.day = Query.today(); schedule(); }
        Component.onCompleted: schedule()
    }
    onPresentationActiveChanged: if (presentationActive) tasks.day = Query.today()
    ColumnLayout {
        anchors.fill: parent; anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.small
        RowLayout {
            visible: !root.selectedId
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true; spacing: Tokens.spacing.extraSmall
                StyledText { text: qsTr("Today"); font: Tokens.font.title.large }
                StyledText { text: root.todayTotal ? qsTr("One thing at a time.") : qsTr("Make room for what matters."); Layout.fillWidth: true; wrapMode: Text.Wrap; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.label.small }
            }
            TaskProgress { objectName: "notesTasksProgress"; completed: root.todayDone; total: root.todayTotal; motion: root.controller.motion }
        }
        Flow {
            visible: !root.selectedId; Layout.fillWidth: true
            spacing: Tokens.spacing.extraSmall
            Repeater {
                model: [{key: "active", label: qsTr("Open")}, {key: "today", label: qsTr("Today")}, {key: "upcoming", label: qsTr("Next")}, {key: "completed", label: qsTr("Done")}, {key: "all", label: qsTr("All")}]
                ActionButton { required property var modelData; text: modelData.label; selected: root.filter === modelData.key; motion: root.controller.motion; onClicked: root.filter = modelData.key }
            }
        }
        ListView {
            id: list
            objectName: "notesTasksTasksList"
            visible: !root.selectedId
            Layout.fillWidth: true; Layout.fillHeight: true
            model: tasks.model
            clip: true; spacing: Tokens.spacing.extraSmall
            boundsBehavior: Flickable.StopAtBounds
            reuseItems: true
            ScrollBar.vertical: ScrollBar {}
            section.property: "group"
            section.delegate: StyledText { required property string section; width: list.width; text: section; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant; topPadding: Tokens.padding.small; bottomPadding: Tokens.padding.extraSmall }
            delegate: TaskRow {
                        required property string recordId
            id: card
            entry: root.controller.record("tasks", recordId)
            onRecordIdChanged: entry = Qt.binding(() => root.controller.record("tasks", recordId))
            Connections {
                target: root.controller
                function onReset() { if (root.controller.record("tasks", card.recordId)) card.entry = Qt.binding(() => root.controller.record("tasks", card.recordId)); }
                function onChanged(kind, id, entry) { if (kind === "tasks" && id === card.recordId && entry) card.entry = entry; }
            }
                width: list.width; height: implicitHeight
                ListView.onReused: { height = Qt.binding(() => implicitHeight); opacity = 1; }
                controller: root.controller
                onEditRequested: id => root.selectedId = id
            }
            add: Transition { Anim { properties: "opacity"; from: 0; to: 1; duration: root.controller.motion ? Math.min(160, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } }
            remove: Transition { Anim { properties: "opacity,height"; to: 0; duration: root.controller.motion ? Math.min(150, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } }
            displaced: Transition { Anim { properties: "y"; duration: root.controller.motion ? Math.min(180, Tokens.anim.durations.small) : 0; type: Anim.FastSpatial } }
            ColumnLayout {
                anchors.centerIn: parent; width: parent.width - Tokens.padding.small * 2
                visible: tasks.model.count === 0
                MaterialIcon { Layout.alignment: Qt.AlignHCenter; text: "task_alt"; fontStyle: Tokens.font.icon.large; color: Colours.palette.m3secondary }
                StyledText { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; text: root.query ? qsTr("No matching tasks") : qsTr("A little breathing room."); color: Colours.palette.m3onSurfaceVariant }
            }
        }
        RowLayout {
            visible: !root.selectedId; Layout.fillWidth: true
            StyledText { text: tasks.model.count + " " + qsTr("tasks"); font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant; Layout.fillWidth: true }
            ActionButton { symbol: "add"; description: qsTr("Capture a task"); motion: root.controller.motion; onClicked: root.captureRequested() }
        }
        TaskEditor { id: editor; visible: !!root.selectedId; Layout.fillWidth: true; Layout.fillHeight: true; controller: root.controller; recordId: root.selectedId; onCloseRequested: root.selectedId = ""; onDeleteRequested: (kind, id) => root.deleteRequested(kind, id); onMoveRequested: (id, direction) => root.moveRecord(id, direction) }
    }
}

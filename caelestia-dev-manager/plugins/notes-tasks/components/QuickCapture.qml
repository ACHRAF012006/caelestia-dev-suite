pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Caelestia.Config

ColumnLayout {
    id: root
    required property var controller
    property string kind: "tasks"
    property string requestId: ""
    signal captured(string kind, string recordId)
    signal closeRequested()
    function open(kind) { root.kind = kind; visible = true; input.forceActiveFocus(); }
    function capture() {
        if (kind === "tasks" && !input.text.trim()) return;
        requestId = Date.now().toString() + Math.random().toString();
        controller.send({action: "create", kind: kind, values: kind === "notes" ? {title: input.text} : {title: input.text.trim()}, requestId: requestId});
        input.text = "";
    }
    visible: false
    spacing: Tokens.spacing.small
    RowLayout {
        Layout.fillWidth: true
        ActionButton { text: qsTr("New Note"); symbol: "edit_note"; selected: root.kind === "notes"; motion: root.controller.motion; onClicked: { root.kind = "notes"; input.forceActiveFocus(); } }
        ActionButton { text: qsTr("New Task"); symbol: "add_task"; selected: root.kind === "tasks"; motion: root.controller.motion; onClicked: { root.kind = "tasks"; input.forceActiveFocus(); } }
        Item { Layout.fillWidth: true }
        ActionButton { symbol: "close"; description: qsTr("Close capture"); motion: root.controller.motion; onClicked: root.closeRequested() }
    }
    RowLayout {
        Layout.fillWidth: true
        InputField {
            id: input
            objectName: "notesTasksCapture"
            Layout.fillWidth: true
            enabled: root.controller.healthy
            placeholderText: root.kind === "notes" ? qsTr("Optional note title…") : qsTr("What needs doing? Enter to add")
            onAccepted: root.capture()
            Keys.onEscapePressed: root.closeRequested()
        }
        ActionButton { symbol: "add"; description: qsTr("Add"); enabled: root.controller.healthy; motion: root.controller.motion; onClicked: root.capture() }
    }
    Connections {
        target: root.controller
        function onCreated(requestId, kind, recordId) {
            if (requestId === root.requestId) { root.captured(kind, recordId); if (kind === "notes") root.closeRequested(); }
        }
    }
}

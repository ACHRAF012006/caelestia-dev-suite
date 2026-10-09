pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

StyledRect {
    id: root
    objectName: "notesTasksQuickCapture"
    required property var controller
    property string kind: "notes"
    property string requestId: ""
    property bool expanded: false
    property bool motion: controller.motion
    property real trailingWidth: 0
    signal captured(string kind, string recordId)
    signal closeRequested()
    function open(kind) { root.kind = kind; expanded = true; input.forceActiveFocus(); }
    function close() { expanded = false; input.focus = false; closeRequested(); }
    function capture() {
        if (!input.text.trim()) return;
        requestId = Date.now().toString() + Math.random().toString();
        controller.send({action: "create", kind: kind, values: kind === "notes" ? {text: input.text} : {title: input.text.trim()}, requestId: requestId});
        input.text = "";
    }
    implicitHeight: body.implicitHeight + Tokens.padding.large * 2
    radius: Tokens.rounding.extraLarge
    color: Colours.tPalette.m3surfaceContainer
    border.width: expanded ? 1 : 0
    border.color: Qt.alpha(Colours.palette.m3primary, 0.25)
    PaperMark { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: Tokens.padding.medium; visible: root.width > Tokens.padding.large * 28; opacity: 0.6; active: root.expanded; motion: root.motion }
    ColumnLayout {
        id: body
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.small
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumHeight: Tokens.padding.large * 2
            MaterialIcon { visible: root.trailingWidth < root.width * 0.6; text: "edit_note"; color: Colours.palette.m3primary; fontStyle: Tokens.font.icon.small }
            StyledText { visible: root.trailingWidth < root.width * 0.6; text: qsTr("Quick capture"); font: Tokens.font.title.small; color: Colours.palette.m3onSurfaceVariant; Layout.fillWidth: true }
            Item { Layout.preferredWidth: root.trailingWidth }
        }
        TextField {
            id: input
            objectName: "notesTasksCapture"
            Layout.fillWidth: true
            Layout.rightMargin: root.width > Tokens.padding.large * 28 ? Tokens.padding.large * 5 : 0
            enabled: root.controller.healthy
            font: Tokens.font.title.large
            color: Colours.palette.m3onSurface
            placeholderTextColor: Colours.palette.m3onSurfaceVariant
            selectionColor: Colours.palette.m3primary; selectedTextColor: Colours.palette.m3onPrimary
            placeholderText: root.kind === "notes" ? qsTr("What's on your mind?") : qsTr("What needs doing?")
            Accessible.name: placeholderText
            selectByMouse: true; padding: 0; background: null
            onActiveFocusChanged: if (activeFocus) root.expanded = true
            onAccepted: root.capture()
            Keys.onEscapePressed: root.close()
        }
        Reveal {
            expanded: root.expanded; motion: root.motion; Layout.fillWidth: true
            Flow {
                width: parent.width; spacing: Tokens.spacing.small
                ActionButton { text: qsTr("Note"); symbol: "note_stack"; selected: root.kind === "notes"; motion: root.motion; onClicked: root.open("notes") }
                ActionButton { text: qsTr("Task"); symbol: "task_alt"; selected: root.kind === "tasks"; motion: root.motion; onClicked: root.open("tasks") }
                ActionButton { text: qsTr("Save"); symbol: "arrow_forward"; selected: true; enabled: !!input.text.trim(); motion: root.motion; onClicked: root.capture() }
                ActionButton { text: qsTr("Cancel"); motion: root.motion; onClicked: root.close() }
            }
        }
    }
    Connections {
        target: root.controller
        function onCreated(requestId, kind, recordId) {
            if (requestId === root.requestId) { root.captured(kind, recordId); if (kind === "notes") root.close(); }
        }
    }
}

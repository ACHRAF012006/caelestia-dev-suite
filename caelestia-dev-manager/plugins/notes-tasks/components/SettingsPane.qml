pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

ScrollView {
    id: root
    required property var controller
    signal closeRequested()
    function preference(key, value) { const values = {}; values[key] = value; controller.send({action: "settings", values: values}); }
    clip: true
    ColumnLayout {
        width: parent.width
        spacing: Tokens.spacing.medium
        RowLayout {
            Layout.fillWidth: true
            ActionButton { symbol: "arrow_back"; description: qsTr("Back"); motion: root.controller.motion; onClicked: root.closeRequested() }
            StyledText { text: qsTr("Notes & Tasks settings"); font: Tokens.font.body.medium; Layout.fillWidth: true }
        }
        StyledText { text: qsTr("Default section") }
        ChoiceBox { Layout.fillWidth: true; model: [qsTr("Notes & Tasks"), qsTr("Notes"), qsTr("Tasks")]; currentIndex: ["both", "notes", "tasks"].indexOf(root.controller.settings.defaultSection); onActivated: root.preference("defaultSection", ["both", "notes", "tasks"][currentIndex]) }
        StyledText { text: qsTr("Notes order · pinned notes always first") }
        ChoiceBox { Layout.fillWidth: true; model: [qsTr("Recently edited"), qsTr("Recently created"), qsTr("Title")]; currentIndex: ["updated", "created", "title"].indexOf(root.controller.settings.noteSort); onActivated: root.preference("noteSort", ["updated", "created", "title"][currentIndex]) }
        StyledText { text: qsTr("Tasks order · within each date section") }
        ChoiceBox { Layout.fillWidth: true; model: [qsTr("Manual"), qsTr("Due date"), qsTr("Priority"), qsTr("Recently created")]; currentIndex: ["manual", "due", "priority", "created"].indexOf(root.controller.settings.taskSort); onActivated: root.preference("taskSort", ["manual", "due", "priority", "created"][currentIndex]) }
        PreferenceToggle { text: qsTr("Show completed in Open tasks"); checked: root.controller.settings.showCompleted; onToggled: root.preference("showCompleted", checked) }
        PreferenceToggle { text: qsTr("Animations"); checked: root.controller.settings.animation; onToggled: root.preference("animation", checked) }
        PreferenceToggle { text: qsTr("Compact cards"); checked: root.controller.settings.compact; onToggled: root.preference("compact", checked) }
        PreferenceToggle { text: qsTr("Confirm permanent deletion"); checked: root.controller.settings.confirmDelete; onToggled: root.preference("confirmDelete", checked) }
    }
}

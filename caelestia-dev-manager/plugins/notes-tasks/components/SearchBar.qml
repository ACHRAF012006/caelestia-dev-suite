pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

RowLayout {
    id: root
    property alias text: input.text
    function focusSearch() { input.forceActiveFocus(); }
    spacing: Tokens.spacing.small
    MaterialIcon { text: "search"; fontStyle: Tokens.font.icon.small; color: Colours.palette.m3onSurfaceVariant }
    InputField {
        id: input
        objectName: "notesTasksSearch"
        Layout.fillWidth: true
        placeholderText: qsTr("Search notes, tasks, tags")
        Accessible.name: placeholderText
        Keys.onEscapePressed: text = ""
    }
    ActionButton { visible: input.text.length > 0; symbol: "close"; description: qsTr("Clear search"); onClicked: input.text = "" }
}

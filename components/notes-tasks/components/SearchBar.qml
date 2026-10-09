pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

StyledRect {
    id: root
    property alias text: input.text
    property bool motion: true
    property bool opened: false
    property real availableWidth: Tokens.padding.large * 21
    readonly property bool expanded: opened || input.activeFocus || text.length > 0
    property real reveal: expanded ? 1 : 0
    readonly property string query: debounce.query
    function focusSearch() { opened = true; input.forceActiveFocus(); }
    implicitWidth: searchButton.implicitWidth + (Math.max(searchButton.implicitWidth, availableWidth) - searchButton.implicitWidth) * reveal
    implicitHeight: searchButton.implicitHeight
    radius: Tokens.rounding.full
    color: expanded ? Colours.tPalette.m3surfaceContainerHighest : "transparent"
    Behavior on color { ColorAnimation { duration: root.motion ? Math.min(160, Tokens.anim.durations.small) : 0 } }
    clip: true
    Behavior on reveal { Anim { duration: root.motion ? Math.min(180, Tokens.anim.durations.small) : 0; type: Anim.FastSpatial } }
    Timer { id: debounce; property string query: ""; interval: 100; onTriggered: query = input.text }
    RowLayout {
        anchors.fill: parent; spacing: 0
        ActionButton { id: searchButton; symbol: "search"; description: qsTr("Search · Ctrl+F"); motion: root.motion; onClicked: root.focusSearch() }
        TextField {
            id: input
            objectName: "notesTasksSearch"
            Layout.fillWidth: true; Layout.minimumWidth: 0
            visible: root.reveal > 0
            opacity: root.reveal
            font: Tokens.font.body.small; color: Colours.palette.m3onSurface
            placeholderTextColor: Colours.palette.m3onSurfaceVariant
            selectionColor: Colours.palette.m3primary; selectedTextColor: Colours.palette.m3onPrimary
            placeholderText: qsTr("Search notes, tasks, tags")
            Accessible.name: placeholderText
            selectByMouse: true; background: null
            onTextChanged: debounce.restart()
            Keys.onEscapePressed: { text = ""; root.opened = false; focus = false; }
        }
        ActionButton { visible: root.expanded; symbol: "close"; description: qsTr("Clear and close search"); motion: root.motion; onClicked: { input.text = ""; input.focus = false; root.opened = false; } }
    }
}

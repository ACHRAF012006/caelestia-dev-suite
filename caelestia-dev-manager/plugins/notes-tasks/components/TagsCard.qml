pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

StyledRect {
    id: root
    required property var controller
    property string selectedTag: ""
    property var tags: []
    property int pinned: 0
    signal tagRequested(string tag)
    function refresh() {
        const counts = {}; let pins = 0;
        for (const entry of Object.values(controller.notes)) {
            if (entry.archived) continue;
            if (entry.pinned) ++pins;
            for (const tag of entry.tags) counts[tag] = (counts[tag] || 0) + 1;
        }
        pinned = pins;
        tags = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b)).slice(0, 8);
    }
    color: Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.extraLarge
    implicitHeight: content.implicitHeight + Tokens.padding.large * 2
    ColumnLayout {
        id: content
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.small
        RowLayout {
            Layout.fillWidth: true
            MaterialIcon { text: "label"; fontStyle: Tokens.font.icon.small; color: Colours.palette.m3secondary }
            StyledText { text: qsTr("Little connections"); font: Tokens.font.title.small; Layout.fillWidth: true }
            MaterialIcon { visible: root.pinned > 0; text: "keep"; fontStyle: Tokens.font.icon.small; color: Colours.palette.m3secondary }
            StyledText { visible: root.pinned > 0; text: root.pinned; color: Colours.palette.m3secondary; font: Tokens.font.label.small }
        }
        Flow {
            Layout.fillWidth: true; spacing: Tokens.spacing.extraSmall
            Repeater { model: root.tags; ActionButton { required property string modelData; text: "#" + modelData; selected: root.selectedTag === modelData; motion: root.controller.motion; onClicked: root.tagRequested(root.selectedTag === modelData ? "" : modelData) } }
        }
        StyledText { visible: !root.tags.length; text: qsTr("Add tags inside a note to connect ideas."); Layout.fillWidth: true; wrapMode: Text.Wrap; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
        ActionButton { visible: !!root.selectedTag && root.tags.indexOf(root.selectedTag) < 0; text: "#" + root.selectedTag; symbol: "close"; selected: true; motion: root.controller.motion; onClicked: root.tagRequested("") }
    }
    Component.onCompleted: refresh()
    Connections { target: root.controller; function onReset() { root.refresh(); } function onChanged(kind, id, entry) { if (kind === "notes") root.refresh(); } }
}

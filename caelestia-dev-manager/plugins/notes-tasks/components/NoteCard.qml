pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

StyledRect {
    id: root
    objectName: "notesTasksNoteCard"
    required property var entry
    required property var controller
    property bool tall: false
    signal editRequested(string recordId)
    signal deleteRequested(string kind, string recordId)
    implicitHeight: Math.max(Tokens.padding.large * (controller.settings.compact ? 7 : tall || entry.pinned ? 10 : 8), metrics.height * (controller.settings.compact ? 5 : tall || entry.pinned ? 7 : 6) + Tokens.padding.large * 2)
    radius: entry.pinned ? Tokens.rounding.extraLarge * 1.2 : Tokens.rounding.extraLarge
    color: entry.pinned ? Qt.tint(Colours.tPalette.m3surfaceContainer, Qt.alpha(Colours.palette.m3tertiary, 0.07)) : hover.hovered ? Colours.tPalette.m3surfaceContainerHigh : Colours.tPalette.m3surfaceContainer
    Accessible.role: Accessible.Button
    Accessible.name: entry.title || entry.text
    activeFocusOnTab: true
    Keys.onReturnPressed: root.editRequested(root.entry.id)
    FontMetrics { id: metrics; font: Tokens.font.body.small }
    HoverHandler { id: hover }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.editRequested(root.entry.id) }
    Behavior on color { ColorAnimation { duration: root.controller.motion ? Math.min(160, Tokens.anim.durations.small) : 0 } }
    Rectangle {
        visible: root.entry.pinned
        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: Tokens.padding.medium
        width: Tokens.padding.large * 2; height: width; radius: width * 0.38; rotation: -15
        color: Colours.palette.m3tertiaryContainer; opacity: 0.35
    }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.small
        RowLayout {
            Layout.fillWidth: true
            StyledText { Layout.fillWidth: true; text: root.entry.title || (root.entry.text.split("\n")[0] || qsTr("Untitled note")); maximumLineCount: 2; wrapMode: Text.Wrap; elide: Text.ElideRight; font: Tokens.font.title.medium }
            ActionButton { symbol: "keep"; visible: root.entry.pinned || hover.hovered || root.activeFocus; selected: root.entry.pinned; description: root.entry.pinned ? qsTr("Unpin") : qsTr("Pin"); motion: root.controller.motion; rotation: root.entry.pinned ? -15 : 0; Behavior on rotation { Anim { duration: root.controller.motion ? Math.min(180, Tokens.anim.durations.small) : 0; type: Anim.FastSpatial } } onClicked: root.controller.edit("notes", root.entry.id, {pinned: !root.entry.pinned}) }
        }
        StyledText {
            Layout.fillWidth: true; Layout.fillHeight: true
            text: root.entry.title ? root.entry.text : root.entry.text.split("\n").slice(1).join("\n")
            maximumLineCount: root.controller.settings.compact ? 2 : root.tall ? 5 : 3
            wrapMode: Text.Wrap; elide: Text.ElideRight
            color: Colours.palette.m3onSurfaceVariant
        }
        RowLayout {
            Layout.fillWidth: true
            StyledText { Layout.fillWidth: true; text: root.entry.tags.length ? "#" + root.entry.tags[0] : root.entry.pinned ? qsTr("Pinned") : ""; color: root.entry.pinned ? Colours.palette.m3secondary : Colours.palette.m3primary; font: Tokens.font.label.small; elide: Text.ElideRight }
            StyledText { text: new Date(root.entry.updatedAt).toLocaleTimeString(Qt.locale(), Locale.ShortFormat); font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant; opacity: hover.hovered || root.activeFocus ? 1 : 0.55 }
        }
    }
}

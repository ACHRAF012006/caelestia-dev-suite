pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

Rectangle {
    id: root
    required property var entry
    required property var controller
    signal editRequested(string recordId)
    signal deleteRequested(string kind, string recordId)
    implicitHeight: body.implicitHeight + Tokens.padding.medium * 2
    radius: Tokens.rounding.small
    color: Colours.palette.m3surfaceContainer
    ColumnLayout {
        id: body
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: Tokens.padding.medium
        spacing: Tokens.spacing.small
        RowLayout {
            Layout.fillWidth: true
            ActionButton { symbol: root.entry.pinned ? "keep" : "keep_off"; description: root.entry.pinned ? qsTr("Unpin") : qsTr("Pin"); selected: root.entry.pinned; motion: root.controller.motion; onClicked: root.controller.edit("notes", root.entry.id, {pinned: !root.entry.pinned}) }
            StyledText { Layout.fillWidth: true; text: root.entry.title || qsTr("Untitled note"); elide: Text.ElideRight; font: Tokens.font.body.medium }
            ActionButton { symbol: "edit"; description: qsTr("Edit note"); motion: root.controller.motion; onClicked: root.editRequested(root.entry.id) }
            ActionButton {
                symbol: "more_horiz"; description: qsTr("Note actions"); motion: root.controller.motion
                onClicked: actions.visible = !actions.visible
            }
        }
        StyledText {
            Layout.fillWidth: true
            text: root.entry.text || qsTr("Add your thoughts…")
            maximumLineCount: root.controller.settings.compact ? 1 : 3
            wrapMode: Text.Wrap; elide: Text.ElideRight
            color: Colours.palette.m3onSurfaceVariant
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.editRequested(root.entry.id) }
        }
        StyledText { visible: !!root.entry.tags.length && !root.controller.settings.compact; Layout.fillWidth: true; text: root.entry.tags.map(tag => "#" + tag).join("  "); elide: Text.ElideRight; color: Colours.palette.m3primary; font: Tokens.font.label.small }
        Flow {
            id: actions
            visible: false; Layout.fillWidth: true
            spacing: Tokens.spacing.small
            ActionButton { text: qsTr("Duplicate"); symbol: "content_copy"; motion: root.controller.motion; onClicked: { root.controller.send({action: "duplicate", kind: "notes", id: root.entry.id}); actions.visible = false; } }
            ActionButton { text: root.entry.archived ? qsTr("Unarchive") : qsTr("Archive"); symbol: "archive"; motion: root.controller.motion; onClicked: root.controller.edit("notes", root.entry.id, {archived: !root.entry.archived}) }
            ActionButton { text: qsTr("Delete"); symbol: "delete"; destructive: true; motion: root.controller.motion; onClicked: root.deleteRequested("notes", root.entry.id) }
        }
    }
}

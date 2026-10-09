import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

ColumnLayout {
    id: root
    property bool motion: true
    property string title: qsTr("Nothing captured yet")
    property string message: qsTr("Write something before it disappears.")
    property bool canCreate: true
    signal createRequested()
    spacing: Tokens.spacing.small
    PaperMark { Layout.alignment: Qt.AlignHCenter; active: create.hovered; motion: root.motion }
    StyledText { Layout.fillWidth: true; text: root.title; font: Tokens.font.title.medium; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter }
    StyledText { Layout.fillWidth: true; text: root.message; color: Colours.palette.m3onSurfaceVariant; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter }
    ActionButton { id: create; visible: root.canCreate; Layout.alignment: Qt.AlignHCenter; text: qsTr("Create note"); symbol: "add"; selected: true; motion: root.motion; onClicked: root.createRequested() }
}

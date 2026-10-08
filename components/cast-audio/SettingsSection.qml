import QtQuick
import QtQuick.Layouts
import Caelestia.Config

Rectangle {
    id: root
    property Theme theme: Theme {}
    property string title: ""
    property string description: ""
    default property alias body: content.data
    implicitHeight: layout.implicitHeight + 32
    radius: Tokens.rounding.large
    color: theme.card
    border.width: 1
    border.color: theme.outline
    ColumnLayout {
        id: layout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 16
        spacing: 8
        CastText { text: root.title; font.pixelSize: 17; font.weight: Font.DemiBold }
        CastText { Layout.fillWidth: true; visible: root.description.length > 0; text: root.description; color: root.theme.secondary; wrapMode: Text.WordWrap }
        ColumnLayout { id: content; Layout.fillWidth: true; spacing: 10 }
    }
}

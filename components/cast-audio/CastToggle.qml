pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Caelestia.Config

Rectangle {
    id: root
    required property var controller
    property Theme theme: Theme {}
    readonly property string status: controller.snapshot.state || "Off"
    implicitWidth: 280
    implicitHeight: 68
    radius: Tokens.rounding.large
    color: status === "Casting" ? theme.selected : theme.card
    Accessible.role: Accessible.Button
    Accessible.name: "Cast Audio: " + subtitle.text

    RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12
        CastIcon {
            tint: root.theme.foreground
            Layout.preferredWidth: 28
            Layout.preferredHeight: 28
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            CastText { text: qsTr("Cast Audio"); font: Tokens.font.body.medium }
            CastText {
                id: subtitle
                Layout.fillWidth: true
                elide: Text.ElideRight
                color: root.theme.secondary
                text: root.status === "Casting" ? root.controller.snapshot.receiver
                    : root.status === "Off" && root.controller.snapshot.scanning ? qsTr("Searching…")
                    : root.status === "Off" ? qsTr("Not connected") : root.status
            }
        }
        ActionButton {
            text: "⌄"
            implicitWidth: 44
            implicitHeight: 44
            Accessible.name: qsTr("Choose Cast receiver")
            onClicked: root.controller.openPanel()
        }
    }
    MouseArea {
        anchors.fill: parent
        anchors.rightMargin: 60
        onClicked: root.controller.toggle()
    }
}

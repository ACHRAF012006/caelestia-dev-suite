pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Caelestia.Config

Rectangle {
    id: root
    required property var controller
    property Theme theme: Theme {}
    readonly property var state: controller.snapshot
    readonly property bool expanded: controller.menuExpanded
    property real expansionProgress: expanded ? 1 : 0
    readonly property bool idle: state.state === "Off" || state.state === "Error"
    objectName: "castAudioMenu"
    implicitWidth: 300
    implicitHeight: layout.implicitHeight + 20
    radius: Tokens.rounding.large
    color: state.state === "Casting" ? theme.selected : theme.card
    onExpandedChanged: controller.menuVisible(visible && expanded)
    onVisibleChanged: controller.menuVisible(visible && expanded)
    Component.onDestruction: controller.menuVisible(false)

    Behavior on expansionProgress {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: 10
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            Layout.bottomMargin: 8
            ActionButton {
                objectName: "castAudioExpand"
                Layout.fillWidth: true
                text: qsTr("Cast Audio") + "  " + (root.expanded ? "⌃" : "⌄")
                Accessible.name: root.expanded ? qsTr("Collapse Cast receivers") : qsTr("Choose Cast receiver")
                onClicked: root.controller.setMenuExpanded(!root.expanded)
            }
            ActionButton {
                objectName: "castAudioSettings"
                text: qsTr("Settings")
                onClicked: root.controller.openSettings()
            }
        }
        CastText {
            Layout.fillWidth: true
            text: root.state.state === "Casting" ? qsTr("Casting to ") + root.state.receiver : root.state.state === "Connecting…" ? qsTr("Connecting…") : qsTr("Not connected")
            elide: Text.ElideRight
            color: root.theme.secondary
        }
        Item {
            Layout.fillWidth: true
            implicitHeight: (details.implicitHeight + 8) * root.expansionProgress
            clip: true
            enabled: root.expanded

            ColumnLayout {
                id: details
                anchors.left: parent.left
                anchors.right: parent.right
                y: 8
                height: implicitHeight
                spacing: 8
                visible: root.expansionProgress > 0
                opacity: root.expansionProgress
                CastText {
                    Layout.fillWidth: true
                    text: root.state.message || qsTr("Select a receiver")
                    wrapMode: Text.WordWrap
                }
                RowLayout {
                    ActionButton {
                        text: root.state.scanning ? qsTr("Searching…") : qsTr("Refresh devices")
                        enabled: !root.state.scanning && root.idle
                        onClicked: root.controller.send({action: "refresh"})
                    }
                    ActionButton {
                        text: qsTr("Stop casting")
                        visible: !root.idle
                        enabled: root.state.state !== "Stopping…"
                        onClicked: root.controller.send({action: "stop"})
                    }
                    ActionButton {
                        text: qsTr("Restart helper")
                        visible: root.state.state === "Error"
                        onClicked: root.controller.restartHelper()
                    }
                }
                Controls.ScrollView {
                    id: devicesScroll
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(240, receivers.implicitHeight)
                    visible: (root.state.devices || []).length > 0
                    contentWidth: availableWidth
                    ColumnLayout {
                        id: receivers
                        width: devicesScroll.availableWidth
                        spacing: 6
                        Repeater {
                            model: root.state.devices || []
                            delegate: ActionButton {
                                required property var modelData
                                objectName: "castAudioReceiver"
                                Layout.fillWidth: true
                                text: modelData.name + (modelData.manual ? qsTr(" · IP") : "")
                                enabled: root.idle && modelData.supported
                                Controls.ToolTip.visible: hovered
                                Controls.ToolTip.text: modelData.detail || ""
                                onClicked: root.controller.send({action: "start", id: modelData.id})
                            }
                        }
                    }
                }
                Controls.Slider {
                    Layout.fillWidth: true
                    visible: root.state.state === "Casting"
                    from: 0; to: 100; stepSize: 1
                    value: root.state.volume || 0
                    onPressedChanged: if (!pressed) root.controller.send({action: "volume", value: Math.round(value)})
                    Accessible.name: qsTr("Receiver volume")
                }
                CastText {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: root.theme.secondary
                    text: qsTr("Streams this output's audio. Closing the menu keeps casting.")
                }
            }
        }
    }
}

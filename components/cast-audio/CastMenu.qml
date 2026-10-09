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
    readonly property bool casting: state.state === "Casting"
    readonly property string statusText: casting ? qsTr("Casting to ") + state.receiver : state.state === "Connecting…" ? qsTr("Connecting to ") + state.receiver : state.state === "Stopping…" ? qsTr("Disconnecting…") : state.state === "Error" ? qsTr("Needs attention") : qsTr("Choose a speaker")
    objectName: "castAudioMenu"
    implicitWidth: 300
    implicitHeight: layout.implicitHeight + 16
    radius: Tokens.rounding.large
    color: theme.surface
    border.width: 1
    border.color: casting ? theme.accent : theme.outline
    onExpandedChanged: controller.menuVisible(visible && expanded)
    onVisibleChanged: controller.menuVisible(visible && expanded)
    Component.onDestruction: controller.menuVisible(false)

    Behavior on expansionProgress { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    Behavior on border.color { ColorAnimation { duration: 180 } }

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: 8
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            spacing: 4
            ActionButton {
                objectName: "castAudioExpand"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                padding: Tokens.padding.small
                flat: true
                Accessible.name: root.expanded ? qsTr("Collapse Cast receivers") : qsTr("Choose Cast receiver")
                onClicked: root.controller.setMenuExpanded(!root.expanded)
                contentItem: RowLayout {
                    spacing: Tokens.spacing.small
                    CastIcon { objectName: "castAudioHeaderIcon"; Layout.alignment: Qt.AlignVCenter; Layout.preferredWidth: Tokens.font.icon.small.pixelSize; Layout.preferredHeight: Tokens.font.icon.small.pixelSize; tint: root.casting ? root.theme.accent : root.theme.foreground }
                    ColumnLayout {
                        objectName: "castAudioHeaderLabels"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.alignment: Qt.AlignVCenter
                        spacing: Tokens.spacing.extraSmall
                        CastText { objectName: "castAudioTitle"; Layout.fillWidth: true; text: qsTr("Cast Audio"); font.family: Tokens.font.body.medium.family; font.pixelSize: Tokens.font.body.medium.pixelSize; font.weight: Font.DemiBold; elide: Text.ElideRight }
                        CastText { objectName: "castAudioStatus"; Layout.fillWidth: true; text: root.statusText; font: Tokens.font.label.small; color: root.state.state === "Error" ? root.theme.error : root.theme.secondary; elide: Text.ElideRight }
                    }
                    CastText {
                        objectName: "castAudioChevron"
                        Layout.alignment: Qt.AlignVCenter
                        text: "expand_more"
                        font: Tokens.font.icon.small
                        color: root.theme.secondary
                        rotation: 180 * root.expansionProgress
                    }
                }
            }
            ActionButton {
                objectName: "castAudioSettings"
                text: qsTr("Settings")
                flat: true
                Layout.alignment: Qt.AlignVCenter
                font: Tokens.font.label.small
                Accessible.name: qsTr("Cast Audio settings")
                onClicked: root.controller.openSettings()
            }
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
                spacing: 6
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.theme.outline }
                SourcePicker {
                    compact: true
                    Layout.fillWidth: true
                    visible: root.idle
                    sources: root.state.sources || []
                    selectedId: (root.state.settings || {}).source || "default"
                    onChosen: identity => root.controller.send({action: "settings", values: {source: identity}})
                }
                CastText {
                    Layout.fillWidth: true
                    visible: !root.idle
                    text: root.state.source_name || qsTr("Desktop audio")
                    color: root.theme.secondary
                    elide: Text.ElideRight
                }
                CastText {
                    Layout.fillWidth: true
                    visible: root.state.state === "Error"
                    text: root.state.message || qsTr("Open Settings for details")
                    color: root.state.state === "Error" ? root.theme.error : root.theme.secondary
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: root.idle
                    CastText { Layout.fillWidth: true; text: qsTr("Speakers"); font.weight: Font.DemiBold }
                    ActionButton {
                        objectName: "castAudioRefresh"
                        visible: root.idle
                        implicitHeight: 30
                        text: root.state.scanning ? qsTr("Searching…") : qsTr("Refresh")
                        flat: true
                        enabled: !root.state.scanning && root.idle
                        onClicked: root.controller.send({action: "refresh"})
                    }
                }
                Controls.ScrollView {
                    id: devicesScroll
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(144, receivers.implicitHeight)
                    visible: root.idle && (root.state.devices || []).length > 0
                    contentWidth: availableWidth
                    palette.highlight: root.theme.accent
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
                                implicitHeight: 36
                                text: modelData.name
                                active: !root.idle && root.state.receiver === modelData.name
                                enabled: root.idle && modelData.supported
                                Controls.ToolTip.visible: hovered
                                Controls.ToolTip.text: modelData.detail || modelData.host || ""
                                onClicked: root.controller.send({action: "start", id: modelData.id})
                            }
                        }
                    }
                }
                CastText {
                    Layout.fillWidth: true
                    visible: !root.state.scanning && (root.state.devices || []).length === 0 && root.idle
                    text: qsTr("No speakers · add IP in Settings")
                    wrapMode: Text.WordWrap
                    color: root.theme.secondary
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: root.casting
                    CastText { text: qsTr("Volume") }
                    Item { Layout.fillWidth: true }
                    CastText { text: Math.round(root.state.volume || 0) + "%"; color: root.theme.secondary }
                    ActionButton {
                        text: root.state.muted ? qsTr("Unmute") : qsTr("Mute")
                        flat: true
                        onClicked: root.controller.send({action: "mute", value: !root.state.muted})
                    }
                }
                Controls.Slider {
                    id: volume
                    Layout.fillWidth: true
                    visible: root.casting
                    from: 0; to: 100; stepSize: 1
                    value: root.state.volume || 0
                    palette.highlight: root.theme.accent
                    onPressedChanged: if (!pressed) root.controller.send({action: "volume", value: Math.round(value)})
                    Accessible.name: qsTr("Receiver volume")
                    background: Rectangle {
                        x: volume.leftPadding; y: volume.topPadding + volume.availableHeight / 2 - height / 2
                        width: volume.availableWidth; height: 4; radius: 2; color: root.theme.outline
                        Rectangle { width: volume.visualPosition * parent.width; height: parent.height; radius: 2; color: root.theme.accent }
                    }
                    handle: Rectangle {
                        x: volume.leftPadding + volume.visualPosition * (volume.availableWidth - width)
                        y: volume.topPadding + volume.availableHeight / 2 - height / 2
                        implicitWidth: 18; implicitHeight: 18; radius: 9
                        color: root.theme.accent
                        border.width: volume.visualFocus ? 2 : 0; border.color: root.theme.foreground
                    }
                }
                ActionButton {
                    Layout.fillWidth: true
                    text: root.state.state === "Stopping…" ? qsTr("Disconnecting…") : qsTr("Disconnect")
                    visible: !root.idle
                    enabled: root.state.state !== "Stopping…"
                    onClicked: root.controller.send({action: "stop"})
                }
                ActionButton {
                    Layout.fillWidth: true
                    text: qsTr("Restart helper")
                    visible: root.state.state === "Error"
                    onClicked: root.controller.restartHelper()
                }
            }
        }
    }
}

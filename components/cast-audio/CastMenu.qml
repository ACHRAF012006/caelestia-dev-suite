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
    implicitHeight: layout.implicitHeight + 20
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
        anchors.margins: 10
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            spacing: 4
            ActionButton {
                objectName: "castAudioExpand"
                Layout.fillWidth: true
                implicitHeight: 54
                flat: true
                Accessible.name: root.expanded ? qsTr("Collapse Cast receivers") : qsTr("Choose Cast receiver")
                onClicked: root.controller.setMenuExpanded(!root.expanded)
                contentItem: RowLayout {
                    spacing: 10
                    CastIcon { Layout.preferredWidth: 24; Layout.preferredHeight: 24; tint: root.casting ? root.theme.accent : root.theme.foreground }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        CastText { text: qsTr("Cast Audio"); font.weight: Font.DemiBold; font.pixelSize: 15 }
                        CastText { Layout.fillWidth: true; text: root.statusText; font.pixelSize: 11; color: root.state.state === "Error" ? root.theme.error : root.theme.secondary; elide: Text.ElideRight }
                    }
                    CastText {
                        text: "⌄"
                        font.pixelSize: 20
                        color: root.theme.secondary
                        rotation: 180 * root.expansionProgress
                    }
                }
            }
            ActionButton {
                objectName: "castAudioSettings"
                text: qsTr("Settings")
                flat: true
                font.pixelSize: 11
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
                spacing: 10
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.theme.outline }
                RowLayout {
                    Layout.fillWidth: true
                    visible: root.idle
                    CastText { Layout.fillWidth: true; text: qsTr("What to cast"); font.weight: Font.DemiBold }
                    ActionButton { objectName: "castAudioRefreshApps"; text: qsTr("Update apps"); flat: true; onClicked: root.controller.send({action: "refresh-audio"}) }
                }
                SourcePicker {
                    Layout.fillWidth: true
                    visible: root.idle
                    sources: root.state.sources || []
                    selectedId: (root.state.settings || {}).source || "default"
                    onChosen: identity => root.controller.send({action: "settings", values: {source: identity}})
                }
                Controls.ComboBox {
                    objectName: "castAudioLatency"
                    Layout.fillWidth: true
                    visible: root.idle && (root.state.settings || {}).format !== "mp3"
                    model: [qsTr("Fast · lowest delay"), qsTr("Balanced · more headroom")]
                    currentIndex: (root.state.settings || {}).latency === "balanced" ? 1 : 0
                    palette.button: root.theme.raised
                    palette.buttonText: root.theme.foreground
                    palette.window: root.theme.card
                    palette.windowText: root.theme.foreground
                    palette.highlight: root.theme.accent
                    palette.highlightedText: root.theme.accentText
                    onActivated: index => root.controller.send({action: "settings", values: {latency: index === 0 ? "fast" : "balanced"}})
                }
                Rectangle {
                    Layout.fillWidth: true
                    visible: !root.idle
                    implicitHeight: sharing.implicitHeight + 24
                    radius: 12
                    color: root.theme.selected
                    ColumnLayout {
                        id: sharing
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12
                        spacing: 4
                        CastText { text: qsTr("NOW SHARING"); font.pixelSize: 10; font.letterSpacing: 1; color: root.theme.selectedText }
                        CastText { Layout.fillWidth: true; text: root.state.source_name || qsTr("Desktop audio"); font.weight: Font.DemiBold; elide: Text.ElideRight; color: root.theme.selectedText }
                        CastText { text: "→ " + (root.state.receiver || qsTr("Speaker")); color: root.theme.selectedText; font.pixelSize: 11 }
                    }
                }
                CastText {
                    Layout.fillWidth: true
                    text: root.state.message || qsTr("Select a receiver")
                    color: root.state.state === "Error" ? root.theme.error : root.theme.secondary
                    wrapMode: Text.WordWrap
                }
                RowLayout {
                    Layout.fillWidth: true
                    CastText { Layout.fillWidth: true; text: qsTr("Speakers"); font.weight: Font.DemiBold }
                    ActionButton {
                        objectName: "castAudioRefresh"
                        visible: root.idle
                        text: root.state.scanning ? qsTr("Searching…") : qsTr("Refresh")
                        flat: true
                        enabled: !root.state.scanning && root.idle
                        onClicked: root.controller.send({action: "refresh"})
                    }
                }
                Controls.ScrollView {
                    id: devicesScroll
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(240, receivers.implicitHeight)
                    visible: (root.state.devices || []).length > 0
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
                                implicitHeight: 58
                                text: modelData.name
                                subtitle: modelData.supported ? (modelData.manual ? qsTr("Saved IP · ") + modelData.host : modelData.detail || qsTr("Google Cast")) : qsTr("Unsupported receiver")
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
                    text: qsTr("No speakers found. Refresh, or add a receiver's IP address in Settings.")
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
                CastText {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    font.pixelSize: 11
                    color: root.theme.secondary
                    text: qsTr("Closing this menu keeps your audio playing.")
                }
            }
        }
    }
}

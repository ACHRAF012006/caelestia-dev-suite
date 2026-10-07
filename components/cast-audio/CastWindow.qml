pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Quickshell
import Caelestia.Config

FloatingWindow {
    id: root
    required property var controller
    property Theme theme: Theme {}
    readonly property var state: controller.snapshot
    readonly property var settings: state.settings || {}
    readonly property bool active: state.state === "Casting"
    readonly property bool idle: state.state === "Off" || state.state === "Error"
    title: qsTr("Cast Audio")
    implicitWidth: 510
    implicitHeight: 650
    minimumSize: Qt.size(360, 360)
    color: theme.surface

    Controls.ScrollView {
        id: scroll
        anchors.fill: parent
        anchors.margins: 20
        contentWidth: availableWidth
        palette.window: root.theme.surface
        palette.base: root.theme.card
        palette.text: root.theme.foreground
        palette.windowText: root.theme.foreground
        palette.buttonText: root.theme.foreground
        palette.button: root.theme.card
        palette.highlight: root.theme.accent
        ColumnLayout {
            width: scroll.availableWidth
            spacing: 12
            CastToggle { Layout.fillWidth: true; controller: root.controller }
            CastText {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: root.state.message || qsTr("Not connected")
            }
            CastText {
                Layout.fillWidth: true
                color: root.theme.secondary
                wrapMode: Text.WordWrap
                text: qsTr("Casts everything playing through one output monitor. Local sound stays on. Expect several seconds of delay.")
            }
            RowLayout {
                ActionButton {
                    text: root.state.scanning ? qsTr("Searching…") : qsTr("Refresh devices")
                    enabled: !root.state.scanning && root.idle
                    onClicked: root.controller.send({action: "refresh"})
                }
                ActionButton {
                    text: qsTr("Stop casting")
                    enabled: !root.idle && root.state.state !== "Stopping…"
                    onClicked: root.controller.send({action: "stop"})
                }
            }
            Repeater {
                model: root.state.devices || []
                delegate: ActionButton {
                    required property var modelData
                    Layout.fillWidth: true
                    text: modelData.name + (root.settings.last === modelData.id ? qsTr(" · Last used") : "")
                    enabled: root.idle && modelData.supported
                    onClicked: root.controller.send({action: "start", id: modelData.id})
                    Controls.ToolTip.visible: hovered
                    Controls.ToolTip.text: modelData.detail
                }
            }
            CastText {
                visible: (root.state.devices || []).some(d => !d.supported)
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Dimmed receivers use a nonstandard Cast port. This version cannot reliably control those speaker groups.")
            }
            CastText {
                visible: root.active
                text: qsTr("Receiver volume: ") + (root.state.volume || 0) + "%"
            }
            Controls.Slider {
                Layout.fillWidth: true
                visible: root.active
                from: 0; to: 100; stepSize: 1
                value: root.state.volume || 0
                palette.highlight: root.theme.accent
                onPressedChanged: if (!pressed) root.controller.send({action: "volume", value: Math.round(value)})
                Accessible.name: qsTr("Cast receiver volume")
            }
            ActionButton {
                visible: root.active
                text: root.state.muted ? qsTr("Unmute receiver") : qsTr("Mute receiver")
                onClicked: root.controller.send({action: "mute", value: !root.state.muted})
            }
            CastText {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Current audio source: ") + (root.state.source_name || qsTr("Selected when casting starts"))
            }
            ActionButton { text: qsTr("Advanced settings"); onClicked: advanced.visible = !advanced.visible }
            ColumnLayout {
                id: advanced
                visible: false
                Layout.fillWidth: true
                enabled: root.idle
                CastText { text: qsTr("Output monitor") }
                Controls.ComboBox {
                    id: source
                    Layout.fillWidth: true
                    model: [{id: "default", name: qsTr("Current default output")}].concat(root.state.sources || [])
                    textRole: "name"
                    currentIndex: Math.max(0, model.findIndex(s => s.id === (root.settings.source || "default")))
                    onActivated: root.controller.settings({source: model[currentIndex].id})
                }
                CastText { text: qsTr("MP3 bitrate · 48 kHz · stereo") }
                Controls.ComboBox {
                    Layout.fillWidth: true
                    model: [128, 192, 256, 320]
                    currentIndex: Math.max(0, model.indexOf(root.settings.bitrate || 192))
                    onActivated: root.controller.settings({bitrate: model[currentIndex]})
                }
                Controls.CheckBox {
                    text: qsTr("Remember last receiver")
                    checked: root.settings.remember === true
                    palette.windowText: root.theme.foreground
                    onClicked: root.controller.settings({remember: checked})
                }
                Controls.CheckBox {
                    text: qsTr("Reconnect at startup (captures audio)")
                    checked: root.settings.reconnect === true
                    enabled: root.settings.remember === true
                    palette.windowText: root.theme.foreground
                    onClicked: root.controller.settings({reconnect: checked})
                }
                CastText { text: qsTr("Discovery deadline (seconds)") }
                Controls.SpinBox {
                    from: 15; to: 60; value: root.settings.discovery_timeout || 45
                    onValueModified: root.controller.settings({discovery_timeout: value})
                }
                CastText {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: root.theme.secondary
                    text: qsTr("Local-network discovery only. No Google account login. Settings apply to the next connection. Closing this window keeps casting; Stop ends it.")
                }
                ActionButton { text: qsTr("Restart helper"); onClicked: root.controller.restartHelper() }
            }
            Item { implicitHeight: 8 }
        }
    }
}

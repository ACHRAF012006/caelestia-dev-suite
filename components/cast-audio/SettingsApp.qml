pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root
    property var snapshot: ({state: "Off", sources: [], settings: {}})
    property var manualDevices: []
    property bool loaded: false
    property bool dirty: false
    property string notice: qsTr("Loading settings…")
    property string errorMessage: ""
    property string sourceChoice: "default"
    function send(message) { if (bridge.running) bridge.write(JSON.stringify(message) + "\n"); }
    function markDirty() { if (loaded) dirty = true; }
    function hydrate(settings) {
        loaded = false;
        format.currentIndex = settings.format === "mp3" ? 1 : 0;
        latency.currentIndex = settings.latency === "balanced" ? 1 : 0;
        bitrate.currentIndex = Math.max(0, [128, 192, 256, 320].indexOf(settings.bitrate || 192));
        remember.checked = settings.remember === true;
        reconnect.checked = settings.reconnect === true;
        timeout.value = settings.discovery_timeout || 45;
        streamPort.value = settings.stream_port || 0;
        manualDevices = settings.manual_devices || [];
        sourceChoice = settings.source || "default";
        loaded = true; dirty = false;
    }
    function save() {
        send({action: "settings", values: {source: sourceChoice,
            format: format.currentIndex === 0 ? "hls" : "mp3", latency: latency.currentIndex === 0 ? "fast" : "balanced", bitrate: [128,192,256,320][bitrate.currentIndex], remember: remember.checked,
            reconnect: reconnect.checked, discovery_timeout: timeout.value,
            stream_port: streamPort.value, manual_devices: manualDevices}});
    }
    Process {
        id: bridge
        command: ["python3", "-B", decodeURIComponent(Qt.resolvedUrl("src/launcher.py").toString().replace(/^file:\/\//, "")), "settings_client.py"]
        stdinEnabled: true
        running: true
        onStarted: root.send({action: "get"})
        stdout: SplitParser {
            onRead: data => {
                try {
                    const reply = JSON.parse(data);
                    if (!reply.ok) { root.errorMessage = reply.error || qsTr("Settings could not be saved"); root.notice = root.errorMessage; return; }
                    if (reply.action === "settings") root.errorMessage = "";
                    root.snapshot = reply.snapshot;
                    if (!root.loaded || reply.action === "settings" || !root.dirty) root.hydrate(reply.snapshot.settings || {});
                    root.notice = root.errorMessage || reply.snapshot.message || qsTr("Ready");
                } catch (error) { root.notice = qsTr("Settings service returned an invalid response"); }
            }
        }
        onExited: root.notice = qsTr("Settings connection stopped. Close and reopen Settings to retry.")
    }
    Timer { interval: 2000; running: true; repeat: true; onTriggered: root.send({action: "get"}) }
    FloatingWindow {
        id: window
        property Theme theme: Theme {}
        visible: true
        title: qsTr("Cast Audio Settings")
        implicitWidth: 720
        implicitHeight: 650
        minimumSize: Qt.size(460, 440)
        color: theme.surface
        onVisibleChanged: if (!visible) Qt.quit()
        ColumnLayout {
            id: settingsLayout
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16
            RowLayout {
                Layout.fillWidth: true
                CastIcon { Layout.preferredWidth: 32; Layout.preferredHeight: 32; tint: window.theme.accent }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    CastText { text: qsTr("Cast Audio"); font.pixelSize: 24; font.weight: Font.DemiBold }
                    CastText { text: qsTr("Choose your audio. Choose your speaker."); color: window.theme.secondary }
                }
                CastText { text: root.dirty ? qsTr("Unsaved changes") : qsTr("Settings"); color: window.theme.secondary; font.pixelSize: 11 }
            }
            Controls.TabBar {
                id: pages
                Layout.fillWidth: true
                palette.button: window.theme.card
                palette.buttonText: window.theme.foreground
                palette.highlight: window.theme.accent
                Controls.TabButton { text: qsTr("Audio") }
                Controls.TabButton { text: qsTr("Speakers") }
                Controls.TabButton { text: qsTr("Connection") }
                Controls.TabButton { text: qsTr("About") }
            }
            Controls.ScrollView {
                id: scroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                palette.window: window.theme.surface
                palette.text: window.theme.foreground
                palette.windowText: window.theme.foreground
                palette.base: window.theme.surface
                palette.alternateBase: window.theme.card
                palette.button: window.theme.raised
                palette.buttonText: window.theme.foreground
                palette.highlight: window.theme.accent
                palette.highlightedText: window.theme.accentText
                palette.mid: window.theme.outline
                palette.dark: window.theme.outline
                palette.light: window.theme.raised
                palette.link: window.theme.accent
                palette.placeholderText: window.theme.secondary
                ColumnLayout {
                    width: scroll.availableWidth
                    spacing: 16
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: noticeText.implicitHeight + 24
                        radius: 12
                        color: window.theme.selected
                        CastText {
                            id: noticeText
                            anchors.fill: parent
                            anchors.margins: 12
                            text: root.errorMessage || (root.snapshot.state !== "Off" && root.snapshot.state !== "Error" ? qsTr("Stop casting to edit settings. Your audio keeps playing while this window is open.") : root.notice)
                            color: root.errorMessage ? window.theme.error : window.theme.selectedText
                            wrapMode: Text.WordWrap
                        }
                    }
                    SettingsSection {
                        Layout.fillWidth: true
                        visible: pages.currentIndex === 0
                        enabled: root.loaded && (root.snapshot.state === "Off" || root.snapshot.state === "Error")
                        title: qsTr("What to cast")
                        description: qsTr("Share your desktop audio, or isolate one app stream without changing local playback.")
                        SourcePicker { Layout.fillWidth: true; sources: root.snapshot.sources || []; selectedId: root.sourceChoice; onChosen: identity => { root.sourceChoice = identity; root.markDirty(); } }
                        CastText { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: window.theme.secondary; text: qsTr("Apps appear when they create an audio stream. Separate browser tabs can appear separately. If the selected stream closes, casting stops.") }
                    }
                    SettingsSection {
                        Layout.fillWidth: true
                        visible: pages.currentIndex === 0
                        enabled: root.loaded && (root.snapshot.state === "Off" || root.snapshot.state === "Error")
                        title: qsTr("Playback")
                        description: qsTr("Balance delay, reliability and quality for this receiver.")
                        CastText { text: qsTr("Streaming mode") }
                        Controls.ComboBox { id: format; Layout.fillWidth: true; model: [qsTr("Live · shorter delay"), qsTr("MP3 · compatibility")]; onActivated: root.markDirty() }
                        CastText { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: window.theme.secondary; text: format.currentIndex === 0 ? qsTr("Short live segments keep playback closer to your PC audio. The speaker still adds a playback buffer.") : qsTr("Use MP3 if your receiver cannot play the live stream. Some speakers buffer 20–30 seconds.") }
                        CastText { visible: format.currentIndex === 0; text: qsTr("Delay profile") }
                        Controls.ComboBox { id: latency; visible: format.currentIndex === 0; Layout.fillWidth: true; model: [qsTr("Fast · lowest delay"), qsTr("Balanced · more headroom")]; onActivated: root.markDirty() }
                        CastText { visible: format.currentIndex === 0; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: window.theme.secondary; text: qsTr("Fast sends 125 ms segments. About 2 seconds is a target, not a guaranteed speaker delay. Choose Balanced if playback has gaps.") }
                        CastText { text: qsTr("Audio bitrate · 48 kHz · stereo") }
                        Controls.ComboBox { id: bitrate; Layout.fillWidth: true; model: [qsTr("128 kbit/s"), qsTr("192 kbit/s"), qsTr("256 kbit/s"), qsTr("320 kbit/s")]; onActivated: root.markDirty() }
                    }
                    SettingsSection {
                        Layout.fillWidth: true
                        visible: pages.currentIndex === 2
                        enabled: root.loaded && (root.snapshot.state === "Off" || root.snapshot.state === "Error")
                        title: qsTr("Connection")
                        description: qsTr("Device discovery runs while idle. The timeout controls how long searches wait for receivers.")
                        Controls.CheckBox { id: remember; text: qsTr("Remember last receiver"); onClicked: root.markDirty() }
                        Controls.CheckBox { id: reconnect; text: qsTr("Reconnect when Caelestia starts"); enabled: remember.checked; onClicked: root.markDirty() }
                        CastText { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: window.theme.secondary; text: qsTr("Automatic reconnect starts sharing the selected output's audio.") }
                        RowLayout {
                            Layout.fillWidth: true
                            CastText { Layout.fillWidth: true; text: qsTr("Discovery timeout") }
                            Controls.SpinBox { id: timeout; from: 15; to: 60; value: 45; onValueModified: root.markDirty() }
                            CastText { text: qsTr("sec"); color: window.theme.secondary }
                        }
                    }
                    SettingsSection {
                        Layout.fillWidth: true
                        visible: pages.currentIndex === 1
                        enabled: root.loaded && (root.snapshot.state === "Off" || root.snapshot.state === "Error")
                        title: qsTr("Saved speakers")
                        description: qsTr("Add a receiver by private IPv4 address when it is on another VLAN or discovery cannot find it.")
                        Repeater {
                            model: root.manualDevices
                            delegate: RowLayout {
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3
                                    CastText { Layout.fillWidth: true; text: modelData.name; elide: Text.ElideRight; font.weight: Font.DemiBold }
                                    CastText { text: modelData.host; color: window.theme.secondary }
                                }
                                ActionButton { text: qsTr("Remove"); flat: true; onClicked: { const items = root.manualDevices.slice(); items.splice(index,1); root.manualDevices = items; root.markDirty(); } }
                            }
                        }
                        CastText { visible: root.manualDevices.length === 0; text: qsTr("No saved speakers yet"); color: window.theme.secondary }
                        Controls.TextField { id: deviceName; Layout.fillWidth: true; placeholderText: qsTr("Speaker name"); maximumLength: 80 }
                        RowLayout {
                            Layout.fillWidth: true
                            Controls.TextField { id: deviceIp; Layout.fillWidth: true; placeholderText: qsTr("IP address, e.g. 192.168.20.10"); maximumLength: 15; onAccepted: addReceiver.clicked() }
                            ActionButton {
                                id: addReceiver
                                text: qsTr("Add")
                                enabled: deviceName.text.trim().length > 0 && deviceIp.text.trim().length > 0 && root.manualDevices.length < 16
                                onClicked: { if (!enabled) return; root.manualDevices = root.manualDevices.concat([{name: deviceName.text.trim(), host: deviceIp.text.trim()}]); deviceName.clear(); deviceIp.clear(); root.markDirty(); }
                            }
                        }
                    }
                    SettingsSection {
                        Layout.fillWidth: true
                        visible: pages.currentIndex === 2
                        enabled: root.loaded && (root.snapshot.state === "Off" || root.snapshot.state === "Error")
                        title: qsTr("Network")
                        RowLayout {
                            Layout.fillWidth: true
                            CastText { Layout.fillWidth: true; text: qsTr("Audio stream TCP port") }
                            Controls.SpinBox { id: streamPort; from: 0; to: 65535; editable: true; onValueModified: root.markDirty() }
                        }
                        CastText { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: window.theme.secondary; text: qsTr("Default: 48200. After changing ports, run Install/Update in Dev Manager to prepare an active UFW firewall. Port 0 uses a free port and requires manual firewall setup.") }
                        CastText { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: window.theme.secondary; text: qsTr("Across VLANs, allow this PC to reach speaker TCP 8009 and device-info ports 8008/8443 as needed. Allow the speaker to reach this PC's stream port, with source port Any. Router rules are configured separately.") }
                    }
                    SettingsSection {
                        Layout.fillWidth: true
                        visible: pages.currentIndex === 3
                        title: qsTr("Google account")
                        description: qsTr("This Linux backend supports local discovery and saved IP addresses. Google account device discovery is unavailable; no sign-in or credentials are needed.")
                        ActionButton { text: qsTr("Google Home API information"); flat: true; onClicked: Qt.openUrlExternally("https://developers.home.google.com/apis") }
                    }
                }
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: window.theme.outline }
            RowLayout {
                Layout.fillWidth: true
                CastText { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: qsTr("Changes apply on your next connection."); color: window.theme.secondary; font.pixelSize: 11 }
                ActionButton { text: qsTr("Save changes"); primary: true; enabled: root.loaded && root.dirty && (root.snapshot.state === "Off" || root.snapshot.state === "Error"); onClicked: root.save() }
            }
        }
    }
}

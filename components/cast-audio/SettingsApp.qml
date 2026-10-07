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
    function send(message) { if (bridge.running) bridge.write(JSON.stringify(message) + "\n"); }
    function markDirty() { if (loaded) dirty = true; }
    function hydrate(settings) {
        loaded = false;
        bitrate.currentIndex = Math.max(0, [128, 192, 256, 320].indexOf(settings.bitrate || 192));
        remember.checked = settings.remember === true;
        reconnect.checked = settings.reconnect === true;
        timeout.value = settings.discovery_timeout || 45;
        streamPort.value = settings.stream_port || 0;
        manualDevices = settings.manual_devices || [];
        const items = [{id: "default", name: qsTr("Current default output")}].concat(snapshot.sources || []);
        if (settings.source && !items.some(s => s.id === settings.source)) items.push({id: settings.source, name: settings.source});
        source.model = items;
        source.currentIndex = Math.max(0, items.findIndex(s => s.id === (settings.source || "default")));
        loaded = true; dirty = false;
    }
    function save() {
        send({action: "settings", values: {source: source.model[source.currentIndex].id,
            bitrate: [128,192,256,320][bitrate.currentIndex], remember: remember.checked,
            reconnect: reconnect.checked, discovery_timeout: timeout.value,
            stream_port: streamPort.value, manual_devices: manualDevices}});
    }
    Process {
        id: bridge
        command: ["python3", "-B", decodeURIComponent(Qt.resolvedUrl("src/settings_client.py").toString().replace(/^file:\/\//, ""))]
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
        implicitWidth: 620
        implicitHeight: 730
        minimumSize: Qt.size(420, 400)
        color: theme.surface
        onVisibleChanged: if (!visible) Qt.quit()
        Controls.ScrollView {
            id: scroll
            anchors.fill: parent
            anchors.margins: 24
            contentWidth: availableWidth
            palette.text: window.theme.foreground
            palette.windowText: window.theme.foreground
            palette.base: window.theme.card
            palette.button: window.theme.card
            palette.buttonText: window.theme.foreground
            palette.highlight: window.theme.accent
            ColumnLayout {
                width: scroll.availableWidth
                spacing: 12
                CastText { text: qsTr("Cast Audio Settings"); font.pixelSize: 24 }
                CastText { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: root.notice }
                ColumnLayout {
                    Layout.fillWidth: true
                    enabled: root.loaded && (root.snapshot.state === "Off" || root.snapshot.state === "Error")
                    CastText { text: qsTr("Audio output") }
                    Controls.ComboBox { id: source; Layout.fillWidth: true; textRole: "name"; model: []; onActivated: root.markDirty() }
                    CastText { text: qsTr("MP3 bitrate · 48 kHz · stereo") }
                    Controls.ComboBox { id: bitrate; model: [128,192,256,320]; onActivated: root.markDirty() }
                    Controls.CheckBox { id: remember; text: qsTr("Remember last receiver"); onClicked: root.markDirty() }
                    Controls.CheckBox { id: reconnect; text: qsTr("Reconnect at startup (starts audio capture)"); enabled: remember.checked; onClicked: root.markDirty() }
                    RowLayout {
                        CastText { text: qsTr("Discovery timeout (seconds)") }
                        Controls.SpinBox { id: timeout; from: 15; to: 60; value: 45; onValueModified: root.markDirty() }
                    }
                    CastText { text: qsTr("Receivers by IP address"); font.pixelSize: 18 }
                    CastText {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                        text: qsTr("Add a private IPv4 address when discovery cannot cross VLANs. Allow receiver TCP 8009 and device-info ports 8008/8443 as needed; the receiver must also reach this computer's audio stream. Adding an IP does not change routing or firewall rules.")
                    }
                    Repeater {
                        model: root.manualDevices
                        delegate: RowLayout {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            CastText { Layout.fillWidth: true; text: modelData.name + " · " + modelData.host; elide: Text.ElideRight }
                            ActionButton { text: qsTr("Remove"); onClicked: { const items = root.manualDevices.slice(); items.splice(index,1); root.manualDevices = items; root.markDirty(); } }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Controls.TextField { id: deviceName; Layout.fillWidth: true; placeholderText: qsTr("Receiver name"); maximumLength: 80 }
                        Controls.TextField { id: deviceIp; Layout.fillWidth: true; placeholderText: "192.168.20.10"; maximumLength: 15 }
                    }
                    ActionButton {
                        text: qsTr("Add receiver")
                        enabled: deviceName.text.trim().length > 0 && deviceIp.text.trim().length > 0 && root.manualDevices.length < 16
                        onClicked: { root.manualDevices = root.manualDevices.concat([{name: deviceName.text.trim(), host: deviceIp.text.trim()}]); deviceName.clear(); deviceIp.clear(); root.markDirty(); }
                    }
                    RowLayout {
                        CastText { text: qsTr("Audio stream TCP port") }
                        Controls.SpinBox { id: streamPort; from: 0; to: 65535; editable: true; onValueModified: root.markDirty() }
                    }
                    CastText { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: qsTr("0 selects an available port. Use a fixed port from 1024–65535 when your VLAN firewall needs one predictable incoming port.") }
                    ActionButton { text: qsTr("Save settings"); enabled: root.dirty; onClicked: { root.save(); } }
                }
                CastText { text: qsTr("Google account"); font.pixelSize: 18 }
                CastText {
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                    text: qsTr("Google account device discovery is unavailable for this Linux Cast backend. Use local discovery or saved IP addresses. Account sign-in would not enable casting across VLANs.")
                }
                ActionButton { text: qsTr("Google Home API information"); onClicked: Qt.openUrlExternally("https://developers.home.google.com/apis") }
                CastText { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: qsTr("Stop casting before saving settings. Changes apply to the next connection."); color: window.theme.secondary }
            }
        }
    }
}

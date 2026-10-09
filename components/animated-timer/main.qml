pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root
    property var snapshot: ({state: "Ready", configured: 1500, remaining: 1500,
        cycle_duration: 1500, fraction: 1, alarm_active: false, cycle: "", revision: 0,
        presets: [], prefs: {animation: true, sound: true, notification: true, repeat: false}})
    property bool healthy: false
    property string error: "Starting timer…"
    readonly property bool motion: snapshot.prefs.animation
    property Component timerPage: Component { TimerPage { controller: root } }
    property Component notchComponent: Component { TimerNotch { controller: root } }
    function send(message) { if (helper.running && healthy) helper.write(JSON.stringify(message) + "\n"); }
    function primary() {
        send({action: snapshot.state === "Running" ? "pause" : snapshot.state === "Paused" ? "resume" : "start"});
    }
    Process {
        id: helper
        command: ["python3", "-B", decodeURIComponent(Qt.resolvedUrl("src/main.py").toString().replace(/^file:\/\//, ""))]
        stdinEnabled: true
        running: true
        stdout: SplitParser {
            onRead: data => {
                try {
                    const value = JSON.parse(data);
                    if (["Ready", "Running", "Paused", "Completed"].indexOf(value.state) >= 0) {
                        root.snapshot = value;
                        root.healthy = true;
                        root.error = value.error ?? "";
                    }
                } catch (error) { root.error = "Timer helper returned invalid data"; }
            }
        }
        onExited: { root.healthy = false; root.error = "Timer helper stopped. Reload the shell to reconnect."; }
    }
    Component.onDestruction: { if (helper.running) helper.write('{"action":"quit"}\n'); }
}

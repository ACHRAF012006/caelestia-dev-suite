pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    property var snapshot: ({state: "Off", message: "Starting helper…", devices: [], sources: [], settings: {}})
    property bool restarting: false
    property bool menuExpanded: false
    property bool menuIsVisible: false
    signal openMenuRequested()
    property Component quickToggle: Component { CastMenu { controller: root } }

    function setMenuExpanded(value) { menuExpanded = value; }
    function menuVisible(value) {
        menuIsVisible = value;
        send({action: "visible", value: value});
    }
    function openSettings() {
        Quickshell.execDetached(["quickshell", "--no-duplicate", "--path",
            decodeURIComponent(Qt.resolvedUrl("SettingsApp.qml").toString().replace(/^file:\/\//, ""))]);
    }

    function send(message) {
        if (helper.running)
            helper.write(JSON.stringify(message) + "\n");
    }
    function openPanel() {
        menuExpanded = true;
        openMenuRequested();
    }
    function toggle() {
        if (menuExpanded)
            menuExpanded = false;
        else
            openPanel();
    }
    function settings(values) { send({action: "settings", values: values}); }
    function restartHelper() {
        if (helper.running) {
            restarting = true;
            send({action: "quit"});
        } else {
            snapshot = {state: "Off", message: "Starting helper…", devices: [], sources: [], settings: {}};
            helper.running = true;
        }
    }

    Process {
        id: helper
        // URL decoding supports installation paths containing spaces.
        command: ["python3", "-B", decodeURIComponent(Qt.resolvedUrl("src/main.py").toString().replace(/^file:\/\//, ""))]
        stdinEnabled: true
        running: true
        onStarted: root.send({action: "visible", value: root.menuIsVisible})
        stdout: SplitParser {
            onRead: data => {
                try {
                    const value = JSON.parse(data);
                    if (typeof value.state === "string")
                        root.snapshot = value;
                } catch (error) {
                    root.snapshot = {state: "Error", message: "Helper returned an invalid response", devices: [], sources: [], settings: {}};
                }
            }
        }
        onExited: {
            root.snapshot = {state: "Error", message: "Cast helper stopped. Capture has ended; use Restart helper to retry.", devices: [], sources: [], settings: {}};
            if (root.restarting) restartTimer.start();
        }
    }
    Timer {
        id: restartTimer
        interval: 150
        onTriggered: { root.restarting = false; root.restartHelper(); }
    }
    // A supported generic Quickshell IPC handler, provided by this plugin itself.
    IpcHandler {
        target: "castAudio"
        function open(): void { root.openPanel(); }
        function settings(): void { root.openSettings(); }
        function toggle(): void { root.toggle(); }
        function stop(): void { root.send({action: "stop"}); }
    }
    Component.onDestruction: send({action: "quit"})
}

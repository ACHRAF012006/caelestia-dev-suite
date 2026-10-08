"""Exercise the host icon with a fake receiver, isolated XDG roots and no session bus."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


QML = '''import QtQuick
import Quickshell
import Caelestia
import qs.components
import qs.services
import Caelestia.Config
import CAST_COMPONENT_URL as CastUI
import "modules/utilities/cards"

ShellRoot {
    id: root
    property alias card: cardItem
    property int phase: 0
    property bool failed: false
    FloatingWindow { id: canvas; visible: false; implicitWidth: 480; implicitHeight: 260 }
    Binding { target: ShellState; property: "shellRoot"; value: root }
    DrawerVisibilities { id: drawers; utilities: true }
    Toggles {
        id: cardItem
        parent: canvas.contentItem
        visibilities: drawers
        popouts: null
        width: 480
    }
    QtObject {
        id: fakeCast
        property var snapshot: ({state: "Off"})
        property bool menuExpanded: false
        property int settingsOpened: 0
        property var lastCommand: ({})
        signal openMenuRequested()
        property Component quickToggle: Component { CastUI.CastMenu { controller: fakeCast } }
        function setMenuExpanded(value) { menuExpanded = value; }
        function menuVisible(value) {}
        function openSettings() { settingsOpened++; }
        function send(message) { lastCommand = message; }
    }
    function check(value, message) {
        if (!value) { failed = true; console.error("CAST_MENU_FAIL", message); }
    }
    function findItem(item, name) {
        if (item.objectName === name) return item;
        for (let child of item.children || []) {
            const found = findItem(child, name);
            if (found) return found;
        }
        return null;
    }
    Component.onCompleted: {
        console.log("CAST_MENU_START");
        GlobalConfig.utilities.quickToggles = [{id: "castAudio", enabled: true}];
        PluginLoader.pluginInstances = {"cast-audio": fakeCast};
        PluginLoader.loadedCount = 1;
        check(card !== null, "host card instantiation");
        console.log("CAST_MENU_CREATED", card !== null);
    }
    Timer {
        interval: 350; repeat: true; running: true
        onTriggered: {
            console.log("CAST_MENU_PHASE", root.phase);
            if (!root.card) { root.check(false, "missing card"); Qt.quit(); return; }
            const menu = root.findItem(root.card, "castAudioMenu");
            if (root.phase === 0) {
                root.check(menu !== null, "separate menu row appears with loaded plugin");
                root.check(!root.findItem(root.card, "castAudioQuickToggle"), "no Cast icon delegate");
                if (!menu) { Qt.quit(); return; }
                root.check(!menu.expanded, "menu starts collapsed");
                root.findItem(menu, "castAudioExpand").clicked();
                fakeCast.snapshot = {state: "Off", message: "Choose a receiver", devices: [{id: "manual:192.168.20.8", host: "192.168.20.8", name: "VLAN Speaker", manual: true, supported: true}], sources: [{id: "app:19:player", kind: "application", name: "Player", detail: "Music"}], settings: {}};
            } else if (root.phase === 1) {
                root.check(menu && menu.expanded, "row expands without opening a window");
                root.findItem(menu, "castAudioApp").clicked();
                root.check(fakeCast.lastCommand.action === "settings" && fakeCast.lastCommand.values.source === "app:19:player", "app selection saves only the selected stream");
                root.findItem(menu, "castAudioLatency").activated(1);
                root.check(fakeCast.lastCommand.values.latency === "balanced", "delay profile can be changed inline");
                const receiver = root.findItem(menu, "castAudioReceiver");
                root.check(receiver !== null, "receiver list is embedded in row");
                if (receiver) receiver.clicked();
                root.check(fakeCast.lastCommand.action === "start" && fakeCast.lastCommand.id === "manual:192.168.20.8", "receiver selects the requested saved IP");
                root.findItem(menu, "castAudioSettings").clicked();
                root.check(fakeCast.settingsOpened === 1, "Settings button launches settings app action");
                drawers.utilities = false;
                fakeCast.openMenuRequested();
                root.check(drawers.utilities, "IPC opens the Quick Toggles drawer");
                fakeCast.snapshot = {state: "Casting", scanning: true, receiver: "VLAN Speaker", devices: [], settings: {}};
            } else if (root.phase === 2) {
                root.check(menu && menu.state.state === "Casting", "live state stays in embedded menu");
                root.check(!root.findItem(menu, "castAudioRefresh").visible, "active sessions never show a scanning action");
                GlobalConfig.utilities.quickToggles = [{id: "castAudio", enabled: false}];
            } else if (root.phase === 3) {
                root.check(!menu, "Nexus setting hides row");
                GlobalConfig.utilities.quickToggles = [{id: "castAudio", enabled: true}];
            } else if (root.phase === 4) {
                root.check(menu !== null, "Nexus setting restores row");
                PluginLoader.pluginInstances = {};
                PluginLoader.loadedCount = 0;
            } else if (root.phase === 5) {
                root.check(!menu, "unloading plugin removes row");
                if (!root.failed) console.log("CAST_MENU_PASS");
                Qt.quit();
            }
            root.phase++;
        }
    }
    Timer { interval: 6000; running: true; onTriggered: { console.error("CAST_MENU_FAIL timeout"); Qt.quit(); } }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", type=Path, required=True, help="Caelestia KDE shell source (read only)")
    args = parser.parse_args()
    patch = Path(__file__).resolve().parents[1] / "patches/quick-toggles.patch"
    with tempfile.TemporaryDirectory(prefix="cast-menu-probe-") as temporary:
        base = Path(temporary)
        preview = base / "shell"
        shutil.copytree(args.shell, preview, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        if "castAudioQuickToggle" in (preview / "modules/utilities/cards/Toggles.qml").read_text():
            subprocess.run(["git", "apply", "-p2", "--reverse", str(patch.with_name("legacy-icon.patch"))], cwd=preview, check=True)
        if "castAudioMenuLoader" not in (preview / "modules/utilities/cards/Toggles.qml").read_text():
            subprocess.run(["git", "apply", "-p2", "--check", str(patch)], cwd=preview, check=True)
            subprocess.run(["git", "apply", "-p2", str(patch)], cwd=preview, check=True)
        (preview / "shell.qml").write_text(QML.replace("CAST_COMPONENT_URL", __import__("json").dumps(Path(__file__).resolve().parents[1].as_uri())))
        runtime = base / "runtime"
        runtime.mkdir(mode=0o700)
        # The host imports PanelWindow types, which require the Wayland backend
        # even though this probe does not show any shell windows.
        env = dict(os.environ, QT_QPA_PLATFORM="wayland", DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent",
                   XDG_RUNTIME_DIR=str(runtime))
        display = Path(os.environ.get("WAYLAND_DISPLAY", "wayland-0"))
        if not display.is_absolute():
            display = Path(os.environ["XDG_RUNTIME_DIR"]) / display
        env["WAYLAND_DISPLAY"] = str(display)
        for name in ("CONFIG", "DATA", "STATE", "CACHE"):
            env["XDG_" + name + "_HOME"] = str(base / name.lower())
            (base / name.lower()).mkdir()
        (base / "config/caelestia").mkdir()
        (base / "config/caelestia/shell.json").write_text("{}")
        env["QML2_IMPORT_PATH"] = os.pathsep.join([str(Path.home() / ".local/lib/qt6/qml"), str(preview), env.get("QML2_IMPORT_PATH", "")])
        result = subprocess.run(["quickshell", "--path", str(preview), "--no-color"], env=env,
                                capture_output=True, text=True, timeout=12)
        output = result.stdout + result.stderr
        if result.returncode or "CAST_MENU_PASS" not in output or "CAST_MENU_FAIL" in output:
            print("Probe exit code:", result.returncode)
            print(output)
            raise SystemExit("Cast Quick Toggle probe failed")
        print("PASS: host QML compiles; expandable row, embedded IP receiver selection, Settings action, drawer opening, Nexus visibility and unload work.")


if __name__ == "__main__":
    main()

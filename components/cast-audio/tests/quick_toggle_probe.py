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
        property int opened: 0
        function openPanel() { opened++; }
    }
    function check(value, message) {
        if (!value) { failed = true; console.error("CAST_ICON_FAIL", message); }
    }
    function findIcon(item) {
        if (item.objectName === "castAudioQuickToggle") return item;
        for (let child of item.children || []) {
            const found = findIcon(child);
            if (found) return found;
        }
        return null;
    }
    Component.onCompleted: {
        console.log("CAST_ICON_START");
        GlobalConfig.utilities.quickToggles = [{id: "castAudio", enabled: true}];
        PluginLoader.pluginInstances = {"cast-audio": fakeCast};
        PluginLoader.loadedCount = 1;
        check(card !== null, "host card instantiation");
        console.log("CAST_ICON_CREATED", card !== null);
    }
    Timer {
        interval: 350; repeat: true; running: true
        onTriggered: {
            console.log("CAST_ICON_PHASE", root.phase);
            if (!root.card) { root.check(false, "missing card"); Qt.quit(); return; }
            const icon = root.findIcon(root.card);
            if (root.phase === 0) {
                root.check(icon !== null, "icon appears with loaded plugin");
                if (!icon) { Qt.quit(); return; }
                root.check(icon.icon === "cast" && !icon.checked, "idle icon state");
                icon.clicked();
            } else if (root.phase === 1) {
                root.check(fakeCast.opened === 1, "click opens receiver controls");
                root.check(!drawers.utilities, "click closes utilities drawer");
                fakeCast.snapshot = {state: "Casting"};
            } else if (root.phase === 2) {
                root.check(icon && icon.icon === "cast_connected" && icon.checked, "live casting highlight");
                GlobalConfig.utilities.quickToggles = [{id: "castAudio", enabled: false}];
            } else if (root.phase === 3) {
                root.check(!icon, "Nexus setting hides icon");
                GlobalConfig.utilities.quickToggles = [{id: "castAudio", enabled: true}];
            } else if (root.phase === 4) {
                root.check(icon !== null, "Nexus setting restores icon");
                PluginLoader.pluginInstances = {};
                PluginLoader.loadedCount = 0;
            } else if (root.phase === 5) {
                root.check(!icon, "unloading plugin removes icon");
                if (!root.failed) console.log("CAST_ICON_PASS");
                Qt.quit();
            }
            root.phase++;
        }
    }
    Timer { interval: 6000; running: true; onTriggered: { console.error("CAST_ICON_FAIL timeout"); Qt.quit(); } }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", type=Path, required=True, help="Caelestia KDE shell source (read only)")
    args = parser.parse_args()
    patch = Path(__file__).resolve().parents[1] / "patches/quick-toggles.patch"
    with tempfile.TemporaryDirectory(prefix="cast-icon-probe-") as temporary:
        base = Path(temporary)
        preview = base / "shell"
        shutil.copytree(args.shell, preview, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        if "castAudioQuickToggle" not in (preview / "modules/utilities/cards/Toggles.qml").read_text():
            subprocess.run(["git", "apply", "-p2", "--check", str(patch)], cwd=preview, check=True)
            subprocess.run(["git", "apply", "-p2", str(patch)], cwd=preview, check=True)
        (preview / "shell.qml").write_text(QML)
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
        if result.returncode or "CAST_ICON_PASS" not in output or "CAST_ICON_FAIL" in output:
            print("Probe exit code:", result.returncode)
            print(output)
            raise SystemExit("Cast Quick Toggle probe failed")
        print("PASS: host QML compiles; icon, click, casting highlight, Nexus visibility and plugin unload work.")


if __name__ == "__main__":
    main()

"""Test Cast alignment and interaction on a copied shell and private KWin output."""
import argparse
import os
import json
import signal
import time
from pathlib import Path
import shutil
import subprocess
import tempfile


QML = r'''import QtQuick
import QtTest
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
    property int panelWidth: 480
    FloatingWindow {
        id: canvas; visible: true; implicitWidth: 480; implicitHeight: 760
        color: Colours.palette.m3surfaceContainerLow
    }
    Rectangle { id: previewCanvas; parent: canvas.contentItem; width: root.panelWidth; height: canvas.height; color: Colours.palette.m3surfaceContainerLow }
    Binding { target: ShellState; property: "shellRoot"; value: root }
    DrawerVisibilities { id: drawers; utilities: true }
    Toggles {
        id: cardItem
        parent: previewCanvas
        visibilities: drawers
        popouts: null
        width: root.panelWidth
    }
    TestCase { id: pointer; when: false }
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
    function aligned(menu) {
        const button = findItem(menu, "castAudioExpand"), icon = findItem(menu, "castAudioHeaderIcon"), labels = findItem(menu, "castAudioHeaderLabels"), title = findItem(menu, "castAudioTitle"), status = findItem(menu, "castAudioStatus"), chevron = findItem(menu, "castAudioChevron"), settings = findItem(menu, "castAudioSettings");
        check(root.card.width === root.panelWidth && menu.width <= root.panelWidth, "actual panel width tracks responsive fixture");
        const center = item => item.mapToItem(menu, item.width / 2, item.height / 2).y;
        check(button.height + 0.1 >= button.contentItem.implicitHeight + button.topPadding + button.bottomPadding, "header fits its two-line content phase=" + root.phase + " height=" + button.height + " implicit=" + button.implicitHeight + " content=" + button.contentItem.implicitHeight + " padding=" + button.topPadding + "/" + button.bottomPadding);
        check(Math.abs(center(icon) - center(labels)) <= 0.6 && Math.abs(center(chevron) - center(labels)) <= 0.6 && Math.abs(center(settings) - center(labels)) <= 0.6, "icon, labels, chevron and settings vertically centered phase=" + root.phase + " centers=" + [center(icon), center(labels), center(chevron), center(settings)]);
        check(icon.status === Image.Ready && Math.abs(icon.width - icon.height) < 0.1 && Math.abs(icon.paintedWidth - icon.paintedHeight) < 0.1, "cast artwork loaded without stretching");
        check(/stroke="#([0-9a-f]{6})"/i.test(decodeURIComponent(icon.source.toString())) && Math.abs(icon.opacity - icon.tint.a) < 0.01, "SVG uses RGB tint with separate theme transparency");
        const a = title.mapToItem(button, 0, 0), b = status.mapToItem(button, 0, 0);
        check(Math.abs(a.x - b.x) < 0.1 && a.y >= button.topPadding - 0.1 && b.y + status.height <= button.height - button.bottomPadding + 0.1, "title/status share left edge and fit padded header title=" + a.x + "," + a.y + " status=" + b.x + "," + b.y + " height=" + status.height);
        check(status.width > 0 && status.mapToItem(menu, status.width, 0).x <= chevron.mapToItem(menu, 0, 0).x + 0.1, "status elides before chevron");
        check(settings.mapToItem(menu, settings.width, 0).x <= menu.width + 0.1, "settings remains inside narrow panel");
        const text = findItem(settings, "castAudioButtonText");
        check(text.font.pixelSize === settings.font.pixelSize && text.font.family === settings.font.family, "buttons respect configured font");
        check(Math.abs(center(text) - center(settings)) < 0.2, "button text centered");
    }
    function screenshot(name, after) {
        const path = Quickshell.env("CAST_MENU_SCREENSHOT");
        if (path) previewCanvas.grabToImage(result => { result.saveToFile(path.replace(/\.png$/, name + ".png")); if (after) after(); });
        else if (after) after();
    }
    function findChoice(item, identity) {
        if (item.objectName === "castAudioSourceChoice" && item.modelData.id === identity) return item;
        for (let child of item.children || []) { const found = findChoice(child, identity); if (found) return found; }
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
                root.aligned(menu); root.screenshot("-collapsed");
                root.findItem(menu, "castAudioExpand").clicked();
                fakeCast.snapshot = {state: "Off", message: "Choose a receiver", devices: [{id: "manual:192.168.20.8", host: "192.168.20.8", name: "VLAN Speaker", manual: true, supported: true}], sources: [{id: "app:19:player", kind: "application", name: "Player", detail: "Music"}, {id: "app:20:browser", kind: "application", name: "Browser", detail: "Video"}], settings: {}};
            } else if (root.phase === 1) {
                root.check(menu && menu.expanded, "row expands without opening a window");
                root.aligned(menu); root.screenshot("-expanded");
                const glyph = root.findItem(menu, "castAudioHeaderIcon");
                const path = Quickshell.env("CAST_MENU_SCREENSHOT");
                if (path) glyph.grabToImage(result => result.saveToFile(path.replace(/\.png$/, "-icon.png")));
                root.findItem(menu, "castAudioApp").clicked();
                root.check(fakeCast.lastCommand.action === "settings" && fakeCast.lastCommand.values.source === "app:19:player", "app selection saves only the selected stream");
                fakeCast.snapshot = Object.assign({}, fakeCast.snapshot, {settings: {source: "app:19:player"}});
                root.check(!root.findItem(menu, "castAudioSource").visible, "panel uses no external source popup");
                root.check(!root.findItem(menu, "castAudioLatency"), "advanced tuning stays in Settings");
                root.check(menu.implicitHeight < 300, "idle Cast panel stays compact");
                const selector = root.findItem(menu, "castAudioSourceExpand");
                pointer.mouseClick(selector);
                pointer.mouseClick(selector);
                root.check(menu.expanded && drawers.utilities, "opening source choices preserves drawer");
            } else if (root.phase === 2) {
                const choice = root.findChoice(menu, "app:20:browser");
                root.check(choice && choice.visible && choice.enabled && choice.height > 0, "inline source choice is visible");
                if (choice) pointer.mouseClick(choice);
                root.check(fakeCast.lastCommand.values.source === "app:20:browser", "pointer selects a different inline source");
                root.check(menu.expanded && drawers.utilities, "selection keeps Quick Toggles open");
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
            } else if (root.phase === 3) {
                root.check(menu && menu.state.state === "Casting", "live state stays in embedded menu");
                root.check(!root.findItem(menu, "castAudioRefresh").visible, "active sessions never show a scanning action");
                root.aligned(menu);
                fakeCast.snapshot = Object.assign({}, fakeCast.snapshot, {receiver: "A very long speaker name in the far corner of the living room"});
                root.panelWidth = 320;
            } else if (root.phase === 4) {
                root.aligned(menu); root.screenshot("-narrow", () => GlobalConfig.appearance.font.scale = 1.4);
            } else if (root.phase === 5) {
                root.aligned(menu); root.screenshot("-large-font", () => {
                    fakeCast.setMenuExpanded(false);
                    fakeCast.snapshot = {state: "Error", message: "A long error message with useful diagnostics", devices: [], sources: [], settings: {}};
                });
            } else if (root.phase === 6) {
                root.aligned(menu);
                fakeCast.setMenuExpanded(true);
            } else if (root.phase === 7) {
                root.aligned(menu);
                root.check(menu.expanded && root.findItem(menu, "castAudioStatus").text === "Needs attention", "error state preserves aligned header");
                GlobalConfig.appearance.font.scale = 1;
                GlobalConfig.utilities.quickToggles = [{id: "castAudio", enabled: false}];
            } else if (root.phase === 8) {
                root.check(!menu, "Nexus setting hides row");
                GlobalConfig.utilities.quickToggles = [{id: "castAudio", enabled: true}];
            } else if (root.phase === 9) {
                root.check(menu !== null, "Nexus setting restores row");
                PluginLoader.pluginInstances = {};
                PluginLoader.loadedCount = 0;
            } else if (root.phase === 10) {
                root.check(!menu, "unloading plugin removes row");
                if (!root.failed) console.log("CAST_MENU_PASS");
                Qt.quit();
            }
            root.phase++;
        }
    }
    Timer { interval: 10000; running: true; onTriggered: { console.error("CAST_MENU_FAIL timeout"); Qt.quit(); } }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", type=Path, required=True, help="Caelestia KDE shell source (read only)")
    parser.add_argument("--screenshot", type=Path, help="Write state previews using synthetic receiver data")
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
        env = dict(os.environ, QT_QPA_PLATFORM="wayland", DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent",
                   XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY="cast-alignment-test",
                   QSG_RHI_BACKEND="software", QT_QUICK_BACKEND="software", QS_DISABLE_CRASH_HANDLER="1")
        env.pop("DISPLAY", None)
        for name in ("CONFIG", "DATA", "STATE", "CACHE"):
            env["XDG_" + name + "_HOME"] = str(base / name.lower())
            (base / name.lower()).mkdir()
        (base / "config/caelestia").mkdir()
        (base / "config/caelestia/shell.json").write_text("{}")
        scheme = Path.home() / ".local/state/caelestia/scheme.json"
        if scheme.is_file():
            (base / "state/caelestia").mkdir()
            shutil.copyfile(scheme, base / "state/caelestia/scheme.json")
        if args.screenshot: env["CAST_MENU_SCREENSHOT"] = str(args.screenshot.resolve())
        env["QML2_IMPORT_PATH"] = os.pathsep.join([str(Path.home() / ".local/lib/qt6/qml"), str(preview), env.get("QML2_IMPORT_PATH", "")])
        with (base / "compositor.log").open("w") as log:
            compositor = subprocess.Popen(["dbus-run-session", "--", "kwin_wayland", "--virtual", "--no-lockscreen", "--no-global-shortcuts", "--no-kactivities", "--width", "960", "--height", "1100", "--scale", "1.25", "--socket", "cast-alignment-test"],
                                          env=env, stdout=log, stderr=log, start_new_session=True)
            try:
                for _ in range(100):
                    if (runtime / "cast-alignment-test").exists(): break
                    if compositor.poll() is not None: raise RuntimeError((base / "compositor.log").read_text())
                    time.sleep(0.05)
                result = subprocess.run(["quickshell", "--path", str(preview), "--no-color"], env=env,
                                        capture_output=True, text=True, timeout=15)
            finally:
                if compositor.poll() is None:
                    os.killpg(compositor.pid, signal.SIGTERM)
                    compositor.wait(timeout=5)
        output = result.stdout + result.stderr
        errors = ("CAST_MENU_FAIL", "ReferenceError:", "TypeError:", "Cannot assign", "Unable to assign", "Binding loop", "is not a type", "Cannot create delegate", "recursive rearrange")
        if result.returncode or "CAST_MENU_PASS" not in output or any(error in output for error in errors):
            print("Probe exit code:", result.returncode)
            print(output)
            raise SystemExit("Cast Quick Toggle probe failed")
        print("PASS: copied host on private KWin at 1.25 scale; centered icon/text/chevron/buttons, long status, 320/480 widths, 140% font, idle/casting/error and expand/collapse; compact row, pointer-driven inline source choices without popups, embedded IP receiver selection, Settings action, drawer opening, Nexus visibility and unload work.")


if __name__ == "__main__":
    main()

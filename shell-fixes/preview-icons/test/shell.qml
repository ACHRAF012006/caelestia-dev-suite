import QtQuick
import Quickshell
import Caelestia.Config
import Caelestia.Services
import qs.components.images
import qs.components.effects

ShellRoot {
    id: root
    property int phase: 0
    property int ticks: 0
    property int cycles: 0
    property string targetTitle: "Caelestia owned preview test " + Quickshell.env("RENDER_PROBE_TOKEN")
    property string targetAddress: ""
    property bool capture: true
    property bool failed: false
    function check(value, message) { if (!value) { failed = true; console.error("RENDER_FAIL", message); } }
    FloatingWindow {
        id: target
        title: root.targetTitle
        visible: true
        implicitWidth: 160
        implicitHeight: 120
        color: "#ff3366"
        Rectangle { anchors.fill: parent; color: "#ff3366" }
    }
    FloatingWindow {
        id: canvas
        title: "Caelestia preview diagnostics"
        visible: true
        implicitWidth: 300
        implicitHeight: 250
        color: "white"
        Item {
            id: frame
            anchors.fill: parent
            Rectangle { anchors.fill: parent; color: "white" }
        WindowPreview {
            id: preview
            objectName: "ownedPreview"
            x: 10; y: 10; width: 200; height: 150
            address: root.targetAddress
            active: root.capture
            fallbackIcon: "file:///usr/share/icons/breeze/apps/48/system-file-manager.svg"
            sourceAspect: 4 / 3
        }
        FallbackIcon {
            id: icon
            x: 230; y: 20; width: 48; height: 48
            source: "file:///nonexistent-caelestia-test-icon.png"
        }
        ColouredIcon {
            id: coloured
            x: 230; y: 100; width: 48; height: 48
            source: "file:///usr/share/icons/breeze/apps/48/system-file-manager.svg"
            colour: "#22ffaa"
        }
        }
    }
    Timer {
        interval: 350; running: true; repeat: true
        onTriggered: {
            root.ticks++;
            if (root.ticks > 90) { console.error("RENDER_FAIL timeout phase",root.phase); Qt.quit(); return; }
            if (root.phase === 0) {
                const found = KWinActiveWindowBridge.windowList.find(w => w.title === root.targetTitle);
                if (!found) return;
                root.targetAddress = found.address;
                root.check(icon.status === Image.Error, "bad icon source must fail");
                root.check(icon.children.some(c => c.objectName === "iconFallback" && c.visible && c.status === Image.Ready), "missing icon keeps a visible fallback");
                root.phase = 1;
            } else if (root.phase === 1) {
                if (!preview.hasStream) return;
                console.log("RENDER_FRAME_READY", root.cycles);
                if (root.cycles === 0) {
                    root.phase = 10;
                    frame.grabToImage(result => {
                        result.saveToFile(Quickshell.env("RENDER_PROBE_IMAGE"));
                        root.capture = false;
                        coloured.visible = false;
                        root.phase = 2;
                    });
                    return;
                }
                root.capture = false;
                coloured.visible = false;
                root.phase = 2;
            } else if (root.phase === 2) {
                root.check(!preview.hasStream, "closing preview discards the video consumer");
                root.capture = true;
                coloured.visible = true;
                root.cycles++;
                root.phase = root.cycles === 4 ? 3 : 1;
            } else if (root.phase === 3) {
                if (!preview.hasStream) return;
                icon.source = "file:///usr/share/icons/breeze/apps/48/system-file-manager.svg";
                root.phase = 4;
            } else if (root.phase === 4) {
                root.check(icon.status === Image.Ready, "icon recovers when its source changes");
                root.check(!icon.children.find(c => c.objectName === "iconFallback").visible, "loaded icon replaces fallback");
                root.check(coloured.status === Image.Ready, "tinted icon survives hide/show cycles");
                target.visible = false;
                root.phase = 5;
            } else if (root.phase === 5) {
                if (preview.hasStream) return;
                root.check(preview.children.some(c => c.objectName === "windowPreviewFallback" && c.visible), "closed window returns to a fallback");
                root.capture = false;
                root.targetAddress = "";
                if (!root.failed) console.log("RENDER_PASS");
                Qt.quit();
            }
        }
    }
}

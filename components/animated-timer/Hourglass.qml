pragma ComponentBehavior: Bound
import QtQuick
import qs.services

Item {
    id: root
    required property var controller
    property bool animationActive: true
    property real fraction: controller.snapshot.fraction
    readonly property color outlineColor: Colours.palette.m3onSurfaceVariant
    onOutlineColorChanged: { if (glass) glass.requestPaint(); }
    onSandColorChanged: { if (glass) glass.requestPaint(); }
    readonly property color sandColor: Qt.tint(Colours.palette.m3tertiary, "#80c7a878")
    property real rotationTarget: 0
    property real turn: rotationTarget
    property real phase: 0
    property bool finishing: false
    property string lastCycle: ""
    property string lastState: "Ready"
    readonly property bool running: controller.snapshot.state === "Running"
    readonly property bool motion: controller.motion
    readonly property bool flowing: running && !rotationAnim.running
    implicitWidth: 42; implicitHeight: 54
    function sync() {
        const state = controller.snapshot.state;
        const cycle = controller.snapshot.cycle;
        if (cycle !== lastCycle && state === "Running") {
            finishing = false; finishTimer.stop();
            rotationTarget += 180;
            phase = 0;
        } else if (state === "Completed" && lastState !== "Completed") {
            finishing = true;
            finishTimer.restart();
        } else if (state === "Ready" && lastState !== "Ready") {
            finishing = false; finishTimer.stop(); pulse.stop(); scale = 1;
            phase = 0;
            rotationTarget = Math.ceil(rotationTarget / 360) * 360;
        }
        lastCycle = cycle;
        lastState = state;
        glass.requestPaint();
    }
    Connections { target: root.controller; function onSnapshotChanged() { root.sync(); } }
    Component.onCompleted: { lastCycle = controller.snapshot.cycle; lastState = controller.snapshot.state; }
    Behavior on turn { NumberAnimation { id: rotationAnim; duration: root.motion ? 520 : 0; easing.type: Easing.InOutCubic } }
    // Geometry rotates as a frame, sand keeps its physical upper/lower orientation.
    Canvas {
        id: glass
        anchors.fill: parent
        renderStrategy: Canvas.Threaded
        onPaint: {
            const c = getContext("2d");
            c.reset();
            c.scale(width / 42, height / 54);
            const f = Math.max(0, Math.min(1, root.fraction));
            const sand = root.sandColor;
            c.fillStyle = sand;
            // Clip into the two transparent, rounded chambers.
            c.save();
            c.beginPath(); c.moveTo(8, 6); c.lineTo(34, 6); c.quadraticCurveTo(34, 17, 23, 26); c.lineTo(19, 26); c.quadraticCurveTo(8, 17, 8, 6); c.closePath(); c.clip();
            c.fillRect(6, 26 - 20 * Math.sqrt(f), 30, 22);
            c.restore();
            c.save();
            c.beginPath(); c.moveTo(19, 28); c.lineTo(23, 28); c.quadraticCurveTo(34, 37, 34, 48); c.lineTo(8, 48); c.quadraticCurveTo(8, 37, 19, 28); c.closePath(); c.clip();
            c.fillRect(6, 48 - 20 * Math.sqrt(1 - f), 30, 22);
            c.restore();
            c.save(); c.translate(21, 27); c.rotate(root.turn * Math.PI / 180); c.translate(-21, -27);
            c.strokeStyle = root.outlineColor; c.lineWidth = 1.4;
            c.beginPath(); c.moveTo(9, 5); c.lineTo(33, 5); c.quadraticCurveTo(35, 18, 23, 27); c.quadraticCurveTo(35, 36, 33, 49); c.lineTo(9, 49); c.quadraticCurveTo(7, 36, 19, 27); c.quadraticCurveTo(7, 18, 9, 5); c.closePath(); c.stroke();
            c.lineCap = "round"; c.lineWidth = 2.5;
            c.beginPath(); c.moveTo(7, 3); c.lineTo(35, 3); c.moveTo(7, 51); c.lineTo(35, 51); c.stroke(); c.restore();
        }
        Connections { target: Colours; function onPaletteChanged() { glass.requestPaint(); } }
    }
    onFractionChanged: glass.requestPaint()
    onTurnChanged: glass.requestPaint()
    // Six bounded grains; a paused animation preserves every grain's position.
    Repeater {
        model: 6
        Rectangle {
            required property int index
            width: Math.max(1, root.width / 28); height: width
            radius: width / 2
            color: root.sandColor
            x: root.width * 0.5 + ((index % 3) - 1) * width - width / 2
            y: root.height * (0.49 + ((root.phase + index / 6) % 1) * 0.33)
            visible: root.motion && ((root.fraction > 0 && (root.running || root.controller.snapshot.state === "Paused")) || root.finishing)
            opacity: root.running && rotationAnim.running ? 0 : 0.7
        }
    }
    NumberAnimation on phase {
        id: falling
        from: 0; to: 1; duration: 900; loops: Animation.Infinite
        running: (root.running || root.controller.snapshot.state === "Paused" || root.finishing) && root.motion
        paused: running && (!root.visible || !root.animationActive || root.controller.snapshot.state === "Paused" || (root.running && rotationAnim.running))
    }
    Timer {
        id: finishTimer
        interval: root.motion ? 240 : 1
        onTriggered: { root.finishing = false; root.rotationTarget += 180; pulse.restart(); }
    }
    SequentialAnimation {
        id: pulse
        NumberAnimation { target: root; property: "scale"; to: 1.06; duration: root.motion ? 180 : 0 }
        NumberAnimation { target: root; property: "scale"; to: 1; duration: root.motion ? 240 : 0 }
    }
}

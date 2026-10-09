pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import Caelestia.Config
import qs.components
import qs.services

Rectangle {
    id: root
    property bool increase: true
    property bool motion: true
    property bool holding: false
    property int repeats: 0
    signal stepped(int delta)
    signal scrolled(var event)
    implicitWidth: 32
    implicitHeight: 20
    radius: Tokens.rounding.small
    color: mouse.containsMouse || holding ? Colours.palette.m3surfaceContainerHigh : "transparent"
    opacity: enabled ? 1 : 0.25
    Behavior on color { ColorAnimation { duration: root.motion ? 140 : 0 } }
    function beginHold() {
        if (!enabled || !visible || holding) return;
        holding = true; repeats = 0;
        stepped(increase ? 1 : -1);
        repeatTimer.interval = 340; repeatTimer.restart();
    }
    function endHold() { holding = false; repeatTimer.stop(); }
    onEnabledChanged: if (!enabled) endHold()
    onVisibleChanged: if (!visible) endHold()
    Component.onDestruction: endHold()
    Timer {
        id: repeatTimer
        repeat: true
        onTriggered: {
            if (!root.holding || !root.enabled || !root.visible) { root.endHold(); return; }
            root.repeats++;
            root.stepped(root.increase ? 1 : -1);
            interval = Math.max(35, Math.round(180 * Math.pow(0.84, root.repeats - 1)));
        }
    }
    MaterialIcon {
        anchors.centerIn: parent
        text: root.increase ? "keyboard_arrow_up" : "keyboard_arrow_down"
        fontStyle: Tokens.font.icon.small
        color: Colours.palette.m3onSurfaceVariant
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true; preventStealing: true
        cursorShape: Qt.PointingHandCursor
        onPressed: root.beginHold()
        onReleased: root.endHold()
        onCanceled: root.endHold()
        onExited: root.endHold()
        onWheel: event => root.scrolled(event)
    }
    activeFocusOnTab: true
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return) {
            if (!event.isAutoRepeat) beginHold();
            event.accepted = true;
        }
    }
    Keys.onReleased: event => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return) {
            if (!event.isAutoRepeat) endHold();
            event.accepted = true;
        }
    }
    onActiveFocusChanged: if (!activeFocus && !mouse.pressed) endHold()
    Connections {
        target: root.Window.window
        function onActiveChanged() { if (!root.Window.window.active) root.endHold(); }
    }
    Accessible.role: Accessible.Button
    Accessible.onPressAction: stepped(increase ? 1 : -1)
}

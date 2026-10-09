pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Caelestia.Config
import qs.components
import qs.services

PanelWindow {
    id: root
    required property var controller
    property var host: null
    readonly property bool wanted: host !== null && controller.healthy &&
        (controller.snapshot.state === "Running" || controller.snapshot.state === "Paused" || controller.snapshot.alarm_active) &&
        !host.visibilities.dashboard && Config.dashboard.enabled && !host.visibilities.overview
    property real reveal: wanted ? 1 : 0
    screen: host ? host.parent.screen : null
    Config.screen: screen ? screen.name : ""
    anchors.top: true
    readonly property real availableWidth: screen ? Math.max(1, screen.width - Math.min(24, screen.width * 0.08)) : 854
    implicitWidth: Math.min(host ? host.timerDashboardWidth : 854, availableWidth)
    implicitHeight: 30
    margins.top: 0
    color: "transparent"
    visible: wanted || reveal > 0
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "caelestia-animated-timer"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    Behavior on reveal { NumberAnimation { duration: root.controller.motion ? 180 : 0; easing.type: Easing.OutCubic } }
    Rectangle {
        anchors.fill: parent
        radius: Tokens.rounding.large
        topLeftRadius: 0; topRightRadius: 0
        objectName: "animatedTimerNotchSurface"
        color: Qt.alpha(GlobalConfig.appearance.pitchBlack ? "#000000" : Colours.tPalette.m3surface,
            GlobalConfig.appearance.pitchBlack ? 1 : Colours.transparency.enabled ? Colours.transparency.base : 1)
        clip: true
        opacity: root.reveal
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { if (root.host) root.host.openTimerTab(); } }
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: root.width < 180 ? 6 : 12; anchors.rightMargin: root.width < 180 ? 6 : 8; spacing: root.width < 180 ? 4 : 10
            Hourglass { visible: root.width >= 180; controller: root.controller; animationActive: root.wanted; Layout.preferredWidth: 17; Layout.preferredHeight: 23 }
            StyledText {
                text: {
                    const s = root.controller.snapshot.remaining;
                    return [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60].map(n => n.toString().padStart(2, "0")).join(":");
                }
            }
            Rectangle {
                visible: root.width >= 220
                Layout.fillWidth: true; implicitHeight: 2; radius: 1
                color: Colours.palette.m3surfaceContainerHighest
                Rectangle { width: parent.width * (1 - root.controller.snapshot.fraction); height: 2; color: Colours.palette.m3primary; radius: 1 }
            }
            Item { visible: root.width < 220; Layout.fillWidth: true }
            TimerButton {
                objectName: "animatedTimerNotchControl"
                icon: root.controller.snapshot.state === "Completed" ? "notifications_off" : root.controller.snapshot.state === "Running" ? "pause" : "play_arrow"
                flat: true; implicitWidth: 28; implicitHeight: 26
                motion: root.controller.motion; activeFocusOnTab: false
                Accessible.name: root.controller.snapshot.state === "Completed" ? qsTr("Stop alarm") : root.controller.snapshot.state === "Running" ? qsTr("Pause") : qsTr("Resume")
                onClicked: {
                    if (root.controller.snapshot.state === "Completed") root.controller.send({action: "dismiss-alarm"});
                    else root.controller.primary();
                }
            }
        }
    }
}

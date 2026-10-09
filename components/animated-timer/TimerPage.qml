pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

Rectangle {
    id: root
    required property var controller
    property bool presentationActive: true
    property bool editingDuration: false
    property string editingPreset: ""
    property string presetError: ""
    property string previousState: "Ready"
    readonly property var timer: controller.snapshot
    readonly property bool activeCountdown: timer.state === "Running" || timer.state === "Paused"
    readonly property bool editing: timer.state === "Ready" || editingDuration
    readonly property int displaySeconds: editing ? timer.configured : timer.remaining
    implicitWidth: Tokens.sizes.dashboard.mediaTabWidth
    implicitHeight: Tokens.sizes.dashboard.mediaTabHeight
    radius: Tokens.rounding.large
    color: Colours.palette.m3surfaceContainerLow
    function editPreset(preset) {
        editingPreset = preset ? preset.id : "";
        presetName.text = preset ? preset.name : "";
        presetMinutes.text = preset ? (preset.seconds / 60).toString() : "25";
        presetError = ""; editor.visible = true; settings.open();
    }
    onPresentationActiveChanged: if (!presentationActive) settings.close()
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 16; spacing: 8
        RowLayout {
            Layout.fillWidth: true
            MaterialIcon { text: "hourglass_top"; fontStyle: Tokens.font.icon.small; color: Colours.palette.m3onSurfaceVariant }
            StyledText { text: root.timer.state; color: Colours.palette.m3onSurfaceVariant }
            Item { Layout.fillWidth: true }
            TimerButton {
                text: ""; icon: "settings"; implicitWidth: 30; implicitHeight: 28
                motion: root.controller.motion; onClicked: settings.open()
                Accessible.name: qsTr("Timer settings")
            }
        }
        Item {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 112
            opacity: root.timer.state === "Paused" ? 0.8 : 1
            Behavior on opacity { NumberAnimation { duration: root.controller.motion ? 180 : 0 } }
            RowLayout {
                id: digitsRow
                anchors.centerIn: parent; spacing: root.width < 550 ? 6 : 20
                Hourglass {
                    objectName: "animatedTimerHourglass"
                    controller: root.controller; animationActive: root.presentationActive
                    Layout.preferredWidth: root.width < 550 ? 30 : 46; Layout.preferredHeight: root.width < 550 ? 48 : 72
                    Layout.rightMargin: root.width < 550 ? 0 : 12
                }
                Repeater {
                    model: 3
                    RowLayout {
                        required property int index
                        spacing: root.width < 550 ? 0 : 4
                        DigitUnit {
                            unit: parent.index; controller: root.controller
                            value: unit === 0 ? Math.floor(root.displaySeconds / 3600) : unit === 1 ? Math.floor(root.displaySeconds / 60) % 60 : root.displaySeconds % 60
                            editable: root.editing && root.controller.healthy && root.presentationActive
                            implicitWidth: root.width < 550 ? 72 : 94
                            onAdjusted: delta => root.controller.send({action: "adjust", unit: unit, delta: delta})
                            onEntered: value => root.controller.send({action: "adjust", unit: unit, value: value})
                        }
                        StyledText { visible: parent.index < 2; text: ":"; font.pixelSize: 28; color: Colours.palette.m3onSurfaceVariant }
                    }
                }
            }
        }
        Rectangle {
            Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: Math.min(root.width - 32, 480)
            implicitHeight: 2; radius: 1; color: Colours.palette.m3surfaceContainerHighest
            Rectangle {
                width: parent.width * (1 - root.timer.fraction); height: parent.height; radius: 1
                color: Colours.palette.m3primary
                Behavior on width { NumberAnimation { duration: root.controller.motion ? 180 : 0; easing.type: Easing.OutCubic } }
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter; spacing: 8
            TimerButton {
                text: root.timer.state === "Completed" && root.timer.alarm_active ? qsTr("Stop") : root.timer.state === "Running" ? qsTr("Pause") : root.timer.state === "Paused" ? qsTr("Resume") : qsTr("Start")
                icon: root.timer.state === "Completed" && root.timer.alarm_active ? "notifications_off" : root.timer.state === "Running" ? "pause" : "play_arrow"
                primary: true; motion: root.controller.motion
                enabled: root.controller.healthy && (root.timer.alarm_active || root.activeCountdown || root.timer.configured > 0)
                objectName: "animatedTimerPrimary"
                onClicked: { root.editingDuration = false; if (root.timer.state === "Completed" && root.timer.alarm_active) root.controller.send({action: "dismiss-alarm"}); else root.controller.primary(); }
            }
            TimerButton {
                objectName: "animatedTimerStopAlarm"
                visible: root.timer.alarm_active && root.timer.state !== "Completed"
                text: qsTr("Stop"); icon: "notifications_off"; motion: root.controller.motion
                onClicked: root.controller.send({action: "dismiss-alarm"})
                Accessible.name: qsTr("Stop alarm")
            }
            TimerButton {
                objectName: "animatedTimerReset"; icon: "restart_alt"; implicitWidth: 38
                motion: root.controller.motion; enabled: root.controller.healthy
                Accessible.name: qsTr("Reset")
                onClicked: { rotationTarget += 360; root.editingDuration = false; root.controller.send({action: "reset"}); }
            }
            TimerButton {
                visible: root.activeCountdown; icon: "stop"; implicitWidth: 38; motion: root.controller.motion
                Accessible.name: qsTr("Cancel")
                onClicked: { root.editingDuration = false; root.controller.send({action: "cancel"}); }
            }
            TimerButton {
                visible: root.activeCountdown || root.timer.state === "Completed"
                icon: root.editingDuration ? "timer" : "edit"; implicitWidth: 38; motion: root.controller.motion
                Accessible.name: root.editingDuration ? qsTr("Show countdown") : qsTr("Edit next duration")
                onClicked: root.editingDuration = !root.editingDuration
            }
        }
        StyledText { visible: root.controller.error !== ""; text: root.controller.error; color: Colours.palette.m3error; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Flickable {
            id: presetStrip
            Layout.fillWidth: true; implicitHeight: 36
            contentWidth: presetsRow.implicitWidth; contentHeight: height; clip: true; boundsBehavior: Flickable.StopAtBounds
            RowLayout {
                id: presetsRow
                anchors.verticalCenter: parent.verticalCenter
                x: Math.max(0, (presetStrip.width - implicitWidth) / 2); spacing: 6
                Repeater {
                    model: root.timer.presets
                    TimerButton {
                        required property var modelData
                        text: modelData.name; implicitHeight: 32; motion: root.controller.motion
                        onClicked: root.controller.send({action: "configure", seconds: modelData.seconds})
                    }
                }
            }
        }
    }
    Popup {
        id: settings
        x: Math.max(8, root.width - width - 12); y: 12
        width: Math.min(380, root.width - 24); height: root.height - 24
        padding: 12; closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: Colours.palette.m3surfaceContainer; radius: Tokens.rounding.large }
        contentItem: ScrollView {
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: settings.availableWidth; spacing: 8
                Repeater {
                    model: [{key: "sound", label: qsTr("Sound")}, {key: "notification", label: qsTr("Notifications")}, {key: "repeat", label: qsTr("Repeat")}, {key: "animation", label: qsTr("Animations")}]
                    TimerButton {
                        required property var modelData
                        Layout.fillWidth: true; implicitHeight: 30
                        text: modelData.label; icon: root.timer.prefs[modelData.key] ? "check_box" : "check_box_outline_blank"
                        motion: root.controller.motion
                        onClicked: { const values = {}; values[modelData.key] = !root.timer.prefs[modelData.key]; root.controller.send({action: "preferences", values: values}); }
                        Accessible.role: Accessible.CheckBox; Accessible.checked: root.timer.prefs[modelData.key]
                    }
                }
                Repeater {
                    model: root.timer.presets
                    RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        StyledText { Layout.fillWidth: true; text: parent.modelData.name; elide: Text.ElideRight }
                        TimerButton { icon: "edit"; implicitWidth: 30; implicitHeight: 28; motion: root.controller.motion; Accessible.name: qsTr("Edit preset"); onClicked: root.editPreset(parent.modelData) }
                        TimerButton { icon: "delete"; implicitWidth: 30; implicitHeight: 28; motion: root.controller.motion; Accessible.name: qsTr("Delete preset"); onClicked: root.controller.send({action: "preset-delete", id: parent.modelData.id}) }
                    }
                }
                TimerButton { text: qsTr("Add preset"); icon: "add"; implicitHeight: 30; motion: root.controller.motion; onClicked: root.editPreset(null) }
                ColumnLayout {
                    id: editor
                    visible: false; Layout.fillWidth: true
                    TextField { id: presetName; Layout.fillWidth: true; placeholderText: qsTr("Name"); maximumLength: 40; color: Colours.palette.m3onSurface; background: Rectangle { radius: 8; color: Colours.palette.m3surfaceContainerHigh } }
                    RowLayout {
                        TextField { id: presetMinutes; Layout.fillWidth: true; placeholderText: qsTr("Minutes"); color: Colours.palette.m3onSurface; validator: DoubleValidator { bottom: 0.016667; top: 5999.98; decimals: 3 } background: Rectangle { radius: 8; color: Colours.palette.m3surfaceContainerHigh } }
                        TimerButton {
                            text: qsTr("Save"); motion: root.controller.motion
                            onClicked: {
                                if (presetName.text.trim() === "" || !presetMinutes.acceptableInput) { root.presetError = qsTr("Enter a name and minutes."); return; }
                                root.controller.send({action: "preset-save", id: root.editingPreset, name: presetName.text, seconds: Math.round(Number(presetMinutes.text) * 60)});
                                editor.visible = false; root.presetError = "";
                            }
                        }
                    }
                    StyledText { visible: root.presetError !== ""; text: root.presetError; color: Colours.palette.m3error }
                }
            }
        }
    }
    Connections {
        target: root.controller
        function onSnapshotChanged() {
            if (root.timer.state === "Running" && (root.previousState === "Ready" || root.previousState === "Completed")) settle.restart();
            root.previousState = root.timer.state;
        }
    }
    NumberAnimation { id: settle; target: digitsRow; property: "scale"; from: 0.985; to: 1; duration: root.controller.motion ? 180 : 0; easing.type: Easing.OutCubic }
}

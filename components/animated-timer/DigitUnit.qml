pragma ComponentBehavior: Bound
import QtQuick
import Caelestia.Config
import qs.components
import qs.services
import "Wheel.js" as Wheel

Item {
    id: root
    required property int value
    required property int unit
    required property var controller
    property bool editable: true
    property bool editing: false
    property real residual: 0
    property int previous: value
    property string oldText: "00"
    property real outgoingTarget: 0
    readonly property bool motion: controller.motion
    readonly property string unitName: [qsTr("Hours"), qsTr("Minutes"), qsTr("Seconds")][unit]
    signal adjusted(int delta)
    signal entered(int value)
    implicitWidth: 94
    implicitHeight: 112
    function padded(number) { return number.toString().padStart(2, "0"); }
    function consumeWheel(event) {
        event.accepted = true;
        if (!editable) return;
        const result = Wheel.consume(residual, event.angleDelta.y, event.pixelDelta.y);
        residual = result.residual;
        if (result.steps !== 0) adjusted(result.steps);
    }
    onEditableChanged: if (!editable) { editing = false; residual = 0; }
    onValueChanged: {
        roll.stop(); oldText = padded(previous); previous = value;
        current.y = value >= Number(oldText) ? viewport.height * 0.45 : -viewport.height * 0.45;
        outgoingTarget = -current.y; outgoing.y = 0; outgoing.opacity = 1; roll.start();
    }
    AdjustArrow {
        objectName: "animatedTimer" + root.unitName + "Increase"
        anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top
        enabled: root.editable; motion: root.motion
        onStepped: delta => root.adjusted(delta)
        onScrolled: event => root.consumeWheel(event)
        Accessible.name: qsTr("Increase") + " " + root.unitName
    }
    Rectangle {
        id: viewport
        anchors.fill: parent; anchors.topMargin: 20; anchors.bottomMargin: 20
        radius: Tokens.rounding.medium; clip: true
        color: mouse.containsMouse && root.editable ? Colours.palette.m3surfaceContainerHigh : "transparent"
        Behavior on color { ColorAnimation { duration: root.motion ? 140 : 0 } }
        Text {
            id: outgoing
            width: parent.width; height: parent.height
            text: root.oldText; opacity: 0; visible: !root.editing
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            font.family: Tokens.font.body.small.family; font.pixelSize: 54
            color: Colours.palette.m3onSurface
        }
        Text {
            id: current
            width: parent.width; height: parent.height
            text: root.padded(root.value); visible: !root.editing
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            font.family: Tokens.font.body.small.family; font.pixelSize: 54
            color: Colours.palette.m3onSurface
        }
        MouseArea {
            id: mouse
            anchors.fill: parent; hoverEnabled: true; preventStealing: true; scrollGestureEnabled: true
            cursorShape: root.editable ? Qt.IBeamCursor : Qt.ArrowCursor
            onExited: root.residual = 0
            onClicked: {
                if (!root.editable) return;
                root.editing = true; input.text = root.padded(root.value);
                input.forceActiveFocus(); input.selectAll();
            }
            onWheel: event => root.consumeWheel(event)
        }
        TextInput {
            id: input
            anchors.fill: parent; visible: root.editing
            horizontalAlignment: TextInput.AlignHCenter; verticalAlignment: TextInput.AlignVCenter
            font.family: Tokens.font.body.small.family; font.pixelSize: 54
            color: Colours.palette.m3primary; selectByMouse: true; maximumLength: 2
            validator: IntValidator { bottom: 0; top: root.unit === 0 ? 99 : 59 }
            onEditingFinished: {
                if (!root.editing) return;
                if (acceptableInput) root.entered(Number(text));
                root.editing = false;
            }
            Keys.onEscapePressed: { root.editing = false; focus = false; }
        }
    }
    AdjustArrow {
        objectName: "animatedTimer" + root.unitName + "Decrease"
        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom
        increase: false; enabled: root.editable; motion: root.motion
        onStepped: delta => root.adjusted(delta)
        onScrolled: event => root.consumeWheel(event)
        Accessible.name: qsTr("Decrease") + " " + root.unitName
    }
    ParallelAnimation {
        id: roll
        NumberAnimation { target: current; property: "y"; to: 0; duration: root.motion ? 180 : 0; easing.type: Easing.OutCubic }
        NumberAnimation { target: outgoing; property: "y"; to: root.outgoingTarget; duration: root.motion ? 180 : 0; easing.type: Easing.OutCubic }
        NumberAnimation { target: outgoing; property: "opacity"; to: 0; duration: root.motion ? 180 : 0 }
    }
    Accessible.role: Accessible.EditableText
    Accessible.name: unitName
}

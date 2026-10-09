pragma ComponentBehavior: Bound
import QtQuick
import Caelestia.Config
import qs.components
import qs.services

Rectangle {
    id: root
    property string text: ""
    property string icon: ""
    property bool primary: false
    property bool flat: false
    readonly property real morphProgress: morph.amount
    property bool motion: true
    property real rotationTarget: 0
    property real iconRotation: rotationTarget
    signal clicked()
    implicitHeight: 38
    implicitWidth: label.implicitWidth + (icon === "" ? 28 : 54)
    radius: Tokens.rounding.medium
    color: primary ? Colours.palette.m3primary : mouse.containsMouse ? Colours.palette.m3surfaceContainerHighest : flat ? "transparent" : Colours.palette.m3surfaceContainerHigh
    opacity: enabled ? 1 : 0.45
    Behavior on color { ColorAnimation { duration: root.motion ? 140 : 0 } }
    Behavior on iconRotation { NumberAnimation { duration: root.motion ? 450 : 0; easing.type: Easing.OutCubic } }
    Row {
        anchors.centerIn: parent; spacing: 7
        MaterialIcon {
            visible: root.icon !== "" && root.icon !== "play_arrow" && root.icon !== "pause"
            text: root.icon
            color: root.primary ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface
            rotation: root.iconRotation
            fontStyle: Tokens.font.icon.small
        }
        Canvas {
            id: morph
            visible: root.icon === "play_arrow" || root.icon === "pause"
            width: visible ? 18 : 0; height: 18
            anchors.verticalCenter: parent.verticalCenter
            readonly property color fillColor: root.primary ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface
            onFillColorChanged: requestPaint()
            property real amount: root.icon === "pause" ? 1 : 0
            Behavior on amount { NumberAnimation { duration: root.motion ? 220 : 0; easing.type: Easing.InOutCubic } }
            onAmountChanged: requestPaint()
            onPaint: {
                const c = getContext("2d"); c.reset();
                c.fillStyle = fillColor;
                const t = amount;
                const play = [[[4,2],[10,5.5],[10,12.5],[4,16]], [[10,5.5],[16,9],[16,9],[10,12.5]]];
                const pause = [[[4,2],[8,2],[8,16],[4,16]], [[11,2],[15,2],[15,16],[11,16]]];
                for (let piece = 0; piece < 2; piece++) {
                    c.beginPath();
                    for (let point = 0; point < 4; point++) {
                        const x = play[piece][point][0] * (1 - t) + pause[piece][point][0] * t;
                        const y = play[piece][point][1] * (1 - t) + pause[piece][point][1] * t;
                        if (point === 0) c.moveTo(x,y); else c.lineTo(x,y);
                    }
                    c.closePath(); c.fill();
                }
            }
            Connections { target: Colours; function onPaletteChanged() { morph.requestPaint(); } }
        }
        StyledText { id: label; visible: root.text !== ""; text: root.text; anchors.verticalCenter: parent.verticalCenter; color: root.primary ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface }
    }
    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.clicked() }
    activeFocusOnTab: true
    Keys.onSpacePressed: clicked()
    Keys.onReturnPressed: clicked()
    Accessible.role: Accessible.Button
    Accessible.name: text
}

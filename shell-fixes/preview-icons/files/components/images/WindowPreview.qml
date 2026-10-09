pragma ComponentBehavior: Bound

import org.kde.pipewire as Pipewire
import QtQuick
import Quickshell
import Quickshell.Widgets
import Caelestia.Config
import Caelestia.Services

Item {
    id: root

    required property string address
    property bool active: true
    /// Shown until the first frame arrives, and whenever there is no stream.
    property url fallbackIcon: ""
    property real fallbackScale: 0.5
    property real sourceAspect: 16 / 9

    readonly property bool captureActive: root.active && root.visible && GlobalConfig.bar.livePreviews
    readonly property bool hasStream: stream.available && (video.item?.ready ?? false)
                                      && video.item?.state !== Pipewire.PipeWireSourceItem.Error

    WindowStream {
        id: stream

        active: root.captureActive
        address: root.address
    }

    FallbackIcon {
        objectName: "windowPreviewFallback"
        anchors.centerIn: parent
        asynchronous: true
        implicitSize: Math.min(root.width, root.height) * root.fallbackScale
        source: root.fallbackIcon || Quickshell.iconPath("application-x-executable")
        visible: !root.hasStream
        z: 1
    }

    Loader {
        id: video
        anchors.fill: parent
        // Zero is not KPipeWire's "no object serial" sentinel. Construct a
        // consumer only after the producer has advertised a valid target.
        active: root.captureActive && stream.available
        sourceComponent: Pipewire.PipeWireSourceItem {
            readonly property real fitted: root.sourceAspect > (root.width / Math.max(1, root.height)) ? root.width / root.sourceAspect : root.height

            anchors.centerIn: parent
            height: fitted
            width: fitted * root.sourceAspect
            // Keep this item visible while waiting for frames: hiding it
            // pauses KPipeWire and prevents ready from becoming true.
            Component.onCompleted: {
                if ("objectSerial" in this)
                    this.objectSerial = Qt.binding(() => stream.objectSerial);
                else if ("nodeId" in this)
                    this.nodeId = Qt.binding(() => stream.nodeId);
            }
        }
    }
}

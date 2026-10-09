pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Widgets

IconImage {
    id: root

    property url fallbackSource: Quickshell.iconPath("application-x-executable")

    // Keep the caller's source binding intact so a later tray/window update
    // automatically recovers from a missing image or unavailable DBus icon.
    IconImage {
        objectName: "iconFallback"
        anchors.fill: parent
        source: root.fallbackSource
        visible: root.status !== Image.Ready
    }
}

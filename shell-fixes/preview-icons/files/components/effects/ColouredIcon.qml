pragma ComponentBehavior: Bound

import QtQuick
import Quickshell.Widgets
import Caelestia
import Caelestia.Images
import qs.components.images

FallbackIcon {
    id: root

    required property color colour

    asynchronous: true

    layer.enabled: visible && status === Image.Ready
    layer.effect: Colouriser {
        sourceColor: analyser.dominantColour
        colorizationColor: root.colour
    }

    layer.onEnabledChanged: {
        if (layer.enabled && status === Image.Ready)
            analyser.requestUpdate();
    }

    onStatusChanged: {
        if (layer.enabled && status === Image.Ready)
            analyser.requestUpdate();
    }

    ImageAnalyser {
        id: analyser

        sourceItem: root
    }
}

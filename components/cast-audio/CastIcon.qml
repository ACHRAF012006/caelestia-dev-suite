import QtQuick
import Quickshell.Io

Image {
    id: root
    property color tint: "#e0e5ef"
    property string artwork: ""
    sourceSize: Qt.size(28, 28)
    source: artwork ? "data:image/svg+xml;utf8," + encodeURIComponent(artwork.replace(/#000000/g, tint.toString())) : ""
    FileView {
        id: iconFile
        path: decodeURIComponent(Qt.resolvedUrl("assets/cast.svg").toString().replace(/^file:\/\//, ""))
        onLoaded: root.artwork = iconFile.text()
    }
}

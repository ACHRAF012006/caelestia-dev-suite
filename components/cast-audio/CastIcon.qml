import QtQuick
import Quickshell.Io

Image {
    id: root
    property color tint: "#e0e5ef"
    property string artwork: ""
    fillMode: Image.PreserveAspectFit
    sourceSize: Qt.size(Math.max(1, width), Math.max(1, height))
    // SVG uses RGB; Qt's alpha-bearing #AARRGGBB is not an SVG colour.
    // Apply transparency to the image instead of embedding it in SVG text.
    opacity: tint.a
    source: artwork ? "data:image/svg+xml;utf8," + encodeURIComponent(artwork.replace(/#000000/g, Qt.rgba(tint.r, tint.g, tint.b, 1).toString())) : ""
    FileView {
        id: iconFile
        path: decodeURIComponent(Qt.resolvedUrl("assets/cast.svg").toString().replace(/^file:\/\//, ""))
        onLoaded: root.artwork = iconFile.text()
    }
}

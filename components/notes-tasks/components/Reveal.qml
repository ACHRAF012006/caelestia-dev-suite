pragma ComponentBehavior: Bound
import QtQuick
import Caelestia.Config
import qs.components

Item {
    id: root
    property bool expanded: false
    property bool motion: true
    default property alias content: body.data
    readonly property real contentHeight: body.childrenRect.height
    implicitHeight: expanded ? contentHeight : 0
    clip: true
    visible: expanded || implicitHeight > 0
    enabled: expanded
    Item { id: body; width: root.width; height: root.contentHeight }
    Behavior on implicitHeight { Anim { duration: root.motion ? Math.min(180, Tokens.anim.durations.small) : 0; type: Anim.FastSpatial } }
    opacity: expanded ? 1 : 0
    Behavior on opacity { Anim { duration: root.motion ? Math.min(180, Tokens.anim.durations.small) : 0; type: Anim.FastEffects } }
}

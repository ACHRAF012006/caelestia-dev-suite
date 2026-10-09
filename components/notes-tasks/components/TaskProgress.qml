import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

CircularProgress {
    id: root
    property int completed: 0
    property int total: 0
    property bool motion: true
    implicitSize: Math.max(Tokens.padding.large * 4, Math.max(doneLabel.implicitWidth, totalLabel.implicitWidth) + Tokens.padding.large)
    value: total ? completed / total : 0
    strokeWidth: Tokens.padding.extraSmall
    spacing: Tokens.spacing.extraSmall
    fgColour: Colours.palette.m3primary
    bgColour: Colours.tPalette.m3surfaceContainerHighest
    wavePaused: true
    Behavior on clampedVal { Anim { duration: root.motion ? Math.min(180, Tokens.anim.durations.small) : 0; type: Anim.FastSpatial } }
    ColumnLayout {
        anchors.centerIn: parent; spacing: 0
        StyledText { id: doneLabel; Layout.alignment: Qt.AlignHCenter; objectName: "notesTasksDoneCount"; text: root.completed; font: Tokens.font.title.medium; color: root.total > 0 && root.completed === root.total ? Colours.palette.m3secondary : root.fgColour }
        StyledText { id: totalLabel; Layout.alignment: Qt.AlignHCenter; objectName: "notesTasksTotalCount"; text: "/ " + root.total; font: Tokens.font.label.small; color: Colours.palette.m3onSurfaceVariant }
    }
}

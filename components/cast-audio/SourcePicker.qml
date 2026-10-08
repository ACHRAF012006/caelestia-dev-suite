pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property Theme theme: Theme {}
    property var sources: []
    property string selectedId: "default"
    readonly property bool appMode: selectedId.startsWith("app:")
    readonly property var choices: appMode ? sources.filter(s => s.kind === "application") : [{id: "default", name: qsTr("All audio · default output")}].concat(sources.filter(s => s.kind !== "application"))
    readonly property var labels: choices.map(s => ({name: s.kind === "application" && s.detail ? s.name + " · " + s.detail : s.name}))
    signal chosen(string identity)
    spacing: 8
    RowLayout {
        Layout.fillWidth: true
        spacing: 6
        ActionButton {
            objectName: "castAudioDesktop"
            Layout.fillWidth: true
            text: qsTr("Desktop audio")
            active: !root.appMode
            onClicked: root.chosen("default")
        }
        ActionButton {
            objectName: "castAudioApp"
            Layout.fillWidth: true
            text: qsTr("One app")
            active: root.appMode
            enabled: root.sources.some(s => s.kind === "application")
            onClicked: root.chosen(root.sources.find(s => s.kind === "application").id)
        }
    }
    Controls.ComboBox {
        objectName: "castAudioSource"
        Layout.fillWidth: true
        model: root.labels
        textRole: "name"
        currentIndex: root.choices.findIndex(s => s.id === root.selectedId)
        displayText: currentIndex >= 0 ? root.labels[currentIndex].name : qsTr("Selected source unavailable")
        palette.button: root.theme.raised
        palette.buttonText: root.theme.foreground
        palette.base: root.theme.card
        palette.text: root.theme.foreground
        palette.window: root.theme.card
        palette.windowText: root.theme.foreground
        palette.highlight: root.theme.accent
        palette.highlightedText: root.theme.accentText
        onActivated: index => root.chosen(root.choices[index].id)
    }
    CastText {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        font.pixelSize: 11
        color: root.theme.secondary
        text: root.appMode ? qsTr("Only this app stream is shared. Local playback continues.") : qsTr("Shares every app playing through the selected output.")
    }
    CastText {
        Layout.fillWidth: true
        visible: root.appMode
        wrapMode: Text.WordWrap
        font.pixelSize: 11
        color: root.theme.secondary
        text: (root.choices.find(s => s.id === root.selectedId) || {}).detail || qsTr("Start audio in the app to make its stream available.")
    }
}

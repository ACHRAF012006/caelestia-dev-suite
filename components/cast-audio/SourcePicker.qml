pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property Theme theme: Theme {}
    property var sources: []
    property string selectedId: "default"
    property bool compact: false
    property bool selecting: false
    readonly property string selectedName: (choices.find(s => s.id === selectedId) || {}).name || qsTr("Choose source")
    readonly property bool appMode: selectedId.startsWith("app:")
    readonly property var choices: appMode ? sources.filter(s => s.kind === "application") : [{id: "default", name: qsTr("All audio · default output")}].concat(sources.filter(s => s.kind !== "application"))
    readonly property var labels: choices.map(s => ({name: s.kind === "application" && s.detail ? s.name + " · " + s.detail : s.name}))
    signal chosen(string identity)
    spacing: root.compact ? 4 : 8
    RowLayout {
        Layout.fillWidth: true
        spacing: 6
        ActionButton {
            objectName: "castAudioDesktop"
            Layout.fillWidth: true
            text: root.compact ? qsTr("Desktop") : qsTr("Desktop audio")
            active: !root.appMode
            implicitHeight: root.compact ? 34 : 44
            onClicked: { root.selecting = false; root.chosen("default"); }
        }
        ActionButton {
            objectName: "castAudioApp"
            Layout.fillWidth: true
            text: qsTr("One app")
            active: root.appMode
            enabled: root.sources.some(s => s.kind === "application")
            implicitHeight: root.compact ? 34 : 44
            onClicked: {
                if (!root.appMode) root.chosen(root.sources.find(s => s.kind === "application").id);
                root.selecting = root.compact;
            }
        }
    }
    Controls.ComboBox {
        objectName: "castAudioSource"
        visible: !root.compact
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
    ActionButton {
        objectName: "castAudioSourceExpand"
        Layout.fillWidth: true
        visible: root.compact
        implicitHeight: 34
        text: root.selectedName + (root.selecting ? "  ⌃" : "  ⌄")
        Accessible.name: qsTr("Choose audio source")
        onClicked: root.selecting = !root.selecting
    }
    Item {
        Layout.fillWidth: true
        visible: root.compact
        implicitHeight: root.selecting ? Math.min(144, options.implicitHeight) : 0
        clip: true
        enabled: root.selecting
        Behavior on implicitHeight { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Controls.ScrollView {
            id: optionsScroll
            anchors.fill: parent
            contentWidth: availableWidth
            ColumnLayout {
                id: options
                width: optionsScroll.availableWidth
                spacing: 2
                Repeater {
                    model: root.choices
                    delegate: ActionButton {
                        required property var modelData
                        objectName: "castAudioSourceChoice"
                        Layout.fillWidth: true
                        implicitHeight: 34
                        text: modelData.name
                        active: modelData.id === root.selectedId
                        onClicked: { root.chosen(modelData.id); root.selecting = false; }
                    }
                }
            }
        }
    }
    CastText {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        font.pixelSize: 11
        color: root.theme.secondary
        visible: !root.compact
        text: root.appMode ? qsTr("Only this app stream is shared. Local playback continues.") : qsTr("Shares every app playing through the selected output.")
    }
    CastText {
        Layout.fillWidth: true
        visible: root.appMode && !root.compact
        wrapMode: Text.WordWrap
        font.pixelSize: 11
        color: root.theme.secondary
        text: (root.choices.find(s => s.id === root.selectedId) || {}).detail || qsTr("Start audio in the app to make its stream available.")
    }
}

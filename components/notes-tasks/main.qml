pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root
    // PluginLoader creates one controller for the entire shell, not per page.
    property var notes: ({})
    property var tasks: ({})
    property var settings: ({defaultSection: "both", showCompleted: false, taskSort: "manual", noteSort: "updated", animation: true, compact: false, confirmDelete: true})
    property bool healthy: false
    property bool saving: false
    property string error: "Starting Notes & Tasks…"
    property int revision: 0
    readonly property bool motion: settings.animation
    signal reset()
    signal changed(string kind, string recordId, var entry)
    signal created(string requestId, string kind, string recordId)
    function records(kind) { return kind === "notes" ? notes : tasks; }
    function record(kind, id) { return records(kind)[id] ?? null; }
    function send(message) {
        if (healthy && helper.running) helper.write(JSON.stringify(message) + "\n");
    }
    function edit(kind, id, values) { send({action: "edit", kind: kind, id: id, values: values}); }
    function tags(value) { return value.split(",").map(tag => tag.trim()).filter(tag => tag.length > 0); }
    function accept(value) {
        if (value.type === "snapshot") {
            notes = {}; tasks = {};
            for (const row of value.notes) notes[row.id] = row;
            for (const row of value.tasks) tasks[row.id] = row;
            settings = value.settings; revision = value.revision;
            healthy = true; error = ""; reset();
        } else if (value.type === "delta") {
            if (value.settings) settings = value.settings;
            revision = value.revision; saving = true; error = "";
            for (const change of value.changes) {
                const rows = records(change.kind);
                const isNew = !rows[change.id];
                if (change.row) rows[change.id] = change.row;
                else delete rows[change.id];
                changed(change.kind, change.id, change.row);
                if (isNew && change.row) created(value.requestId ?? "", change.kind, change.id);
            }
        } else if (value.type === "saved") {
            if (value.revision >= revision) saving = false;
        } else if (value.type === "fatal" || value.type === "error") {
            error = value.error;
            if (value.type === "fatal") healthy = false;
        }
    }
    Process {
        id: helper
        command: ["python3", "-B", decodeURIComponent(Qt.resolvedUrl("helper/main.py").toString().replace(/^file:\/\//, ""))]
        stdinEnabled: true
        running: true
        stdout: SplitParser {
            onRead: data => {
                try { root.accept(JSON.parse(data)); }
                catch (error) { root.error = "Storage helper returned invalid data"; root.healthy = false; }
            }
        }
        onExited: { root.healthy = false; if (!root.error) root.error = "Storage helper stopped. Reload the shell to reconnect."; }
    }
    Component.onDestruction: if (helper.running) helper.write('{"action":"quit"}\n')
}

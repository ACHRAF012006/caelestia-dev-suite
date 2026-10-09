pragma ComponentBehavior: Bound
import QtQuick
import "Query.js" as Query

QtObject {
    id: root
    required property var controller
    required property string kind
    property string query: ""
    property string tag: ""
    property int completionDelay: 0
    property var pending: ({})
    property Timer settle: Timer {
        onTriggered: {
            const now = Date.now();
            for (const id of Object.keys(root.pending)) {
                if (root.pending[id].due <= now) { const entry = root.pending[id].entry; delete root.pending[id]; root.update(id, entry, true); }
            }
            root.schedule();
        }
    }
    function schedule() {
        const delays = Object.values(pending).map(value => value.due - Date.now());
        if (delays.length) { settle.interval = Math.max(1, Math.min(...delays)); settle.restart(); }
        else settle.stop();
    }
    property string filter: "active"
    property string sortOrder: kind === "notes" ? controller.settings.noteSort : controller.settings.taskSort
    property bool showCompleted: controller.settings.showCompleted
    property string day: Query.today()
    property var positions: ({})
    function accepts(entry) { return (!tag || entry.tags.indexOf(tag) >= 0) && Query.matches(kind, entry, query, filter, showCompleted, day); }
    function compare(a, b) { return Query.compare(kind, a, b, sortOrder, day); }
    function dto(entry) { return {recordId: entry.id, entry: entry, group: kind === "tasks" ? Query.group(entry, day) : ""}; }
    function rebuild(refresh) {
        pending = {}; settle.stop();
        const entries = Object.values(controller.records(kind)).filter(row => accepts(row)).sort((a, b) => compare(a, b));
        const wanted = new Set(entries.map(entry => entry.id));
        for (let i = rows.count - 1; i >= 0; --i)
            if (!wanted.has(rows.get(i).recordId)) rows.remove(i);
        positions = {}; reindex(0, rows.count);
        for (let i = 0; i < entries.length; ++i) {
            const entry = entries[i], old = positions[entry.id];
            if (old === undefined) { rows.insert(i, dto(entry)); reindex(i, rows.count); }
            else {
                if (old !== i) { rows.move(old, i, 1); reindex(Math.min(old, i), Math.max(old, i) + 1); }
                if (refresh) rows.setProperty(i, "entry", entry);
                const group = kind === "tasks" ? Query.group(entry, day) : "";
                if (rows.get(i).group !== group) rows.setProperty(i, "group", group);
            }
        }
    }
    function reindex(start, end) {
        for (let i = start; i < end; ++i) positions[rows.get(i).recordId] = i;
    }
    function update(recordId, entry, settled) {
        const old = positions[recordId] ?? -1;
        if (!settled && old >= 0 && entry && kind === "tasks" && completionDelay > 0 && rows.get(old).entry.completed !== entry.completed) {
            rows.setProperty(old, "entry", entry);
            pending[recordId] = {entry: entry, due: Date.now() + completionDelay}; schedule();
            return;
        }
        if (!settled && pending[recordId] && entry) { pending[recordId].entry = entry; rows.setProperty(old, "entry", entry); return; }
        delete pending[recordId];
        if (!entry || !accepts(entry)) {
            if (old >= 0) { rows.remove(old); delete positions[recordId]; reindex(old, rows.count); }
            return;
        }
        if (old >= 0) {
            rows.setProperty(old, "entry", entry);
            rows.setProperty(old, "group", kind === "tasks" ? Query.group(entry, day) : "");
            // Only the changed record moves; delegates for other records survive.
            let target = old;
            while (target > 0 && compare(entry, rows.get(target - 1).entry) < 0) --target;
            while (target < rows.count - 1 && compare(entry, rows.get(target + 1).entry) > 0) ++target;
            if (target !== old) { rows.move(old, target, 1); reindex(Math.min(target, old), Math.max(target, old) + 1); }
        } else {
            let low = 0, high = rows.count;
            while (low < high) { const mid = Math.floor((low + high) / 2); if (compare(entry, rows.get(mid).entry) < 0) high = mid; else low = mid + 1; }
            rows.insert(low, dto(entry)); reindex(low, rows.count);
        }
    }
    function adjacent(recordId, offset) {
        const i = positions[recordId] ?? -1;
        return i >= 0 && i + offset >= 0 && i + offset < rows.count ? rows.get(i + offset).recordId : "";
    }
    onCompletionDelayChanged: if (completionDelay === 0) {
        settle.stop();
        for (const id of Object.keys(pending)) { const entry = pending[id].entry; delete pending[id]; update(id, entry, true); }
    }
    onTagChanged: rebuild()
    onQueryChanged: rebuild()
    onFilterChanged: rebuild()
    onSortOrderChanged: rebuild()
    onShowCompletedChanged: rebuild()
    onDayChanged: rebuild()
    Component.onCompleted: rebuild()
    readonly property ListModel model: ListModel { id: rows; dynamicRoles: true }
    property Connections subscription: Connections {
        target: root.controller
        function onReset() { root.day = Query.today(); root.rebuild(true); }
        function onChanged(kind, recordId, entry) { if (kind === root.kind) root.update(recordId, entry); }
    }
}

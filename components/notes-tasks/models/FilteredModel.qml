pragma ComponentBehavior: Bound
import QtQuick
import "Query.js" as Query

QtObject {
    id: root
    required property var controller
    required property string kind
    property string query: ""
    property string filter: "active"
    property string sortOrder: kind === "notes" ? controller.settings.noteSort : controller.settings.taskSort
    property bool showCompleted: controller.settings.showCompleted
    property string day: Query.today()
    property var positions: ({})
    function accepts(entry) { return Query.matches(kind, entry, query, filter, showCompleted, day); }
    function compare(a, b) { return Query.compare(kind, a, b, sortOrder, day); }
    function dto(entry) { return {recordId: entry.id, entry: entry, group: kind === "tasks" ? Query.group(entry, day) : ""}; }
    function rebuild() {
        const entries = Object.values(controller.records(kind)).filter(row => accepts(row)).sort((a, b) => compare(a, b));
        rows.clear(); positions = {};
        for (const entry of entries) { positions[entry.id] = rows.count; rows.append(dto(entry)); }
    }
    function reindex(start, end) {
        for (let i = start; i < end; ++i) positions[rows.get(i).recordId] = i;
    }
    function update(recordId, entry) {
        const old = positions[recordId] ?? -1;
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
    onQueryChanged: rebuild()
    onFilterChanged: rebuild()
    onSortOrderChanged: rebuild()
    onShowCompletedChanged: rebuild()
    onDayChanged: rebuild()
    Component.onCompleted: rebuild()
    readonly property ListModel model: ListModel { id: rows; dynamicRoles: true }
    property Connections subscription: Connections {
        target: root.controller
        function onReset() { root.day = Query.today(); root.rebuild(); }
        function onChanged(kind, recordId, entry) { if (kind === root.kind) root.update(recordId, entry); }
    }
}

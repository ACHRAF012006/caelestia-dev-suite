.pragma library

function today() {
    const d = new Date();
    return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
}
function group(row, day) {
    return row.completed ? "Completed" : !row.due.date ? "Anytime" : row.due.date <= day ? "Today" : "Upcoming";
}
function matches(kind, row, query, filter, showCompleted, day) {
    const words = query.trim().toLowerCase().split(/\s+/).filter(word => word.length);
    if (!words.every(word => row.searchText.indexOf(word) >= 0)) return false;
    if (kind === "notes") return filter === "archived" ? row.archived : !row.archived;
    if (filter === "completed") return row.completed;
    if (filter === "all") return true;
    if (row.completed && !showCompleted) return false;
    if (filter === "today") return !row.completed && row.due.date && row.due.date <= day;
    if (filter === "upcoming") return !row.completed && row.due.date > day;
    return true;
}
function compare(kind, a, b, sort, day) {
    if (kind === "notes") {
        if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
        const c = sort === "title" ? a.title.localeCompare(b.title) : sort === "created" ? b.createdAt.localeCompare(a.createdAt) : b.updatedAt.localeCompare(a.updatedAt);
        return c || a.id.localeCompare(b.id);
    }
    const rank = {Today: 0, Upcoming: 1, Anytime: 2, Completed: 3};
    const g = rank[group(a, day)] - rank[group(b, day)];
    if (g) return g;
    let c = 0;
    if (sort === "due") c = (a.due.date || "9999").localeCompare(b.due.date || "9999") || a.due.time.localeCompare(b.due.time);
    else if (sort === "priority") c = b.priority - a.priority;
    else if (sort === "created") c = b.createdAt.localeCompare(a.createdAt);
    else c = a.order - b.order;
    return c || a.id.localeCompare(b.id);
}

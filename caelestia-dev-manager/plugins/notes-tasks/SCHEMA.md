# Personal data schema 1

The document contains `schemaVersion: 1`, monotonic `revision`, `notes`, `tasks`
and `settings`. IDs are opaque UUID strings; timestamps are UTC ISO 8601. Due
values use local calendar strings `YYYY-MM-DD` and optional `HH:MM`, never
implicit UTC conversion. Unknown newer schema versions fail before any write.
The pure migration registry advances one version at a time on a copy, validates
the result and commits through the normal atomic writer. There is no historical
schema migration in version 1. A future release must supply and test each step.

```json
{
  "schemaVersion": 1,
  "revision": 0,
  "notes": [{
    "id": "opaque-id", "title": "", "content": {"format": "plain", "text": ""},
    "tags": [], "pinned": false, "archived": false,
    "createdAt": "2026-10-09T12:00:00.000+00:00", "updatedAt": "2026-10-09T12:00:00.000+00:00",
    "extensions": {}
  }],
  "tasks": [{
    "id": "opaque-task-id", "title": "", "details": "", "tags": [],
    "completed": false, "completedAt": "", "order": 1024,
    "due": {"date": "", "time": ""}, "priority": 0,
    "subtasks": [{"id": "opaque-subtask-id", "title": "", "completed": false}],
    "recurrence": null, "projectId": null,
    "createdAt": "2026-10-09T12:00:00.000+00:00", "updatedAt": "2026-10-09T12:00:00.000+00:00",
    "extensions": {}
  }],
  "settings": {
    "defaultSection": "both", "showCompleted": false, "taskSort": "manual",
    "noteSort": "updated", "animation": true, "compact": false, "confirmDelete": true
  }
}
```

Priority is 0 (none), 1 (low), 2 (medium), or 3 (high). Manual order uses spaced
integers; reordering renumbers only changed rows and emits incremental deltas.
Completed tasks retain all their data. User deletion is permanent subject to the
preference and retained previous snapshot. Record extension fields survive edits;
format/recurrence semantics must be added deliberately in a future version.

The wire protocol is separate: `snapshot`, field-level `delta`, `saved`, `error`
and `fatal`. DTOs flatten note bodies and cache searchable text. QML never reads
or writes files. All dashboards use one controller's commands and deltas; the
helper performs serialized mutations under its lifetime writer lock. Saves coalesce
multiple revisions. A sidecar conflict fails visibly rather than starting a second
writer. Cross-process or cross-device live synchronization is not implemented.

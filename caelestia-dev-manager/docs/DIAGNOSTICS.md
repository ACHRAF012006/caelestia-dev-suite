# Read-only diagnostics and jobs

Diagnostics → Check System Health uses a read-only SQLite connection and a bounded
background job. It checks DB quick_check/schema, pending journal, source and exact
installed ownership, missing/changed files, shortcuts, dependency metadata, backup
integrity, reviewed host signatures/receipts, environment/tools/XDG paths and cached
Store commit. Corrupt/incomplete backups are reported. No repair, network fetch,
source execution, dependency install or discovery write runs during diagnostics.
Use Components/Backups/Settings for existing explicit reviewed repair/restore.
Operation History displays structured lifecycle transaction/recovery results.

The supported CLI is read-only and uses the same backend without QApplication:

    caelestia-dev-manager --json status
    caelestia-dev-manager --json doctor
    caelestia-dev-manager list
    caelestia-dev-manager validate <id>
    caelestia-dev-manager backup list

Options --project and --sandbox select source/temporary roots. Missing registry is
reported without creating directories. Doctor performs full backup verification;
status omits blob verification. Output is JSON. Mutating CLI commands are absent.
The installed launcher dispatches to backend.cli; no command opens the normal GUI.

backend.jobs owns queued/running/succeeded/failed/cancelled states, generation IDs,
structured redacted errors and bounded in-memory progress logs. A shared pool runs
at most two jobs, with a bounded queue. app.jobs delivers results/progress to Qt.
Existing Store/Inspection APIs are retained as bridges over that scheduler.
Inspection still freezes inventory on the main thread and drops obsolete results.
Reviewed slow operations use their own Manager/SQLite connection created and closed
in the worker, never the UI connection. Dependency cancellation is checked between
stages; an active venv/pip subprocess finishes or times out before cancellation.
File mutations cannot be cancelled midway. The native dialog stays open while they
finish. Production post-mutation inspections run asynchronously.

Manager logs rotate at 1 MiB with three retained files, and DB events/history retain
at most 3,000 entries. Error URLs/credentials are redacted before persistence.
Component stdout logs remain independent; the manager does not become a log daemon
or runtime supervisor. Display results are not mutation authorization. Some small
source/UI operations and service/log queries still run synchronously; these are
recorded as remaining work in the audit/release notes.

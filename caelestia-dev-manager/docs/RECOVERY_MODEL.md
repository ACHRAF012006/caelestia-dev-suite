# Recovery model

The manager coordinates files, SQLite and reviewed manager-owned host adapters;
it cannot make these and systemd a single atomic transaction. Operations take an
advisory cross-process lock. Sequence: fresh plan/ownership checks → full touched
snapshot → synced backup metadata → synced journal → atomic file changes → adapter
changes → SQLite record/ownership/history commit → durable journal removal.
Atomic file replacement syncs data/mode and its parent directory; newly created directories and host-receipt deletions also sync their parents. Journal v2 records intended
payload hashes/modes as well as the old backup. Closing the manager never removes
components or stops their independent runtimes.

On startup a journal blocks mutations; read-only inspection remains available.
Explicit Settings recovery finalizes an operation whose ID is already committed,
or preflights ALL backup blobs and payload paths before rollback. Current payloads
must match either the saved before state or journal after state. A missing old file
is accepted only when the journal proves an intended removal. Third-party edits,
symlinks, foreign ownership, missing/corrupt blobs or invalid receipts retain the
journal and fail closed for manual reconciliation. Legacy journals lacking after
state can recover unchanged files; ambiguous changed files require reconciliation.
Trusted host outputs/receipts are re-derived, never accepted as arbitrary journal
code. A failed rollback keeps its intent. Repeated recovery is idempotent.

Crash during backup: incomplete snapshot has no completed metadata and never
becomes a restore candidate. Missing blob: inspection/recovery reports corruption,
not a partial restore. DB commit before crash: operation ID finalizes journal.
Files changed before receipt commit: rollback restores old receipts and verified
old files. Host partial apply: restore exact verified originals/previous receipts.
Runtime services and native package/firewall preparation are external state: check
status after failure; completed machine setup is not automatically undone.

Dependency partial preparation has no readiness marker; retry inspects its private
files. Deleted source does not remove installed runtime. Missing/offline catalogue
uses the last validated cache and cannot update runtime. Source swaps retain old
source directories and metadata under source-backups; crash recovery of those swaps
remains manual (COMPONENT_STORE). Database corruption stops writes; preserve DB,
WAL and journal and inspect online migration backups (DATABASE_MIGRATIONS).

Recovery never guesses ownership, force overwrites edited host files, removes
unrelated data, runs component hooks or restarts production as a development test.
Power-loss guarantees depend on the filesystem honoring fsync. Same-user external
path races still need future openat/O_NOFOLLOW hardening; flock is advisory.

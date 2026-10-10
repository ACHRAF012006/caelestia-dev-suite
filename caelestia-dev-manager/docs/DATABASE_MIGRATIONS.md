# Database migrations

`backend.database` owns all schema changes. SQLite user_version increases from
legacy 0 to base tables 1 to structured operation history/indexes 2. Legacy tables
must match the known contract. Each upgrade runs under BEGIN IMMEDIATE and commits
DDL plus version together. Existing databases receive an online SQLite backup
(including committed WAL state) under registry parent `database-backups/` first.
Future schemas and unknown legacy structures fail before mutation. Errors preserve
the database and explain the recovery path. WAL plus synchronous=FULL remains the
normal registry mode. Connections remain confined to the thread that creates them.

Keep the database and its WAL/SHM files together when investigating corruption.
Close all manager processes before restoring an inspected database backup; do not
restore an older DB alone over newer filesystem receipts. Reconcile interrupted
file operations through the journal with the manager version that understands it.
No automatic destructive repair, table dropping, or downgrade is provided.

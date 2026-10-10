# Portable personal data and data migrations: design boundary

Schema 2 validates optional portable_data root/path declarations, restricted to
children of XDG data/config/state `caelestia-components/<id>/`. This is a declaration,
not authorization to collect or mutate files. Existing components' personal data
locations are preserved; declarations are not added retroactively. Local installed
backups/restore remain implemented. Portable component archives transfer source and
resources only. Portable installed/personal-data backup execution is deferred.

A future portable backup must map generated destinations to logical payload,
launcher, unit and approved shortcut roles, not trust absolute paths from another
machine. Imported receipts must never grant ownership. Host originals/receipts and
compiled Python environments require compatibility/reconstruction, not blind copying.
Export review must enumerate each explicit data file/size/hash with opt-in selection,
exclude sockets/device files/links, and warn about private data actually selected.
Restore must plan fixed target roots, check collisions and current ownership, back
up existing data and participate in a separate recoverable data transaction.

Proposed data migration API (not executed by this release): versioned descriptors
with from/to data schema and operations rename-json-key, create-directory,
move-owned-file and copy-owned-file. Operands are relative to one declared portable
location. No shell, Python expressions, URLs, root commands or arbitrary hooks.
JSON transforms must reject duplicate keys and collisions, preserve original bytes
in backups, and seal both old/new hashes. A pure planner must show exact changes,
refuse missing/foreign files and ambiguous source/destination aliases, and provide
inverse operations where practical. Review acceptance seals file identity and data
schema. A durable data journal coordinates files, explicit ownership receipts and
committed schema, refusing third-party edits during rollback. Unsupported migrations
fail before writing. Testing must simulate every interrupted step and personal-data
conflict before enabling execution. No executable migration field is accepted in
current manifests. This avoids widening payload ownership into users' home trees.

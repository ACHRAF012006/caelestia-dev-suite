# Manager 0.8 evolution / scope ledger

This release is an incremental foundation on the working 0.7 manager. No production
installation/restart or component release is part of publishing it.

| Requested phase | Outcome |
| --- | --- |
| 1 Audit | FUTURE_PROOF_AUDIT records architecture, evidence, severity and pre-change discrepancies |
| 2 Manifest evolution | Central strict schemas 1/2; deterministic in-memory migration and original preservation |
| 3 Adapter V2 | Closed capability/type/host route registry; existing reviewed adapters and receipts reused |
| 4 Host matrix | Central release/commit/signature/revision rules; explicit unsupported/modified statuses |
| 5 Jobs | Bounded backend jobs, Qt bridge, shared Store/inspection scheduler, reviewed slow operations off Qt; safe stage cancellation |
| 6 Binary assets | Declared inert byte resources, limits/checksums/MIME/signatures, text/hash previews |
| 7 Packages | Portable source .cdmpkg export and metadata-first staged import; separate source/install reviews |
| 8 Portable backups | Local backups strengthened; portable installed/personal-data bundle execution deferred (DATA_EVOLUTION) |
| 9 Data migrations | Narrow portable-data schema declaration and constrained migration API design; execution deferred until owned-data journals exist |
| 10 Store | Stable/Beta/Development channels, installed version/channel pins, ignored updates, immutable provenance; no historical release index yet |
| 11 Dependencies | Shared pip wheel/download cache, interpreter/ABI fingerprints, stale preparation, Python specifiers and update diffs; environments remain private |
| 12 Runtime | Persistent launch identity/token records, boot/start/executable checks and pidfd-safe stop; fork/re-exec health can remain unknown |
| 13 Diagnostics | Read-only database/files/dependencies/backups/host/environment/store checks and dedicated UI; repairs use existing reviews |
| 14 Review | Actual file/environment/service/shortcut/host authority displayed separately from runtime disclosures |
| 15 Recovery | Directory fsync, payload preflight/edit preservation, trusted host output re-derivation, blob-use verification, RECOVERY_MODEL |
| 16 DB migrations | Explicit monotonic transactional versions 0→1→2, online backups, future/unknown schema refusal and rollback tests |
| 17 Boundaries | Qt-free schemas/resources/archives/jobs/policies/diagnostics; existing Manager retains lifecycle coordination |
| 18 CLI | Supported read-only status/doctor/list/validate/backup list; no lifecycle mutation convenience commands |
| 19 UX | Component search/filter/Ctrl+F, progress/cancellation dialogs, quiet Diagnostics/History, binary metadata; existing native navigation/motion setting preserved |
| 20 History | Bounded structured lifecycle results, transaction/recovery IDs, error categories; source/dependency/backup actions included |
| 21 Logging | URL/auth redaction, structured JSON manager logs, 1MiB rotation/3 backups, bounded DB event/history retention |
| 22 Development | Existing wizard/templates/import reused; shell-service and dashboard templates, source package review/export; no new general manifest editor or build pipeline |
| 23 Harness | Existing temporary fake-host fixtures reused for lifecycle/composition/fault tests; matrix/forged Cast plan tests added |
| 24 Testing | Existing regressions plus schemas/DB/archive/binary/jobs/diagnostics/cache/pin/runtime/recovery tests; temporary paths only |
| 25 Performance | Batched Git blobs, background post-mutation inspection, metadata-only dependency source read, background catalogue cache loading, releasing completed job/dialog payloads, preserved icon/snapshot caches; no stale mutation authorization |
| 26 Docs | Actual behavior/contracts updated; deferred work clearly labeled |

Remaining limits: only the recorded Caelestia KDE v2.5.1 host is reviewed. Loader
structural detection is weaker than adapter authorization and does not prove QML
health. Beta/development branches are optional: absence is reported, with no silent
fallback. Version pinning holds the installed snapshot; old release selection needs
a future index. Pip cache uses normal pip validation; no offline lockfile/wheelhouse
or compiled build support is promised. Cancellation waits for active preparation
subprocess completion/timeout; mutating writes finish before close. Some short source,
service/log/UI calls remain synchronous. Source swaps retain backups but crash
recovery/cross-filesystem exchange remains manual. Installer in-place environment
updates, same-user filesystem races, continuous component stdout growth and fully
portable backup/data migration remain later work. No systemd scopes or arbitrary
component Python adapter imports are introduced. New templates have static checks;
no new native/hardware compatibility is claimed.

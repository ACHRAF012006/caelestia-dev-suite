# Future-proof architecture audit

Audited 2026-10-10, working manager 0.7.0, before implementation changes.
The required project documents, all backend modules, UI lifecycle/inspection/store
flows, installers, component manifests/runtime/data entrypoints and existing
temporary-path tests were inspected. Implementation is authoritative for current
behavior; documentation alone is not an authorization contract.

## Architecture and existing strengths

Qt Widgets calls a Qt-independent Manager. Source projects and installed snapshots
are separate. Type installers return sealed FilePlans, never execute install hooks.
SQLite owns exact absolute files with hashes/modes. Fixed XDG roots, strict JSON,
safe relative paths, reserved environment paths, symlink refusal, collision checks,
backup-before-write, flock and durable intent journals protect lifecycle operations.
Apps launch detached with independent launchers; services use user systemd; shell
components load in real Caelestia. Manager uninstall has separate ownership and
preserves components, source, receipts, backups and personal data.

Dependency preparation already uses private per-component environments and binary
wheels; static inspection reads distribution metadata. Native authentication only
executes fixed manager-owned Cast package/firewall recipes. Store discovery reads
immutable bare Git objects, protects local edits and retains previous source.
The shared dashboard adapter already composes multiple pages and the legacy Timer
bridge deterministically. Inspection freezes SQLite inventory on its owner thread,
rejects stale generations, and navigation reuses display data. Backups have a cheap
metadata catalogue and freshly checked restore. Static SVG previews reject active
content. The existing fake-host fixtures and lifecycle tests should be extended,
not replaced. None of these boundaries needs a rewrite.

## Documentation discrepancies recorded before changes

| Documentation | Actual 0.7.0 behavior | Authority / resolution |
| --- | --- | --- |
| README limits says version 0.5; architecture extension paragraph says Timer-only | Shared dashboard capability exists and supports multiple components | Code and DASHBOARD_INTEGRATION are authoritative; update stale paragraphs |
| Prompt's illustrative camelCase schemaVersion | Existing contract is optional snake_case schema_version=1 | Retain snake_case; versioning must read old manifests and original bytes |
| Quick Toggles docs imply pinned release | Cast checks exact hashes and legacy hashes, but not commit/version markers | Exact signature acceptance is implemented; centralize and report this distinction |
| Recovery described as protection against third-party edits | Dashboard checks edits; Cast/payload recovery are weaker | Strengthen checks and document fail-closed manual reconciliation |
| Text-only source claim | Source/store are text-only, but prepared environments already contain owned binary files | Extend source transport; preserve FilePlan/receipt byte checks |
| Testing docs give several historical test counts | Current suite has additional dashboard/component tests | Run current baseline and final suite; keep historical results labeled |
| Git workflow assumes a suite checkout | Workspace Git is unborn master, no remote; suite is a separate repository | Publish scoped patches in a fresh suite/main checkout; preserve local Timer changes |

## Findings

Severity describes concrete impact, not stylistic preference. Critical means a
trust/ownership boundary can be crossed; High means recovery or main workflows can
fail materially; Medium means compatibility/scaling/maintenance cost; Low means
minor usability/documentation debt.

| ID | Severity | Finding and evidence | Required response |
| --- | --- | --- | --- |
| A01 | Critical | Cast check validates keys/current files but accepts arbitrary AFTER source; unlike dashboard it does not re-derive trusted transformation | Re-derive BEFORE/AFTER and receipts, including recovery |
| A02 | High | Manager._recover writes every backup path without checking for third-party changes after interruption | Record intended after hashes/modes; validate all payloads before rollback; retain journal on conflict |
| A03 | High | atomic_write fsyncs file, not parent after rename; journal unlink/backup directory publication have same power-loss weakness | Sync parent entries; document limits of filesystem/systemd coordination |
| A04 | High | Registry uses implicit CREATE IF NOT EXISTS, no user_version/newer-schema refusal | Explicit transactional migrations and online SQLite backups |
| A05 | High | prepare_dependencies/system preparation/install plans/restore checks block Qt, pip timeout is 600s | Shared bounded background jobs with independent worker connections; defer cancellation inside mutations |
| A06 | Medium | StoreCheck and Inspection duplicate QThread lifecycle; downloads/import/export/diagnostics lack job status/history | Reuse one backend job model and Qt delivery bridge incrementally |
| A07 | Medium | Manifest schema is explicitly 1 but migration/version assumptions sit inside validators | Central deterministic registry, original preservation, strict v2 and future-version errors |
| A08 | Medium | Cast/Timer dispatch replaces earlier functions with aliases and ID branches | Explicit reviewed adapter registry; preserve legacy receipt routing and public API |
| A09 | High | Host signatures/releases spread across 3 modules; unknown loader matches weak textual markers | Structured compatibility reports; never bless unknown host patches; keep loader detection limitation explicit |
| A10 | Medium | Manager combines source, store provenance, dependencies, shortcuts, transactions and status (~800 lines) | Extract pure policies/registries/jobs/diagnostics incrementally; retain transaction coordinator |
| A11 | Medium | Text-only maps and JSON hashes are duplicated in Manager/Store/import/encode/installers | Common byte/text resource contract, compatible old text fingerprints |
| A12 | High | read_source silently ignores FIFO/device/socket entries; import scans without aggregate size enforcement | Reject special files, bound before reads and across every entrypoint |
| A13 | Medium | Archive import and portable transport absent | Bounded inert archive staging, complete checksums, normal source/install review |
| A14 | High | Backups.read/content have limited structural validation and content reread is not checked; corrupt backups may raise opaque KeyError | Strict identity/path/mode/blob validation and checksum recheck at use |
| A15 | Medium | Source swap has exception rollback but no crash journal and can cross filesystems into XDG backups | Retained source recovery remains manual until same-filesystem/source transaction design is completed |
| A16 | Medium | Personal data intentionally excluded, portable-data authority absent | Declare narrowly namespaced portable locations; design explicit inclusion review; no broad personal-data export |
| A17 | High | Arbitrary data migrations would cross personal-data boundary; no current owned-data receipts | Design constrained reviewed API; defer execution until reversible data journal exists |
| A18 | Medium | Store embeds complete files in catalogue, per-file Git subprocesses, 128 components/64MiB | Bound caches consistently, batch Git blob reads where practical; lazy transport is future work |
| A19 | Medium | Store has main only, no pin/ignore/channel policy; update is fingerprint based | Stable default, optional reviewed channel policy and explicit pins; retain exact commits |
| A20 | Medium | Prepared key uses manager Python minor; actual python3 may differ; marker only checks requirement list | Runtime interpreter fingerprint, Python specifier checks, environment staleness and package cache |
| A21 | High | /proc matching has PID reuse race before kill; fork/re-exec may vanish from detection | Recheck identity through pidfd when available; persisted launch records; report unknown rather than guessed ownership |
| A22 | Medium | Events are unstructured and unbounded; general errors are not centrally redacted | Structured operation history, bounded rotating redacted logs |
| A23 | Medium | No supported headless diagnostics; startup Manager mutates discovery and schema | Read-only CLI connection/snapshot, independent diagnostic module, safe UI health page |
| A24 | Medium | Qt tests cover stale inspection but not generic queued cancellation, archive attacks or DB upgrades | Add targeted adversarial/fault tests on temporary paths |
| A25 | Medium | UI action grid/static cards get crowded, Components lacks search; technical details dominate | Search/filter, explicit job progress and quiet health/history pages, retain native navigation/reduced motion |
| A26 | Medium | Python >=3.11/Qt >=6.8 declared, only local interpreter/platform exercised | Report exact tested versions; no claim of broad KDE/distro verification |
| A27 | Medium | Arch/Debian fixed recipes tested through mocks; systemd/Linux /proc assumed | Fail clearly without executables; other desktop/OS adapters remain unsupported |
| A28 | Medium | Installer updates environment in place, rescans receipt after pip, no install transaction | Manager installer recovery design remains separate; never adopt unrelated files |
| A29 | Low | Cached icons reread fallback SVG; source manifests repeatedly parsed during status/dependency checks | Cache only display assets; mutation authorization continues fresh reads |
| A30 | Medium | Advisory lock waits synchronously and does not prevent same-user external path races | Move waits off Qt; bound conflict handling; openat/O_NOFOLLOW hardening remains future work |
| A31 | Medium | Restore does not revalidate current manifest compatibility/dependencies | Check static installed snapshot/host compatibility without requiring development source |
| A32 | Medium | Component permissions are marketing disclosures, not derived authority | Review actual files/env/service/adapter/system plans; clearly label unenforced runtime disclosures |

## Sequencing and scope

Audit first; schemas/DB/recovery next; registry/compatibility next; jobs and
diagnostics; binary/archive transport; store/dependencies/runtime and UI. Each
commit must pass appropriate tests, preserve old receipts and leave the project
working. Portable personal data and executable data migration are gated on a
proper owned-data recovery design, not generalized scripts. No production install,
shell restart, global Git setting, force push or destructive live test is allowed.
Implemented/deferred outcomes are recorded in the release documentation; this
table records the pre-change evidence, not a claim that every finding is fixed.

## Follow-up findings and disposition

Later transport inspection found that old directory read_text normalized CRLF,
while Git blobs did not. New directory reads preserve original bytes for resource
checksums. Existing text-map hash algorithms remain unchanged; a legacy CRLF source
can display a byte-level update after upgrade. Installed code is never replaced
silently. This is a Low transport consistency issue, now explicitly documented.

EVOLUTION_0_8 is the implemented/deferred ledger for every requested phase. A01–A04,
A07–A09, A11–A14, A19–A22 and A31–A32 received direct fixes or strengthened boundaries.
A05/A06/A10/A18/A23–A25 received incremental changes, with remaining synchronous,
scaling and responsibility limits documented. A15–A17 and A26–A30 remain partly or
fully deferred; safer declarations/designs do not claim execution or compatibility.

A33 (Medium, found during foundation verification): retaining completed job results
and parent-owned closed operation dialogs could retain entire binary catalogues
after repeated refresh/import. The pool now retains only active jobs; callers own
completed results and closed operation dialogs are deleted through Qt. A weakref
regression checks release of an 8 MiB result while the pool remains alive.

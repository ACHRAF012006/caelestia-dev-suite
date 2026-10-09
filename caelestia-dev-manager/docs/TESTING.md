# Verification

## Automated suite

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python -m build
```

The tests use pytest temporary XDG roots. They cover structured/multi-file/single-file package parsing, language detection, malicious paths/duplicates, manifest keys/types, static Python syntax, registry persistence, ownership collisions, exact app/plugin/service planning, uninstall isolation, enable/disable, source/installed differences, stale previews, manual and automatic backup restore, checksum tampering, service-unit verification using systemd-analyze, explicit crash recovery, compatibility detection, read-only environment detection, source deletion confirmation, inert install scripts, and the Qt import/external-source-change/context-copy/reopen flow.

The systemd-analyze test only reads generated temporary unit files; it never starts a live service. The Qt test runs offscreen and uses the real UI and backend with temporary paths and mocked systemd.

Desktop shortcut tests use temporary XDG roots exclusively. They cover localized/custom desktop-directory detection, disabled/missing/unsafe configuration, no command evaluation, symlink rejection, default-off manifests, canonical launcher reuse, create/remove/existence, cross-component and unrelated collisions, reviewed alternate filenames, ownership, modified-file protection, source preservation, uninstall cleanup after XDG changes, script launchers, enable/disable, source updates, full backup restore and rollback after commit failure. UI tests cover import and wizard preferences, installation toggles, alternate selection, unsupported services, status/actions and clipboard context.

Dependency diagnostic regression tests in `tests/test_dependencies.py` mock venv/pip subprocesses and use temporary component environments. They cover per-component isolation, version checks without imports, missing system tools, transitive package failures, authenticated URL redaction, network/timeout classification, failure persistence, verified retries, stale readiness markers, symlink rejection and the Qt Dependencies/error views. These checks do not download packages or alter real component environments.

`tests/test_store.py` uses temporary repositories and XDG roots to exercise real
bare Git discovery, immutable commits, caches and source updates. It verifies
that discovery never executes source, rejects symlink/submodule Git objects and
unsafe paths, constrains repository URLs/branches, protects local edits, refuses
stale reviews, restores a failed source swap, preserves installed files, and
retains source backups. Qt checks cover one-button installation, update, Open,
cancel/retry without repeated source backups, fixed catalogue settings, filters,
navigation without a Code page, asynchronous offline failure and previous-version
restore. Restore checks preserve user configuration, latest source and store
provenance, detect same-version payload changes and skip same-payload backups.
`tests/test_review.py` verifies readable summaries, optional exact technical
details and disabled acceptance for invalid plans. Bootstrap checks reject
missing Git and unowned directories.
No GitHub download or production installation is required by these tests.

`tests/test_navigation.py` covers cached tab switching without scans, event-loop
responsiveness during slow inspection, frozen inventory reads without sharing
SQLite, obsolete-result rejection, retaining data on refresh failure, request
coalescing, deferred startup, cancelling workers on close, rapid/disabled page
transitions and preference persistence. It also verifies that metadata-only
backup lists never read blobs while restore still rejects checksum tampering,
and that cached healthy status never bypasses installed-file ownership checks.

The navigation highlight regression checks its intermediate position, rapid
mouse/keyboard selection, immediate page changes, final alignment, resize and
disabling animation. `tests/test_branding.py` renders the logo under changed
system palettes/themes and verifies installer ownership, pre-logo upgrades,
modified-file protection and owned-only uninstall using mocked downloads.
Desktop shortcut tests preserve the declared original SVG and its absolute
installed path through enable/disable and uninstall.

The Notes & Tasks copied-shell probe (`scripts/dashboard_qml_probe.py`) uses two
private virtual KWin outputs and temporary XDG data. It verifies per-view/search
task counters, undated completion/undo across monitors, centered fixed-size
completion controls, removed settings UI and immediate note/task deletion with
the historical confirmation preference enabled. It also exercises keyboard
capture/editing, filters, fonts, reduced motion, large models and a second shell
process loading the same v1 data. See the component's TESTING.md for requirements.

## Desktop acceptance

The explicit acceptance helper performs live **harmless unique dummy** app/service checks. It never installs or modifies a Caelestia plugin and never restarts the production shell.

Build the catalogue probe using existing Qt/KDE development headers:

```bash
mkdir -p workspace/catalogue-probe
cp scripts/catalogue-probe.cpp workspace/catalogue-probe/
cp scripts/probe-CMakeLists.txt workspace/catalogue-probe/CMakeLists.txt
cmake -S workspace/catalogue-probe -B workspace/catalogue-probe/build
cmake --build workspace/catalogue-probe/build
~/.local/share/caelestia-dev-manager/manager/venv/bin/python scripts/desktop_acceptance.py \
  --probe workspace/catalogue-probe/build/cdm-catalogue-probe
```

It uses the native Wayland Qt UI, clipboard paste (Ctrl+V), actual buttons and installation confirmation dialogs. Separate manager processes close/reopen around a standalone QML ApplicationWindow. KDE KApplicationTrader verifies a visible independent desktop entry; KIO ApplicationLauncherJob launches it with the manager process absent. This verifies the real KDE application catalogue and launch path programmatically, rather than a manual Meta-key search. The app also survives its original manager process exiting.

The reopened manager recognizes installation, detects development-source edits, and disables/uninstalls from the UI. All owned files disappear; source and a deliberately unowned file survive. A unique dummy user service is installed, enabled, started, queried, logged, stopped, disabled and uninstalled through real user systemd. All temporary component source, installed files, registry records and test backups are then removed. Reports/screenshots are ignored under `workspace/acceptance/`.

Additional temporary integration checks:

```bash
PYTHONPATH=. .venv/bin/python scripts/dependency_acceptance.py
.venv/bin/python scripts/manager_uninstall_acceptance.py
PYTHONPATH=. .venv/bin/python scripts/shortcut_acceptance.py \
  --probe workspace/catalogue-probe/build/cdm-catalogue-probe
```

The first prepares real binary-wheel Python dependencies in an isolated environment, installs an exact owned environment, launches through its installed interpreter, checks unchanged installed checksums and uninstalls while preserving source. The second installs/updates/uninstalls the manager under a temporary HOME/XDG environment and confirms its separate standalone app, desktop entry, registry and source survive manager removal. Both temporary environments are removed automatically; neither touches live components.

The shortcut helper uses native clipboard paste/import and installation dialogs with **temporary source, XDG and desktop directories only**. It closes the manager window, launches the generated executable desktop file through real KDE KIO, checks the independent application's output, reopens the manager to verify shortcut recognition, then uninstalls while preserving source and an unrelated desktop file. It does not add a shortcut to the real KDE desktop or alter Plasma folder settings. Rebuild the catalogue probe from the current source first; its `--file` mode validates launching a specific desktop entry outside the application catalogue.

## Results on this machine

Manager 0.3.2 (2026-10-07): **175 automated tests passed**; wheel and source
distribution include the bundled SVG. Offscreen previews checked the logo and
moving/final highlight. A real temporary HOME/XDG manager install/update/uninstall
passed, including installed version, original logo contents, absolute desktop
icon path, receipt ownership and preservation of an independently launchable
component, its source and registry. Production installations were not changed.

Manager 0.3.1 (2026-10-07): **171 automated tests passed**; wheel and source
distribution built successfully. Navigation and refresh regression tests use temporary
XDG roots and verify worker/UI thread affinity. A read-only offscreen profile used the live registry's one component,
4,376 owned files and three backups without changing the live installation.
The full status baseline took about 2 seconds with profiling enabled. With
inspection on a worker and real Qt event-loop navigation, switches averaged
2.8 ms (5.21 ms slowest) while 21 timer ticks ran during inspection/final frames.
Metadata-only backup listing took 0.007 seconds. These are measurements on this
machine, not performance guarantees for other hardware or native display setups.

Manager 0.3.0: **160 automated tests passed**; wheel and source distribution
built successfully. The simplified store was visually checked offscreen with
the normal dark stylesheet and TouchDeck icon. The one-button update/restore
workflow was exercised with harmless components under temporary XDG roots.
No production manager installation or component was changed for this release.

Verified 2026-10-06 on CachyOS, Plasma 6.7.5, Wayland, Caelestia installed commit `e34b6957fad5ce9395841b65be9e3df180ccd65c`:

- **118 automated tests passed**, including 44 added desktop-shortcut/backend/UI checks. Native manager build (sdist/wheel), installation/update, version command and KDE catalogue registration succeeded.
- Desktop acceptance passed the complete paste → reconstruct → install → independent launch → manager close → KDE launch → reopen → detect changes → disable → owned-only uninstall → source-preservation workflow.
- A real unique dummy user service passed start/stop/enable/disable/status/logs/uninstall checks.
- Isolated Python dependency relocation, launch and ownership checks passed.
- Temporary manager uninstall left its component application functional and preserved registry and source.
- Optional shortcut acceptance passed native paste/import/install, real KDE KIO launch after the manager window closed, reopened shortcut detection and owned-only uninstall entirely under temporary paths. No real desktop shortcut was created.
- All dummy components and backups were removed. Installed Caelestia files were only inspected; production Caelestia was not modified or restarted.

The first live service check found a WorkingDirectory quoting bug. It was fixed, a regression test using systemd's own verifier was added, and the live check passed after cleanup and rerun. An installed Caelestia plugin runtime was deliberately not exercised. QML static validation does not guarantee compilation for arbitrary user code; runtime errors remain visible through logs. No reboot or manual launcher search was performed.

Manager 0.4.0 / Cast Audio 0.2.0 (2026-10-07): all 186 manager tests passed, including 10 adapter lifecycle/receipt/recovery tests. All 16 component tests passed. Wheel/source distribution builds succeeded. The isolated native panel probe verified inline expansion, receiver selection, Settings action, drawer opening, Nexus visibility and unload; the separate Settings QML and preference bridge loaded under isolated XDG roots. The authorized local upgrade automatically migrated the previous icon, installed the managed row and restarted Caelestia. No physical Google Cast playback was tested.

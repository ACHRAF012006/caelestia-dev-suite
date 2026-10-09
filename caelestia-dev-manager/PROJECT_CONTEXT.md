# Project context

Project: **Caelestia Dev Manager**, command `caelestia-dev-manager`, version 0.6.1. Native Python/PySide6 Qt Widgets desktop application. Target: CachyOS/Arch, Plasma 6, Wayland, ladybug-me/caelestia-kde.

Read README.md, docs/ARCHITECTURE.md, docs/PLUGIN_SPEC.md (alias to COMPONENT_SPEC), docs/COMPONENT_SPEC.md, docs/CODEX_PACKAGE_FORMAT.md, docs/CODEX_WORKFLOW.md and docs/COMPONENT_STORE.md before changing component behavior.

The manager administers existence and lifecycle; it is never the runtime container for components. Development source is `plugins/<id>/`; installed code is a separate snapshot. Installed components survive manager exit and manager uninstall. Do not build real Notes or another extension unless asked.

Caelestia facts are documented in docs/ENVIRONMENT_FINDINGS.md. Inspect current installed files and refresh the reference before adding integration methods. Never treat a guessed dashboard/plugin API as supported. Never write custom applications into the reference clone.

Architecture constraints: strict component manifest; path traversal and symlink rejection; fixed per-type destination roots; SQLite exact file ownership; static import/validation; collision refusal; backup plus recoverable transaction journal; no arbitrary install scripts; no arbitrary privileged hooks; reviewed fixed Cast Audio machine preparation via pkexec; reviewed virtual environments for Python and Quickshell sidecar dependencies; independent launchers; `systemd --user` for service lifetimes.

Components created by Codex should go into `plugins/<component-id>/`. Copy/paste responses use `CAELESTIA_DEV_PACKAGE`. Type-specific adapters determine capabilities. `kde-integration` is reserved and fails installation until a verified adapter exists. `qml-component` supports only a Caelestia-plugin target in v0.1.

Standalone applications and scripts may optionally declare `desktop.createShortcut: true`; omission defaults to false. Create / Import and installation expose a shortcut checkbox; installed component actions expose Create/Remove Desktop Shortcut. Copy the canonical application launcher into the configured XDG desktop directory, never hardcode `~/Desktop`. Desktop configuration is parsed as data, never executed. Record the exact approved shortcut path, checksum and mode as component ownership; preserve unrelated collisions and offer a reviewed alternate filename. Shortcut toggles are independent of payload installation, and owned shortcuts participate in backup/restore, enable/disable and uninstall. Services, Caelestia plugins, QML shell components and reserved KDE integrations cannot request direct launch shortcuts. See docs/DESKTOP_SHORTCUTS.md.

Verification: run the temporary-path automated tests and build. Run the explicitly documented desktop acceptance helper only for harmless dummy components. Never use live Caelestia as a destructive test target. Do not mutate global Git settings. Ignore virtualenvs, logs, backups, staging, reference clone and build output.

Tab navigation reuses display snapshots. Startup, manual Refresh and stale-view checks use a cancellable read-only inspection worker; capture SQLite records/receipts on the main thread and never share its connection with a worker. Discard results from an older generation after a reviewed mutation. Backup lists read metadata without hashing blobs; restore/inspection still revalidate the complete backup. Display caches must never authorize installs/removals/restores: fresh sealed plans and ownership checks remain mandatory. Page fades last 140 ms; the navigation highlight slides for 180 ms behind transparent labels without blocking native mouse/keyboard input. Interrupt animation on rapid switches/resize/scroll/close; Settings disables both effects.

The manager uses `app/assets/icon.svg`, a bundled SVG with fixed colors, for its window icon and desktop launcher. The installer copies it to its owned manager root and records its checksum; the desktop Icon field uses that absolute installed path instead of a system theme name. SVG assets must be included in both wheel and source distributions. Component shortcuts already copy the declared original SVG's absolute installed path.

The GitHub suite separates `caelestia-dev-manager/` (manager, installer and docs) from `components/<id>/` (published component source). The Component Store uses the built-in suite/main catalogue without repository fields. It fetches Git objects on startup in a background worker; it never checks out or executes catalogue code. One Install/Update/Open button downloads inert local source and proceeds into existing dependency and installation reviews. Summaries are readable with full source/exact plans available as technical details; there is no Code tab. Cancelling may retain downloaded development source but never changes installed files. Previous version selects a differing installed backup and preserves current source, store provenance and runtime configuration. Protect local edits, pin downloads to a commit and retain previous source in XDG data source-backups. Never pull catalogue changes directly into installed runtimes. See docs/COMPONENT_STORE.md.

Cast Audio 0.2 declares integration.target=caelestia-quick-toggles. The manager owns a checksum-pinned two-file adapter with separate host receipts and transaction recovery. New installs enable it and restart the shell; updates preserve disabled state; uninstall restores original host files. Never execute component-supplied patches or generalize this into arbitrary host writes. Read docs/QUICK_TOGGLES_INTEGRATION.md.

Manager 0.5 supports private Python environments for Quickshell sidecars. Cast Audio 0.5.0 uses installed _venv/bin/python via src/launcher.py and invokes catt.cli as a module to avoid staging shebangs. Installation reviews fixed ffmpeg/pactl/parec package mappings and portable active-UFW rules through native authentication; no component can supply privileged commands. Select the current PC address by receiver route, never hardcode development IPs. Do not claim audio works from a Cast connection sound or LOAD acknowledgement: verify receiver bytes and PLAYING.

Animated Timer 0.1.2 uses the separate manager-owned `caelestia-dashboard-timer` adapter in `backend/timer_integration.py` (manager 0.6.0). It pins v2.5.1 and two dashboard host files, with independent receipts and existing recovery coordination. Read docs/ANIMATED_TIMER_INTEGRATION.md. Generic dashboard injection remains unsupported. Never deploy or restart production as a development test.

Manager 0.6.1 shows shared per-component SVG icons in Components and the Store.
Inspections carry bounded icon source as display data; navigation never rereads
component files. Static SVG rendering refuses active or external resources.
The generated Codex prompt requires scoped commits and pushes by default unless
the request explicitly overrides it, verifies remote delivery, and reports real
authentication/repository/branch blockers. Preserve unrelated work and never
force-push or change global Git settings. Git publication remains separate from
reviewed production installation and shell reload.

# Project context

Project: **Caelestia Dev Manager**, command `caelestia-dev-manager`, version 0.2.0. Native Python/PySide6 Qt Widgets desktop application. Target: CachyOS/Arch, Plasma 6, Wayland, ladybug-me/caelestia-kde.

Read README.md, docs/ARCHITECTURE.md, docs/PLUGIN_SPEC.md (alias to COMPONENT_SPEC), docs/COMPONENT_SPEC.md, docs/CODEX_PACKAGE_FORMAT.md and docs/CODEX_WORKFLOW.md before changing component behavior.

The manager administers existence and lifecycle; it is never the runtime container for components. Development source is `plugins/<id>/`; installed code is a separate snapshot. Installed components survive manager exit and manager uninstall. Do not build real Notes or another extension unless asked.

Caelestia facts are documented in docs/ENVIRONMENT_FINDINGS.md. Inspect current installed files and refresh the reference before adding integration methods. Never treat a guessed dashboard/plugin API as supported. Never write custom applications into the reference clone.

Architecture constraints: strict component manifest; path traversal and symlink rejection; fixed per-type destination roots; SQLite exact file ownership; static import/validation; collision refusal; backup plus recoverable transaction journal; no arbitrary install scripts; no sudo; reviewed virtual environments for Python dependencies; independent launchers; `systemd --user` for service lifetimes.

Components created by Codex should go into `plugins/<component-id>/`. Copy/paste responses use `CAELESTIA_DEV_PACKAGE`. Type-specific adapters determine capabilities. `kde-integration` is reserved and fails installation until a verified adapter exists. `qml-component` supports only a Caelestia-plugin target in v0.1.

Standalone applications and scripts may optionally declare `desktop.createShortcut: true`; omission defaults to false. Create / Import and installation expose a shortcut checkbox; installed component actions expose Create/Remove Desktop Shortcut. Copy the canonical application launcher into the configured XDG desktop directory, never hardcode `~/Desktop`. Desktop configuration is parsed as data, never executed. Record the exact approved shortcut path, checksum and mode as component ownership; preserve unrelated collisions and offer a reviewed alternate filename. Shortcut toggles are independent of payload installation, and owned shortcuts participate in backup/restore, enable/disable and uninstall. Services, Caelestia plugins, QML shell components and reserved KDE integrations cannot request direct launch shortcuts. See docs/DESKTOP_SHORTCUTS.md.

Verification: run the temporary-path automated tests and build. Run the explicitly documented desktop acceptance helper only for harmless dummy components. Never use live Caelestia as a destructive test target. Do not mutate global Git settings. Ignore virtualenvs, logs, backups, staging, reference clone and build output.

The GitHub suite separates `caelestia-dev-manager/` (manager, installer and docs) from `components/<id>/` (published component source). The Component Store fetches Git objects on startup in a background worker; it never checks out or executes catalogue code. Store downloads are separately reviewed source-only operations into the manager's local `plugins/`; installation remains the existing reviewed transaction. Protect local edits, pin downloads to a commit and retain previous source in XDG data source-backups. Never pull catalogue changes directly into installed runtimes. See docs/COMPONENT_STORE.md.

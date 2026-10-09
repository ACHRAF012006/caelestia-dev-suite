# Caelestia Dev Manager

A local Qt 6 desktop control center for independently installed components on CachyOS, KDE Plasma 6 and Caelestia KDE. Command: `caelestia-dev-manager`.

The manager creates, imports, validates, installs, enables, disables, updates, backs up, restores and removes components. Applications run as their own applications; services run through `systemd --user`; Caelestia plugins load into the actual shell. Closing or uninstalling the manager does not remove components or close applications.

Tabs switch using the information already loaded, with a short fade and a sliding selection highlight. Startup and **Refresh** check component information in the background; navigating after 30 seconds requests a fresh check without blocking the page switch. Settings → **Animate tab transitions** turns both animations off. Installation and restore still perform fresh ownership and checksum checks.

## Install and launch

Need the Caelestia desktop first? Follow [Install Caelestia on KDE Plasma](docs/CAELESTIA_KDE_SETUP.md), based on the upstream ladybug-me/caelestia-kde repository, then return here to install Dev Manager.

```bash
./install.sh
caelestia-dev-manager
```

Installation creates a dedicated manager virtual environment, launcher and KDE desktop entry under user XDG directories. The launcher and window use the bundled logo with its own colors, independent of the system icon theme. It downloads PySide6 and build dependencies into that environment; it never runs sudo or installs system packages. Existing component state and source remain during manager updates. Run `./install.sh` again to update the manager. `./uninstall.sh` removes only manager-owned files. See [installation details](docs/INSTALLATION.md).

For a new computer, `install-from-github.py` checks for Git, clones the suite into
user XDG data and invokes the manager installer. Run it with Python 3.11+; missing
Git is reported for manual installation. `--clone-only` downloads source without
running the installer. Repeated runs refuse local changes and use a fast-forward
update. In the suite repository the manager is under `caelestia-dev-manager/` and
published components are under `components/`.

## Component Store

Open **Component Store**, choose an app and press **Install**. The same button
changes to **Update** when a newer snapshot is available, or **Open** for an
installed application. No repository setup is needed: the store uses the suite's
built-in GitHub catalogue. Search and the All apps / Installed / Updates filter
help you find apps. Installation reviews show a readable summary and optional
technical details, including exact paths and complete source.

The manager checks for updates in the background when it opens. **Refresh**
repeats the check; Settings can disable startup checks. The last catalogue remains
available offline. **Previous version** restores a differing saved installation
after review, preserving your settings and current development source. Restart
the app after updating or restoring. Local source edits are protected. Private
repositories use existing Git credentials or GitHub CLI login; no token is
stored in manager settings. See [component store details](docs/COMPONENT_STORE.md).

## Workflow

1. Choose **New Component**, or open **Create / Import** and paste generated code.
2. **Analyze Code / Preview Files** parses the package without executing it. Inspect the Files, Manifest, Destination and Validation tabs.
3. **Create Component** writes development source under `plugins/<id>/`. **Save as Draft** permits incomplete static validation, but still requires safe paths and valid metadata.
4. Use **Open Source** in Components to edit development files with your preferred editor. **Install** reviews permissions before writing installed files; **Show technical details** includes exact destinations, generated launchers, services, dependencies and complete source. There is no Code tab.
5. Launch the application from KDE. Enable services explicitly. General Caelestia plugins install undiscoverable initially; enable them and reload through Settings. Cast Audio uses the reviewed automatic Quick Toggles adapter described below.
6. Editing source changes nothing live. **Update Installed Version** applies the source snapshot after review and backup.
7. **Disable**, **Uninstall** and **Delete Source** have separate meanings. Source deletion requires typing the component ID; uninstall keeps source.

Select a component and open **Dependencies** to check its declared system executables and Python package versions. Development preparation and the installed runtime are shown separately; packages installed in the manager or global Python do not satisfy a component's isolated environment. The component details show missing tools, unprepared packages and version mismatches without downloads or executing component code. **Install / Update** offers reviewed preparation or retry.

Uninstalled components blocked only by missing executables show **Missing Dependencies**, with the exact names in Dependencies and Validation. They are not counted as broken source. Installation stays blocked until those tools are available; compatibility and source errors still retain their own failure status.

Preparation failures show the component, the requirement reported by pip (including transitive packages), the Python version and captured output. Network/index failures are distinguished from unavailable binary wheels and dependency conflicts. A redacted diagnostic is retained for that component's current dependency set and in Logs; authenticated URLs are removed. Failed preparation never marks the environment ready or proceeds with installation. Only binary wheels are accepted; no source builds or global package installation are enabled.

**Codex Context** assembles the environment, inventory, dependency diagnostics, architecture, component spec, package format and current request into one clipboard prompt. It includes the GitHub store target, publishing layout and verification steps. Completed code tasks require scoped Git commits and pushes unless your request explicitly opts out: local `plugins/<id>/` projects appear in the store only after their complete source reaches the suite's `components/<id>/` on `main`. Components are never added as runtime pages inside this manager.

Standalone apps and scripts offer **Create shortcut on desktop** in New Component, Create / Import and the installation preview. It defaults to off; packages can opt in with `"desktop": {"createShortcut": true}`. Installed component actions can create/remove the shortcut separately. Shortcuts copy the normal application launcher into your configured XDG desktop directory, including localized paths. Existing unrelated files are preserved; the UI offers an alternate filename. Owned shortcuts are backed up and removed with component uninstall. See [desktop shortcuts](docs/DESKTOP_SHORTCUTS.md).

## Verified Caelestia integration

The inspected upstream and installed shell use `metadata.json` discovery at `$XDG_CONFIG_HOME/caelestia/plugins/<id>/`, loading a `quickshell` plugin's `main.qml` or explicit `ui`. The exposed plugin IPC supports count only. The manager does not invent an external activation API. It changes only its owned discovery file (`metadata.json` / `metadata.json.disabled`) and offers an explicit shell-service restart. See [environment findings](docs/ENVIRONMENT_FINDINGS.md) for inspected paths, source links and commit.

Cast Audio 0.5.0 uses the manager 0.5.1 [verified Quick Toggles adapter](docs/QUICK_TOGGLES_INTEGRATION.md): a redesigned expandable receiver row with desktop/app selection, Fast/Balanced live profiles, tabbed Settings, saved device IPs and an optional fixed audio stream port. Reviewed installation adds the row, enables new installs and restarts Caelestia. Updates preserve disabled state. Removal restores the original host files; later host edits block replacement. Install prepares component-owned catt libraries, known missing audio packages and active-UFW rules for the saved port with native authentication where required. No PC IP is hardcoded. Google account discovery is unavailable in this Linux backend.

Caelestia Animated Timer 0.1.2 uses the separate [Timer adapter](docs/ANIMATED_TIMER_INTEGRATION.md) in manager 0.6.0. It adds a native dashboard Timer tab and per-monitor slim notch using two checksum-pinned host files for Caelestia KDE v2.5.1. Install reviews exact host source, preserves originals and supports recovery/uninstall. Manager 0.7.0 adds the reusable [dashboard page capability](docs/DASHBOARD_INTEGRATION.md), composing generic pages with the legacy Timer bridge. KDE/KWin extensions remain unsupported.

## Development and tests

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest build
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python -m build
.venv/bin/python -m app.main
# Completely separate test workspace and mocked systemd:
.venv/bin/python -m app.main --sandbox /tmp/cdm-sandbox
```

The automated suite uses temporary paths. The separate desktop acceptance helper installs only uniquely named harmless test components, checks KDE's application catalogue, closes/reopens the manager, and cleans up. See [testing](docs/TESTING.md) for explicit commands and results.

## Project layout

`app/` contains the Qt desktop UI; `backend/` separates environment, registry, installers, validators, runtime, backups and Codex tooling; `plugins/` holds development projects; `reference/caelestia-kde/` is the upstream inspection clone; `workspace/` is ignored staging; `docs/` describes the contracts; `tests/` verifies safety and lifecycle behavior. Runtime database and backups live in XDG state/data, rather than the source repository.

## Current limits

Version 0.5 handles UTF-8 text packages, including SVG assets. Raster/binary package assets, archive import, compiled application build pipelines, KWin/Plasma package adapters and arbitrary QML module destinations are not implemented. Python/QML/shell applications, commands, Python/shell services and verified Caelestia Quickshell plugins are supported. Static validation checks Python syntax and metadata; it cannot prove code safety or guarantee QML imports compile. Python dependency preparation runs as a separately reviewed synchronous operation and can temporarily block the UI. App PID detection is best effort through `/proc`; applications that replace themselves or fork away from installed paths may not be detected.

Start future work with [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md). Notes & Tasks is an independent dashboard component. Animated Timer source is bundled for the dedicated adapter tests; published components remain independent runtimes.

Manager 0.6.1 gives each component a consistent icon in Components and the Store,
including bundled artwork for Cast Audio, TouchDeck and Animated Timer. Declared
static SVGs take precedence; other apps use an ID-based monogram. Codex Context
now leads with the task, documents both verified host adapters, and requires scoped
Git commits/pushes with remote verification unless the request explicitly opts out.
Push failures must be reported; production installation still uses its reviewed
lifecycle.

## Reusable dashboard pages (0.7.0)

Dashboard components declare a validated `caelestia-dashboard` page capability.
One shared manager adapter composes their tabs, keeps Timer's existing notch and
legacy target, and preserves lifecycle backups/recovery/dirty-host protection.
Only verified Caelestia KDE v2.5.1 is currently supported. Read
[the integration contract](docs/DASHBOARD_INTEGRATION.md).

[Notes & Tasks 0.2.2](plugins/notes-tasks/README.md) supplies native notes, tasks,
quick capture, search, inline editors, archives, subtasks and local autosave. Its
shared helper and personal-data directory survive updates and uninstall. Update
Dev Manager to 0.7.0 before reviewing Store installation. Publication does not
install/enable the component or restart your shell.

# Component manifest, schema 1

Every component has `manifest.json` at source root. JSON duplicate/unknown keys are errors.

```json
{
  "schema_version": 1,
  "id": "my-utility",
  "name": "My Utility",
  "version": "0.1.0",
  "description": "Independent desktop utility",
  "type": "standalone-app",
  "runtime": "python",
  "entrypoint": "src/main.py",
  "args": [],
  "dependencies": {"system": [], "python": []},
  "desktop": {"terminal": false, "categories": "Utility;", "icon": "assets/icon.svg", "createShortcut": false},
  "permissions": ["Reads files selected by the user"]
}
```

The optional icon must actually exist. Declare a distinct static `desktop.icon` SVG for each component, including shell plugins; it identifies the component without creating a shortcut. Components and Store show the same artwork. Without valid artwork, known apps use bundled identity icons and other components use a stable ID-based monogram. Canonical desktop launchers retain their existing fallback when no icon is declared.

| Field | Meaning |
| --- | --- |
| schema_version | Optional integer 1 |
| id | Required lowercase letters/digits separated by single hyphens, starts with a letter, max 64; manager/system command IDs reserved |
| name | Required single-line display name, max 120 |
| version | Required `major.minor.patch`, optional prerelease/build suffix |
| description | Single-line description, optional empty string |
| type | standalone-app, script, user-service, caelestia-plugin, qml-component, kde-integration |
| runtime | python, python-pyside6, shell, qml, quickshell, none (draft) |
| entrypoint | Safe source-relative file, required to install |
| args | Optional array of literal command arguments; no shell interpolation |
| dependencies.system | Executable names checked on PATH. Fixed Cast Audio recipes can prepare ffmpeg/pactl/parec after review; other missing tools need explicit setup. |
| dependencies.python | Package names with optional simple version comparator; no URLs, flags or hooks |
| desktop | Optional terminal boolean, semicolon-separated categories, safe source-relative SVG icon, createShortcut boolean, startupNotify boolean |
| service.restart | no, on-failure, always; defaults to no |
| compatibility.plasma | Optional installed Plasma version prefix |
| compatibility.caelestia_commit | Optional exact installed commit |
| compatibility.manager_min_version | Optional minimum manager `major.minor.patch` |
| integration.target | qml-component requires caelestia-plugin; Cast Audio may declare caelestia-quick-toggles; Animated Timer retains caelestia-dashboard-timer; compatible Quickshell plugins may declare caelestia-dashboard in manager 0.7.0 |
| permissions | Descriptive string list shown during review; this is disclosure, not a security sandbox |

Python/PySide6, standalone QML (`qml6`) and shell runtimes work for apps/commands/services. Caelestia integration requires quickshell. `python-pyside6` must declare a PySide6 Python dependency. `none` creates drafts. General KDE integration is reserved and cannot install in v0.1. Python dependencies support Python runtimes and Quickshell Python sidecars. Sidecars must explicitly use installed `_venv/bin/python`; launch module entrypoints instead of relocated console scripts.

## Optional desktop shortcut

`desktop.createShortcut` defaults to false and accepts only a JSON boolean. Set it to true for `standalone-app` or `script` to request a desktop shortcut during reviewed installation. Other types cannot set it true. A creation/import checkbox writes this preference to the source manifest; it never installs the component or writes a desktop shortcut during source creation. The installation checkbox can override the preference for the installed copy.

The canonical launcher remains `$XDG_DATA_HOME/applications/<id>.desktop`; a shortcut copies its contents to the directory declared by `XDG_DESKTOP_DIR` in `$XDG_CONFIG_HOME/user-dirs.dirs`. Scripts acquire a canonical desktop entry when first requesting a shortcut. Existing script entries remain when removing the shortcut. `desktop.terminal` defaults to true for scripts and false for standalone apps. `desktop.startupNotify` defaults to false; set true only for an application implementing startup notification. Name, Comment, Exec, Icon, Categories, Terminal and StartupNotify come from one launcher generator. Arbitrary desktop Exec overrides are forbidden.

Post-install Create/Remove Desktop Shortcut actions change the installed preference without changing source or reinstalling the payload. That choice persists through source updates until the source manifest explicitly changes its shortcut preference or the installation checkbox overrides it. Uninstall removes an owned shortcut and preserves source. See [desktop shortcut behavior](DESKTOP_SHORTCUTS.md).

## Caelestia host metadata

The manager manifest and Caelestia's `metadata.json` are different formats. A Caelestia component must also ship:

```json
{
  "id": "example-plugin",
  "name": "Example Plugin",
  "version": "0.1.0",
  "description": "Example shell component",
  "type": "quickshell",
  "ui": "main.qml",
  "restart": true
}
```

ID, name, description and version must match the manager manifest. `ui` must match its entrypoint (defaults to main.qml). The actual runtime loader uses `Qt.createComponent` and `createObject` under the shell PluginLoader. A plugin may provide Quickshell windows or objects using real shell imports. There is no assumed dashboard-tab API. Optional host author/icon/settings metadata is passed through as source; unsafe code remains the user's responsibility to review.

Source supports UTF-8 text files and SVG; package import rejects traversal, absolute paths, hidden/cache paths, duplicates, file/directory conflicts and symlinks. `_venv` is manager-reserved. All source files are copied as inert text data; only generated launchers or service entries invoke the declared entrypoint. Executable bits on source scripts are unnecessary: the launcher calls the interpreter explicitly. Install scripts are never auto-executed. Destination overrides and arbitrary service/desktop Exec fields are not supported.

The Cast Audio-only `caelestia-quick-toggles` adapter requires manager 0.4 or newer. Its reviewed install adds a separate expandable row, enables new installs and restarts the shell. See [Quick Toggles integration](QUICK_TOGGLES_INTEGRATION.md). Other plugins keep the explicit enable/reload workflow.

Animated Timer requires the dedicated [Timer adapter](ANIMATED_TIMER_INTEGRATION.md) in manager 0.6.0; the store does not upgrade managers. Unknown integration targets are rejected.

## Dashboard pages (manager 0.7.0+)

A `caelestia-plugin` with runtime `quickshell` may use integration target
`caelestia-dashboard` with a required `dashboard` object containing exactly
`id`, `title`, `icon`, `component`, `order`. Example:

```json
"integration": {
  "target": "caelestia-dashboard",
  "dashboard": {"id": "calendar", "title": "Calendar", "icon": "calendar_month", "component": "DashboardPage.qml", "order": 60}
}
```

IDs must be lowercase and unique among all installed dashboard pages; native IDs
and Timer are reserved. Titles have 1–40 printable characters. Icon is a Material
symbol name. Component must be an existing relative QML source with no traversal,
URLs or hidden paths. Order is an integer 1–1000. Unknown options, executable
patches and arbitrary destinations are rejected. The manager calculates the
bridge and page URL. The page exposes `controller` (required var) and
`presentationActive` (bool), and uses responsive layouts/native sizing tokens.
`compatibility.manager_min_version` optionally declares a semantic minimum manager
version; Notes & Tasks declares 0.7.0. The old Timer target remains supported.
Read [the shared integration contract](DASHBOARD_INTEGRATION.md) before writing a
new dashboard component. Own user data separately in a namespaced XDG location.

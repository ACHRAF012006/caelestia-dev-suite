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

The optional icon must actually exist. Omit it to use the desktop development icon.

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
| dependencies.system | Executable names checked on PATH. User installs missing system packages manually. |
| dependencies.python | Package names with optional simple version comparator; no URLs, flags or hooks |
| desktop | Optional terminal boolean, semicolon-separated categories, safe source-relative SVG icon, createShortcut boolean, startupNotify boolean |
| service.restart | no, on-failure, always; defaults to no |
| compatibility.plasma | Optional installed Plasma version prefix |
| compatibility.caelestia_commit | Optional exact installed commit |
| integration.target | qml-component currently requires caelestia-plugin |
| permissions | Descriptive string list shown during review; this is disclosure, not a security sandbox |

Python/PySide6, standalone QML (`qml6`) and shell runtimes work for apps/commands/services. Caelestia integration requires quickshell. `python-pyside6` must declare a PySide6 Python dependency. `none` creates drafts. General KDE integration is reserved and cannot install in v0.1. Python dependencies require a Python runtime.

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

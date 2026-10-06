# Environment and upstream findings

Inspected 2026-10-06 before integration implementation. Local desktop: CachyOS (`ID=cachyos`, `ID_LIKE=arch`), KDE Plasma 6.7.5, Wayland. Caelestia runs via `caelestia-shell.service`, executing the shell under `~/.config/quickshell/caelestia/shell.qml`. The recorded installed commit and the freshly cloned upstream main both were `e34b6957fad5ce9395841b65be9e3df180ccd65c`. Installed and reference PluginLoader.qml compared identical.

Reference clone: `reference/caelestia-kde/`, origin https://github.com/ladybug-me/caelestia-kde. Custom components do not belong inside this clone. Update with `./update-reference.sh`, which checks remote, branch and clean worktree and fast-forwards only.

## Verified host contract

Inspected local and reference:

- `shell/modules/plugins/README.md`: bundled plugins in `quickshell/caelestia/modules/plugins/`; user plugins in XDG config `caelestia/plugins/`.
- `shell/scripts/list-plugins.sh`: immediate child directories with `metadata.json` are discovered; XDG_CONFIG_HOME honored, HOME/.config fallback.
- `shell/services/PluginLoader.qml`: reads metadata, type quickshell defaults to main.qml; `ui` overrides; `Qt.createComponent(file://...)` then createObject under the loader. Enabled plugins are loaded as real shell objects.
- Same loader: native disabledPlugins is a QtCore Settings property in category Plugins; Nexus calls `setPluginEnabled` internally. There is no externally exposed IPC method to change this setting. `qs -c caelestia ipc show` confirmed target plugins supports only `count(): string`.
- `shell/services/PluginStore.qml`: user plugin installation uses the verified user directory and then internally informs PluginLoader. The manager does not invoke its shell-script installation routines.
- `shell/services/api/README.md`, `CaelestiaApi.qml`, `PluginsApi.qml`: singleton `qs.services.api` exposes available plugin ListModel, with system/window/network/media/visual/UI/shortcut APIs. Availability is not a dashboard registration hook.
- `shell/modules/dashboard/Content.qml`: built-in dashboard, media, performance, weather and terminal components form a fixed list controlled by Config flags. No dynamic plugin tab registry was found. Arbitrary dashboard injection is unsupported.
- Local user-service unit and installed service activity inspected read-only. Explicit `systemctl --user restart caelestia-shell.service` is the available manager reload strategy. Production shell was not restarted during tests.

The manager conservatively verifies loader discovery markers before planning installs. It installs new plugins disabled by naming its discovery file `metadata.json.disabled`. Enabling/restoring metadata and explicitly restarting the shell makes the installed component discoverable. This is a manager-owned file strategy using verified discovery behavior, not a claimed upstream enable API. Native Nexus disabled state remains a separate control and can still block loading. Per-plugin QML runtime health is unknown; inspect shell logs.

## Standalone and service conventions

Standalone apps use controlled XDG data payloads, `~/.local/bin/<id>` executable launchers, and XDG data `applications/<id>.desktop`. Launchers call installed code/interpreters directly and survive manager deletion. KDE's application catalogue can be checked with KApplicationTrader after kbuildsycoca6. User service files belong to XDG config `systemd/user/`, are named `cdm-<id>.service`, and reference installed payloads. Enable/start/stop/log operations call user systemd directly; there is no manager background daemon.

Sources:

- [Upstream project](https://github.com/ladybug-me/caelestia-kde)
- [Pinned PluginLoader](https://github.com/ladybug-me/caelestia-kde/blob/e34b6957fad5ce9395841b65be9e3df180ccd65c/shell/services/PluginLoader.qml)
- [Pinned discovery script](https://github.com/ladybug-me/caelestia-kde/blob/e34b6957fad5ce9395841b65be9e3df180ccd65c/shell/scripts/list-plugins.sh)
- [Pinned dashboard](https://github.com/ladybug-me/caelestia-kde/blob/e34b6957fad5ce9395841b65be9e3df180ccd65c/shell/modules/dashboard/Content.qml)
- [Desktop Exec specification](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html)
- [KDE application catalogue API](https://api.kde.org/kapplicationtrader.html)

Reinspect and revise this document when upstream changes. Detection is read-only; it does not guarantee every future loader version remains compatible.

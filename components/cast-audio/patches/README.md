# Optional Quick Toggles integration — review only

`quick-toggles.patch` is inert text. Neither Dev Manager nor this plugin applies it. Installation of the plugin never writes to the production shell.

The patch and its upstream context are modifications of GPL-3.0-only Caelestia source and use that upstream license, rather than the MIT license of the component's original code/artwork. See [GPL version 3](https://www.gnu.org/licenses/gpl-3.0.html).

## Inspected files

Installed root: `$XDG_CONFIG_HOME/quickshell/caelestia` (normally `~/.config/quickshell/caelestia`).

Reference: [ladybug-me/caelestia-kde](https://github.com/ladybug-me/caelestia-kde/tree/e34b6957fad5ce9395841b65be9e3df180ccd65c), commit `e34b6957fad5ce9395841b65be9e3df180ccd65c`.

These installed files compared byte-identical to that reference:

| File relative to installed root | SHA-256 |
| --- | --- |
| `modules/utilities/cards/Toggles.qml` | `fae4d5d5c4c56341b10aa66a79e016704d2c5d4a77b5f32b3b72cca4702967ba` |
| `modules/nexus/pages/utilities/QuickTogglesPage.qml` | `91785c48250415814ae9a85c2197d57b8a502406f62defdd950406f12fd33900` |
| `services/PluginLoader.qml` | `153a03d6aaa828049445701415cf6f70107ac3db1c9b906b096446ba97b94564` |
| `scripts/list-plugins.sh` | `83e455010abeb2d7c639dcfd1469ea4cf068b003f867d41b454c6ff7ceb5f60c` |

The [toggle implementation](https://github.com/ladybug-me/caelestia-kde/blob/e34b6957fad5ce9395841b65be9e3df180ccd65c/shell/modules/utilities/cards/Toggles.qml) builds a config/built-in ID list and chooses from fixed delegates. There is no dynamic toggle component registry. The [loader](https://github.com/ladybug-me/caelestia-kde/blob/e34b6957fad5ce9395841b65be9e3df180ccd65c/shell/services/PluginLoader.qml) discovers `metadata.json`, calls `Qt.createComponent`, creates the plugin below its Item and records it in `pluginInstances`. The plugin availability model and count IPC are not Quick Toggle injection APIs.

## Minimal proposed modification

The patch changes two upstream source files:

1. `shell/modules/utilities/cards/Toggles.qml`: reads the existing internal `PluginLoader.pluginInstances["cast-audio"]`, observes `loadedCount`, and adds a full-width Loader beneath the existing toggle rows. Its source is this plugin's declared `quickToggle` Component. It excludes the new `castAudio` config ID from the fixed icon delegate list and honors its enabled flag.
2. `shell/modules/nexus/pages/utilities/QuickTogglesPage.qml`: adds `castAudio` to Connectivity so the user can hide/show the added control.

The resulting control shows the Cast SVG, title and state. Its arrow opens the plugin's selector window; its main area opens the selector when off or stops when casting/connecting. No Cast backend is added to the shell. When the plugin is absent/unloaded, the Loader is inactive. The existing plugin loader is not patched.

This is a proposed bridge to an internal loader map, not a supported public API. A future upstream plugin registration interface would be preferable. Upstream changes may invalidate the patch; it is deliberately pinned to the inspected commit.

For review, use a separate clean checkout at the pinned commit and run `git apply --check /absolute/path/to/cast-audio/patches/quick-toggles.patch`. Apply only in that reviewed checkout when desired, inspect the diff and test/build the host through its own documented workflow. The patch paths refer to the upstream repository's `shell/` directory, not the installed root. Reverting the two-file patch removes the placement; the plugin's window/IPC continue to work.

The host patch is outside component installation ownership. Keep its review, deployment, backup and reversal separate. The component does not provide an installer hook or a command that patches the live installation. Reloading any changed shell remains an explicit user action: `systemctl --user restart caelestia-shell.service`.

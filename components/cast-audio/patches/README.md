# Cast icon in Caelestia KDE Quick Toggles

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

1. `shell/modules/utilities/cards/Toggles.qml`: reads the existing internal `PluginLoader.pluginInstances["cast-audio"]`, observes `loadedCount`, and adds `castAudio` to the built-in model and native icon delegates. It uses the shell's own IconButton styling, displays `cast` / `cast_connected`, highlights while connecting/casting, and opens the plugin's controls after closing the utilities drawer. It honors the configured visibility flag, deduplicates custom entries and removes the icon when the plugin is absent.
2. `shell/modules/nexus/pages/utilities/QuickTogglesPage.qml`: adds `castAudio` to Connectivity so the user can hide/show the added control.

The resulting control is an icon alongside Wi-Fi, Bluetooth and the other Quick Toggles. Its tooltip says Cast Audio and the current state. Clicking always opens the receiver window; Stop casting remains in that window. No Cast backend is added to the shell. The existing plugin loader is not patched.

This is a proposed bridge to an internal loader map, not a supported public API. A future upstream plugin registration interface would be preferable. Upstream changes may invalidate the patch; it is deliberately pinned to the inspected commit.

For review, use a separate clean checkout at the pinned commit and run `git apply --check /absolute/path/to/cast-audio/patches/quick-toggles.patch`. Apply only in that reviewed checkout when desired, inspect the diff and test/build the host through its own documented workflow. The patch paths refer to the upstream repository's `shell/` directory, not the installed root. Reverting the two-file patch removes the placement; the plugin's window/IPC continue to work.

The host patch is outside component installation ownership. Keep its review, deployment, backup and reversal separate. The component does not provide an installer hook or a command that patches the live installation. Reloading any changed shell remains an explicit user action: `systemctl --user restart caelestia-shell.service`.

## Deployment on an installed Caelestia KDE shell

Verify the installed commit matches the reference above and inspect both files for local edits. Back up these two exact installed files before applying changes:

- `modules/utilities/cards/Toggles.qml`
- `modules/nexus/pages/utilities/QuickTogglesPage.qml`

For this patch, `git apply -p2 --check /absolute/path/to/quick-toggles.patch` from the installed shell root checks paths without changing files. Apply the reviewed patch there using `git apply -p2 /absolute/path/to/quick-toggles.patch`, then explicitly restart `caelestia-shell.service`. The `-p2` removes the repository-only `a/shell/` prefix. Enable Cast Audio in Dev Manager and Nexus; Nexus → Utilities → Quick toggles → Connectivity controls icon visibility. No shell.json edits are required for default visibility.

To reverse, first check `git apply -p2 --reverse --check /absolute/path/to/quick-toggles.patch`, then apply with `--reverse` and restart the shell. If either file changed since deployment, inspect the diff before restoring the saved copy. Shell upgrades can replace this host integration; recheck compatibility before reapplying. Run `python3 -B tests/quick_toggle_probe.py --shell /path/to/installed/caelestia` from the component to verify it in an isolated copy.

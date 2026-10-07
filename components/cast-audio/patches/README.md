# Expandable Cast receiver row for Caelestia KDE

Dev Manager **0.4.0** applies its own reviewed, checksum-pinned adapter when Cast Audio declares `integration.target=caelestia-quick-toggles`. The plugin never applies a patch; these files are inert review/probe references. No arbitrary installation hook is supported.

Reference: [ladybug-me/caelestia-kde commit e34b6957fad5ce9395841b65be9e3df180ccd65c](https://github.com/ladybug-me/caelestia-kde/tree/e34b6957fad5ce9395841b65be9e3df180ccd65c).

| Installed file | Original SHA-256 |
| --- | --- |
| `modules/utilities/cards/Toggles.qml` | `fae4d5d5c4c56341b10aa66a79e016704d2c5d4a77b5f32b3b72cca4702967ba` |
| `modules/nexus/pages/utilities/QuickTogglesPage.qml` | `91785c48250415814ae9a85c2197d57b8a502406f62defdd950406f12fd33900` |

The first file reads the existing `PluginLoader.pluginInstances` map and loads the plugin's `quickToggle` Component in a separate full-width row. The second adds the Nexus visibility option. The row expands inside Utilities; receiver clicks start playback there. Only its Settings button opens an application. PluginLoader and dashboard tabs are not patched.

The install preview includes complete before/after sources. Original content, modes and installed checksums are tracked in `$XDG_DATA_HOME/caelestia-dev-manager/host-integrations/cast-audio.json`. The durable transaction journal restores host and payload together on failure. Later host edits/mode changes block update/removal. New installs auto-enable and restart the shell; updates preserve disabled state. Uninstall restores the original host files and restarts. Preferences remain.

`quick-toggles.patch` represents the new row against pristine upstream. `legacy-icon.patch` archives the previous 0.1.1 icon for reviewed migration and the isolated probe; do not deploy it for 0.2. The adapter recognizes only its exact legacy checksums. Shell upgrades may invalidate this pinned adapter and require a new verified manager release.

For inspection only, check the new patch from a clean pinned upstream checkout with `git apply --check /absolute/path/to/quick-toggles.patch`. Run the component's `tests/quick_toggle_probe.py` against the installed root to test a temporary copy without production changes. Manual patching is unnecessary with manager 0.4 and bypasses its ownership receipt.

Patch context remains GPL-3.0-only upstream source; see [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html). Original plugin code retains its MIT license.

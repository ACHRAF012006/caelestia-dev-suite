# Caelestia KDE preview and icon repair

A scoped repair for the shell at commit `e34b6957fad5ce9395841b65be9e3df180ccd65c`. It fixes preview transitions that connect KPipeWire to serial zero, shows an application icon until a real frame arrives or when capture fails, and supplies a visible fallback for failed/loading taskbar and tray images. It retains source bindings so icons recover on later updates. Alt-Tab and dock hover consumers are released when their UI is closed. Invisible recolored dock icons no longer allocate a rendering layer.

These are shell QML changes. Cast Audio remains 0.5.1 and Dev Manager remains 0.5.1; their payloads, integration receipts and Quick Toggles host files are untouched. No compositor, graphics driver or global PipeWire configuration changes are required. The inspected logs showed `target not found` errors from window previews; they did not establish that Cast Audio caused the visual failures. A driver-level rendering fault can have additional causes beyond this repair.

Review `files/` and `manifest.json`, then run:

```sh
python3 apply.py --check
python3 apply.py --apply
systemctl --user restart caelestia-shell.service
```

Use `--shell /absolute/path/to/caelestia` for another installation. All five existing files must match the supported original or repaired checksums; the sixth is a new shared image component. The tool refuses other edits and symlinks, makes backups under `$XDG_DATA_HOME/caelestia-shell-fixes` (normally `~/.local/share/caelestia-shell-fixes`), and rolls back completed writes if applying fails. Repeat application is harmless. It does not restart anything automatically; restarting the shell stops any active Cast session.

To restore the printed backup:

```sh
python3 apply.py --restore /absolute/path/to/printed/backup
systemctl --user restart caelestia-shell.service
```

Restore checks current and backup hashes and refuses to overwrite later shell edits. A Caelestia update may replace these files; review the updated source rather than applying this repair to an unknown revision. These shell files remain separate from the Component Store's component catalogue.

Native verification:

```sh
python3 test/run.py --shell /absolute/path/to/caelestia
```

The probe needs Quickshell, the installed Caelestia QML modules, KDE Wayland, Breeze icons and PySide6. It uses temporary shell/config/state/cache paths, two owned test windows and only its synthetic window's live capture. It checks four preview reopen cycles, closed-window fallback, failed icon fallback, source-change recovery and tinted-icon hide/show. A screenshot pixel check verifies the live window content and both icons are actually rendered. The verified machine used NVIDIA RTX 3080, Quickshell 0.3.2, Qt 6.12 and KWin 6.7.5. This finite test cannot guarantee that an intermittent graphics-driver problem never recurs.

The KPipeWire [`ready` and stream-target implementation](https://github.com/KDE/kpipewire/blob/master/src/pipewiresourceitem.cpp) distinguishes a delivered frame from an advertised producer; its unset serial is `quint64(-1)`, rather than zero. The consumer must stay visible while waiting for frames, because hiding it pauses capture. This repair avoids creating the consumer until a valid target exists and keeps the fallback above it until ready.

Modified Caelestia QML is GPL-3.0-or-later under the [upstream project license](https://github.com/ladybug-me/caelestia-kde/blob/e34b6957fad5ce9395841b65be9e3df180ccd65c/LICENSE). New helper/test code in this directory uses the same license.

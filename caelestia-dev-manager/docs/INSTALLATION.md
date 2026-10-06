# Installation

For the desktop itself, see [Install Caelestia on KDE Plasma](CAELESTIA_KDE_SETUP.md). That guide follows the upstream desktop installer; the steps below install Dev Manager.

Requires Python 3.11+, venv/pip, Qt/PySide6 available as binary wheels, and a working KDE/Wayland session for desktop use. Arch/CachyOS detection is informational; missing system packages are reported for manual installation. `systemctl --user` is required for service control. `qml6` is needed for standalone QML templates. `desktop-file-validate` and `kbuildsycoca6` are used when available. Qt/PySide6 is installed inside the manager's own user virtualenv; system Python is unchanged.

From the repository:

```bash
./install.sh
~/.local/bin/caelestia-dev-manager
```

The manager appears in the KDE Application Launcher as **Caelestia Dev Manager**. The command works where `~/.local/bin` is on PATH. The installer records absolute development repository location; launcher paths are quoted to support spaces. Use `caelestia-dev-manager --project /path/to/repository` to manage another repository, or `--sandbox /tmp/cdm-test` for isolated source/data/config/state paths and mocked systemd.

The GitHub suite keeps the manager in `caelestia-dev-manager/` and published
components in `components/`. Its standalone `install-from-github.py` checks Git
and Python, clones the suite into user XDG data, then invokes the same user-level
installer. It never installs Git or other system packages. `--clone-only` fetches
source without running downloaded code. Updating an existing checkout requires
the expected origin, `main`, a clean working tree and a fast-forward merge. It
never resets source or discards local changes. Private repositories require GitHub
access through Git's normal credential mechanism.

After launching, Component Store scans published components asynchronously.
The built-in catalogue needs no repository setup. Its single Install / Update
button downloads local source under the manager project's `plugins/` and proceeds
to the dependency and installation reviews. Cancelling leaves installed files
unchanged. Previous version restores an installed backup; restart the application
after updates or restores. Settings can disable startup checks. See
[store documentation](COMPONENT_STORE.md).

| Data | Default location |
| --- | --- |
| Installed manager | ~/.local/share/caelestia-dev-manager/manager/venv/ |
| Manager launcher | ~/.local/bin/caelestia-dev-manager |
| Manager desktop entry | ~/.local/share/applications/caelestia-dev-manager.desktop |
| Manager installation receipt | ~/.config/caelestia-dev-manager/manager-install.json |
| Component source | `<project>/plugins/<id>/` |
| Installed application/command/service payload | ~/.local/share/caelestia-dev-manager/apps/<id>/ |
| Component app launcher | ~/.local/bin/<id> |
| Component app desktop entry | ~/.local/share/applications/<id>.desktop |
| Optional component desktop shortcut | Configured `$XDG_DESKTOP_DIR/<component name>.desktop` |
| User service | ~/.config/systemd/user/cdm-<id>.service |
| Caelestia user plugin | ~/.config/caelestia/plugins/<id>/ |
| Component registry/events/journal | ~/.local/state/caelestia-dev-manager/ |
| Installed snapshots/backups | ~/.local/share/caelestia-dev-manager/backups/ |
| Dependency preparation | `<project>/workspace/dependencies/<id>/<fingerprint>/venv/` |

XDG_DATA_HOME, XDG_CONFIG_HOME and XDG_STATE_HOME overrides are honored. Executables use `~/.local/bin`, the standard user binary location. Symlinked managed parent paths are rejected rather than followed. Use real XDG paths.

Desktop shortcuts are optional for standalone apps and scripts. The manager reads `XDG_DESKTOP_DIR` from `$XDG_CONFIG_HOME/user-dirs.dirs`, supporting standard quoted `$HOME`/`${HOME}` paths and absolute customized locations. It never assumes `~/Desktop`. Missing configuration, an empty value, or a value equal to HOME means no desktop is available; leave the checkbox off or configure your XDG user directories. No shortcut is created during source import. Installation and later shortcut actions preview the exact path. Enabled shortcuts have executable mode 0755 for KDE; disabled copies use mode 0644 and Hidden=true. See [desktop shortcuts](DESKTOP_SHORTCUTS.md).

Run `./install.sh` again after updating source. Manager updates preserve component registry, backups, sources and installed payloads. `./uninstall.sh` deletes only files in the separate manager-install receipt and removes empty manager directories. There is intentionally no automatic purge option: components, backups, state and source remain. Per-component uninstall is available in the UI. Modified manager files block uninstall to preserve manual edits.

Python component dependencies are prepared only after a separate review, in a component-specific `venv --copies` environment; only binary wheels are accepted. No system packages or project install scripts run. The exact prepared files are then included in the install plan/ownership receipt and copied into the installed `_venv`. The launcher's interpreter points to the installed environment and does not use the manager virtualenv. Only interpreter relocation is supported; auxiliary environment command scripts may retain staging shebangs and should not be used as component entrypoints. Runtime Python upgrades on rolling distributions may require preparing a new environment and reinstalling components.

The manager itself has no persistent daemon or autostart service. User-service components run under their own units without it. Updating/restoring a service stops it first; use Start afterward as needed. After errors or interrupted operations, inspect actual unit state and use Settings recovery when a journal exists.

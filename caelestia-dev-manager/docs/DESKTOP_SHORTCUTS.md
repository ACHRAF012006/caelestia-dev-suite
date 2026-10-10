# Optional desktop shortcuts

For standalone apps and scripts, choose **Create shortcut on desktop** in New Component, Create / Import or the installation preview. It defaults to off. New Component and import store only a preference in development source; installation remains a separate reviewed action. Other component types have disabled shortcut controls.

```json
{
  "desktop": {
    "createShortcut": true,
    "terminal": false,
    "startupNotify": false
  }
}
```

Use this object inside the normal component manifest. The normal launcher remains `$XDG_DATA_HOME/applications/<id>.desktop`. The shortcut is an exact content copy at `$XDG_DESKTOP_DIR/<component name>.desktop`, with safe filename normalization. Both execute the installed application's user command directly; neither invokes Dev Manager. A script gets a canonical desktop entry when first requesting a shortcut; it remains until component uninstall even if the shortcut is removed.

## Desktop directory and KDE

The manager reads `$XDG_CONFIG_HOME/user-dirs.dirs` as data. For example, `XDG_DESKTOP_DIR="$HOME/Bureau"` uses the localized directory, and an absolute custom directory works too. No shell configuration is sourced and `~/Desktop` is never guessed. Missing/empty desktop configuration or HOME itself means disabled. Configure a real XDG desktop directory or leave the option unchecked. Symlink directories and unsafe paths fail with an explanation. A configured missing directory is created only when applying the reviewed shortcut plan.

Name, Comment, Exec, Icon, Categories, Terminal and StartupNotify share the canonical launcher definition. Terminal defaults to true for scripts, false for apps. StartupNotify defaults to false because support belongs to the launched application; the [Desktop Entry specification](https://specifications.freedesktop.org/desktop-entry/latest/recognized-keys.html) defines the application's notification contract. Enabled shortcut files are executable (0755), allowing KDE's [application launcher](https://invent.kde.org/frameworks/kio/-/blob/master/src/gui/applicationlauncherjob.cpp) to recognize them as launchable desktop files. KDE may still apply local trust policies or prompt after files are manually changed. Desktop icon visibility depends on Plasma's desktop layout and its configured folder; the manager does not change those settings.

## Existing files, toggles and lifecycle

Installed Components show **Desktop Shortcut: Created** or **Not Created** and offer **Create Desktop Shortcut** / **Remove Desktop Shortcut**. Toggling writes/removes only the shortcut (and creates the canonical launcher if a script needs one), retaining application payload, source and version fingerprints. The installed preference survives source updates unless the source manifest changes its preference or the installation checkbox overrides it.

If another file uses the proposed name, creation is blocked. The UI offers an unused filename such as `Quick Clipboard (quick-clipboard).desktop`; review it before installation/creation. Existing component-owned files are checked for manual modification before replacement or deletion. Shortcuts manually moved or edited are reported missing/modified and are never discovered or deleted by a filename guess.

The registry owns the exact shortcut path, checksum and permissions alongside all other installed files. Disabling an application sets both entries Hidden=true, removes the shortcut executable bit and disables its command; enabling restores launchability. Updating installed source regenerates both entries from the same metadata. Removing the shortcut leaves the normal launcher and installed app intact. Uninstall removes the owned shortcut, retaining source and unrelated desktop files. Changing XDG desktop configuration does not prevent cleanup of the previously recorded location. Remove then recreate a shortcut to move it to the new configured directory.

Creation/removal participate in recoverable transactions and full installed-state backups. Restoring a shortcut-operation backup also preserves the previous app payload and ownership receipts. Manager uninstall preserves components and their shortcuts.

## Backend API

`Manager.create_desktop_shortcut(id, filename=None, expected=None)`, `remove_desktop_shortcut(id)` and `has_desktop_shortcut(id)` operate on installed components. Preview creation/removal with `plan_create_desktop_shortcut(id, filename=None)` and `plan_remove_desktop_shortcut(id)`. `plan_install` / `install` accept optional `create_shortcut` and reviewed `shortcut_filename` overrides. Desktop location/filenames are not arbitrary manifest destination overrides.

See [testing](TESTING.md) for temporary-path unit/UI tests and a native KDE shortcut acceptance helper. Automated tests never create real desktop shortcuts.

Manager 0.8 retains this ownership and lifecycle contract. Reviews include actual
shortcut authority from the validated plan. Slow installation/restore work runs
on private-connection jobs; no mutation is cancelled midway. Component packages
transfer source/resources, never foreign absolute shortcut ownership receipts.

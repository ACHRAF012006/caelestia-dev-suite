# Install Caelestia on KDE Plasma

This guide follows [ladybug-me/caelestia-kde](https://github.com/ladybug-me/caelestia-kde), the KDE port of Caelestia. It is for CachyOS with an existing KDE desktop. Caelestia's upstream installer handles the desktop setup; install Dev Manager afterward to manage your independent components.

## 1. Start with KDE Plasma

On a new CachyOS installation, select **KDE Plasma** as your desktop in the installer. See the official [CachyOS installation guide](https://wiki.cachyos.org/installation/installation_on_root/) and [desktop choices](https://wiki.cachyos.org/installation/desktop_environments/). On an existing installation without KDE, follow the [CachyOS desktop switching guide](https://wiki.cachyos.org/configuration/desktop_environments/switch_desktop/) first.

Sign in to a **Plasma Wayland** session. Open Konsole and check:

```bash
plasmashell --version
printf '%s\n' "$XDG_SESSION_TYPE"
git --version
```

You need Plasma **6**, a session reporting **wayland**, Git, an internet connection, and **Qt 6.9 or newer**. Upstream also supports Fedora and Debian/Ubuntu; this walkthrough uses CachyOS. If Git is missing, install it through your distribution's package tools first. These requirements come from the [upstream installation instructions](https://github.com/ladybug-me/caelestia-kde#installation).

## 2. Download and inspect the upstream installer

Save your current desktop configuration before proceeding. The upstream installer can install system packages, change KDE settings and apply a login-screen theme, and requests administrator authentication for privileged steps. Dev Manager's user-only installation rules apply to Dev Manager and its components, not this separate upstream desktop installer.

Clone the stable branch, including its submodules:

```bash
git clone --branch main --recurse-submodules https://github.com/ladybug-me/caelestia-kde.git "$HOME/caelestia-kde"
cd "$HOME/caelestia-kde"
less install.sh
less scripts/setup.sh
```

Press **q** to leave each viewer. Review the installer and the scripts it calls before running them. If this checkout already exists, use the update section below instead of cloning over it. This uses the same repository, branch and submodule setup as the [upstream entry script](https://github.com/ladybug-me/caelestia-kde/blob/main/install.sh).

## 3. Install using the upstream menu

From the **Caelestia KDE checkout**, run:

```bash
bash ./install.sh
```

Choose **Install Caelestia**. Use the arrow keys and Enter to navigate. Review Packages, Appearance, Shell and Applications; turn off optional changes you do not want. For example, the SDDM theme, custom lockscreen and third-party app themes are configurable. Choose **Review installation**, inspect the steps, then start. See the upstream [menu options](https://github.com/ladybug-me/caelestia-kde/blob/main/installer/data/menu.json) and [installer interface](https://github.com/ladybug-me/caelestia-kde/blob/main/installer/tui/UI.cpp).

Let installation finish, then log out and sign back into Plasma Wayland. Keep the checkout and its backups for later maintenance.

## 4. Set up your desktop and Dev Manager

Press **Super**, type **>Settings**, and open Nexus. Choose your wallpaper and appearance there so the shell's colors follow your wallpaper. Upstream stores shell preferences in `~/.config/caelestia/shell.json`. See [upstream configuration](https://github.com/ladybug-me/caelestia-kde#configuring).

Next follow [Dev Manager installation](../README.md#install-and-launch), or the [suite README](https://github.com/ACHRAF012006/caelestia-dev-suite#install-dev-manager). Open **Component Store** and choose **TouchDeck → Install**. TouchDeck runs independently and continues working when Dev Manager closes.

## Update or uninstall Caelestia

For updates, use **Nexus → Updates**, choose **main**, and select **Install Updates**. Alternatively, from the upstream checkout:

```bash
cd "$HOME/caelestia-kde"
bash ./update.sh main
```

Upstream preserves shell settings across updates. Its updater may stash source edits, so review your checkout changes first. Follow [upstream update guidance](https://github.com/ladybug-me/caelestia-kde#updating) and the [update script](https://github.com/ladybug-me/caelestia-kde/blob/main/update.sh).

To remove Caelestia, choose **Uninstall** in its installer, or run its uninstaller:

```bash
cd "$HOME/caelestia-kde"
bash ./uninstall.sh
```

Review the restore choices for the desktop backups. This is Caelestia's uninstaller; the Dev Manager folder has a separate `uninstall.sh`. See [upstream removal instructions](https://github.com/ladybug-me/caelestia-kde#uninstalling).

## If something goes wrong

| Problem | Next step |
| --- | --- |
| Shell missing after installation | Log out and back in; check `systemctl --user status caelestia-shell.service`. |
| Need debugging information | Enable Debug Mode in Nexus → About → Advanced, then run `caelestia shell -l`. |
| Installer stopped halfway | From the upstream checkout, rerun `bash ./scripts/setup.sh` and review the failure. |
| Packages failed | Check `${XDG_CACHE_HOME:-$HOME/.cache}/caelestia-kde/failed_packages.txt`. |
| Wrong colors | Set the wallpaper through Nexus Appearance. |

For detailed remedies, use the [upstream troubleshooting guide](https://github.com/ladybug-me/caelestia-kde/blob/main/docs/TROUBLESHOOTING.md). Report desktop installer/shell issues to [Caelestia KDE](https://github.com/ladybug-me/caelestia-kde/issues); report manager/store issues to this suite.

Checked on 2026-10-06 against upstream commit [`e34b6957`](https://github.com/ladybug-me/caelestia-kde/commit/e34b6957fad5ce9395841b65be9e3df180ccd65c). Consult the linked upstream documentation for later changes.

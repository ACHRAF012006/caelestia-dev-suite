# Caelestia Dev Suite

Caelestia Dev Manager and independent touchscreen components for CachyOS / KDE Plasma / Wayland.

## Repository layout

- **`caelestia-dev-manager/`** — Dev Manager 0.5.1, installer, documentation and tests.
- **`components/`** — published standalone applications, services and reviewed Caelestia components. TouchDeck 0.1.1 and Cast Audio 0.5.1 are included.

The manager handles installation and lifecycle. Components continue running after it closes.

Pages reuse loaded information and switch with a brief fade and sliding tab highlight. Startup and Refresh check component information in the background, keeping navigation responsive. Settings → **Animate tab transitions** turns both animations off. Dev Manager's window and desktop launcher use its bundled logo with fixed colors, independent of the system icon theme. Recreate desktop copies from the updated application launcher if they still show the old generic icon.

## Install Caelestia on KDE

Start with **KDE Plasma 6 on Wayland**. On a new CachyOS installation, choose KDE Plasma in the installer. Then follow our [Caelestia KDE setup guide](caelestia-dev-manager/docs/CAELESTIA_KDE_SETUP.md), based on [ladybug-me/caelestia-kde](https://github.com/ladybug-me/caelestia-kde).

The guide covers requirements, downloading and reviewing the upstream installer, its installation menu, Nexus settings, updates, uninstalling and troubleshooting. The upstream desktop installer installs system dependencies and may request administrator authentication. Once the desktop is ready, install Dev Manager below.

## Install Dev Manager

With Git installed and repository access configured:

```bash
git clone https://github.com/ACHRAF012006/caelestia-dev-suite.git
cd caelestia-dev-suite/caelestia-dev-manager
./install.sh
~/.local/bin/caelestia-dev-manager
```

Alternatively download [install-from-github.py](caelestia-dev-manager/install-from-github.py), inspect it, then run:

```bash
python3 install-from-github.py
```

This standalone bootstrap checks Git and Python, clones the suite into user XDG data and invokes the user-level installer. Git must be installed manually if missing. `--clone-only` downloads source without installing it; `--directory /path/to/checkout` chooses the source location. Repeated runs require the expected origin, clean source and a fast-forward update. No root access, global Python changes or system package installation.

Private repositories require access through Git credentials or an authenticated GitHub CLI. The helper uses GitHub CLI credentials per command without changing global Git settings. No credentials are stored in manager settings.

## Download and update components

Dev Manager's **Component Store** checks this repository automatically when it opens, with no repository setup. Choose an app and press **Install**; the same button becomes **Update** when needed or **Open** for installed apps. Downloads continue directly into readable permission and installation reviews, with technical details available on demand. **Previous version** restores an earlier installed snapshot while keeping settings and current source. Local edits are protected and offline checks keep the last catalogue. Settings can disable startup checks; **Refresh** checks manually. There is no Code tab; use Components → Open Source for development edits.

Launch installed TouchDeck from KDE or with `touchdeck`; it does not need Dev Manager running.

For [Cast Audio](components/cast-audio/README.md), update Dev Manager to **0.5.1**, then choose Component Store → Refresh → Cast Audio → Install/Update. Reviewed installation automatically adds a **separate expandable row beneath Quick Toggles**, enables new installations and restarts Caelestia KDE. Updates preserve disabled state. Expand the row and choose a receiver inline; its **Settings** button opens a separate app with desktop/app selection and live delay/bitrate preferences, saved device IPs and an optional fixed stream port for routed VLANs. Google-account discovery is unavailable in this Linux backend. Installation prepares private catt dependencies, known missing audio tools and portable active-UFW rules for the saved fixed port using native authentication where required. The README includes router requirements and current playback-test limitations. Uninstall restores the managed host originals; later host edits are preserved and block replacement.

## Development

Edit manager code in `caelestia-dev-manager/`. Publish components in `components/<id>/` with semantic versions and strict manifests. Commit and push to `main`; the next store check discovers changes. Local downloaded/draft source under the manager's `plugins/` is ignored and never published automatically.

[Manager documentation](caelestia-dev-manager/README.md) · [Component contract](caelestia-dev-manager/docs/COMPONENT_SPEC.md) · [Component Store](caelestia-dev-manager/docs/COMPONENT_STORE.md) · [TouchDeck](components/touchdeck/README.md) · [Cast Audio](components/cast-audio/README.md)

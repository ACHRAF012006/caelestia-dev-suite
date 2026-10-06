# TouchDeck 0.1.1

TouchDeck is an independent Python / Qt 6 application for a secondary 7-inch
touchscreen on CachyOS and KDE Plasma / Wayland. Closing or uninstalling Dev
Manager does not close TouchDeck. This package contains development source only;
importing it does not install, enable, launch or change your desktop.

## Installation

Paste the complete CAELESTIA_DEV_PACKAGE into Dev Manager's Create / Import.
Analyze and review the manifest, files, permissions and exact destinations.
Create the component, prepare its declared Python dependencies through the
manager's reviewed component environment, and review Install. Launch TouchDeck
from KDE's applications menu or the generated user command `touchdeck`.
Use Dev Manager for updates, enable/disable, installed-payload backup/restore
and uninstall. No installer hooks or manager runtime imports are included.

Python 3.11+, PySide6, pulsectl, dbus-next and psutil are declared in the manifest.
`gio` supplies desktop-entry launching. Audio additionally needs the existing
user PipeWire / pipewire-pulse service and libpulse; these are not Python packages
or executable dependencies and are detected at runtime. TouchDeck never installs
system packages. Optional `nvidia-smi` and `nmcli` improve status widgets when
already available. Neither is required. No root access, sudo, global configuration
changes, symlinks or downloaded runtime code are used.

## Use and customization

First launch offers a skippable setup wizard for display, layout and installed
application launchers. Startup is windowed and autostart is off. Home, Audio and
Media pages are immediately useful. Add the optional Gaming preset in Settings
→ Pages, then choose your own game/application launchers.

Tap a button to act. Swipe horizontally over a tile or dashboard background to
change pages; sliders retain horizontal dragging for volume/seek. Header arrows
and the optional scrollable page bar provide navigation without gestures.
Vertical scrolling supports overflowing layouts and the full mixer. Controls
use large buttons and 30-pixel slider handles with 48-pixel touch areas.

Press Edit, then Add or tap an existing widget. Long-press its title or background
for edit, duplicate, remove and reorder actions. The widget editor changes type,
label, icon, size, page, position, clock options and action. Choose 1x1, 2x1 or 2x2.
Settings → Pages creates, renames, duplicates, deletes and reorders pages and sets
grid dimensions. Columns adapt to available width; content that cannot fit stays
accessible by scrolling. Undo keeps the last 20 configuration edits this session.
No normal customization requires editing Python or JSON.

Buttons support installed application selection, URL, file/folder, media,
audio, audio profile, session action, page switch, Settings and sequential macro.
The application picker searches names/descriptions from XDG desktop entries and
uses their icons. Desktop activation and foreground behavior depend on the
application and compositor; TouchDeck does not attempt to bypass Wayland focus
rules. Missing applications remain editable and show Unavailable.

Advanced commands are explicit argument lists, displayed in the editor and
stored in configuration. Shell interpolation is disabled; a shell is used only
if you explicitly configure one as the command. Every command requires runtime
confirmation. Macros contain up to 32 built-in actions edited through the UI,
with optional explicit delays. Steps wait for completion or accepted launch
submission; failures stop remaining steps. Cancel action in Settings stops
remaining steps and does not undo submitted operations or kill started programs.

## Audio and media

The Audio page controls the default output, default microphone and individual
active application streams. It shows device choices, percentages and mute state.
Tap the master volume heading marked Expand to open a full-size mixer. Active
application volumes appear first and update as streams start or stop; scroll to
reach every stream, output device and microphone. Back returns to the same page.
The large microphone widget toggles the default microphone and shows text/icon
feedback plus a toast. Default-device changes affect future routing; this release
does not forcibly move existing streams. Volumes are limited to 0–100%.

Settings → Audio saves the current mix as a named profile, including selected
devices, output/input levels and mute state, and active application levels keyed
by application identity. Add profile buttons through the widget editor. Missing
devices are reported and skipped. Profiles apply application levels to streams
active at activation time; they do not continuously enforce future stream levels.

Audio uses the [PipeWire PulseAudio-compatible server](https://docs.pipewire.org/devel/page_module_protocol_pulse.html)
through [pulsectl](https://pypi.org/project/pulsectl/), with subscription updates
on a dedicated worker and a five-second reconciliation check. An unavailable
server/library disables audio controls and retries without stopping the app.

Now Playing supports player selection or automatic preference for a playing
player, track/artist/album information, local artwork, progress, seeking and
previous/play-pause/next. Separate buttons also expose Play, Pause and Stop.
Controls honor player capabilities. [MPRIS](https://specifications.freedesktop.org/mpris/latest/Player_Interface.html)
uses the session D-Bus through [dbus-next](https://python-dbus-next.readthedocs.io/en/latest/message-bus/aio-message-bus.html).
Signals trigger updates, with five-second reconciliation and local position
interpolation between samples. Remote album art is deliberately not downloaded;
local artwork falls back to a system icon. No player shows No media playing.

## Display, appearance and system controls

Settings remembers a display identity, with Windowed, Borderless and Fullscreen
modes. A missing selected monitor falls back to another secondary screen, or a
safe window on the primary screen. Automatic selection also stays windowed when
only the primary display exists; explicitly select it to request fullscreen there.
The Fullscreen header button or F11 toggles fullscreen on the current display.
Fullscreen hides the top controls and bottom page bar by default. Swipe to change
pages; tap the small Menu button to reveal navigation, Settings and Edit. Hide
bars restores the clean dashboard. Editing keeps its controls visible until you
leave Edit mode. Settings → Display can turn off fullscreen bar hiding.
Escape closes an expanded mixer first, then returns to a window. Reopening
Settings discovers changed display lists.

Dark is the default, with OLED Dark, Light and a restrained configurable accent.
Built-in microphone, volume and media icons follow the theme's foreground color;
bundled SVG fallbacks remain available without a KDE icon theme. Application and
user-provided icons keep their original colors.
Pressed highlights supply visual touch feedback. No haptic or compositor blur
API is assumed. Optional idle mode replaces the dashboard with a dim visual
clock, now-playing title and CPU/RAM status; touching restores the dashboard.
It does not change hardware brightness. Sound feedback is not implemented.

CPU/RAM and network throughput refresh about once per second, accessible CPU
temperature and NVIDIA status about every two seconds, and disk/network metadata
about every five seconds. Network widgets show local IP, active connections and
their types, including VPN/WireGuard when NetworkManager exposes them. They do
not configure networking. Unsupported metrics disappear or show unavailable.

Configure system buttons for lock, logout, suspend, reboot or shutdown.
All except lock require a Cancel-default confirmation on every execution,
including inside macros. Requests use documented [login1 interfaces](https://github.com/systemd/systemd/blob/main/man/org.freedesktop.login1.xml)
with interactive authorization disabled. Policy denial is shown without privilege
escalation. Logout explicitly terminates the current session; its confirmation
asks you to save your work. Power actions are never used by automated tests.

## Persistent data and lifecycle

Configuration is `$XDG_CONFIG_HOME/touchdeck/config.json`, with a previous valid
`config.backup.json` and a preserved rejected copy on recovery/save. Invalid
configuration loads a backup or safe defaults and shows a notice. Writes use
atomic replacement; symlink paths are refused. XDG defaults are respected.
Logs live in `$XDG_STATE_HOME/touchdeck/touchdeck.log` with three bounded rotated
files. Settings → Advanced reveals logs/configuration. Commands, media metadata
and command output are not recorded in logs.

Settings → Startup optionally owns only the marked user preference
`$XDG_CONFIG_HOME/autostart/touchdeck-user.desktop`, after installation. Its Exec
and TryExec point to the manager's fixed `~/.local/bin/touchdeck` launcher;
disable/uninstall prevents subsequent automatic starts. An unrelated file at
that path is refused. Turn the preference off in TouchDeck to remove it.
The autostart preference and runtime configuration are user data, separate from
the manager's exact installed-file ownership. Dev Manager backs up/restores the
installed payload; copy the TouchDeck config directory separately if you also
want to archive user layouts/profiles. Uninstall preserves user data. Installing
or updating this source never enables autostart automatically.

## Development and verification

Run `python -B src/main.py` from the component directory using an environment
containing the declared dependencies. For isolated testing, set all XDG home
variables to temporary directories. The included tests use temporary writable
paths and mocked audio/media/session actions:

    QT_QPA_PLATFORM=offscreen python -B -m unittest discover -s tests -v

The source is divided into configuration/action models, asynchronous audio and
D-Bus services, monitoring/application/display services, Qt UI modules and XDG
utilities. Additional built-in widget/action types can extend these interfaces
in reviewed versions. There is no arbitrary Python plugin loader.

Automated checks cover configuration recovery/Undo, desktop discovery, denied
commands/power actions, macro failure ordering, volume limits, page editing and
dynamic mixer streams, MPRIS seek signatures, and window sizes 800x480, 1024x600
and 1280x800. Regression checks also cover fullscreen bar visibility, the touch
Menu, Edit and idle recovery, the persisted display preference, expanded mixer
updates and Back, and light/dark SVG contrast with preserved custom artwork.
Physical touchscreen gestures, actual
power transitions, display hotplug and KDE's autostart execution still require
manual desktop acceptance; offscreen tests cannot verify those host behaviors.

# Animated Timer integration (manager 0.6.0)

Manager 0.8 routes this existing adapter through the trusted CapabilityRegistry
and central compatibility matrix. Receipt formats and native runtime behavior
remain unchanged. See [ADAPTER_API](ADAPTER_API.md) and [RECOVERY_MODEL](RECOVERY_MODEL.md).

The `animated-timer` Quickshell component declares `caelestia-dashboard-timer`.
This is a dedicated manager-owned adapter, not an upstream dashboard API. Install
manager 0.6.0 source before installing this component; the Component Store does
not update the manager.

Verified against installed Caelestia KDE v2.5.1, commit
`e34b6957fad5ce9395841b65be9e3df180ccd65c`, on 2026-10-09. Installed dashboard
Content/Wrapper files exactly matched the reference clone at this commit.
`backend/timer_integration.py` pins SHA-256 hashes and release markers. Only
`modules/dashboard/Content.qml` and `modules/dashboard/Wrapper.qml` can change.
There is no component-provided patch, installer hook or generic host destination.

Content appends a Timer tab only while the real PluginLoader contains the timer.
The plugin supplies a QML Component; loaders never create independent engines.
Wrapper loads one notch window per dashboard wrapper (per screen). It exposes
existing visibility, screen and screenState objects, retains actual dashboard
width as its lazy content unloads and opens the filtered Timer index on click.
Quickshell PanelWindow uses logical pixels, the wrapper's own screen, Overlay layer,
Ignore exclusion and None keyboard focus. The existing dashboard animation and
other tabs remain the host's responsibility. Disabled native Nexus plugins remain
subject to Caelestia's own plugin setting.

The adapter participates in the same sealed lifecycle plan, exact BEFORE/AFTER
review, intent journal and recovery coordinator as component files. Its separate
`host-integrations/animated-timer.json` receipt contains original source, original
modes and resulting hashes. It does not claim host files in payload ownership.
New installations enable the component; updates preserve enabled state. Successful
reviewed mutations restart the user shell service. Restart failures leave Reload
Required recorded. Development tests never call production systemd.

Unexpected content, changed modes, release changes or corrupted receipts block
replacement/removal. Edits are preserved: reconcile them explicitly against the
reviewed original and transformed source before retrying. Recovery refuses third
party content/mode/receipt changes. No force-overwrite or broad tree ownership is
provided. Unrelated Cast Audio files use their independent existing adapter.

## Reviewed installation and removal

1. Update the manager from this reviewed source (`./install.sh`).
2. Open Components and select local `animated-timer` source, or import its complete
   package. Read source, dependencies and permission declarations.
3. Review Install, including the exact two host diffs. Confirm the lifecycle action
   to copy the installed snapshot, retain originals, enable and reload Caelestia.
4. Choose Timer in the dashboard. A running or paused timer appears as a 30 px
   notch on each available monitor when that monitor's dashboard is closed.
5. Disable hides discovery after the reviewed reload. Uninstall restores the two
   original host files, removes only owned payload and retains source/user state.

Backup/Restore and Previous version use the manager's existing reviewed workflow.
Restore can reconstruct the adapter after uninstall; each replacement first backs
up the current installed version. Select a prior backup to roll back an update.
Uninstall the timer through the manager before downgrading to a manager without
this adapter. Do not manually delete receipts or overwrite host files.

## Runtime and persistence

The helper uses Python's standard library with an exclusive file lock under
`$XDG_STATE_HOME/animated-timer/`. Linux CLOCK_BOOTTIME deadlines count suspended
time; normal wall-clock adjustments do not change an active countdown. Same-boot
shell restarts recover the same deadline. Across reboot a wall deadline estimates
remaining time; changing the clock while powered off necessarily affects that
estimate. Preferences, presets and countdown persist atomically with fsync. A
completion receipt and pending alarm are committed before external effects.
A crash/reload resumes the pending alarm without recreating its completed cycle.
Notification IDs are checked against the unique notification-server connection
before replacing or closing them; a restarted server cannot affect foreign alerts.
Auto-repeat starts one fresh cycle after a long sleep, without replaying every
missed cycle. No animation delays engine start. Disable/enable retains the running
deadline; explicit Cancel ends the countdown.

The helper wakes at most once per second while running and blocks on stdin when
idle/paused. One-second snapshots serve every UI; particle loops run only in
visible presentations and pause without resetting phase. Animation-off is the
explicit reduced-motion preference (no upstream reduced-motion flag was found).
Sound uses an original generated PCM bell through canberra, repeating every two
seconds until Stop. Notification actions use notify-send; gdbus closes only the
timer notification on Stop. Pending alarm state and notification IDs persist
across shell restarts. Audio and notification delivery depend on desktop services.

## Validation

Run the normal temporary-XDG pytest suite and `scripts/timer_qml_probe.py`.
The latter copies installed host source, restores the pinned dashboard fixtures
in that copy, applies the fixed adapter there,
uses isolated XDG roots and private D-Bus sessions, and starts a virtual KWin
compositor with two outputs and 1.25 scaling. No production shell is changed.
See the component's TESTING.md for the automated coverage and hardware acceptance
checks. Publication and production installation are separate authorized actions.

Timer 0.1.1 uses the native Media tab width and height tokens, keeps preferences
and preset management behind the settings icon, and adds accelerating hold arrows
for each time unit. The per-monitor notch uses zero top margin and square upper
corners at the physical screen edge, on the Overlay layer without keyboard focus.
The dedicated host adapter and its pinned transforms remain unchanged.

Timer 0.1.2 adds persistent, stoppable completion alarms, an actionable notification,
and a dashboard Stop control. The notch clamps width to each logical screen with
edge clearance, uses the dashboard surface/transparency/pitch-black settings, and
provides a play/pause button with a 220 ms morph. The host adapter stays unchanged.

## Shared pages in manager 0.7.0

Timer-only installations keep the original target, pinned transform and receipt.
When generic pages are installed, the shared dashboard adapter composes Timer
first and preserves its notch routing and per-monitor state. Presentation
activity uses the Timer ID instead of last-tab position. Removal of the last
generic page reconstructs the legacy-only form. Read
[DASHBOARD_INTEGRATION.md](DASHBOARD_INTEGRATION.md) for receipts, interrupted
composition recovery and manager downgrade requirements.

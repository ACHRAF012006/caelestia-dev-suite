# Caelestia Animated Timer 0.1.2

A native Caelestia dashboard Timer tab and a 30 px top-attached notch. One independent
Python helper drives every presentation; Dev Manager can be closed or removed.
The original QML hourglass has bounded sand grains, state-aware rotations and
sand levels driven by actual remaining time. It uses Caelestia palette/typography.

Requires **Timer-capable Dev Manager 0.6.0**, Caelestia KDE **v2.5.1** at commit
`e34b6957fad5ce9395841b65be9e3df180ccd65c`, Linux CLOCK_BOOTTIME, Python 3.11+,
Quickshell, `notify-send`, `canberra-gtk-play` (libcanberra) and `gdbus` (GLib).
There are no pip dependencies, network requests, privileged hooks or GIF assets.
Inspect the manifest's complete permissions before installation.

## Install and lifecycle

Keep this complete directory in `plugins/animated-timer/` for development, or
publish it unchanged under the suite's `components/animated-timer/` after review.
Update Dev Manager from the companion 0.6.0 manager source first. Select this
component in Components, Validate and review Install. Installation includes exact
before/after source for two pinned dashboard files and an automatic shell reload.
An older manager cannot install this integration. Do not manually patch the host
or run main.qml as an independent production timer.

Enable/Disable, Update Installed Version, Backup, Restore, Previous version and
Uninstall all use reviewed manager lifecycle actions. Updates preserve disabled
state. Uninstall restores host originals and retains component source and timer
state. Later host edits block uninstall/update until explicitly reconciled; they
are never overwritten. Cast Audio and TouchDeck retain their own integrations.
Restore a saved backup to roll back an update or reconstruct after uninstall.
Uninstall through the Timer-capable manager before downgrading it.

## Use

Choose **Timer** in the Caelestia dashboard. Hover and scroll HH/MM/SS (one wheel
notch per unit, accumulated high-resolution touchpad motion) or click to type.
Use the small up/down arrows for single steps; holding an arrow accelerates its
repeat rate. Releasing, leaving the arrow or closing the tab stops adjustment.
Hours are 0–99; minutes/seconds are 0–59. Zero cannot start. Units consume wheel
input so it does not navigate the dashboard. Digits roll in 180 ms.

Start/Pause/Resume apply immediately. Reset restores the configured duration and
adds a full turn to its arrow's animation target, even on repeated clicks. Cancel
returns to Ready. During a countdown, use the pencil button to edit the
configuration safely. Presets always set configuration without changing an active
countdown. Add, rename, edit duration and delete presets from the settings icon.
Focus (25m), Short Break (5m), Study (45m) and Quick (10m) are provided initially.

The main surface uses the same width/height tokens as the native Media tab.
Preferences and preset editing stay behind the settings icon.
At completion, an original soft bell repeats until **Stop** in the notification
or Timer tab (also available in the completed notch). The notification stays
until stopped; closing the notification without pressing Stop leaves the alarm
active. Reset/Cancel also stop the alarm. Pending alarms survive shell restarts.
Auto-repeat can keep counting while the previous alarm awaits Stop.

Preferences control sound, notification, repeat and animation. Disable animations
for reduced motion. Auto-repeat starts a fresh cycle with an hourglass turnover;
missed cycles during a long sleep are not replayed. Pomodoro automation is not
included; the Focus/Short Break presets support manual work/break transitions.

The notch is visible while running or paused with the local dashboard closed.
It follows that monitor's actual dashboard width, capped to its logical screen
width with edge clearance, and respects per-screen scaling. Its square
upper corners attach directly to the physical screen edge, above the bar.
Click its body to open the Timer tab; its play/pause icon controls the timer
directly and morphs smoothly. It never takes keyboard focus. During completion,
the notch stays available until the alarm is stopped. Its background uses the
exact dashboard surface color, transparency and pitch-black preference.
Closing the dashboard never resets timing. New monitors obtain their own notch.

## Persistence and limitations

State and presets live in `$XDG_STATE_HOME/animated-timer/state.json`, defaulting to
`~/.local/state/animated-timer/`. The directory's engine.lock enforces one helper.
Installed executable files stay immutable. Countdown includes suspended time and
recovers across shell restarts. Across reboot a saved wall deadline is used, so
clock changes while powered off affect recovery. Alarm state is persisted before
playback and resumes after a crash/reload. One sound player and one actionable
notification are supervised; restarting replaces the timer notification using its
saved ID only when the same notification-server connection still owns it.
After a server restart, a new timer notification is created safely. Stop is durable, and stale notification actions cannot stop a newer
alarm. Actual sound delivery and notification actions depend on the desktop
audio/notification services. Muting sound or disabling the component silences
playback; a pending alarm resumes on re-enable unless explicitly stopped. Native Nexus disabled-plugin settings also apply.

Compatibility is intentionally limited to the pinned host files and release.
There is no upstream dashboard extension point and no arbitrary component patch.
For upstream upgrades, review and release a compatible manager adapter first.
The helper exiting displays an error and requires shell reload to reconnect.

See TESTING.md for automated tests and hardware acceptance. Nothing is published,
installed into production or restarted by development scripts.

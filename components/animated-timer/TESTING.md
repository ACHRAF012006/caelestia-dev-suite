# Timer verification

The included engine tests can also run from this component directory with
`python -m pytest tests/` (pytest is a development-only dependency).

From the companion Dev Manager repository:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python scripts/timer_qml_probe.py
.venv/bin/python -m build
```

Engine tests use injected BOOTTIME/wall clocks and private state: fractional pause,
deadline accuracy without drift, wall-clock jumps, suspend, restart, reboot,
exactly-one completion, rapid idempotent commands, atomic wheel unit adjustments,
preset rename/delete and safe active-countdown edits, repeat after a long suspend.
Lifecycle tests use temporary XDG host fixtures: exact diffs, install/disable/update,
backup/restore/uninstall, changed release/content/receipts, partial host-write and
registry-failure recovery. Existing Cast Audio adapter regression tests run too.

The native QML probe requires installed Quickshell, KWin, dbus-run-session and
Caelestia QML libraries. It copies the host into a temporary directory and applies
the manager-owned adapter to that copy. Two virtual outputs at 1.25 scaling use
private Wayland sockets, D-Bus sessions and XDG roots. The helper disables sound
and notifications. The probe compiles patched host QML, instantiates the real
TimerPage and TimerNotch, checks wheel/touchpad accumulation, runs start/pause/resume,
rapid reset and completion, checks accelerating held arrows and release/hidden
cancellation, verifies native Media tab dimensions and top-edge notch attachment,
and changes dashboard visibility/width. It also exercises notch play/pause, the
220 ms icon morph, native surface color, oversized-width clamping and alarm Stop
from both the Timer page and notch. It does not
install anything or restart the user's shell.

Silent fake desktop commands test real helper alarm repetition, notification Stop
actions, dashboard Stop commands, persisted alarm recovery/replacement, stale
action rejection, notification-server ID ownership, disabled preferences, child cleanup and the generated PCM bell.
No test sends production notifications or plays production audio.

Hardware acceptance after a separately reviewed install:

- Mouse wheel over each unit changes one step per notch; fractional touchpad
  movement accumulates smoothly. Reversing direction and switching units have
  no residual jumps. Dashboard flicking never wins over the editor. Keyboard
  entry accepts valid ranges and Escape cancels.
- Click each arrow: one step. Hold it: repeat speeds up gradually. Release, move
  outside, switch tabs or close the dashboard: adjustment stops. Running digits
  stay protected; the pencil selects the next configured duration.
- Rapid Start/Pause/Resume/Reset keeps one countdown, Reset rolls digits and its
  arrow smoothly, grains freeze on Pause and resume at the same phase. Rotation
  begins sand after the turn; chamber fill follows elapsed time; completion pulses.
- Closing/opening dashboard never changes the deadline. Every monitor notch
  matches its dashboard's last actual width, respects scale, hides immediately on
  dashboard open and opens the correct Timer tab on click without keyboard focus.
- Change active theme, dashboard tab visibility, bar placement and monitor scale;
  disconnect/reconnect a screen; use narrow screens. Check readability and geometry.
- Disable animations: digit/button/hourglass/notch transitions become immediate,
  particles stop. Sound/notification off are silent. Verify actual completion sound
  and notification with the desktop's selected sound theme and notification daemon.
- Complete a short timer with sound/notifications on: the bell repeats until
  Stop in the notification or Timer tab. Closing the popup alone leaves it ringing.
  Restart the shell while ringing, then Stop: no duplicate active notification
  or overlapping players. The notch button pauses/resumes without opening the
  dashboard; its body still opens Timer. Test narrow outputs and differing scales.
- Suspend through an expiry, restart shell midway, and reload after completion:
  restored remaining time/pending alarm and one active notification/player.
- Review update/rollback/uninstall host diffs and verify Cast Audio and TouchDeck.

These physical-input, sound-delivery and real-monitor checks must be reported
separately from automated virtual-compositor coverage; no development task claims
to have performed a production deployment.

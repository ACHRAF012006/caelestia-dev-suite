# Developer testing

From the manager checkout, run `.venv/bin/pytest -q`. Notes/task/domain/storage
coverage lives in `tests/test_notes_tasks.py`; generic host lifecycle coverage in
`tests/test_dashboard_integration.py`. Tests use temporary XDG locations, pinned
host fixtures and a fake Runtime. Never point lifecycle tests at your real XDG
roots. No automated test invokes production shell reload.

Run `.venv/bin/python scripts/dashboard_qml_probe.py --screenshot /tmp/notes.png`
for real QML against a **copied** installed shell, private D-Bus/XDG directories,
and two virtual KWin outputs at fractional scale 1.25. Requires Quickshell, the
installed Caelestia Qt modules, KWin and dbus-run-session. The probe loads a second
synthetic dashboard component and Animated Timer, then tests native ordering,
shared data, inline editing, search, capture, subtasks, task filters, preferences,
responsive stacking and notch routing. It starts from a frozen v1 document,
types into editors with QtTest key events, exercises deletion, exact tag filters,
completion/undo and row delay, checks retained search rows and reused grid cells,
tests 130% font scaling and global/component reduced motion, then launches a
second shell process against the same temporary data to compare its snapshot.
The screenshot option writes wide and `-narrow.png` previews with the current
shell colour scheme (only colour data is copied, never personal notes). Virtual compositor warnings about absent
PipeWire/desktop services are expected; component QML errors fail the probe.

Manual acceptance after a separately reviewed installation: try keyboard focus
with your shell settings, narrow logical screens, rapid capture/completion,
long text and multilingual input, date boundaries, disabled native tabs, Nexus
plugin disabling, and a shell restart with pending edits. Save a personal-data
backup first. Automated virtual-output testing establishes only its tested
configuration, not every hardware/DPI/input combination.

The probe requires the QtTest QML module. Its previews render the exact component
on an opaque themed test surface so translucent chips have the same contrast as
in a native drawer. The two-monitor native adapter test separately loads the real
top navigation; the component does not modify that navigation. Screenshots show
synthetic records. Narrow previews show the viewport; scroll to reach remaining
widgets. No production shell process or data directory is modified.

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
responsive stacking and notch routing. Virtual compositor warnings about absent
PipeWire/desktop services are expected; component QML errors fail the probe.

Manual acceptance after a separately reviewed installation: try keyboard focus
with your shell settings, narrow logical screens, rapid capture/completion,
long text and multilingual input, date boundaries, disabled native tabs, Nexus
plugin disabling, and a shell restart with pending edits. Save a personal-data
backup first. Automated virtual-output testing establishes only its tested
configuration, not every hardware/DPI/input combination.

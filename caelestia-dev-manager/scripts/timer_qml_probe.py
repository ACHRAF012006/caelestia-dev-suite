#!/usr/bin/env python3
"""Compile/run timer QML against copied installed Caelestia, in temporary XDG roots.

No live host writes, service restarts, notifications, or Git operations.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import time
import argparse

ROOT = Path(__file__).resolve().parents[1]
HOST = Path.home() / '.config/quickshell/caelestia'
PROBE = r'''
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import "timer" as T
import "timer/Wheel.js" as Wheel
import qs.services
import qs.components
import Caelestia
import Caelestia.Config
import qs.modules.dashboard as Dashboard

ShellRoot {
    id: root
    property var controller: null
    signal toggleNotch()
    property int stage: 0
    property int waits: 0
    property real pausedPhase: 0
    property int heldValue: 0
    property int initialRepeats: 0
    function check(ok, message) { if (!ok) { console.error("PROBE FAILED: " + message); Qt.exit(1); } }
    Component.onCompleted: {
        const component = Qt.createComponent("timer/main.qml");
        check(component.status === Component.Ready, component.errorString());
        controller = component.createObject(root);
        PluginLoader.pluginInstances = {"animated-timer": controller};
        PluginLoader.loadedCount = 1;
        check(controller !== null, component.errorString());
        const patched = Qt.createComponent("modules/dashboard/Content.qml");
        check(patched.status === Component.Ready, patched.errorString());
        const wrapper = Qt.createComponent("modules/dashboard/Wrapper.qml");
        check(wrapper.status === Component.Ready, wrapper.errorString());
        let a = Wheel.consume(0, 120, 0); check(a.steps === 1 && a.residual === 0, "wheel notch");
        a = Wheel.consume(0, 0, 12); a = Wheel.consume(a.residual, 0, 12); a = Wheel.consume(a.residual, 0, 16);
        check(a.steps === 1, "touchpad accumulated step");
        check(Wheel.consume(0.9, -120, 0).steps === -1, "direction reversal");
    }
    PanelWindow {
        visible: true; implicitWidth: Tokens.sizes.dashboard.mediaTabWidth + 40; implicitHeight: Tokens.sizes.dashboard.mediaTabHeight + 40
        Loader {
            id: visualPage
            anchors.fill: parent; anchors.margins: 20
            active: root.controller !== null
            sourceComponent: T.TimerPage { controller: root.controller }
        }
    }
    Variants {
        model: Quickshell.screens
        Item {
            id: monitorHost
            required property ShellScreen modelData
            property var notch: null
            property var screen: modelData
            property real topMargin: 48
            property var visibilities: DrawerVisibilities { dashboard: false; overview: false }
            property var screenState: ScreenState { modelData: monitorHost.modelData }
            width: 1000; height: 850
            Dashboard.Wrapper {
                id: realDashboard
                screenState: monitorHost.screenState
                visibilities: monitorHost.visibilities
            }
            Connections {
                target: root
                function onToggleNotch() {
                    CUtils.findChild(monitorHost.notch.contentItem, "animatedTimerNotchControl").clicked();
                }
                function onStageChanged() {
                    if (root.stage === 1) {
                        monitorHost.notch = CUtils.findChild(realDashboard, "animatedTimerNotchLoader").item;
                        root.check(monitorHost.notch !== null, "host creates notch");
                        root.check(monitorHost.notch.screen === monitorHost.modelData, "screen binding");
                        root.check(monitorHost.notch.margins.top === 0, "notch touches screen top despite host bar offset");
                        root.check(monitorHost.notch.implicitWidth === Math.min(realDashboard.timerDashboardWidth, monitorHost.notch.availableWidth), "notch matches dashboard within screen");
                        realDashboard.timerDashboardWidth = 5000;
                        root.check(monitorHost.notch.implicitWidth <= monitorHost.modelData.width, "oversized dashboard cannot overflow screen");
                        realDashboard.timerDashboardWidth = 510;
                        root.check(monitorHost.notch.implicitWidth === 510, "dynamic notch width");
                        const surface = CUtils.findChild(monitorHost.notch.contentItem, "animatedTimerNotchSurface");
                        root.check(surface !== null, "native notch surface");
                        root.check(Qt.colorEqual(surface.color, Qt.alpha(GlobalConfig.appearance.pitchBlack ? "#000000" : Colours.tPalette.m3surface, GlobalConfig.appearance.pitchBlack ? 1 : Colours.transparency.enabled ? Colours.transparency.base : 1)), "dashboard surface color and transparency");
                    } else if (root.stage === 2) {
                        root.check(monitorHost.notch.wanted, "paused notch visible");
                        monitorHost.notch.host.openTimerTab();
                        root.check(monitorHost.visibilities.dashboard, "notch opens dashboard");
                        root.check(monitorHost.screenState.dashboardTab === [Config.dashboard.showDashboard, Config.dashboard.showMedia,
                            Config.dashboard.showPerformance, Config.dashboard.showWeather, Config.dashboard.showTerminal].filter(v => v).length, "actual Timer tab index");
                        root.check(!monitorHost.notch.wanted, "notch hides for open dashboard");
                    } else if (root.stage === 3) {
                        monitorHost.visibilities.dashboard = false;
                        const control = CUtils.findChild(monitorHost.notch.contentItem, "animatedTimerNotchControl");
                        root.check(control.icon === "play_arrow" && Math.abs(control.morphProgress) < 0.0001, "notch pause morph completes");
                    } else if (root.stage === 4) {
                        const control = CUtils.findChild(monitorHost.notch.contentItem, "animatedTimerNotchControl");
                        root.check(control.icon === "pause" && Math.abs(control.morphProgress - 1) < 0.0001, "notch resume morph completes");
                    } else if (root.stage === 5) {
                        root.check(!monitorHost.notch.wanted, "reset hides notch");
                    } else if (root.stage === 18) {
                        root.check(monitorHost.notch.wanted, "completed alarm retains notch");
                        CUtils.findChild(monitorHost.notch.contentItem, "animatedTimerNotchControl").clicked();
                    }
                }
            }
        }
    }
    Connections {
        target: root.controller
        function onSnapshotChanged() {
            if (root.controller.snapshot.state === "Paused" && visualPage.item)
                root.pausedPhase = CUtils.findChild(visualPage.item, "animatedTimerHourglass").phase;
        }
    }
    Timer {
        interval: 600; repeat: true; running: true
        onTriggered: {
            if (!root.controller || !root.controller.healthy) {
                if (++root.waits > 15) { console.error("PROBE FAILED: helper did not become healthy"); Qt.exit(1); }
                return;
            }
            const c = root.controller;
            if (root.stage === 0) {
                c.send({action: "preferences", values: {notification: false, sound: false}});
                c.send({action: "configure", seconds: 30}); c.send({action: "start"});
            } else if (root.stage === 1) {
                root.check(c.snapshot.state === "Running", "start");
                root.check(visualPage.item.implicitWidth === Tokens.sizes.dashboard.mediaTabWidth && visualPage.item.implicitHeight === Tokens.sizes.dashboard.mediaTabHeight, "native tab size");
                root.check(CUtils.findChild(visualPage.item, "animatedTimerHourglass").turn === 180, "start rotates hourglass");
                root.toggleNotch();
                const screenshot = Quickshell.env("TIMER_PROBE_SCREENSHOT");
                if (screenshot) visualPage.item.grabToImage(result => result.saveToFile(screenshot));
            } else if (root.stage === 2) {
                root.check(c.snapshot.state === "Paused", "pause");
                root.check(Math.abs(CUtils.findChild(visualPage.item, "animatedTimerHourglass").phase - root.pausedPhase) < 0.00001, "sand freezes on pause");
                Colours.current.m3primary = "#93b59c";
                root.toggleNotch();

            } else if (root.stage === 3) {
                root.check(c.snapshot.state === "Running", "resume");

                const reset = CUtils.findChild(visualPage.item, "animatedTimerReset");
                for (let i = 0; i < 8; i++) reset.clicked();
                root.check(reset.rotationTarget === 2880, "reset rotation target preserves every click");
                visualPage.item.editPreset({id: "", name: "Probe", seconds: 45});
            } else if (root.stage === 4) {
                root.check(c.snapshot.state === "Ready" && c.snapshot.remaining === 30, "rapid reset");
                root.check(CUtils.findChild(visualPage.item, "animatedTimerReset").iconRotation === 2880, "reset arrow accumulates exact turns");
                visualPage.item.presentationActive = false; visualPage.item.presentationActive = true;
                c.send({action: "configure", seconds: 1}); c.send({action: "start"});
            } else if (root.stage === 7) {
                root.check(c.snapshot.state === "Completed" && c.snapshot.alarm_active, "completion leaves stoppable alarm");
                CUtils.findChild(visualPage.item, "animatedTimerPrimary").clicked();
                c.send({action: "configure", seconds: 0});
            } else if (root.stage === 8) {
                root.check(!c.snapshot.alarm_active, "dashboard Stop dismisses alarm");
                visualPage.item.presentationActive = false; visualPage.item.presentationActive = true;
                CUtils.findChild(visualPage.item, "animatedTimerSecondsIncrease").beginHold();
            } else if (root.stage === 9) {
                const arrow = CUtils.findChild(visualPage.item, "animatedTimerSecondsIncrease");
                root.check(c.snapshot.configured >= 2, "held arrow repeats: " + c.snapshot.configured + ", holding " + arrow.holding + ", repeats " + arrow.repeats + ", state " + c.snapshot.state);
                root.initialRepeats = arrow.repeats;
            } else if (root.stage === 10) {
                const arrow = CUtils.findChild(visualPage.item, "animatedTimerSecondsIncrease");
                root.check(arrow.repeats - root.initialRepeats > root.initialRepeats, "held arrow accelerates");
                arrow.endHold();
            } else if (root.stage === 11) {
                root.heldValue = c.snapshot.configured;
            } else if (root.stage === 12) {
                root.check(c.snapshot.configured === root.heldValue, "release stops changes");
                const arrow = CUtils.findChild(visualPage.item, "animatedTimerSecondsDecrease");
                arrow.beginHold(); arrow.endHold();
            } else if (root.stage === 13) {
                root.check(c.snapshot.configured === root.heldValue - 1, "down arrow changes one unit");
                const arrow = CUtils.findChild(visualPage.item, "animatedTimerSecondsIncrease");
                arrow.beginHold(); visualPage.item.presentationActive = false;
                root.check(!arrow.holding, "closing presentation cancels hold");
            } else if (root.stage === 14) {
                root.check(c.snapshot.configured === root.heldValue, "hidden timer does not keep adjusting");
                visualPage.item.presentationActive = true;
                c.send({action: "start"});
            } else if (root.stage === 15) {
                const arrow = CUtils.findChild(visualPage.item, "animatedTimerSecondsIncrease");
                root.check(!arrow.enabled, "running countdown cannot be edited accidentally");
                arrow.beginHold(); root.check(!arrow.holding, "disabled arrow cannot repeat");
                c.send({action: "cancel"}); c.send({action: "configure", seconds: 1}); c.send({action: "start"});
            } else if (root.stage === 17) {
                root.check(c.snapshot.alarm_active, "second alarm");
            } else if (root.stage === 19) {
                root.check(!c.snapshot.alarm_active && c.snapshot.state === "Completed", "notch Stop dismisses alarm");
                console.log("TIMER QML PROBE PASSED"); Qt.quit();
            }
            root.stage++;
        }
    }
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot', type=Path, help='Save the isolated native timer page to this PNG')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    from backend.timer_integration import panel_sources, FILES
    with tempfile.TemporaryDirectory(prefix='caelestia-timer-probe-') as temporary:
        temp = Path(temporary)
        copied = temp / 'shell'
        shutil.copytree(HOST, copied, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        shutil.copytree(ROOT / 'plugins/animated-timer', copied / 'timer', ignore=shutil.ignore_patterns('__pycache__'))
        for name, text in panel_sources({n: (ROOT / "tests/fixtures/caelestia-kde" / n).read_text() for n in FILES}).items():
            (copied / name).write_text(text)
        (copied / 'Probe.qml').write_text(PROBE)
        env = dict(os.environ, QT_QPA_PLATFORM='wayland', QSG_RHI_BACKEND='software',
                   QT_QUICK_BACKEND='software', QS_DISABLE_CRASH_HANDLER='1',
                   QML2_IMPORT_PATH=str(Path.home() / '.local/lib/qt6/qml') + ':' + str(copied))
        for key, directory in [('XDG_CONFIG_HOME','config'), ('XDG_DATA_HOME','data'), ('XDG_STATE_HOME','state'), ('XDG_CACHE_HOME','cache'), ('XDG_RUNTIME_DIR','runtime')]:
            p = temp / directory; p.mkdir(mode=0o700); env[key] = str(p)
        if args.screenshot:
            env['TIMER_PROBE_SCREENSHOT'] = str(args.screenshot.resolve())
        env['WAYLAND_DISPLAY'] = 'timer-test'
        env.pop('DISPLAY', None)
        # The virtual compositor gets its own D-Bus session and runtime socket.
        with open(temp / 'kwin.log', 'w') as log:
            compositor = subprocess.Popen(['dbus-run-session', '--', 'kwin_wayland', '--virtual',
                '--no-lockscreen', '--no-global-shortcuts', '--no-kactivities', '--output-count', '2',
                '--width', '1440', '--height', '900', '--scale', '1.25', '--socket', 'timer-test'],
                env=env, stdout=log, stderr=log, start_new_session=True)
            try:
                for _ in range(100):
                    if (temp / 'runtime/timer-test').exists(): break
                    if compositor.poll() is not None: raise RuntimeError((temp / 'kwin.log').read_text())
                    time.sleep(0.05)
                # Quickshell services must not contact the production session bus.
                process = subprocess.Popen(['dbus-run-session', '--', 'quickshell', '--no-color', '--path',
                    str(copied / 'Probe.qml')], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                try:
                    stdout, stderr = process.communicate(timeout=24)
                except subprocess.TimeoutExpired:
                    import signal
                    os.killpg(process.pid, signal.SIGTERM)
                    stdout, stderr = process.communicate(timeout=5)
                result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
            finally:
                import signal
                os.killpg(compositor.pid, signal.SIGTERM)
                compositor.wait(timeout=5)
        output = result.stdout + result.stderr
        # Keep routine output concise; retain full diagnostics on failure.
        print(output if result.returncode != 0 or 'PROBE FAILED' in output else '\n'.join(line for line in output.splitlines() if 'TIMER QML PROBE' in line or '@timer/' in line or 'TypeError' in line or 'ReferenceError' in line))
        errors = ('TypeError:', 'ReferenceError:', 'Cannot assign', 'Error loading', 'is not a type', 'Binding loop', 'PROBE FAILED')
        return 0 if result.returncode == 0 and 'TIMER QML PROBE PASSED' in output and not any(e in output for e in errors) else 1

if __name__ == '__main__':
    raise SystemExit(main())

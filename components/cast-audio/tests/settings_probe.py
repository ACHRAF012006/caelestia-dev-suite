"""Compile and exercise redesigned Settings in an isolated fake backend."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main():
    component = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='cast-settings-probe-') as temporary:
        base = Path(temporary)
        ui = base / 'component'
        shutil.copytree(component, ui, ignore=shutil.ignore_patterns('__pycache__', '_venv'))
        runtime = base / 'runtime'
        runtime.mkdir(mode=0o700)
        fake = base / 'fake.py'
        fake.write_text('''import json, sys
settings = {"source": "default", "format": "hls", "latency": "fast", "bitrate": 192, "remember": True}
for line in sys.stdin:
    request = json.loads(line)
    if request['action'] == 'settings': settings.update(request['values'])
    print(json.dumps({'ok': True, 'action': request['action'], 'snapshot': {'state': 'Off', 'message': 'Ready', 'settings': settings, 'sources': [{'id': 'app:19:player', 'kind': 'application', 'name': 'Player', 'detail': 'Music'}]}}), flush=True)
''')
        path = ui / 'SettingsApp.qml'
        qml = path.read_text()
        qml = re.sub(r'command: \["python3".*?"settings_client.py"\]',
                     'command: ["python3", "-B", ' + json.dumps(str(fake)) + ']', qml)
        qml = qml.replace('id: pages', 'id: pages; objectName: "castSettingsTabs"')
        qml = qml.replace('id: window', 'id: window; objectName: "castSettingsWindow"')
        check = '''
    function find(item, name) {
        if (item.objectName === name) return item;
        for (let child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
    }
    property int phase: 0
    Timer {
        interval: 300; running: true; repeat: true
        onTriggered: {
            if (!root.loaded) return;
            const tabs = root.find(window.contentItem, "castSettingsTabs");
            const app = root.find(window.contentItem, "castAudioApp");
            if (!tabs || !app) { console.error("SETTINGS_FAIL missing controls"); Qt.quit(); return; }
            if (root.phase === 0) {
                app.clicked();
                if (root.sourceChoice !== "app:19:player" || !root.dirty) { console.error("SETTINGS_FAIL app selection"); Qt.quit(); return; }
                root.save();
            } else if (root.phase === 1) {
                if (root.dirty || root.snapshot.settings.source !== "app:19:player") { console.error("SETTINGS_FAIL save"); Qt.quit(); return; }
                if (Quickshell.env("CAST_SETTINGS_SCREENSHOT")) window.contentItem.grabToImage(result => result.saveToFile(Quickshell.env("CAST_SETTINGS_SCREENSHOT")));
                tabs.currentIndex = 1;
            } else if (root.phase === 2) tabs.currentIndex = 2;
            else if (root.phase === 3) tabs.currentIndex = 3;
            else { console.log("SETTINGS_PASS"); Qt.quit(); }
            root.phase++;
        }
    }
    Timer { interval: 6000; running: true; onTriggered: { console.error("SETTINGS_FAIL timeout"); Qt.quit(); } }
'''
        qml = qml.rsplit('}', 1)[0] + check + '\n}\n'
        path.write_text(qml)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime),
                   XDG_CONFIG_HOME=str(base / 'config'), XDG_STATE_HOME=str(base / 'state'))
        result = subprocess.run(['quickshell', '--path', str(path), '--no-color'],
                                env=env, capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        if result.returncode or 'SETTINGS_PASS' not in output or 'SETTINGS_FAIL' in output or 'ReferenceError' in output:
            print(output)
            raise SystemExit('Settings probe failed')
        print('PASS: redesigned Settings tabs, app selection, save and native QML compilation.')


if __name__ == '__main__':
    main()

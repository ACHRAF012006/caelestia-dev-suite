"""Check active scheme loading/reloading and Qt fallback in an isolated process."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

QML = '''import QtQuick
import Quickshell
import COMPONENT as CastUI
ShellRoot {
    property CastUI.Theme theme: CastUI.Theme {}
    property int phase: 0
    Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
            if (parent.phase === 0 && parent.theme.accent.toString() === "#123456") {
                if (parent.theme.selectedText.toString() !== "#abcdef") { console.error("THEME_FAIL contrast"); Qt.quit(); return; }
                console.log("THEME_INITIAL"); parent.phase = 1;
            } else if (parent.phase === 1 && parent.theme.accent.toString() === "#654321") {
                console.log("THEME_RELOADED"); parent.phase = 2;
            } else if (parent.phase === 2 && Object.keys(parent.theme.scheme).length === 0) {
                if (parent.theme.accent.toString() !== parent.theme.system.highlight.toString()) console.error("THEME_FAIL fallback");
                else console.log("THEME_PASS");
                Qt.quit();
            }
        }
    }
    Timer { interval: 5000; running: true; onTriggered: { console.error("THEME_FAIL timeout"); Qt.quit(); } }
}
'''

def main():
    component = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='cast-theme-probe-') as temporary:
        base = Path(temporary)
        state = base/'state/caelestia'; state.mkdir(parents=True)
        scheme = state/'scheme.json'
        scheme.write_text(json.dumps({'colours':{'primary':'123456','onSecondaryContainer':'abcdef'}}))
        runtime = base/'runtime'; runtime.mkdir(mode=0o700)
        qml = base/'shell.qml'; qml.write_text(QML.replace('COMPONENT', json.dumps(component.as_uri())))
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_STATE_HOME=str(base/'state'), XDG_RUNTIME_DIR=str(runtime))
        process = subprocess.Popen(['quickshell','--path',str(qml),'--no-color'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        output = []
        try:
            for line in process.stdout:
                output.append(line)
                if 'THEME_INITIAL' in line:
                    scheme.write_text(json.dumps({'colours':{'primary':'654321','onSecondaryContainer':'fedcba'}}))
                elif 'THEME_RELOADED' in line:
                    scheme.write_text('{invalid')
            process.wait(timeout=1)
        finally:
            if process.poll() is None: process.kill(); process.wait()
        output = ''.join(output)
        if process.returncode or 'THEME_PASS' not in output or 'THEME_FAIL' in output:
            print(output); raise SystemExit('Cast palette probe failed')
        print('PASS: active scheme colors, text contrast, live reload and Qt palette fallback.')

if __name__ == '__main__':
    main()

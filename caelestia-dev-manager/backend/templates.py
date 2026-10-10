import json
from backend.schemas import CURRENT_SCHEMA

TEMPLATES = {"Empty Caelestia Plugin": ("caelestia-plugin", "quickshell"),
             "Qt/QML Application": ("standalone-app", "qml"),
             "Python + PySide6 Application": ("standalone-app", "python-pyside6"),
             "QML Component": ("qml-component", "quickshell"),
             "Shell Script": ("script", "shell"), "Python Script": ("script", "python"),
             "systemd User Service": ("user-service", "python"), "Shell User Service": ("user-service", "shell"),
             "Caelestia Dashboard Page": ("caelestia-plugin", "quickshell"), "Empty Project": ("standalone-app", "none")}

def template(name, id, choice, description=""):
    type, runtime = TEMPLATES[choice]
    m = {"schema_version": CURRENT_SCHEMA, "id": id, "name": name, "version": "0.1.0", "description": description,
         "type": type, "runtime": runtime}
    files = {"README.md": f"# {name}\n\n{description}\n\nReview and validate before installing. This component runs independently of Dev Manager.\n"}
    if runtime == "qml":
        m["entrypoint"] = "ui/Main.qml"
        files[m["entrypoint"]] = 'import QtQuick\nimport QtQuick.Controls\n\nApplicationWindow {\n    visible: true\n    width: 480; height: 320\n    title: ' + json.dumps(name) + '\n    Label { anchors.centerIn: parent; text: "Your application" }\n}\n'
    elif runtime == "python-pyside6":
        m["entrypoint"] = "src/main.py"
        m["dependencies"] = {"python": ["PySide6>=6.8"]}
        files[m["entrypoint"]] = 'from PySide6.QtWidgets import QApplication, QLabel\n\napp = QApplication([])\nwindow = QLabel("Your application")\nwindow.setWindowTitle(' + repr(name) + ')\nwindow.resize(480, 320)\nwindow.show()\napp.exec()\n'
    elif runtime == "python":
        m["entrypoint"] = "src/main.py"
        files[m["entrypoint"]] = 'print("Hello from your independent command")\n'
        if type == "user-service":
            m["service"] = {"restart": "on-failure"}
            files[m["entrypoint"]] = 'import time\n\nprint("Service started", flush=True)\nwhile True:\n    time.sleep(30)\n'
    elif runtime == "shell":
        m["entrypoint"] = "src/main.sh"
        files[m["entrypoint"]] = '#!/bin/bash\nset -euo pipefail\nprintf "%s\\n" "Hello from your independent command"\n'
    elif runtime == "quickshell":
        m["entrypoint"] = "main.qml"
        files["main.qml"] = 'import QtQuick\nimport Quickshell\n\n// PluginLoader creates this object inside Caelestia, independently of Dev Manager.\nQtObject {\n    Component.onCompleted: console.log("Managed plugin loaded")\n}\n'
        files["metadata.json"] = json.dumps({"id": id, "name": name, "version": m["version"], "description": description,
                                              "type": "quickshell", "ui": "main.qml", "restart": True}, indent=2) + "\n"
        if type == "qml-component": m["integration"] = {"target": "caelestia-plugin"}
    if choice == 'Shell User Service':
        m['service'] = {'restart': 'on-failure'}
        files[m['entrypoint']] = '#!/bin/bash\nset -euo pipefail\nwhile true; do sleep 30; done\n'
    if choice == 'Caelestia Dashboard Page':
        from backend.compatibility import COMMIT
        m['compatibility'] = {'manager_min_version': '0.8.0', 'caelestia_commit': COMMIT}
        m['integration'] = {'target': 'caelestia-dashboard', 'dashboard': {'id': id, 'title': name[:40], 'icon': 'widgets', 'component': 'DashboardPage.qml', 'order': 50}}
        files['DashboardPage.qml'] = 'import QtQuick\nimport QtQuick.Layouts\nimport QtQuick.Controls\n\nItem {\n    required property var controller\n    property bool presentationActive: true\n    implicitWidth: 480; implicitHeight: 320\n    Label { anchors.centerIn: parent; text: ' + json.dumps(name) + ' }\n}\n'
    files = {"manifest.json": json.dumps(m, indent=2) + "\n", **files}
    return m, files

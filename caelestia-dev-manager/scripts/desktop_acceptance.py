"""Explicit desktop acceptance: unique harmless app/service, complete cleanup.

Run with the manager venv Python and a built catalogue-probe executable.
Separate child processes exercise real Qt paste/buttons and manager process exit.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from backend.paths import Paths, inside, no_symlinks
from backend.manager import Manager
from backend.codex.package import encode

def wait_for(fn, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = fn()
        if result: return result
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for desktop state")

def ui_stage(args):
    from PySide6.QtWidgets import QApplication, QPushButton, QDialog
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from app.main import Window
    app = QApplication([]); app.setApplicationName("Caelestia Dev Manager"); app.setDesktopFileName("caelestia-dev-manager")
    from app.main import STYLE
    app.setStyle("Fusion"); app.setStyleSheet(STYLE)
    manager = Manager(Paths.default(args.project)); window = Window(manager); window.show(); app.processEvents(); QTest.qWait(400)
    def click(text):
        matches = [b for b in window.findChildren(QPushButton) if b.text() == text and b.isVisible()]
        assert matches, text
        QTest.mouseClick(matches[0], Qt.LeftButton); app.processEvents()
    def auto_accept():
        modal = app.activeModalWidget()
        assert isinstance(modal, QDialog), "Expected installation/action preview dialog"
        modal.accept()
    if args.stage == "create":
        m = {"id": args.id, "name": "CDM Acceptance Dummy", "version": "0.1.0", "description": "Temporary desktop lifecycle check",
             "type": "standalone-app", "runtime": "qml", "entrypoint": "ui/Main.qml"}
        files = {"manifest.json": json.dumps(m, indent=2), "README.md": "Temporary acceptance source\n",
                 "ui/Main.qml": 'import QtQuick\nimport QtQuick.Controls\nApplicationWindow { visible: true; width: 380; height: 160; title: "CDM Acceptance Dummy"; Label { anchors.centerIn: parent; text: "Independent test application" } }\n'}
        window.nav.setCurrentRow(2)
        app.clipboard().setText(encode(files, m)); window.paste.setFocus(); QTest.keyClick(window.paste, Qt.Key_V, Qt.ControlModifier)
        click("Analyze Code")
        assert "ui/Main.qml" in window.file_preview.toPlainText()
        assert not manager.paths.source(args.id).exists()
        click("Create Component")
        actual = manager.read_source(args.id)
        assert set(actual) == set(files)
        assert actual["ui/Main.qml"].strip() == files["ui/Main.qml"].strip()
        QTimer.singleShot(300, auto_accept); click("Install")
        assert manager.installed(args.id)["installed"]
        click("Launch / Start"); QTest.qWait(1000)
        assert manager.runtime.processes(manager.installed(args.id))
        window.nav.setCurrentRow(4); window.request.setPlainText("Build an independent test utility")
        click("Copy Full Codex Prompt")
        assert "CAELESTIA_DEV_PACKAGE" in app.clipboard().text() and "independent test utility" in app.clipboard().text()
        window.nav.setCurrentRow(0); window.grab().save(str(args.output / "dashboard.png"))
        window.nav.setCurrentRow(2); window.grab().save(str(args.output / "import.png"))
        print(json.dumps({"source_files": list(actual), "owned_files": manager.registry.files(args.id), "pids": manager.runtime.processes(manager.installed(args.id)), "clipboard_verified": True}))
    else:
        window.nav.setCurrentRow(1); window.select_id(args.id)
        assert manager.installed(args.id)["installed"]
        assert "installed_version" in window.component_info.toPlainText()
        manager.save_file(args.id, "README.md", "Edited development source\n")
        assert manager.status(manager.installed(args.id))["source_modified"]
        installed_readme = manager.paths.root(manager.installed(args.id)["installed_manifest"]) / "README.md"
        assert installed_readme.read_text() != "Edited development source\n"
        owned = manager.registry.files(args.id)
        extra = manager.paths.root(manager.installed(args.id)["installed_manifest"]) / "unowned-keep.txt"
        extra.write_text("This file must survive uninstall")
        QTimer.singleShot(300, auto_accept); click("Disable")
        assert not manager.installed(args.id)["enabled"]
        QTimer.singleShot(300, auto_accept); click("Uninstall")
        assert all(not Path(f["path"]).exists() for f in owned)
        assert manager.paths.source(args.id).exists() and extra.exists()
        extra.unlink(); extra.parent.rmdir()
        print(json.dumps({"reopen_installed_verified": True, "source_modified_verified": True, "owned_only_removed": True, "source_preserved": True}))
    window.close(); app.processEvents()

def clean_component(manager, id):
    record = manager.registry.get(id)
    if not record: return
    if record.get("installed"):
        manager.uninstall(id)
    if manager.paths.source(id).exists(): manager.delete_source(id, id)
    for backup in manager.backups.list():
        if backup["component_id"] == id:
            root = inside(manager.paths.backups, manager.paths.backups / backup["backup_id"])
            for f in root.iterdir():
                no_symlinks(f)
                if not f.is_file(): raise RuntimeError("Unexpected test backup contents")
                f.unlink()
            root.rmdir()
    with manager.registry.db:
        assert not manager.registry.files(id)
        manager.registry.db.execute("DELETE FROM events WHERE component=?", (id,))
        manager.registry.db.execute("DELETE FROM components WHERE id=?", (id,))
    log = no_symlinks(manager.paths.state / "caelestia-dev-manager/logs" / (id + ".log"))
    if log.exists(): log.unlink()

def main(args):
    suffix = uuid.uuid4().hex[:10]
    id = "cdm-acceptance-" + suffix
    service_id = "cdm-service-check-" + suffix
    output = args.output.absolute(); output.mkdir(parents=True, exist_ok=True)
    manager = Manager(Paths.default(args.project)); initial = {r["id"] for r in manager.registry.all()}
    report = {"app_id": id, "service_id": service_id, "environment": manager.environment}
    try:
        common = [sys.executable, str(Path(__file__).resolve()), "--project", str(args.project), "--output", str(output), "--id", id]
        # Each stage process exits; the application must outlive the first manager process.
        result = subprocess.run([*common, "--stage", "create"], capture_output=True, text=True, timeout=90)
        (output / "stage-create.log").write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        record = manager.installed(id)
        assert wait_for(lambda: manager.runtime.processes(record))
        report["survived_manager_process_exit"] = True
        result = subprocess.run([str(args.probe), id], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
        report["kde_catalogue_entry"] = result.stdout.strip()
        initial_pids = set(manager.runtime.processes(record))
        result = subprocess.run([str(args.probe), id, "--launch"], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
        wait_for(lambda: set(manager.runtime.processes(record)) - initial_pids)
        report["launched_through_kde_without_manager"] = True
        result = subprocess.run([*common, "--stage", "remove"], capture_output=True, text=True, timeout=90)
        (output / "stage-remove.log").write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        report["ui_import_install_reopen_disable_uninstall"] = True
        from backend.templates import template
        m, files = template("CDM Service Acceptance", service_id, "systemd User Service")
        manager.create(files); manager.install(service_id)
        manager.set_enabled(service_id, True)
        assert wait_for(lambda: manager.status(manager.installed(service_id))["running"])
        assert manager.runtime.systemctl("is-enabled", manager.runtime.unit(service_id)) == "enabled"
        manager.runtime.logs(manager.installed(service_id))
        manager.runtime.stop(manager.installed(service_id))
        assert manager.runtime.systemctl("is-active", manager.runtime.unit(service_id)) != "active"
        manager.set_enabled(service_id, False); owned = manager.registry.files(service_id); manager.uninstall(service_id)
        assert all(not Path(f["path"]).exists() for f in owned) and manager.paths.source(service_id).exists()
        report["real_user_service_lifecycle"] = True
        report["passed"] = True
    finally:
        clean_component(manager, id); clean_component(manager, service_id)
        manager.runtime.refresh_desktop()
        assert {r["id"] for r in manager.registry.all()} == initial
        report["temporary_components_cleaned"] = True
        (output / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("workspace/acceptance"))
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--stage", choices=["create", "remove"])
    parser.add_argument("--id")
    args = parser.parse_args()
    if args.stage: ui_stage(args)
    elif not args.probe: parser.error("--probe is required")
    else: main(args)

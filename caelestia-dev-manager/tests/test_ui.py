import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from app.main import Window
from backend.codex.package import encode

def test_paste_create_editor_copy_and_reopen(manager, app_files):
    app = QApplication.instance() or QApplication([])
    window = Window(manager); window.show(); app.processEvents()
    m, files = app_files
    window.nav.setCurrentRow(2)
    window.paste.setPlainText(encode(files, m))
    window.analyze()
    assert "src/main.py" in window.file_preview.toPlainText()
    assert "CREATE SOURCE ONLY" in window.destination_preview.toPlainText()
    assert not manager.paths.source(m["id"]).exists()
    window.create_import()
    assert manager.paths.source(m["id"]).exists() and not (manager.paths.bin / m["id"]).exists()
    # Same actual component action and installation preview path; auto-accept the test-owned plan.
    window.confirm = lambda *args: True
    window.install_selected()
    assert manager.registry.get(m["id"])["installed"]
    window.edit_selected(); window.code_editor.setPlainText('print("source edit")\n'); window.save_editor()
    assert manager.status(manager.registry.get(m["id"]))["source_modified"]
    window.request.setPlainText("Build a clipboard application"); window.copy_context()
    assert "Build a clipboard application" in app.clipboard().text()
    assert "CAELESTIA_DEV_PACKAGE" in app.clipboard().text()
    window.close(); app.processEvents()
    reopened = Window(manager); reopened.show(); app.processEvents()
    assert "installed_version" in reopened.component_info.toPlainText()
    assert manager.registry.get(m["id"])["installed"]
    reopened.confirm = lambda *args: True; reopened.uninstall_selected()
    assert manager.paths.source(m["id"]).exists()
    assert not (manager.paths.bin / m["id"]).exists()
    reopened.close()

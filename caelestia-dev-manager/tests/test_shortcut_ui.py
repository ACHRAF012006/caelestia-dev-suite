import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QLineEdit, QPushButton
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QPoint
from app.main import Window
from backend.codex import context
from backend.codex.package import encode
from backend.desktop import shortcut_filename
from backend.paths import atomic_write
from backend.templates import template

@pytest.fixture
def window(manager):
    application = QApplication.instance() or QApplication([])
    atomic_write(manager.paths.config / "user-dirs.dirs", b'XDG_DESKTOP_DIR="$HOME/Bureau test"\n')
    view = Window(manager); view.show(); application.processEvents()
    yield view
    view.close(); application.processEvents()

def paste(window, files, m):
    window.nav.setCurrentRow(2)
    window.paste.setPlainText(encode(files, m)); window.analyze()
    QApplication.processEvents()

def test_import_checkbox_and_manifest_preference(window, manager, app_files):
    m, files = app_files; paste(window, files, m)
    assert window.import_shortcut.isEnabled() and not window.import_shortcut.isChecked()
    QTest.mouseClick(window.import_shortcut, Qt.LeftButton, pos=QPoint(8, window.import_shortcut.height() // 2))
    window.analyze()
    assert json.loads(window.manifest_preview.toPlainText())["desktop"]["createShortcut"] is True
    assert "Bureau test" in window.destination_preview.toPlainText()
    window.create_import()
    assert json.loads(manager.read_source(m["id"])["manifest.json"])["desktop"]["createShortcut"] is True
    assert not manager.paths.bin.joinpath(m["id"]).exists()
    assert not manager.paths.home.joinpath("Bureau test").exists()

def test_install_checkbox_then_details_create_remove(window, manager, app_files):
    m, files = app_files; manager.create(files); window.refresh(); window.select_id(m["id"])
    def accept_install(title, text, label, options):
        assert options.checkbox.isEnabled() and not options.checkbox.isChecked()
        options.checkbox.setChecked(True)
        assert "Bureau test" in options.preview_text
        return True
    window.confirm = accept_install; window.install_selected()
    assert manager.has_desktop_shortcut(m["id"])
    assert window.actions["shortcut"].text() == "Remove Desktop Shortcut"
    assert window.shortcut_state.text() == "Desktop Shortcut: Created"
    window.confirm = lambda *args: True; window.toggle_desktop_shortcut()
    assert not manager.has_desktop_shortcut(m["id"])
    assert window.shortcut_state.text() == "Desktop Shortcut: Not Created"
    window.toggle_desktop_shortcut()
    assert manager.has_desktop_shortcut(m["id"])
    window.request.setPlainText("Build a utility with an optional desktop icon"); window.copy_context()
    prompt = QApplication.clipboard().text()
    assert "desktop.createShortcut=true (default false)" in prompt
    assert '"desktop_shortcut_created": true' in prompt and "Bureau test" in prompt
    window.uninstall_selected()
    assert manager.paths.source(m["id"]).is_dir()

def test_service_controls_disabled(window, manager):
    m, files = template("Background Test", "background-test", "systemd User Service")
    headers_only = {p: text for p, text in files.items() if p != "manifest.json"}
    paste(window, headers_only, m)
    assert window.import_type.currentText() == "user-service"
    assert not window.import_shortcut.isEnabled()
    paste(window, files, m)
    assert not window.import_shortcut.isEnabled() and not window.import_shortcut.isChecked()
    window.create_import()
    def accept_install(title, text, label, options):
        assert not options.checkbox.isEnabled() and not options.checkbox.isChecked()
        return True
    window.confirm = accept_install; window.install_selected()
    assert not window.actions["shortcut"].isEnabled()

def test_install_conflict_can_choose_alternate(window, manager, app_files):
    m, files = app_files; manager.create(files); window.refresh(); window.select_id(m["id"])
    directory = manager.paths.home / "Bureau test"; directory.mkdir(parents=True)
    unrelated = directory / shortcut_filename(m); unrelated.write_text("preserve me")
    def accept_install(title, text, label, options):
        options.checkbox.setChecked(True)
        assert options.plan is None and "unrelated desktop file" in options.preview_text
        next(b for b in options.findChildren(QPushButton) if b.text() == "Use alternate safe filename").click()
        assert options.plan is not None and options.filename != unrelated.name
        return True
    window.confirm = accept_install; window.install_selected()
    assert manager.has_desktop_shortcut(m["id"]) and unrelated.read_text() == "preserve me"
    assert manager.installed(m["id"])["desktop_shortcut"]["filename"] != unrelated.name

def test_new_component_wizard_preference(window, monkeypatch):
    def accept(dialog):
        fields = dialog.findChildren(QLineEdit)
        fields[0].setText("Wizard Test"); fields[1].setText("wizard-test")
        choice = dialog.findChild(QComboBox); choice.setCurrentText("systemd User Service")
        checkbox = dialog.findChild(QCheckBox); assert not checkbox.isEnabled()
        choice.setCurrentText("Python Script"); assert checkbox.isEnabled()
        checkbox.setChecked(True)
        return QDialog.Accepted
    monkeypatch.setattr(QDialog, "exec", accept)
    window.new_component()
    assert json.loads(window.manifest_preview.toPlainText())["desktop"]["createShortcut"] is True
    assert window.import_shortcut.isChecked()

def test_context_handles_disabled_or_invalid_desktop(manager):
    assert '"desktop_shortcuts": null' in context(manager, "request")
    atomic_write(manager.paths.config / "user-dirs.dirs", b'XDG_DESKTOP_DIR="$(bad-command)"\n')
    assert "Unavailable:" in context(manager, "request")

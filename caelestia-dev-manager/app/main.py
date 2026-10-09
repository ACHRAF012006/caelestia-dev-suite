import argparse
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time

from PySide6.QtCore import Qt, QTimer, QUrl, Slot, QSize
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from app.editor import CodeEditor
from app.store import StorePage
from app.review import ReviewDialog
from app.navigation import AnimatedStack, AnimatedNavigation
from app.branding import application_icon
from app.component_icons import ComponentIcons
from app.inspection import Inspection
from app import preferences
from backend.paths import VERSION, Paths, SafetyError, no_symlinks, relative
from backend.manager import Manager
from backend import host_integration
from backend.validators import TYPES, RUNTIMES, manifest_parse, validate
from backend.codex import context
from backend.codex.package import parse, detect, encode
from backend.templates import TEMPLATES, template
from backend.desktop import SHORTCUT_TYPES, ShortcutConflict, desktop_directory, shortcut_filename
from backend.dependencies import DependencyError
from backend.store import Store

STYLE = """
QWidget { background: #171b23; color: #e0e5ef; font-size: 13px; }
QMainWindow { background: #171b23; }
QLabel#title { font-size: 27px; font-weight: 600; }
QLabel#subtitle { color: #99a5b9; font-size: 13px; }
QLabel#metric { font-size: 30px; font-weight: 600; }
QFrame#card { background: #202631; border: 1px solid #303a48; border-radius: 10px; }
QFrame#card QLabel { background: transparent; }
QPushButton { background: #2c3545; border: 1px solid #3b475b; border-radius: 6px; padding: 9px 14px; }
QPushButton:hover { background: #3b475b; }
QPushButton:disabled { color: #667187; background: #202631; border-color: #28303e; }
QPushButton#primary { background: #b4c4f6; color: #171d2c; border: none; font-weight: 600; }
QPushButton#primary:hover { background: #c6d3f8; }
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox { background: #10151d; border: 1px solid #323c4e; border-radius: 6px; padding: 8px; selection-background-color: #43557b; }
QListWidget { background: #1c222d; border: none; border-radius: 8px; padding: 8px; }
QListWidget::item { padding: 13px 10px; margin: 3px 0; border-radius: 6px; }
QListWidget::item:selected { background: #354260; color: #eaf0ff; }
QListWidget::item:hover { background: #2a3447; }
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 10px 14px; background: #202631; }
QTabBar::tab:selected { background: #354260; }
QSplitter::handle { background: #303a48; }
QToolTip { background: #303a48; color: #e0e5ef; }
"""

def button(text, slot, primary=False):
    b = QPushButton(text)
    if primary: b.setObjectName("primary")
    b.clicked.connect(lambda _checked=False: slot())
    return b

def row(*widgets):
    box = QHBoxLayout()
    for w in widgets: box.addWidget(w)
    return box

def page(title, subtitle):
    widget = QWidget(); layout = QVBoxLayout(widget); layout.setContentsMargins(26, 22, 26, 22); layout.setSpacing(16)
    heading = QLabel(title); heading.setObjectName("title"); layout.addWidget(heading)
    label = QLabel(subtitle); label.setObjectName("subtitle"); label.setWordWrap(True); layout.addWidget(label)
    return widget, layout

class Window(QMainWindow):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.current_id = None
        self.backup_metadata = []
        self.statuses = []
        self.snapshot_ready = False
        self.dependency_reports = {}
        self.source_fingerprints = {}
        self.refresh_worker = None
        self.refresh_generation = 0
        self.refresh_pending = False
        self.last_refresh = 0
        self.closing = False
        self.initializing = True
        self.setWindowTitle("Caelestia Dev Manager")
        self.setWindowIcon(application_icon())
        self.resize(1240, 830)
        container = QWidget(); main = QHBoxLayout(container); main.setContentsMargins(0, 0, 0, 0)
        self.nav = AnimatedNavigation(); self.nav.setFixedWidth(202)
        for name in ["Dashboard", "Components", "Create / Import", "Codex Context", "Backups", "Logs", "Settings", "Component Store"]: self.nav.addItem(name)
        self.stack = AnimatedStack()
        self.stack.set_animations_enabled(preferences.load(manager.paths).get("animations_enabled", True) is not False)
        self.nav.set_animations_enabled(self.stack.animations_enabled)
        main.addWidget(self.nav); main.addWidget(self.stack, 1)
        self.setCentralWidget(container)
        self.component_icons = ComponentIcons()
        self.make_dashboard(); self.make_components(); self.make_import(); self.make_context()
        self.make_backups(); self.make_logs(); self.make_settings()
        self.store_page = StorePage(self); self.stack.addWidget(self.store_page)
        self.nav.currentRowChanged.connect(self.change_page)
        self.nav.setCurrentRow(0)
        self.initializing = False
        if manager.runtime.real:
            self.apply_snapshot({"statuses": [], "dependencies": {}, "environment": manager.environment,
                                 "backups": [], "logs": manager.registry.logs()}, ready=False)
            QTimer.singleShot(0, lambda: self.guard(self.request_refresh) if not self.closing else None)
        else:
            self.refresh()

    def guard(self, fn):
        try: return fn()
        except Exception as e:
            self.statusBar().showMessage(str(e), 15000)
            if isinstance(e, DependencyError):
                self.refresh()
                self.show_text("Dependency preparation failed", e.details())
            else:
                QMessageBox.warning(self, "Action could not be completed", str(e))
            return None

    def notify(self, message): self.statusBar().showMessage(message, 10000)

    def confirm(self, title, text, label="Continue", extra=None):
        return ReviewDialog(self, title, text, label, extra).exec() == QDialog.Accepted

    def show_text(self, title, text):
        dialog = QDialog(self); dialog.setWindowTitle(title); dialog.resize(880, 650)
        layout = QVBoxLayout(dialog); editor = CodeEditor(readonly=True); editor.setPlainText(text); layout.addWidget(editor)
        controls = QDialogButtonBox(QDialogButtonBox.Close); controls.rejected.connect(dialog.reject); layout.addWidget(controls)
        dialog.exec()

    def change_page(self, index):
        self.stack.setCurrentIndex(index)
        if index == 3: self.generate_context()
        if not self.initializing and self.manager.runtime.real and self.refresh_worker is None and time.monotonic() - self.last_refresh > 30:
            self.guard(self.request_refresh)

    def navigate(self, name):
        for index in range(self.nav.count()):
            if self.nav.item(index).text() == name:
                self.nav.setCurrentRow(index)
                return
        raise SafetyError("Unknown page: " + name)

    def make_dashboard(self):
        p, layout = page("Developer control center", "Create safely. Install independently. Manage the complete component lifecycle.")
        self.environment_label = QLabel(); self.environment_label.setWordWrap(True); layout.addWidget(self.environment_label)
        self.metrics = {}
        cards = QHBoxLayout()
        for title in ["Components", "Installed", "Enabled", "Running Apps", "Updates", "Broken"]:
            card = QFrame(); card.setObjectName("card"); l = QVBoxLayout(card)
            metric = QLabel("0"); metric.setObjectName("metric"); l.addWidget(metric); l.addWidget(QLabel(title)); self.metrics[title] = metric
            cards.addWidget(card)
        layout.addLayout(cards)
        layout.addLayout(row(button("+ New Component", self.new_component, True), button("Paste Codex Package", lambda: self.nav.setCurrentRow(2)),
                             button("Import Folder", self.import_folder), button("Copy Codex Prompt", self.copy_context), button("Refresh", lambda: self.guard(self.request_refresh))))
        self.dashboard_text = CodeEditor(readonly=True); layout.addWidget(self.dashboard_text)
        self.stack.addWidget(p)

    def make_components(self):
        p, layout = page("Components", "Development source and installed copies are tracked separately. Select a component to manage it.")
        layout.addLayout(row(button("+ New Component", self.new_component, True), button("Import Folder", self.import_folder),
                             button("Refresh", lambda: self.guard(self.request_refresh))))
        split = QSplitter(); self.components = QListWidget(); self.components.setMinimumWidth(260); self.components.setIconSize(QSize(44, 44))
        self.components.currentItemChanged.connect(self.select_component); split.addWidget(self.components)
        details = QWidget(); dl = QVBoxLayout(details); dl.setContentsMargins(12, 0, 0, 0)
        identity = QHBoxLayout()
        self.component_icon = QLabel(); self.component_icon.setFixedSize(56, 56)
        self.component_name = QLabel("Select a component"); self.component_name.setStyleSheet("font-size: 21px; font-weight: 600;")
        identity.addWidget(self.component_icon); identity.addWidget(self.component_name, 1); dl.addLayout(identity)
        self.shortcut_state = QLabel("Desktop Shortcut: Not Created"); dl.addWidget(self.shortcut_state)
        self.dependency_state = QLabel("Dependencies: Select a component"); self.dependency_state.setWordWrap(True); dl.addWidget(self.dependency_state)
        self.component_info = CodeEditor(readonly=True); dl.addWidget(self.component_info)
        self.actions = {}
        operations = [("Install / Update", "install", self.install_selected), ("Validate", "validate", self.validate_selected),
                      ("Enable", "enable", lambda: self.enable_selected(True)), ("Disable", "disable", lambda: self.enable_selected(False)),
                      ("Launch / Start", "launch", self.launch_selected), ("Stop", "stop", self.stop_selected),
                      ("Restart", "restart", self.restart_selected), ("Uninstall", "uninstall", self.uninstall_selected),
                      ("Open Source", "open", self.open_source),
                      ("Installed Files", "files", self.view_files), ("Logs", "logs", self.component_logs),
                      ("Backup", "backup", self.backup_selected), ("Delete Source", "delete", self.delete_selected),
                      ("Create Desktop Shortcut", "shortcut", self.toggle_desktop_shortcut),
                      ("Dependencies", "dependencies", self.show_dependencies)]
        for i in range(0, len(operations), 3):
            controls = QHBoxLayout()
            for title, key, action in operations[i:i+3]:
                b = button(title, lambda action=action: self.guard(action), key == "install")
                self.actions[key] = b; controls.addWidget(b)
            dl.addLayout(controls)
        split.addWidget(details); split.setStretchFactor(1, 1); layout.addWidget(split)
        self.stack.addWidget(p)

    def make_import(self):
        p, layout = page("Create / Import", "Paste a Codex package or generated source. Preview files before saving a development project.")
        fields = QHBoxLayout(); self.import_name = QLineEdit(); self.import_name.setPlaceholderText("Component name")
        self.import_id = QLineEdit(); self.import_id.setPlaceholderText("component-id")
        self.import_type = QComboBox(); self.import_type.addItems(sorted(TYPES)); self.import_type.setCurrentText("standalone-app")
        self.import_runtime = QComboBox(); self.import_runtime.addItems(sorted(RUNTIMES)); self.import_runtime.setCurrentText("python")
        for w in (self.import_name, self.import_id, self.import_type, self.import_runtime): fields.addWidget(w)
        layout.addLayout(fields)
        self.import_description = QLineEdit(); self.import_description.setPlaceholderText("Description"); layout.addWidget(self.import_description)
        self.import_shortcut = QCheckBox("Create shortcut on desktop"); self.import_shortcut_override = None
        self.import_shortcut.clicked.connect(lambda checked: setattr(self, "import_shortcut_override", checked))
        def shortcut_type_changed():
            supported = self.import_type.currentText() in SHORTCUT_TYPES
            self.import_shortcut.setEnabled(supported)
            if not supported: self.import_shortcut.setChecked(False); self.import_shortcut_override = None
        self.import_type.currentTextChanged.connect(shortcut_type_changed)
        layout.addWidget(self.import_shortcut)
        hint = QLabel("For packages with manifest.json, edit metadata in the pasted manifest. The shortcut checkbox overrides its optional preference. Other form fields generate a missing manifest.")
        hint.setObjectName("subtitle"); hint.setWordWrap(True); layout.addWidget(hint)
        self.single_filename = QLineEdit("src/main.py"); self.single_filename.setToolTip("Filename used only for a single pasted source file")
        layout.addLayout(row(QLabel("Single-file destination:"), self.single_filename, button("New from Template", self.new_component)))
        split = QSplitter(); self.paste = CodeEditor("Paste generated code here"); self.paste.setObjectName("pasteGeneratedCode"); split.addWidget(self.paste)
        self.import_tabs = QTabWidget(); self.file_preview = CodeEditor(readonly=True); self.manifest_preview = CodeEditor(readonly=True)
        self.destination_preview = CodeEditor(readonly=True); self.validation_output = CodeEditor(readonly=True)
        for name, w in [("Files", self.file_preview), ("Manifest", self.manifest_preview), ("Destination", self.destination_preview), ("Validation", self.validation_output)]:
            self.import_tabs.addTab(w, name)
        split.addWidget(self.import_tabs); split.setSizes([600, 430]); layout.addWidget(split, 1)
        self.paste.textChanged.connect(lambda: self.notify("Paste changed; Analyze/Preview recalculates before creation"))
        self.paste.textChanged.connect(lambda: setattr(self, "import_shortcut_override", None))
        layout.addLayout(row(button("Analyze Code", lambda: self.guard(self.analyze)), button("Preview Files", lambda: self.guard(self.analyze)),
                             button("Validate", lambda: self.guard(lambda: (self.analyze(), self.import_tabs.setCurrentIndex(3)))),
                             button("Save as Draft", lambda: self.guard(lambda: self.create_import(True))),
                             button("Create Component", lambda: self.guard(self.create_import), True)))
        self.stack.addWidget(p)

    def analyze(self):
        text = self.paste.toPlainText()
        if not text.strip(): raise SafetyError("Paste code or choose a template first")
        package = parse(text, self.single_filename.text())
        files = package.files
        if "manifest.json" in files:
            m = manifest_parse(files["manifest.json"])
            self.import_name.setText(m["name"]); self.import_id.setText(m["id"]); self.import_type.setCurrentText(m["type"])
            self.import_runtime.setCurrentText(m["runtime"]); self.import_description.setText(m.get("description", ""))
        else:
            runtime = detect("\n".join(files.values()))
            if runtime != "none": self.import_runtime.setCurrentText(runtime)
            if len(files) == 1 and "src/main.py" in files and runtime in {"qml", "quickshell", "shell"} and "--- FILE:" not in text:
                filename = {"qml": "ui/Main.qml", "quickshell": "main.qml", "shell": "src/main.sh"}[runtime]
                files[filename] = files.pop("src/main.py"); self.single_filename.setText(filename)
            m = {"id": package.headers.get("id", self.import_id.text().strip()), "name": package.headers.get("name", self.import_name.text().strip()),
                 "version": package.headers.get("version", "0.1.0"), "description": self.import_description.text().strip(),
                 "type": package.headers.get("type", self.import_type.currentText()), "runtime": self.import_runtime.currentText(),
                 "entrypoint": next((name for name in files if name.endswith((".py", ".qml", ".sh"))), next(iter(files)))}
            if m["runtime"] == "python-pyside6": m["dependencies"] = {"python": ["PySide6>=6.8"]}
            if not m["id"] and m["name"]: m["id"] = re.sub(r"[^a-z0-9]+", "-", m["name"].lower()).strip("-")
            m = manifest_parse(json.dumps(m)); files["manifest.json"] = json.dumps(m, indent=2) + "\n"
            self.import_id.setText(m["id"]); self.import_name.setText(m["name"])
        self.import_type.setCurrentText(m["type"])
        self.import_shortcut.setEnabled(m["type"] in SHORTCUT_TYPES)
        requested = self.import_shortcut_override if self.import_shortcut_override is not None else m.get("desktop", {}).get("createShortcut", False)
        self.import_shortcut.setChecked(bool(requested) if m["type"] in SHORTCUT_TYPES else False)
        if self.import_shortcut_override is not None:
            m.setdefault("desktop", {})["createShortcut"] = self.import_shortcut.isChecked()
            files["manifest.json"] = json.dumps(m, indent=2) + "\n"
        requested = m.get("desktop", {}).get("createShortcut", False)
        result = validate(files, m, self.manager.environment)
        self.file_preview.setPlainText(m["id"] + "/\n" + "\n".join("  " + path for path in sorted(files)))
        self.manifest_preview.setPlainText(json.dumps(m, indent=2))
        self.destination_preview.setPlainText("CREATE SOURCE ONLY\n" + str(self.manager.paths.source(m["id"])) +
                "\n\nAfter a separate reviewed install:\n" + str(self.manager.paths.root(m)) +
                ("\n" + str(self.manager.paths.bin / m["id"]) + "\n" + str(self.manager.paths.data / "applications" / (m["id"] + ".desktop")) if m["type"] == "standalone-app" else "") +
                "\n\nNo pasted code has been executed.")
        if requested:
            try:
                directory = desktop_directory(self.manager.paths)
                destination = str(directory / shortcut_filename(m)) if directory else "Not configured / disabled"
            except SafetyError as e: destination = str(e)
            self.destination_preview.appendPlainText("\nOptional desktop shortcut after installation:\n" + destination)
        self.validation_output.setPlainText(("✓ Valid manifest and safe relative paths\n✓ Entrypoint and static source checks passed\n" if result["valid"] else "\n".join("ERROR: " + x for x in result["errors"]) + "\n") +
                                            "\n".join("REVIEW: " + x for x in result["warnings"]) + "\n\nDetected runtime: " + m["runtime"])
        return files, m, result

    def create_import(self, draft=False):
        files, m, result = self.analyze()
        id = self.manager.create(files, draft=draft)
        self.refresh(); self.select_id(id); self.nav.setCurrentRow(1)
        self.notify("Created development source " + id + ". Install is a separate action.")
        return id

    def new_component(self):
        dialog = QDialog(self); dialog.setWindowTitle("New Component"); dialog.resize(510, 350)
        layout = QVBoxLayout(dialog); form = QFormLayout()
        name, id, desc = QLineEdit(), QLineEdit(), QLineEdit(); choice = QComboBox(); choice.addItems(TEMPLATES)
        for title, field in [("Name", name), ("ID", id), ("Description", desc), ("Language / Framework", choice)]: form.addRow(title, field)
        shortcut = QCheckBox("Create shortcut on desktop"); form.addRow(shortcut)
        def update_shortcut():
            shortcut.setEnabled(TEMPLATES[choice.currentText()][0] in SHORTCUT_TYPES)
            if not shortcut.isEnabled(): shortcut.setChecked(False)
        choice.currentTextChanged.connect(update_shortcut); update_shortcut()
        name.textChanged.connect(lambda text: id.setText(re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")) if not id.hasFocus() else None)
        layout.addLayout(form); layout.addWidget(QLabel("The template is previewed in Create / Import before files are saved."))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            def load():
                m, files = template(name.text(), id.text(), choice.currentText(), desc.text())
                if shortcut.isChecked():
                    m.setdefault("desktop", {})["createShortcut"] = True; files["manifest.json"] = json.dumps(m, indent=2) + "\n"
                manifest_parse(files["manifest.json"])
                self.paste.setPlainText(encode(files, m)); self.nav.setCurrentRow(2); self.analyze()
            self.guard(load)

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Import existing component source")
        if not folder: return
        def load():
            root = no_symlinks(Path(folder)); files = {}
            for path in root.rglob("*"):
                if any(x.startswith(".") or x in {"__pycache__", "node_modules"} for x in path.relative_to(root).parts): continue
                no_symlinks(path)
                if path.is_file():
                    name = str(relative(str(path.relative_to(root))))
                    if path.stat().st_size > 8 * 1024 * 1024: raise SafetyError("Imported text file is too large")
                    files[name] = path.read_text()
            m = manifest_parse(files["manifest.json"])
            self.paste.setPlainText(encode(files, m)); self.nav.setCurrentRow(2); self.analyze()
        self.guard(load)

    def make_context(self):
        p, layout = page("Codex Context", "Generate a prompt with your environment, dependency diagnostics, component contract, and GitHub store publishing steps.")
        self.request = QTextEdit(); self.request.setPlaceholderText("Describe what to build or fix. Completed work must be committed and pushed to Git; include any repository or branch constraints."); self.request.setMaximumHeight(150); layout.addWidget(self.request)
        layout.addLayout(row(button("Generate Prompt", self.generate_context), button("Copy Full Codex Prompt", self.copy_context, True)))
        self.context_editor = CodeEditor(readonly=True); layout.addWidget(self.context_editor); self.stack.addWidget(p)

    def generate_context(self):
        if not self.snapshot_ready:
            self.context_editor.setPlainText("Loading component information…")
            return ""
        prompt = context(self.manager, self.request.toPlainText(), self.statuses, self.dependency_reports)
        if prompt != self.context_editor.toPlainText(): self.context_editor.setPlainText(prompt)
        return prompt

    def copy_context(self):
        if not self.snapshot_ready:
            self.notify("Component information is still loading. Copy the prompt after the refresh completes.")
            return False
        QApplication.clipboard().setText(self.generate_context()); self.notify("Full Codex prompt copied to clipboard")

    def make_backups(self):
        p, layout = page("Backups", "Checksummed snapshots are taken before installed files are replaced or removed. Restore never changes development source.")
        self.backup_list = QListWidget(); layout.addWidget(self.backup_list)
        layout.addLayout(row(button("Inspect Metadata", lambda: self.guard(self.inspect_backup)), button("Restore", lambda: self.guard(self.restore_backup), True),
                             button("Refresh", lambda: self.guard(self.request_refresh))))
        self.stack.addWidget(p)

    def selected_backup(self):
        item = self.backup_list.currentItem()
        if not item: raise SafetyError("Select a backup")
        return item.data(Qt.UserRole)

    def inspect_backup(self): self.show_text("Backup metadata", json.dumps(self.manager.backups.read(self.selected_backup()), indent=2))

    def restore_backup(self):
        id = self.selected_backup(); meta, record, entries, remove = self.manager.plan_restore(id)
        text = "RESTORE " + meta["component_id"] + "\n" + "\n".join("WRITE " + str(x.path) for x in entries) + "\n" + "\n".join("REMOVE " + f["path"] for f in remove)
        host = host_integration.plan(self.manager.paths, meta["record"]["installed_manifest"])
        if host:
            text += "\n\n" + host["summary"] + "\nCaelestia KDE will restart.\n" + json.dumps(host, indent=2)
        if self.confirm("Restore installed backup", text, "Restore"):
            self.manager.restore(id); self.refresh(); self.notify("Backup restored; inspect service state and reload Caelestia if required")

    def make_logs(self):
        p, layout = page("Logs", "Manager lifecycle events. Component runtime logs are available from Components.")
        self.logs_editor = CodeEditor(readonly=True); layout.addWidget(self.logs_editor)
        layout.addWidget(button("Refresh", lambda: self.guard(self.request_refresh))); self.stack.addWidget(p)

    def make_settings(self):
        p, layout = page("Settings", "Local paths, environment detection, reference updates, and recovery.")
        self.settings_editor = CodeEditor(readonly=True); layout.addWidget(self.settings_editor)
        self.store_startup = QCheckBox("Check for component updates when Dev Manager opens")
        self.store_startup.setChecked(Store(self.manager.paths).settings["check_on_startup"])
        self.store_startup.toggled.connect(lambda checked: self.guard(lambda: self.store_page.set_startup_check(checked)))
        layout.addWidget(self.store_startup)
        self.animations_setting = QCheckBox("Animate tab transitions")
        self.animations_setting.setChecked(self.stack.animations_enabled)
        self.animations_setting.toggled.connect(lambda checked: self.guard(lambda: self.set_animations(checked)))
        layout.addWidget(self.animations_setting)
        layout.addLayout(row(button("Refresh Detection", lambda: self.guard(self.request_refresh)), button("Reload Caelestia Shell", lambda: self.guard(self.reload_shell)),
                             button("Recover Interrupted Operation", lambda: self.guard(self.recover))))
        layout.addWidget(button("Reference Update Command", lambda: self.guard(self.update_reference)))
        self.stack.addWidget(p)

    def set_animations(self, checked):
        preferences.save_animations(self.manager.paths, checked)
        self.stack.set_animations_enabled(checked)
        self.nav.set_animations_enabled(checked)

    def update_reference(self):
        self.show_text("Update reference", "Run this from your terminal:\n\n" + shlex.join([str(self.manager.paths.project / "update-reference.sh")]) +
                       "\n\nThe helper refuses local changes and uses a fast-forward-only update. It never modifies installed Caelestia.")

    def reload_shell(self):
        if self.confirm("Reload Caelestia shell", "Restart caelestia-shell.service now?\n\nThis reloads the actual shell and all its plugins.\nIt does not restart Plasma. Inspect component logs for QML errors afterward.", "Reload Shell"):
            self.manager.reload_caelestia(); self.refresh()

    def recover(self):
        if self.confirm("Recover interrupted operation", "Restore the last installed-file snapshot and registry state for the interrupted operation. Development source is unaffected.", "Recover"):
            self.notify(self.manager.recover()); self.refresh()

    def refresh(self):
        """Immediate refresh after a reviewed mutation; tab navigation never calls this."""
        self.refresh_generation += 1
        if self.refresh_worker is not None: self.refresh_worker.cancelled.set()
        from backend.environment import detect as detect_environment
        self.manager.environment = detect_environment(self.manager.paths)
        self.manager.discover()
        statuses = self.manager.all_status()
        self.apply_snapshot({"statuses": statuses,
            "dependencies": {r["id"]: self.manager.dependency_status(r["id"]) for r in statuses},
            "environment": self.manager.environment, "backups": self.manager.backups.catalog(),
            "logs": self.manager.registry.logs()})

    def request_refresh(self):
        if self.closing: return
        if self.refresh_worker is not None:
            self.refresh_pending = True
            return
        self.manager.discover()
        self.refresh_generation += 1
        self.last_refresh = time.monotonic()
        self.refresh_worker = Inspection(self.manager, self.refresh_generation, self)
        self.refresh_worker.result.connect(self.inspected)
        self.refresh_worker.failed.connect(self.inspection_failed)
        self.refresh_worker.finished.connect(self.inspection_finished)
        self.notify("Checking components in the background…")
        self.refresh_worker.start()

    @Slot(int, dict)
    def inspected(self, generation, snapshot):
        if self.closing or generation != self.refresh_generation: return
        self.apply_snapshot(snapshot)
        self.notify("Component information refreshed")

    @Slot(int, str)
    def inspection_failed(self, generation, message):
        if not self.closing and generation == self.refresh_generation:
            self.notify("Could not refresh component information: " + message)

    @Slot()
    def inspection_finished(self):
        worker, self.refresh_worker = self.refresh_worker, None
        if worker is not None: worker.deleteLater()
        pending, self.refresh_pending = self.refresh_pending, False
        if pending and not self.closing: self.guard(self.request_refresh)

    def apply_snapshot(self, snapshot, ready=True):
        self.snapshot_ready = ready
        self.statuses = snapshot["statuses"]
        self.dependency_reports = snapshot["dependencies"]
        self.source_fingerprints = {r["id"]: r.get("source_hash") for r in self.statuses}
        self.manager.environment = snapshot["environment"]
        self.last_refresh = time.monotonic()
        env = snapshot["environment"]
        self.environment_label.setText(f"Caelestia  {'Running' if env['caelestia_running'] else 'Stopped / not detected'}     •     KDE Plasma  {env['plasma_version'] or 'Not detected'}     •     Session  {env['session']}")
        counts = {"Components": len(self.statuses), "Installed": sum(bool(x.get("installed")) for x in self.statuses),
                  "Enabled": sum(bool(x.get("enabled")) for x in self.statuses),
                  "Running Apps": sum(x["running"] and x["manifest"]["type"] == "standalone-app" for x in self.statuses),
                  "Updates": sum(x["source_modified"] for x in self.statuses),
                  "Broken": sum(bool(x["missing"] or x["modified"] or (not x["validation"]["valid"] and x["source_exists"] and x["status"] != "Missing Dependencies")) for x in self.statuses)}
        for title, metric in self.metrics.items(): metric.setText(str(counts[title]))
        self.dashboard_text.setPlainText("DEVELOPMENT WORKFLOW\n\n1. Create a template or paste a Codex package\n2. Preview files and validate source\n3. Review installation destinations and executable source\n4. Install into the real application, shell or service environment\n5. Update installed copies when source changes\n\n" +
                                         ("\n".join(x["manifest"]["name"] + "  •  " + x["status"] for x in self.statuses) or "No components yet. Start with New Component or Paste Codex Package."))
        selected = self.current_id
        self.components.blockSignals(True); self.components.clear()
        for r in self.statuses:
            item = QListWidgetItem(f"{r['manifest']['name']}\n{r['manifest']['type']}\n{r['status']}"); item.setData(Qt.UserRole, r["id"]); item.setIcon(self.component_icons.icon(r["manifest"], r.get("icon_svg", ""), ratio=self.devicePixelRatioF())); self.components.addItem(item)
        self.components.blockSignals(False)
        if selected: self.select_id(selected)
        elif self.components.count(): self.components.setCurrentRow(0)
        else: self.select_component(None)
        selected_backup = self.backup_list.currentItem()
        selected_backup = selected_backup.data(Qt.UserRole) if selected_backup else None
        self.backup_list.clear()
        self.backup_metadata = snapshot["backups"]
        for b in self.backup_metadata:
            item = QListWidgetItem(f"{b['component_id']}  •  {b['version'] or 'not installed'}  •  {b['reason']}\n{b['date']}"); item.setData(Qt.UserRole, b["backup_id"]); self.backup_list.addItem(item)
            if b["backup_id"] == selected_backup: self.backup_list.setCurrentItem(item)
        self.logs_editor.setPlainText("\n".join(snapshot["logs"]) or "No events recorded")
        self.settings_editor.setPlainText(json.dumps({"project": str(self.manager.paths.project), "database": str(self.manager.paths.database),
                "backups": str(self.manager.paths.backups), "manager_version": VERSION,
                "recovery_required": self.manager.journal.exists(), **env}, indent=2))
        if hasattr(self, "store_page"): self.store_page.fill()
        if self.nav.currentRow() == 3: self.generate_context()

    def select_id(self, id):
        for i in range(self.components.count()):
            if self.components.item(i).data(Qt.UserRole) == id:
                self.components.setCurrentRow(i); self.select_component(self.components.item(i)); break

    def select_component(self, item, _previous=None):
        from backend.installers import installer
        self.current_id = item.data(Qt.UserRole) if item else None
        if not self.current_id:
            self.component_icon.clear(); self.component_name.setText("Select a component")
            self.shortcut_state.setText("Desktop Shortcut: Not Created")
            self.dependency_state.setText("Dependencies: Select a component")
            self.component_info.setPlainText("Select a component")
            for b in self.actions.values(): b.setEnabled(False)
            return
        r = next((r for r in self.statuses if r["id"] == self.current_id), None)
        if not r: return
        self.component_icon.setPixmap(self.component_icons.pixmap(r["manifest"], r.get("icon_svg", ""), 56, self.devicePixelRatioF()))
        self.component_name.setText(r["manifest"]["name"])
        self.shortcut_state.setText("Desktop Shortcut: " + r["desktop_shortcut_state"])
        dependencies = self.dependency_reports.get(self.current_id)
        if dependencies is None: return
        dev = dependencies["development"]
        problems = [x["requirement"] + " (" + x["status"] + ")" for x in [*dev["system"], *dev["python"]] if x["status"] not in {"available", "prepared"}]
        summary = "Development dependencies: " + ("Ready" if dev["ready"] else ", ".join(problems) or "Inspection unavailable") + (" · Last preparation failed; open Dependencies" if dev["last_preparation_error"] else "")
        if "installed" in dependencies:
            live = dependencies["installed"]
            missing = [x["requirement"] + " (" + x["status"] + ")" for x in [*live["system"], *live["python"]] if x["status"] not in {"available", "prepared"}]
            summary += "\nInstalled dependencies: " + ("Ready" if live["ready"] else ", ".join(missing) or "Inspection unavailable")
        self.dependency_state.setText(summary)
        self.component_info.setPlainText(json.dumps({"name": r["manifest"]["name"], "id": r["id"], "status": r["status"],
            "source_version": r["manifest"]["version"], "installed_version": r.get("installed_version"),
            "source": r["source"], "source_exists": r["source_exists"], "destination": r.get("destination"),
            "source_modified": r["source_modified"], "pids": r["pids"], "service": r.get("service"),
            "last_install": r.get("installed_at"), "last_update": r.get("updated_at"), "enabled": r.get("enabled"),
            "compatible": r["compatible"], "service_state": r.get("service_state"),
            "Desktop Shortcut": r["desktop_shortcut_state"], "desktop_shortcut_path": (r.get("desktop_shortcut") or {}).get("path"),
            "caelestia_state": "Discovery enabled; inspect shell logs for actual runtime health" if r["manifest"]["type"] in {"caelestia-plugin", "qml-component"} and r.get("enabled") else None,
            "missing_files": r["missing"], "modified_files": r["modified"], "validation": r["validation"], "dependencies": dependencies}, indent=2))
        caps = installer(self.manager.paths, r.get("installed_manifest", r["manifest"])).capabilities
        for key, b in self.actions.items():
            if key in {"open", "delete", "validate"}: active = r["source_exists"]
            elif key == "dependencies": active = True
            elif key == "install": active = r["source_exists"] and "install" in caps
            elif key == "files": active = r.get("installed", False)
            elif key == "shortcut": active = r.get("installed") and r["installed_manifest"]["type"] in SHORTCUT_TYPES
            elif key == "enable": active = r.get("installed") and not r.get("enabled") and key in caps
            elif key == "disable": active = r.get("installed") and r.get("enabled") and key in caps
            elif key in {"stop", "restart"}: active = r.get("installed") and r["running"] and key in caps
            elif key == "launch": active = r.get("installed") and (r.get("enabled") or r["manifest"]["type"] == "user-service") and key in caps
            else: active = r.get("installed") and key in caps
            b.setEnabled(bool(active))
        self.actions["install"].setText("Update Installed Version" if r.get("installed") else "Install")
        self.actions["shortcut"].setText("Remove Desktop Shortcut" if r["desktop_shortcut_created"] else "Create Desktop Shortcut")

    def show_dependencies(self):
        if not self.current_id: raise SafetyError("Select a component")
        result = self.manager.dependency_status(self.current_id)
        lines = ["Component: " + self.current_id, "Read-only check: no downloads, component imports or system changes."]
        if result["source_manifest_error"]:
            lines += ["Source manifest error: " + result["source_manifest_error"], "Showing dependencies from the last valid registered manifest."]
        for scope in ("development", "installed"):
            if scope not in result: continue
            data = result[scope]
            lines += ["", scope.upper() + " DEPENDENCIES", "Python environment: " + data["environment"], "Python version: " + data["python_version"]]
            for entry in data["system"]:
                lines.append("System: " + entry["requirement"] + " — " + entry["status"] + (" — " + entry["path"] if entry["path"] else " (install manually)"))
            for entry in data["python"]:
                lines.append("Python: " + entry["requirement"] + " — " + entry["status"] + " — installed version: " + (entry["installed_version"] or "none"))
            if not data["system"] and not data["python"]: lines.append("No declared dependencies.")
            if data["inspection_error"]: lines.append("Inspection error: " + data["inspection_error"])
            if data["last_preparation_error"]:
                error = data["last_preparation_error"]
                lines += ["", "LAST PREPARATION ERROR", error["reason"], "Reported requirements: " + (", ".join(error["reported_requirements"]) or "not identified"),
                          "Python version: " + error.get("python_version", "unknown"), error["output"]]
        lines += ["", "Python dependencies are checked in the component environment, not the manager or system Python.",
                  "Install / Update offers a reviewed preparation or retry. Only binary wheels are allowed."]
        self.show_text("Component dependencies", "\n".join(lines))

    def install_selected(self):
        if not self.current_id: raise SafetyError("Select a component")
        r = self.manager.registry.get(self.current_id)
        m = manifest_parse(self.manager.read_source(self.current_id)["manifest.json"])
        setup = self.manager.plan_system_setup(self.current_id)
        if setup["commands"]:
            if not self.confirm("Prepare this PC for Cast Audio", setup["summary"], "Prepare PC"): return False
            self.notify("Preparing this PC…"); QApplication.processEvents()
            self.manager.prepare_system(self.current_id, expected=setup)
        deps = m.get("dependencies", {}).get("python", [])
        if deps and not self.manager.dependencies_prepared(m):
            if not self.confirm("Download required libraries", m["name"] + " needs these Python libraries:\n\n" + "\n".join(deps) + "\n\nThey will be downloaded into this component's private environment. No system packages will be changed. This may take a few minutes.", "Download Libraries"): return False
            self.notify("Preparing Python dependencies…"); QApplication.processEvents()
            self.manager.prepare_dependencies(self.current_id)
        options = QWidget(); controls = QVBoxLayout(options); options.plan = None; options.filename = None; options.alternate_filename = None
        options.checkbox = QCheckBox("Create shortcut on desktop"); controls.addWidget(options.checkbox)
        options.checkbox.setEnabled(m["type"] in SHORTCUT_TYPES)
        options.checkbox.setChecked(self.manager.desired_shortcut(m, r, None) if m["type"] in SHORTCUT_TYPES else False)
        alternative = button("Use alternate safe filename", lambda: choose_alternate()); controls.addWidget(alternative); alternative.hide()
        def rebuild():
            try:
                plan = self.manager.plan_install(self.current_id, options.checkbox.isChecked(), options.filename)
                options.plan = plan; alternative.hide()
                executables = "\n\n".join(str(x.path) + "\n" + x.data.decode() for x in plan["files"] if (x.mode & 0o111 or x.path.suffix == ".service") and x.data is not None)
                text = (f"{m['name']} {m['version']}\n\n" + plan["preview"] + "\n\nEXECUTABLE LAUNCHERS\n" + executables +
                    "\n\nREQUESTED PERMISSIONS\n" + json.dumps(m.get("permissions", [])) + "\n\nDEPENDENCIES\n" + json.dumps(m.get("dependencies", {})) +
                    "\n\n" + "\n".join(plan["warnings"]) + "\n\nThis payload step writes user files. Any reviewed PC preparation is separate. Existing owned files are backed up.\nReview component source before launching or enabling.")
                options.summary_text = (m["name"] + " " + m["version"] + "\n\n" + m.get("description", "") +
                    "\n\nInstall location\n" + str(self.manager.paths.root(m)) +
                    "\n\nPermissions\n" + ("\n".join("• " + p for p in m.get("permissions", [])) or "No additional permissions declared.") +
                    "\n\nExisting versions are backed up so you can go back. The app runs independently of Dev Manager.\nRestart an open app to use its updated version.")
                if plan["warnings"]: options.summary_text += "\n\nPlease note\n" + "\n".join(plan["warnings"])
                if plan.get("host_integration"):
                    options.summary_text += "\n\nCaelestia host integration\n" + plan["host_integration"]["summary"] + "\nTwo verified host files are backed up and tracked separately; technical details show the complete before/after source."
                text += "\n\nCOMPLETE COMPONENT SOURCE\n" + encode(self.manager.read_source(self.current_id), m)
            except SafetyError as e:
                options.plan = None; text = str(e); alternative.setVisible(isinstance(e, ShortcutConflict))
                options.summary_text = text
                if isinstance(e, ShortcutConflict): options.alternate_filename = e.alternate
            options.preview_text = text
            if hasattr(options, "refresh_preview"): options.refresh_preview(text, options.plan is not None)
        def choose_alternate(): options.filename = options.alternate_filename; rebuild()
        options.checkbox.toggled.connect(rebuild); rebuild()
        updating = r.get("installed", False)
        if self.confirm(("Update " if updating else "Install ") + m["name"], options.preview_text, "Update" if updating else "Install", options):
            if options.plan is None: raise SafetyError(options.preview_text)
            self.manager.install(self.current_id, expected=options.plan); self.refresh(); self.notify("Installed. Components run independently of Dev Manager.")
            return True
        return False

    def toggle_desktop_shortcut(self):
        id = self.current_id
        if self.manager.has_desktop_shortcut(id):
            receipt = self.manager.plan_remove_desktop_shortcut(id)
            if self.confirm("Remove Desktop Shortcut", "REMOVE " + receipt["path"] + "\n\nThe application and normal launcher remain installed.", "Remove Shortcut"):
                self.manager.remove_desktop_shortcut(id); self.refresh()
            return
        filename = None
        try: plan = self.manager.plan_create_desktop_shortcut(id)
        except ShortcutConflict as e:
            if not self.confirm("Desktop shortcut conflict", str(e) + "\n\nUse the suggested alternate filename? The existing file will remain untouched.", "Use Alternate Filename"): return
            filename = e.alternate; plan = self.manager.plan_create_desktop_shortcut(id, filename)
        if self.confirm("Create Desktop Shortcut", plan["preview"] + "\n\nUses the installed application's canonical desktop entry. Dev Manager is not launched.", "Create Shortcut"):
            self.manager.create_desktop_shortcut(id, filename, expected=plan); self.refresh()

    def validate_selected(self): self.show_text("Static validation", json.dumps(self.manager.validation(self.current_id), indent=2))

    def enable_selected(self, enabled):
        record = self.manager.installed(self.current_id)
        text = ("Activate" if enabled else "Deactivate") + " " + record["manifest"]["name"] + "\n"
        if record["installed_manifest"]["type"] == "user-service": text += "systemctl --user " + ("enable --now " if enabled else "disable --now ") + self.manager.runtime.unit(self.current_id)
        elif record["installed_manifest"]["type"] in {"caelestia-plugin", "qml-component"}: text += "Rename only this plugin's owned metadata discovery file. An explicit Caelestia shell reload is required afterward."
        else: text += "Change this component's launcher permission and desktop visibility. Disabling also stops detected managed processes."
        if self.confirm("Enable component" if enabled else "Disable component", text, "Enable" if enabled else "Disable"):
            self.manager.set_enabled(self.current_id, enabled); self.refresh()

    def launch_selected(self):
        self.manager.runtime.launch(self.manager.installed(self.current_id)); QTimer.singleShot(600, lambda: self.guard(self.request_refresh)); self.notify("Launch requested")

    def stop_selected(self):
        self.manager.runtime.stop(self.manager.installed(self.current_id)); QTimer.singleShot(600, lambda: self.guard(self.request_refresh))

    def restart_selected(self):
        record = self.manager.installed(self.current_id)
        if record["installed_manifest"]["type"] == "user-service": self.manager.runtime.systemctl("restart", self.manager.runtime.unit(self.current_id))
        else:
            self.manager.runtime.stop(record)
            QTimer.singleShot(700, lambda: self.guard(lambda: self.manager.runtime.launch(record)))
        QTimer.singleShot(1100, lambda: self.guard(self.request_refresh))

    def uninstall_selected(self):
        files = self.manager.plan_uninstall(self.current_id)
        text = "Remove only these owned installed files:\n\n" + "\n".join(f["path"] for f in files) + "\n\nDevelopment source will remain. Running managed processes/services will be stopped."
        host = host_integration.plan(self.manager.paths, {"id": self.current_id})
        if host:
            text += "\n\n" + host["summary"] + " Caelestia KDE will restart. Changed host files are preserved and block this operation."
            text += "\n\n" + "\n".join("HOST FILE " + str(self.manager.paths.shell / name) + "\nBEFORE\n" + host["before"][name] + "\nAFTER\n" + host["after"][name] for name in host["before"])
        if self.confirm("Uninstall component", text, "Uninstall"):
            self.manager.uninstall(self.current_id); self.refresh(); self.notify("Uninstalled owned files; source preserved")

    def open_source(self): QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.manager.paths.source(self.current_id))))

    def view_files(self): self.show_text("Owned installed files", json.dumps(self.manager.registry.files(self.current_id), indent=2))
    def component_logs(self): self.show_text("Component logs", self.manager.runtime.logs(self.manager.registry.get(self.current_id)))

    def backup_selected(self):
        self.manager.backup(self.current_id); self.refresh(); self.notify("Backup created")

    def delete_selected(self):
        r = self.manager.registry.get(self.current_id)
        text = "Delete development source:\n" + str(self.manager.paths.source(self.current_id)) + "\n\n"
        if r.get("installed"): text += "WARNING: An installed copy still exists. It will remain installed.\n\n"
        text += "Type " + self.current_id + " to confirm:"
        confirmation, ok = QInputDialog.getText(self, "Delete Source", text)
        if ok:
            self.manager.delete_source(self.current_id, confirmation); self.refresh()

    def closeEvent(self, event):
        self.closing = True
        self.stack.stop_transition()
        self.nav.stop_transition()
        if self.refresh_worker is not None: self.refresh_worker.cancelled.set()
        inspected = self.refresh_worker is None or self.refresh_worker.wait(50)
        if not self.store_page.shutdown() or not inspected:
            event.ignore()
            QTimer.singleShot(500, self.close)
            return
        event.accept()

def main():
    parser = argparse.ArgumentParser(description="Caelestia Dev Manager")
    parser.add_argument("--project", type=Path, help="Development repository (default CDM_PROJECT or source root)")
    parser.add_argument("--sandbox", type=Path, help="Use isolated XDG paths and a mocked systemd controller")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1]); app.setApplicationName("Caelestia Dev Manager"); app.setDesktopFileName("caelestia-dev-manager")
    app.setStyle("Fusion"); app.setStyleSheet(STYLE)
    paths = Paths.sandbox(args.sandbox) if args.sandbox else Paths.default(args.project)
    try:
        window = Window(Manager(paths, real=not bool(args.sandbox)))
        window.show(); return app.exec()
    except Exception as e:
        QMessageBox.critical(None, "Caelestia Dev Manager could not start", str(e)); return 1

if __name__ == "__main__": sys.exit(main())

"""Component browsing and cancellable background Git checks."""
import json

from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
                              QCheckBox, QPushButton, QListWidget, QListWidgetItem, QSplitter,
                              QTabWidget, QComboBox)
from app.editor import CodeEditor
from backend.codex.package import encode
from backend.store import Store, describe_entry
from backend.validators import validate


class StoreCheck(QThread):
    result = Signal(dict)
    failed = Signal(str)

    def __init__(self, store, parent):
        super().__init__(parent)
        # The worker never accesses the registry or GUI. Capture settings for this request.
        self.store = Store(store.paths)
        self.store.settings = dict(store.settings)

    def run(self):
        try:
            self.result.emit(self.store.scan())
        except Exception as error:
            self.failed.emit(str(error))


class StorePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.manager = window, window.manager
        self.store = Store(self.manager.paths)
        self.catalog, self.worker = self.store.cached(), None
        self.closing = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        title = QLabel("Component Store"); title.setObjectName("title"); layout.addWidget(title)
        subtitle = QLabel("Browse your GitHub components. Review source before download; installation and updates require a separate review.")
        subtitle.setWordWrap(True); layout.addWidget(subtitle)
        form = QFormLayout()
        self.repository = QLineEdit(self.store.settings["repository"])
        self.branch = QLineEdit(self.store.settings["branch"])
        self.auto_check = QCheckBox("Check this repository when Dev Manager opens")
        self.auto_check.setChecked(self.store.settings["check_on_startup"])
        form.addRow("Repository", self.repository); form.addRow("Branch", self.branch); form.addRow(self.auto_check)
        layout.addLayout(form)
        controls = QHBoxLayout()
        self.save_button = QPushButton("Save repository settings")
        self.save_button.clicked.connect(lambda: window.guard(self.save_settings))
        self.check_button = QPushButton("Check for Updates")
        self.check_button.clicked.connect(lambda: window.guard(self.check))
        controls.addWidget(self.save_button); controls.addWidget(self.check_button)
        layout.addLayout(controls)
        self.status = QLabel(self.store.notice or "No repository check yet")
        self.status.setWordWrap(True); layout.addWidget(self.status)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search components by name, description or type")
        self.search.textChanged.connect(self.fill); layout.addWidget(self.search)
        split = QSplitter()
        self.list = QListWidget(); self.list.currentItemChanged.connect(self.select)
        split.addWidget(self.list)
        tabs = QTabWidget()
        self.overview = CodeEditor(readonly=True); tabs.addTab(self.overview, "Overview")
        source = QWidget(); source_layout = QVBoxLayout(source)
        self.files = QComboBox(); self.files.currentTextChanged.connect(self.show_file)
        self.source = CodeEditor(readonly=True)
        source_layout.addWidget(self.files); source_layout.addWidget(self.source)
        tabs.addTab(source, "Source files"); split.addWidget(tabs); split.setStretchFactor(1, 1)
        layout.addWidget(split, 1)
        actions = QHBoxLayout()
        self.download_button = QPushButton("Download source")
        self.download_button.clicked.connect(lambda: window.guard(self.download))
        self.install_button = QPushButton("Install / Update Installed Version")
        self.install_button.clicked.connect(lambda: window.guard(self.install))
        actions.addWidget(self.download_button); actions.addWidget(self.install_button); layout.addLayout(actions)
        self.fill()
        if self.manager.runtime.real and self.auto_check.isChecked():
            QTimer.singleShot(300, lambda: window.guard(self.check) if not self.closing else None)

    def save_settings(self):
        if self.worker is not None: return
        self.store.save_settings(self.repository.text().strip(), self.branch.text().strip(), self.auto_check.isChecked())
        self.catalog = self.store.cached()
        self.fill()
        self.status.setText("Repository settings saved; Check for Updates to refresh")

    def check(self):
        if self.worker is not None or self.closing: return
        self.save_settings()
        self.status.setText("Checking repository in the background…")
        self.check_button.setEnabled(False); self.save_button.setEnabled(False)
        self.worker = StoreCheck(self.store, self)
        self.worker.result.connect(self.checked)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    @Slot(dict)
    def checked(self, catalog):
        if self.closing: return
        self.catalog = catalog
        self.fill()
        message = "Checked " + catalog["checked_at"] + " · " + str(len(catalog["entries"])) + " components · " + catalog["commit"][:12]
        if catalog["issues"]: message += "\nSkipped entries: " + "; ".join(catalog["issues"][:8])
        self.status.setText(message)
        updates = [e["manifest"]["name"] for e in catalog["entries"] if "update available" in describe_entry(self.manager, e, catalog["repository"])]
        self.window.notify("Component updates: " + ", ".join(updates) if updates else "Component store is up to date")

    @Slot(str)
    def failed(self, message):
        if not self.closing:
            self.status.setText(message + ("\nShowing the last cached catalogue." if self.catalog else ""))

    @Slot()
    def finished(self):
        worker, self.worker = self.worker, None
        if worker is not None: worker.deleteLater()
        self.check_button.setEnabled(True); self.save_button.setEnabled(True)

    def entry(self):
        item = self.list.currentItem()
        ident = item.data(Qt.UserRole) if item else None
        return next((e for e in (self.catalog or {}).get("entries", []) if e["manifest"]["id"] == ident), None)

    def fill(self, *_):
        selected = self.entry()
        self.list.blockSignals(True); self.list.clear()
        for entry in (self.catalog or {}).get("entries", []):
            m = entry["manifest"]
            if self.search.text().casefold() not in (m["name"] + " " + m["id"] + " " + m.get("description", "") + " " + m["type"]).casefold(): continue
            state = describe_entry(self.manager, entry, self.catalog["repository"])
            item = QListWidgetItem(m["name"] + " · " + m["version"] + "\n" + state)
            item.setData(Qt.UserRole, m["id"]); self.list.addItem(item)
        self.list.blockSignals(False)
        index = next((i for i in range(self.list.count()) if selected and self.list.item(i).data(Qt.UserRole) == selected["manifest"]["id"]), 0)
        self.list.setCurrentRow(index)
        self.select()
        if self.catalog and self.status.text() == "No repository check yet":
            self.status.setText("Cached catalogue from " + self.catalog["checked_at"] + " · checking on startup is " + ("on" if self.auto_check.isChecked() else "off"))

    def select(self, *_):
        entry = self.entry()
        self.files.blockSignals(True); self.files.clear()
        self.download_button.setEnabled(entry is not None)
        self.install_button.setEnabled(bool(entry and self.manager.registry.get(entry["manifest"]["id"]) and self.manager.paths.source(entry["manifest"]["id"]).exists()))
        if entry:
            self.files.addItems(sorted(entry["files"]))
            m = entry["manifest"]
            result = validate(entry["files"], m, self.manager.environment)
            self.overview.setPlainText(m["name"] + " " + m["version"] + "\n" + m.get("description", "") + "\n\n" +
                describe_entry(self.manager, entry, self.catalog["repository"]) + "\nRepository: " + self.catalog["repository"] +
                "\nCommit: " + self.catalog["commit"] + "\n\nPermissions:\n" + "\n".join(m.get("permissions", [])) +
                "\n\nDependencies:\n" + json.dumps(m.get("dependencies", {}), indent=2) +
                "\n\nValidation:\n" + json.dumps(result, indent=2) + "\n\nSource destination: " + str(self.manager.paths.source(m["id"])))
            self.download_button.setText("Download / Update Source" if self.manager.paths.source(m["id"]).exists() else "Download source")
        else:
            self.overview.setPlainText("No matching components. Check the repository or change your search.")
            self.source.clear()
        self.files.blockSignals(False)
        self.show_file()

    def show_file(self, *_):
        entry = self.entry()
        self.source.setPlainText(entry["files"].get(self.files.currentText(), "") if entry else "")

    def download(self):
        entry = self.entry()
        if entry is None: return
        if not self.window.discard_editor(): return
        plan = self.manager.plan_store_download(entry["files"], self.catalog["repository"], self.catalog["commit"])
        review = "Download development source only. No dependencies are installed and no component code is run.\nPrevious source is retained in source-backups. Local edits are protected.\n\n" + json.dumps({k: v for k, v in plan.items() if k != "record"}, indent=2) + "\n\n" + encode(entry["files"], entry["manifest"])
        if self.window.confirm("Review store source", review, "Download Source"):
            self.manager.download_store_source(entry["files"], plan)
            self.window.current_id = plan["id"]
            self.window.refresh(); self.fill()
            self.window.notify("Source downloaded. Install / Update Installed Version applies it after review.")

    def install(self):
        entry = self.entry()
        if entry:
            self.window.select_id(entry["manifest"]["id"])
            self.window.install_selected()
            self.fill()

    def shutdown(self):
        self.closing = True
        if self.worker is not None:
            self.worker.store.cancelled.set()
            return self.worker.wait(2000)
        return True

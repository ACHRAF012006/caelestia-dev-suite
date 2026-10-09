"""A simple app store with integrated installs and saved-version recovery."""
import json

from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot, QSize
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
                              QListWidget, QListWidgetItem, QSplitter, QComboBox, QFrame)
from app.component_icons import ComponentIcons
from backend.codex.package import encode
from backend.paths import SafetyError
from backend.store import Store, DEFAULT_REPOSITORY
from backend.validators import validate
from backend import host_integration


class StoreCheck(QThread):
    result = Signal(dict)
    failed = Signal(str)

    def __init__(self, store, parent):
        super().__init__(parent)
        self.store = Store(store.paths)
        self.store.settings = dict(store.settings)

    def run(self):
        try: self.result.emit(self.store.scan())
        except Exception as error: self.failed.emit(str(error))


class StorePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.manager = window, window.manager
        self.store = Store(self.manager.paths)
        self.store.settings = {"repository": DEFAULT_REPOSITORY, "branch": "main",
                               "check_on_startup": self.store.settings["check_on_startup"]}
        self.catalog, self.worker = self.store.cached(), None
        self.closing, self.busy = False, False
        self.component_icons = ComponentIcons()
        self.last_error = ""
        self.setStyleSheet("""
            QFrame#storeDetail { background: #202631; border: 1px solid #303a48; border-radius: 16px; }
            QFrame#storeDetail QLabel, QWidget#storeListCard, QWidget#storeListCard QLabel { background: transparent; border: none; }
            QLabel#storeAppName { font-size: 26px; font-weight: 600; }
            QLabel#storeCardName { font-size: 16px; font-weight: 600; }
            QLabel#storeMuted { color: #a4afc0; }
            QLabel#storeBadge { color: #c3d0ec; }
            QPushButton#primary { min-height: 30px; font-size: 15px; }
            QListWidget#storeApps::item { padding: 0; margin: 4px 0; }
        """)
        layout = QVBoxLayout(self); layout.setContentsMargins(26, 22, 26, 22); layout.setSpacing(16)
        heading = QHBoxLayout()
        title = QLabel("Component Store"); title.setObjectName("title"); heading.addWidget(title, 1)
        self.check_button = QPushButton("Refresh"); self.check_button.setMinimumHeight(44)
        self.check_button.clicked.connect(lambda: window.guard(self.check))
        heading.addWidget(self.check_button); layout.addLayout(heading)
        layout.addWidget(self.label("Find useful apps for your desktop. Install, update or go back to a saved version.", "storeMuted"))
        tools = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Search apps…"); self.search.setMinimumHeight(32)
        self.search.textChanged.connect(self.fill); tools.addWidget(self.search, 1)
        self.filter = QComboBox(); self.filter.addItems(["All apps", "Installed", "Updates"])
        self.filter.setMinimumHeight(32); self.filter.currentIndexChanged.connect(self.fill); tools.addWidget(self.filter)
        layout.addLayout(tools)
        self.status = self.label("Apps are checked automatically when you open Dev Manager." if self.store.settings["check_on_startup"] else "Choose Refresh to check for new apps and updates.", "storeMuted")
        layout.addWidget(self.status)
        split = QSplitter()
        self.list = QListWidget(); self.list.setObjectName("storeApps"); self.list.setMinimumWidth(260)
        self.list.setAccessibleName("Available apps"); self.list.currentItemChanged.connect(self.select)
        split.addWidget(self.list)
        details = QFrame(); details.setObjectName("storeDetail")
        body = QVBoxLayout(details); body.setContentsMargins(24, 24, 24, 24); body.setSpacing(16)
        self.app_icon = QLabel(); self.app_icon.setFixedSize(80, 80); body.addWidget(self.app_icon)
        self.app_name = self.label("Choose an app", "storeAppName"); body.addWidget(self.app_name)
        self.description = self.label("Select an app to see what it does."); body.addWidget(self.description)
        self.version = self.label("", "storeMuted"); body.addWidget(self.version)
        self.state_label = self.label("", "storeBadge"); body.addWidget(self.state_label)
        self.hint = self.label("", "storeMuted"); body.addWidget(self.hint); body.addStretch(1)
        self.install_button = QPushButton("Install"); self.install_button.setObjectName("primary")
        self.install_button.setMinimumHeight(48); self.install_button.clicked.connect(lambda: window.guard(self.install))
        body.addWidget(self.install_button)
        self.previous_button = QPushButton("Previous version"); self.previous_button.setMinimumHeight(42)
        self.previous_button.clicked.connect(lambda: window.guard(self.rollback)); body.addWidget(self.previous_button)
        self.details_button = QPushButton("More details")
        self.details_button.clicked.connect(lambda: window.guard(self.show_details)); body.addWidget(self.details_button)
        split.addWidget(details); split.setStretchFactor(0, 1); split.setStretchFactor(1, 1)
        layout.addWidget(split, 1)
        self.fill()
        if self.manager.runtime.real and self.store.settings["check_on_startup"]:
            QTimer.singleShot(300, lambda: window.guard(self.check) if not self.closing else None)

    @staticmethod
    def label(text, name=""):
        item = QLabel(text); item.setTextFormat(Qt.PlainText); item.setWordWrap(True)
        if name: item.setObjectName(name)
        return item

    def app_state(self, entry):
        ident = entry["manifest"]["id"]
        record = self.manager.registry.get(ident)
        installed = bool(record and record.get("installed"))
        update = installed and record.get("installed_source_hash") != entry["hash"]
        protected = False
        if self.manager.paths.source(ident).exists():
            if ident in self.window.source_fingerprints:
                local = self.window.source_fingerprints[ident]
            else:
                local = self.manager.source_hash(self.manager.read_source(ident))
            origin = (record or {}).get("store_origin", {})
            protected = local != entry["hash"] and (origin.get("repository") != self.store.settings["repository"] or origin.get("hash") != local)
        launchable = installed and record["installed_manifest"]["type"] in {"standalone-app", "script", "user-service"} and (record.get("enabled") or record["installed_manifest"]["type"] == "user-service")
        if protected: return {"label": "Local changes protected", "action": "Open" if launchable else "Installed" if installed else "Install", "enabled": bool(launchable), "installed": installed, "update": update, "protected": True}
        if not installed: return {"label": "Ready to install", "action": "Install", "enabled": True, "installed": False, "update": False, "protected": False}
        if update: return {"label": "Update available", "action": "Update", "enabled": True, "installed": True, "update": True, "protected": False}
        return {"label": "Installed" if record.get("enabled") else "Installed · Disabled", "action": "Open" if launchable else "Installed", "enabled": bool(launchable), "installed": True, "update": False, "protected": False}

    def app_image(self, entry, size=80):
        manifest = entry["manifest"]
        svg = entry["files"].get(manifest.get("desktop", {}).get("icon") or "assets/icon.svg", "")
        return self.component_icons.pixmap(manifest, svg, size, self.devicePixelRatioF())

    def set_startup_check(self, checked):
        self.store.save_settings(DEFAULT_REPOSITORY, "main", checked)

    def check(self):
        if self.worker is not None or self.closing or self.busy: return
        self.status.setText("Checking for new apps and updates…"); self.check_button.setEnabled(False)
        self.worker = StoreCheck(self.store, self)
        self.worker.result.connect(self.checked); self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished); self.worker.start()

    @Slot(dict)
    def checked(self, catalog):
        if self.closing: return
        self.catalog = catalog; self.last_error = ""; self.fill()
        count = len(catalog["entries"])
        self.status.setText(str(count) + (" app available" if count == 1 else " apps available") + " · Up to date")
        updates = sum(self.app_state(e)["update"] for e in catalog["entries"])
        if updates: self.status.setText(str(updates) + (" update available" if updates == 1 else " updates available"))
        if catalog["issues"]: self.status.setText(self.status.text() + " · Some apps could not be loaded")
        self.window.notify("App store refreshed")

    @Slot(str)
    def failed(self, message):
        if not self.closing:
            self.last_error = message
            self.status.setText("Could not refresh. Showing saved apps." if self.catalog else "Store unavailable. Check your connection or GitHub access, then Refresh.")

    @Slot()
    def finished(self):
        worker, self.worker = self.worker, None
        if worker is not None: worker.deleteLater()
        self.check_button.setEnabled(not self.busy)

    def entry(self):
        item = self.list.currentItem()
        ident = item.data(Qt.UserRole) if item else None
        return next((e for e in (self.catalog or {}).get("entries", []) if e["manifest"]["id"] == ident), None)

    def fill(self, *_):
        selected = self.entry(); self.list.blockSignals(True); self.list.clear()
        for entry in (self.catalog or {}).get("entries", []):
            m, state = entry["manifest"], self.app_state(entry)
            if self.search.text().casefold() not in (m["name"] + " " + m["id"] + " " + m.get("description", "") + " " + m["type"]).casefold(): continue
            if self.filter.currentText() == "Installed" and not state["installed"]: continue
            if self.filter.currentText() == "Updates" and not state["update"]: continue
            item = QListWidgetItem(); item.setData(Qt.UserRole, m["id"]); item.setSizeHint(QSize(280, 176))
            item.setData(Qt.AccessibleTextRole, m["name"] + ". " + state["label"]); self.list.addItem(item)
            card = QWidget(); card.setObjectName("storeListCard"); card.setAttribute(Qt.WA_TransparentForMouseEvents)
            row = QHBoxLayout(card); row.setContentsMargins(12, 14, 12, 14)
            image = QLabel(); image.setFixedSize(56, 56); image.setPixmap(self.app_image(entry, 56))
            row.addWidget(image)
            labels = QVBoxLayout(); labels.setSpacing(6)
            labels.addWidget(self.label(m["name"], "storeCardName"))
            description = m.get("description", "Desktop component")
            labels.addWidget(self.label(description if len(description) <= 120 else description[:117].rstrip() + "…", "storeMuted"))
            labels.addWidget(self.label(state["label"], "storeBadge")); row.addLayout(labels, 1)
            self.list.setItemWidget(item, card)
        self.list.blockSignals(False)
        index = next((i for i in range(self.list.count()) if selected and self.list.item(i).data(Qt.UserRole) == selected["manifest"]["id"]), 0)
        self.list.setCurrentRow(index); self.select()

    def select(self, *_):
        entry = self.entry(); self.details_button.setEnabled(entry is not None and not self.busy)
        self.previous_button.hide()
        if entry is None:
            self.app_icon.clear(); self.app_name.setText("Choose an app")
            self.description.setText("No apps match your search." if self.catalog else "Refresh to discover apps.")
            self.version.clear(); self.state_label.clear(); self.hint.clear(); self.install_button.setEnabled(False)
            return
        m, state = entry["manifest"], self.app_state(entry)
        record = self.manager.registry.get(m["id"])
        self.app_icon.setPixmap(self.app_image(entry)); self.app_name.setText(m["name"])
        self.description.setText(m.get("description", ""))
        self.version.setText("Latest version " + m["version"] + (" · Installed " + record["installed_version"] if state["installed"] else ""))
        self.state_label.setText(state["label"])
        self.hint.setText("Your local changes will be kept. Resolve them in Components before updating." if state["protected"] else "You'll review permissions before installation. Previous versions are saved automatically when you update.")
        self.install_button.setText(state["action"]); self.install_button.setEnabled(state["enabled"] and not self.busy)
        previous = self.manager.previous_version_backup(m["id"], self.window.backup_metadata)
        if previous:
            self.previous_button.setText("Previous version · " + str(previous["version"]))
            self.previous_button.setVisible(True); self.previous_button.setEnabled(not self.busy)

    def install(self):
        entry = self.entry()
        if entry is None or self.busy: return
        state = self.app_state(entry)
        if not state["enabled"]: return
        ident = entry["manifest"]["id"]
        if state["action"] == "Open":
            self.window.select_id(ident); self.window.launch_selected(); return
        result = validate(entry["files"], entry["manifest"], self.manager.environment)
        if not result["valid"]: raise SafetyError("This app cannot be installed yet:\n" + "\n".join(result["errors"]))
        plan = self.manager.plan_store_download(entry["files"], self.catalog["repository"], self.catalog["commit"])
        self.busy = True; self.window.nav.setEnabled(False); self.check_button.setEnabled(False); self.select()
        try:
            origin = (plan["record"] or {}).get("store_origin", {})
            if plan["before"] != plan["hash"] or origin.get("repository") != plan["repository"]:
                self.status.setText("Downloading " + entry["manifest"]["name"] + "…")
                self.manager.download_store_source(entry["files"], plan)
            self.window.current_id = ident; self.window.refresh(); self.window.select_id(ident)
            installed = self.window.install_selected()
            self.status.setText(entry["manifest"]["name"] + (" updated." if state["update"] else " installed.") if installed else "Installation cancelled. No installed files were changed.")
        finally:
            self.busy = False; self.window.nav.setEnabled(True)
            self.check_button.setEnabled(self.worker is None); self.fill()

    def rollback(self):
        entry = self.entry()
        if entry is None or self.busy: return
        previous = self.manager.previous_version_backup(entry["manifest"]["id"])
        if previous is None: self.window.notify("No previous version is available yet"); return
        meta, record, entries, remove = self.manager.plan_restore(previous["backup_id"])
        options = QWidget()
        options.summary_text = ("Restore " + entry["manifest"]["name"] + " " + str(meta["version"]) + "?\n\nYour current installation is backed up first. Your settings and current development source are kept.\n\nClose and reopen the app after restoring. Background services will need to be started again.")
        details = "RESTORE " + meta["component_id"] + "\n" + "\n".join("WRITE " + str(f.path) for f in entries) + "\n" + "\n".join("REMOVE " + f["path"] for f in remove)
        host = host_integration.plan(self.manager.paths, meta["record"]["installed_manifest"])
        if host:
            options.summary_text += "\n\n" + host["summary"] + " Caelestia KDE will restart."
            details += "\n\n" + json.dumps(host, indent=2)
        if self.window.confirm("Go back to previous version", details, "Restore Version", options):
            self.manager.restore(meta["backup_id"]); self.window.refresh(); self.fill()
            self.status.setText("Version " + str(meta["version"]) + " restored. Close and reopen the app to use it.")

    def show_details(self):
        entry = self.entry()
        if entry:
            m = entry["manifest"]
            text = m["name"] + " " + m["version"] + "\n\nPermissions\n" + "\n".join(m.get("permissions", []))
            text += "\n\nRequired libraries\n" + json.dumps(m.get("dependencies", {}), indent=2)
            text += "\n\nRepository: " + self.catalog["repository"] + "\nCommit: " + self.catalog["commit"]
            if self.last_error: text += "\n\nLast refresh error\n" + self.last_error
            text += "\n\n" + encode(entry["files"], m)
            self.window.show_text("About " + m["name"], text)

    def shutdown(self):
        self.closing = True
        if self.worker is not None:
            self.worker.store.cancelled.set(); return self.worker.wait(2000)
        return True

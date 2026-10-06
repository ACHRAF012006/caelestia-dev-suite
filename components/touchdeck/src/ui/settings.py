import copy
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QTabWidget, QLineEdit,
                              QComboBox, QCheckBox, QSpinBox, QListWidget, QLabel, QMessageBox, QInputDialog)
from models.config import page, preset, uid
from services import display
from ui.common import FormDialog, button
from ui.editor import TileEditor


class Settings(FormDialog):
    def __init__(self, window):
        super().__init__("TouchDeck settings", window)
        self.window = window
        self.data = copy.deepcopy(window.config.data)
        tabs = QTabWidget()
        self.form_layout.addWidget(tabs)
        self.forms = {}
        for title in ("General", "Display", "Appearance", "Pages", "Audio", "Media", "Launchers", "Actions", "Startup", "Advanced"):
            widget = QWidget()
            layout = QFormLayout(widget)
            self.forms[title] = layout
            tabs.addTab(widget, title)
        self.quickbar = QCheckBox("Show persistent page bar")
        self.quickbar.setChecked(self.data["quickbar"])
        self.idle = QSpinBox()
        self.idle.setRange(0, 86400)
        self.idle.setValue(self.data["idle_seconds"])
        self.idle.setSuffix(" seconds (0 disables)")
        self.forms["General"].addRow(self.quickbar)
        self.forms["General"].addRow("Idle clock", self.idle)
        self.screen = QComboBox()
        self.screen.addItem("Automatic: secondary display / safe fallback", "")
        for screen in display.screens():
            self.screen.addItem(screen.name() + " · " + str(screen.size().width()) + "×" + str(screen.size().height()), display.screen_id(screen))
        self.screen.setCurrentIndex(max(0, self.screen.findData(self.data["screen"])))
        self.mode = QComboBox()
        self.mode.addItems(["Windowed", "Borderless", "Fullscreen"])
        self.mode.setCurrentText(self.data["mode"])
        self.forms["Display"].addRow("Open on display", self.screen)
        self.forms["Display"].addRow("Startup and current mode", self.mode)
        self.hide_bars = QCheckBox("Hide top and page bars in fullscreen")
        self.hide_bars.setChecked(self.data.get("fullscreen_hide_bars", True))
        self.forms["Display"].addRow(self.hide_bars)
        self.forms["Display"].addRow(QLabel("Fullscreen stays on the chosen display. Menu reveals the controls.\nF11 toggles fullscreen; Escape returns to a window.\nIf the display disappears, use a secondary display or a safe window."))
        self.theme = QComboBox()
        self.theme.addItems(["Dark", "OLED Dark", "Light"])
        self.theme.setCurrentText(self.data["theme"])
        self.accent = QLineEdit(self.data["accent"])
        self.forms["Appearance"].addRow("Theme", self.theme)
        self.forms["Appearance"].addRow("Accent #RRGGBB", self.accent)
        self.pages = QListWidget()
        self.pages.setMinimumHeight(160)
        self.forms["Pages"].addRow(self.pages)
        self.page_name = QLineEdit()
        self.grid = QComboBox()
        self.grid.addItems(["3x2", "4x2", "4x3", "5x3", "6x4"])
        self.forms["Pages"].addRow("Name", self.page_name)
        self.forms["Pages"].addRow("Maximum columns × visible rows", self.grid)
        row = QWidget()
        controls = QHBoxLayout(row)
        for text, callback in (("New", self.new_page), ("Copy", self.copy_page), ("Delete", self.delete_page), ("↑", lambda: self.move(-1)), ("↓", lambda: self.move(1))):
            controls.addWidget(button(text, callback))
        self.forms["Pages"].addRow(row)
        self.forms["Pages"].addRow(button("Apply page name/grid", self.apply_page))
        self.pages.currentRowChanged.connect(self.load_page)
        self.fill_pages()
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("Gaming, Music, Movie, Voice Chat, Night…")
        self.profiles = QListWidget()
        self.forms["Audio"].addRow("Save current mix as", self.profile_name)
        self.forms["Audio"].addRow(button("Capture audio profile", self.capture_profile))
        self.forms["Audio"].addRow(self.profiles)
        self.forms["Audio"].addRow(button("Delete selected profile", self.delete_profile))
        self.forms["Audio"].addRow(QLabel("Place a profile button through Edit → Add → button → profile.\nOnly currently active application streams are captured.\nMissing devices/streams are skipped; profiles do not reroute existing streams."))
        self.fill_profiles()
        self.auto = QCheckBox("Automatically choose playing media player")
        self.auto.setChecked(self.data["auto_player"])
        self.forms["Media"].addRow(self.auto)
        self.forms["Media"].addRow(QLabel("Choose a specific player from any Now Playing widget.\nArtwork uses local files only; remote artwork is not downloaded."))
        self.forms["Launchers"].addRow(QLabel("Edit → Add → button → launch → Choose application.\nThe picker searches XDG .desktop entries and uses application icons.\nDesktop activation/foreground behavior depends on the application and Wayland."))
        self.forms["Actions"].addRow(QLabel("Edit → Add → button to configure an action or sequential macro.\nMacros use the built-in action editor, up to 32 steps, with explicit delays.\nAdvanced commands show their argument list and require runtime confirmation."))
        self.forms["Actions"].addRow(button("Cancel remaining macro steps", window.actions.cancel))
        self.startup = QCheckBox("Start TouchDeck on login (off by default)")
        try:
            self.startup.setChecked(display.autostart_enabled())
        except OSError:
            self.startup.setEnabled(False)
        self.initial_startup = self.startup.isChecked()
        self.forms["Startup"].addRow(self.startup)
        self.forms["Startup"].addRow(QLabel("Uses the installed user launcher and TryExec.\nDisable or uninstall in Dev Manager prevents future automatic launches.\nTurn this off here to remove TouchDeck's user autostart preference."))
        self.forms["Advanced"].addRow(button("Reveal logs", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(window.log_path.parent)))))
        self.forms["Advanced"].addRow(button("Reveal configuration", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(window.config.path.parent)))))
        self.forms["Advanced"].addRow(QLabel("Configuration: " + str(window.config.path) + "\nBackups are automatic; Undo retains 20 edits for this session."))
        self.buttons.accepted.connect(self.save)

    def fill_pages(self, index=0):
        self.pages.clear()
        self.pages.addItems([p["name"] for p in self.data["pages"]])
        self.pages.setCurrentRow(min(index, len(self.data["pages"]) - 1))

    def load_page(self, index):
        if index >= 0:
            p = self.data["pages"][index]
            self.page_name.setText(p["name"])
            value = str(p["cols"]) + "x" + str(p["rows"])
            if self.grid.findText(value) < 0:
                self.grid.addItem(value)
            self.grid.setCurrentText(value)

    def apply_page(self):
        index = self.pages.currentRow()
        if index >= 0:
            p = self.data["pages"][index]
            p["name"] = self.page_name.text().strip() or "Page"
            p["cols"], p["rows"] = map(int, self.grid.currentText().split("x"))
            self.fill_pages(index)

    def new_page(self):
        if len(self.data["pages"]) < 32:
            name, ok = QInputDialog.getItem(self, "New page", "Preset", ["Custom", "Home", "Audio", "Media", "Gaming"], 0, False)
            if ok:
                self.data["pages"].append(page("Custom") if name == "Custom" else preset(name))
                self.fill_pages(len(self.data["pages"]) - 1)

    def copy_page(self):
        index = self.pages.currentRow()
        if index >= 0 and len(self.data["pages"]) < 32:
            p = copy.deepcopy(self.data["pages"][index])
            p["name"] += " copy"
            for item in [p, *p["tiles"]]:
                item["id"] = uid()
            self.data["pages"].insert(index + 1, p)
            self.fill_pages(index + 1)

    def delete_page(self):
        index = self.pages.currentRow()
        if index >= 0 and len(self.data["pages"]) > 1 and QMessageBox.question(self, "Delete page?", "Delete this page and its widgets?", QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Yes:
            self.data["pages"].pop(index)
            self.fill_pages()

    def move(self, direction):
        index, target = self.pages.currentRow(), self.pages.currentRow() + direction
        if index >= 0 and 0 <= target < len(self.data["pages"]):
            self.data["pages"][index], self.data["pages"][target] = self.data["pages"][target], self.data["pages"][index]
            self.fill_pages(target)

    def fill_profiles(self):
        self.profiles.clear()
        self.profiles.addItems(sorted(self.data["profiles"]))

    def capture_profile(self):
        name = self.profile_name.text().strip()
        if name and self.window.audio.state.get("available"):
            self.data["profiles"][name] = self.window.audio.profile()
            self.fill_profiles()
        else:
            QMessageBox.warning(self, "Profile unavailable", "Enter a name and connect to audio first")

    def delete_profile(self):
        item = self.profiles.currentItem()
        if item:
            self.data["profiles"].pop(item.text(), None)
            self.fill_profiles()

    def save(self):
        try:
            self.apply_page()
            self.data.update(theme=self.theme.currentText(), accent=self.accent.text().strip(), quickbar=self.quickbar.isChecked(),
                             fullscreen_hide_bars=self.hide_bars.isChecked(), idle_seconds=self.idle.value(),
                             screen=self.screen.currentData(), mode=self.mode.currentText(), auto_player=self.auto.isChecked())
            self.window.commit(self.data)
            if self.startup.isEnabled() and self.startup.isChecked() != self.initial_startup:
                display.set_autostart(self.startup.isChecked())
            self.accept()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot apply settings", str(error))

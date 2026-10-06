import copy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWizard, QWizardPage, QVBoxLayout, QLabel, QComboBox, QListWidget, QListWidgetItem
from models.config import preset, page, tile
from services.display import screens, screen_id
from ui.common import icon


class SetupWizard(QWizard):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Welcome to TouchDeck")
        self.resize(min(700, window.width() - 24), min(500, window.height() - 24))
        self.setButtonText(QWizard.CancelButton, "Skip setup")
        def step(title, description):
            p = QWizardPage()
            p.setTitle(title)
            layout = QVBoxLayout(p)
            label = QLabel(description)
            label.setWordWrap(True)
            layout.addWidget(label)
            self.addPage(p)
            return layout
        step("Welcome to TouchDeck", "Your independent touchscreen control center. Tap to act, long-press to edit, and swipe horizontally between pages. All controls can be customized without changing source files.")
        display = step("Choose display", "Start safely in a window. Fullscreen and borderless modes are available in Settings → Display.")
        self.screen = QComboBox()
        self.screen.addItem("Automatic secondary display", "")
        for screen in screens():
            self.screen.addItem(screen.name(), screen_id(screen))
        display.addWidget(self.screen)
        layout = step("Choose layout", "Choose a starting layout. Add, resize and move widgets later through Edit Mode.")
        self.layout = QComboBox()
        self.layout.addItems(["Simple", "Media", "Gaming", "Custom"])
        layout.addWidget(self.layout)
        apps = step("Choose useful launchers", "Select installed applications for your Home page. You can add others at any time.")
        self.apps = QListWidget()
        for app in sorted(window.apps.apps.values(), key=lambda x: x["name"].casefold()):
            item = QListWidgetItem(icon(app["icon"]), app["name"])
            item.setData(Qt.UserRole, app["id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if app["name"].casefold() in ("steam", "discord", "firefox") else Qt.Unchecked)
            self.apps.addItem(item)
        apps.addWidget(self.apps)
        step("Ready", "TouchDeck runs independently of Dev Manager. Autostart is off. Audio and media services are optional and unavailable features show their status.")

    def result_config(self):
        data = copy.deepcopy(self.window.config.data)
        data["first_run"] = False
        if self.result() == QWizard.Accepted:
            data["screen"] = self.screen.currentData()
            name = self.layout.currentText()
            if name == "Custom":
                data["pages"] = [page("Home")]
            elif name == "Gaming":
                data["pages"] = [preset("Home"), preset("Gaming"), preset("Audio"), preset("Media")]
            elif name == "Media":
                data["pages"] = [preset("Media"), preset("Home"), preset("Audio")]
            else:
                data["pages"] = [preset("Home"), preset("Audio"), preset("Media")]
            home = next((p for p in data["pages"] if p["name"] == "Home"), data["pages"][0])
            for index in range(self.apps.count()):
                item = self.apps.item(index)
                if item.checkState() == Qt.Checked:
                    app = self.window.apps.apps[item.data(Qt.UserRole)]
                    entry = tile("button", app["name"], action={"type": "launch", "value": app["id"]})
                    home["tiles"].append(entry)
        return data

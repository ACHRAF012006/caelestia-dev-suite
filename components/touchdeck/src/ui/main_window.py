import copy
import time
from datetime import datetime
from PySide6.QtCore import Qt, QEvent, QTimer, QPoint
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
                              QApplication, QMenu, QMessageBox, QSlider, QComboBox, QLineEdit, QScrollArea, QAbstractButton)
from models.actions import Actions
from models.config import uid
from services import display
from ui.common import button, scroll, TouchButton, set_icon_theme
from ui.dashboard import Dashboard
from ui.editor import TileEditor
from ui.settings import Settings
from ui.theme import stylesheet
from ui.wizard import SetupWizard
from ui.widgets import Tile, MixerPanel


class MainWindow(QMainWindow):
    def __init__(self, config, apps, audio, media, monitor, log_path):
        super().__init__()
        self.config, self.apps, self.audio, self.media, self.monitor, self.log_path = config, apps, audio, media, monitor, log_path
        self.page_index, self.edit_mode = 0, False
        self.controls_revealed = False
        self.was_fullscreen = False
        self.last_touch = time.monotonic()
        self.press_origin = None
        self.press_widget = None
        self.hold_timer = QTimer(self)
        self.hold_timer.setSingleShot(True)
        self.hold_timer.setInterval(650)
        self.hold_timer.timeout.connect(self.hold_tile)
        self.setWindowTitle("TouchDeck")
        self.setMinimumSize(480, 320)
        self.resize(1024, 600)
        self.actions = Actions(self)
        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        self.header = QWidget()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(0, 0, 0, 0)
        self.page_title = QLabel("TouchDeck")
        self.page_title.setTextFormat(Qt.PlainText)
        header.addWidget(self.page_title, 1)
        header.addWidget(button("‹", lambda: self.advance(-1)))
        header.addWidget(button("›", lambda: self.advance(1)))
        self.edit_button = button("Edit", self.toggle_edit)
        self.edit_button.setCheckable(True)
        header.addWidget(self.edit_button)
        self.add_button = button("Add", lambda: self.edit_tile(None))
        header.addWidget(self.add_button)
        self.undo_button = button("Undo", self.undo)
        header.addWidget(self.undo_button)
        header.addWidget(button("Settings", self.open_settings))
        self.fullscreen_button = button("Fullscreen", self.toggle_fullscreen)
        header.addWidget(self.fullscreen_button)
        self.hide_bars_button = button("Hide bars", self.hide_controls)
        header.addWidget(self.hide_bars_button)
        layout.addWidget(self.header)
        self.stack = QStackedWidget()
        self.dashboard = Dashboard(self)
        self.stack.addWidget(self.dashboard)
        idle = QWidget()
        idle_layout = QVBoxLayout(idle)
        self.idle_clock = QLabel()
        self.idle_clock.setAlignment(Qt.AlignCenter)
        self.idle_clock.setStyleSheet("font-size: 54px; color: #87919f; background: #080a0e;")
        self.idle_info = QLabel()
        self.idle_info.setTextFormat(Qt.PlainText)
        self.idle_info.setAlignment(Qt.AlignCenter)
        self.idle_info.setWordWrap(True)
        self.idle_info.setStyleSheet("font-size: 24px; color: #87919f; background: #080a0e;")
        idle.setStyleSheet("background: #080a0e;")
        idle_layout.addWidget(self.idle_clock, 2)
        idle_layout.addWidget(self.idle_info, 1)
        self.stack.addWidget(idle)
        self.mixer_panel = MixerPanel(self)
        self.stack.addWidget(self.mixer_panel)
        layout.addWidget(self.stack, 1)
        self.quick_body = QWidget()
        self.quick_layout = QHBoxLayout(self.quick_body)
        self.quick_layout.setContentsMargins(0, 0, 0, 0)
        self.quick_area = scroll(self.quick_body)
        self.quick_area.setFixedHeight(64)
        self.quick_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.quick_area)
        self.menu_button = button("Menu", self.show_controls)
        self.menu_button.setParent(container)
        self.menu_button.setFixedSize(84, 48)
        self.menu_button.setAccessibleName("Show navigation, Settings and Edit")
        self.menu_button.hide()
        self.toast_label = QLabel(self)
        self.toast_label.setTextFormat(Qt.PlainText)
        self.toast_label.setObjectName("toast")
        self.toast_label.setWordWrap(True)
        self.toast_label.hide()
        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.timeout.connect(self.toast_label.hide)
        self.tick = QTimer(self)
        self.tick.setInterval(1000)
        self.tick.timeout.connect(self.refresh)
        self.tick.start()
        audio.changed.connect(self.audio_changed)
        media.changed.connect(lambda state: self.dashboard.refresh())
        QApplication.instance().installEventFilter(self)
        QShortcut(QKeySequence("Escape"), self, activated=self.escape)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.toggle_edit)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QApplication.instance().screenRemoved.connect(self.screen_removed)
        self.rebuild()

    def current_page(self):
        pages = self.config.data["pages"]
        self.page_index = max(0, min(self.page_index, len(pages) - 1))
        return pages[self.page_index]

    def start(self):
        display.apply(self, self.config.data)
        if self.config.data["first_run"]:
            QTimer.singleShot(100, self.setup)
        if self.config.notice:
            QTimer.singleShot(400, lambda: self.toast(self.config.notice))

    def setup(self):
        wizard = SetupWizard(self)
        wizard.exec()
        try:
            self.commit(wizard.result_config())
            display.apply(self, self.config.data)
        except (OSError, ValueError) as error:
            self.toast(str(error))

    def commit(self, data):
        self.config.save(data)
        self.rebuild()

    def rebuild(self):
        set_icon_theme(self.config.data["theme"])
        self.setStyleSheet(stylesheet(self.config.data["theme"], self.config.data["accent"]))
        self.page_title.setText(self.current_page()["name"] + " · " + str(self.page_index + 1) + "/" + str(len(self.config.data["pages"])))
        self.add_button.setVisible(self.edit_mode)
        self.undo_button.setVisible(self.edit_mode)
        self.edit_button.setChecked(self.edit_mode)
        while self.quick_layout.count():
            item = self.quick_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        for p in self.config.data["pages"]:
            b = button(p["name"], lambda checked=False, ident=p["id"]: self.switch_page(ident))
            b.setCheckable(True)
            b.setChecked(p["id"] == self.current_page()["id"])
            self.quick_layout.addWidget(b)
        self.quick_layout.addStretch()
        self.dashboard.rebuild()
        self.update_chrome()
        self.last_touch = time.monotonic()

    def update_chrome(self):
        fullscreen = self.isFullScreen()
        if fullscreen != self.was_fullscreen:
            self.controls_revealed = False
            self.was_fullscreen = fullscreen
        clean = fullscreen and self.config.data.get("fullscreen_hide_bars", True)
        dashboard = self.stack.currentIndex() == 0
        show_bars = dashboard and (not clean or self.controls_revealed or self.edit_mode)
        self.header.setVisible(show_bars)
        self.quick_area.setVisible(show_bars and self.config.data["quickbar"])
        self.fullscreen_button.setText("Windowed" if fullscreen else "Fullscreen")
        self.hide_bars_button.setVisible(clean and not self.edit_mode)
        self.menu_button.setVisible(dashboard and clean and not show_bars)
        self.position_menu()

    def position_menu(self):
        self.menu_button.move(max(0, self.centralWidget().width() - 100), max(0, self.centralWidget().height() - 64))
        self.menu_button.raise_()

    def show_controls(self):
        self.controls_revealed = True
        self.update_chrome()

    def hide_controls(self):
        self.controls_revealed = False
        self.update_chrome()

    def toggle_fullscreen(self):
        data = copy.deepcopy(self.config.data)
        data["mode"] = "Windowed" if self.isFullScreen() else "Fullscreen"
        if data["mode"] == "Fullscreen" and self.screen():
            # An explicit toggle targets the screen already hosting TouchDeck.
            data["screen"] = display.screen_id(self.screen())
        try:
            self.commit(data)
            display.apply(self, data)
            self.update_chrome()
        except (OSError, ValueError) as error:
            self.toast(str(error))

    def open_mixer(self):
        self.mixer_panel.mixer.refresh()
        self.mixer_panel.mixer.area.verticalScrollBar().setValue(0)
        self.stack.setCurrentIndex(2)
        self.last_touch = time.monotonic()
        self.update_chrome()

    def close_mixer(self):
        self.stack.setCurrentIndex(0)
        self.last_touch = time.monotonic()
        self.update_chrome()

    def escape(self):
        if self.stack.currentIndex() == 2:
            self.close_mixer()
        else:
            self.windowed()

    def audio_changed(self, state):
        self.dashboard.refresh()
        if self.stack.currentIndex() == 2:
            self.mixer_panel.mixer.refresh()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and hasattr(self, "menu_button"):
            QTimer.singleShot(0, self.update_chrome)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "menu_button"):
            self.position_menu()

    def switch_page(self, ident):
        index = next((i for i, p in enumerate(self.config.data["pages"]) if p["id"] == ident), None)
        if index is None:
            return False
        self.page_index = index
        self.rebuild()
        return True

    def advance(self, direction):
        self.page_index = (self.page_index + direction) % len(self.config.data["pages"])
        self.rebuild()

    def toggle_edit(self):
        self.edit_mode = not self.edit_mode
        self.controls_revealed = False
        self.rebuild()

    def edit_tile(self, item):
        TileEditor(self, item).exec()

    def tile_menu(self, item, widget):
        menu = QMenu(self)
        menu.addAction("Edit / move / resize", lambda: self.edit_tile(item))
        menu.addAction("Duplicate", lambda: self.modify_tile(item, "duplicate"))
        menu.addAction("Move earlier", lambda: self.modify_tile(item, "earlier"))
        menu.addAction("Move later", lambda: self.modify_tile(item, "later"))
        menu.addAction("Remove", lambda: self.modify_tile(item, "remove"))
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(widget.mapToGlobal(QPoint(0, widget.height())))

    def hold_tile(self):
        widget = self.press_widget
        while widget is not None and not isinstance(widget, Tile):
            widget = widget.parentWidget()
        if widget is not None:
            self.press_origin = None
            self.tile_menu(widget.item, widget)

    def modify_tile(self, item, operation):
        data = copy.deepcopy(self.config.data)
        p = data["pages"][self.page_index]
        index = next((i for i, t in enumerate(p["tiles"]) if t["id"] == item["id"]), None)
        if index is None:
            return
        if operation == "duplicate":
            other = copy.deepcopy(item)
            other["id"] = uid()
            p["tiles"].insert(index + 1, other)
        elif operation == "remove":
            p["tiles"].pop(index)
        else:
            target = index + (-1 if operation == "earlier" else 1)
            if 0 <= target < len(p["tiles"]):
                p["tiles"][index], p["tiles"][target] = p["tiles"][target], p["tiles"][index]
        try:
            self.commit(data)
        except (OSError, ValueError) as error:
            self.toast(str(error))

    def undo(self):
        try:
            self.config.undo()
            self.rebuild()
            display.apply(self, self.config.data)
            self.toast("Edit undone")
        except (OSError, ValueError) as error:
            self.toast(str(error))

    def open_settings(self):
        if Settings(self).exec():
            self.controls_revealed = False
            display.apply(self, self.config.data)
            self.update_chrome()

    def windowed(self):
        data = copy.deepcopy(self.config.data)
        data["mode"] = "Windowed"
        try:
            self.commit(data)
            display.apply(self, data)
            self.update_chrome()
        except (OSError, ValueError) as error:
            self.toast(str(error))

    def screen_removed(self, screen):
        QTimer.singleShot(100, lambda: display.apply(self, self.config.data))

    def toast(self, text):
        self.toast_label.setText(text)
        self.toast_label.setFixedWidth(min(560, self.width() - 36))
        self.toast_label.adjustSize()
        self.toast_label.move((self.width() - self.toast_label.width()) // 2, max(10, self.height() - self.toast_label.height() - 84))
        self.toast_label.show()
        self.toast_label.raise_()
        self.toast_timer.start(3500)

    def refresh(self):
        self.dashboard.refresh()
        if self.stack.currentIndex() == 2:
            self.mixer_panel.mixer.refresh()
        timeout = self.config.data["idle_seconds"]
        if timeout and time.monotonic() - self.last_touch > timeout and not self.edit_mode and not QApplication.activeModalWidget():
            self.stack.setCurrentIndex(1)
            self.update_chrome()
        if self.stack.currentIndex() == 1:
            self.idle_clock.setText(datetime.now().strftime("%H:%M\n%A · %d %B"))
            _, props = self.media.selected(self.config.data)
            state = self.monitor.state
            self.idle_info.setText(str(props.get("Metadata", {}).get("xesam:title", "No media playing")) + "\nCPU %.0f%% · RAM %.0f%%\nTouch to return" % (state.get("cpu", 0), state.get("ram", 0)))

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind in (QEvent.MouseButtonPress, QEvent.TouchBegin, QEvent.KeyPress, QEvent.Wheel):
            self.last_touch = time.monotonic()
            if self.stack.currentIndex() == 1:
                self.stack.setCurrentIndex(0)
                self.update_chrome()
                return True
        if isinstance(obj, QWidget) and self.dashboard.isAncestorOf(obj):
            if kind == QEvent.MouseButtonPress and not isinstance(obj, (QSlider, QComboBox, QLineEdit)):
                self.press_origin, self.press_widget = event.globalPosition(), obj
                if not isinstance(obj, QAbstractButton):
                    self.hold_timer.start()
            elif kind == QEvent.MouseMove and self.press_origin is not None:
                delta = event.globalPosition() - self.press_origin
                if delta.manhattanLength() > 18:
                    self.hold_timer.stop()
                if abs(delta.x()) > 50 and isinstance(self.press_widget, TouchButton):
                    self.press_widget.timer.stop()
                    self.press_widget.long_press = True
                    self.press_widget.setDown(False)
            elif kind == QEvent.MouseButtonRelease and self.press_origin is not None:
                self.hold_timer.stop()
                delta = event.globalPosition() - self.press_origin
                self.press_origin = None
                if abs(delta.x()) > 100 and abs(delta.y()) < 70:
                    self.advance(-1 if delta.x() > 0 else 1)
                    return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        self.audio.close()
        self.media.close()
        self.monitor.close()
        super().closeEvent(event)

import copy
import json
import shlex
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
                              QComboBox, QSpinBox, QListWidget, QListWidgetItem, QMessageBox, QCheckBox)
from models.config import ACTION_TYPES, KINDS, MEDIA, POWER, tile, uid, validate_action
from ui.common import FormDialog, button, icon


class AppPicker(FormDialog):
    def __init__(self, window):
        super().__init__("Choose installed application", window)
        self.selected = None
        window.apps.refresh()
        search = QLineEdit()
        search.setPlaceholderText("Search applications")
        self.form_layout.addWidget(search)
        self.list = QListWidget()
        self.list.setMinimumHeight(220)
        self.form_layout.addWidget(self.list)
        self.apps = window.apps
        search.textChanged.connect(self.fill)
        self.buttons.accepted.connect(self.choose)
        self.fill("")

    def fill(self, query):
        self.list.clear()
        for app in sorted(self.apps.apps.values(), key=lambda x: x["name"].casefold()):
            if query.casefold() not in (app["name"] + " " + app["description"]).casefold():
                continue
            item = QListWidgetItem(icon(app["icon"]), app["name"] + ("\n" + app["description"][:90] if app["description"] else ""))
            item.setData(Qt.UserRole, app["id"])
            self.list.addItem(item)

    def choose(self):
        if self.list.currentItem():
            self.selected = self.apps.apps[self.list.currentItem().data(Qt.UserRole)]
            self.accept()


class ActionForm(QWidget):
    def __init__(self, window, action=None, allow_macro=True):
        super().__init__()
        self.window = window
        self.current = copy.deepcopy(action or {"type": "settings"})
        layout = QVBoxLayout(self)
        self.type = QComboBox()
        self.type.addItems([x for x in ACTION_TYPES if allow_macro or x != "macro"])
        layout.addWidget(QLabel("Action type"))
        layout.addWidget(self.type)
        self.details = QWidget()
        self.details_layout = QFormLayout(self.details)
        layout.addWidget(self.details)
        self.delay = QSpinBox()
        self.delay.setRange(0, 60000)
        self.delay.setSuffix(" ms delay before this action")
        self.delay.setValue(self.current.get("delay_ms", 0))
        layout.addWidget(self.delay)
        self.type.setCurrentText(self.current["type"])
        self.type.currentTextChanged.connect(self.build)
        self.build(self.type.currentText())

    def build(self, kind):
        while self.details_layout.rowCount():
            self.details_layout.removeRow(0)
        value = self.current.get("value", "") if self.current.get("type") == kind else ""
        self.value = QLineEdit(str(value))
        if kind == "launch":
            self.value.setReadOnly(True)
            self.details_layout.addRow("Desktop entry ID", self.value)
            self.details_layout.addRow(button("Choose application…", self.pick))
        elif kind in ("media", "system", "audio", "page", "profile"):
            self.choice = QComboBox()
            if kind == "page":
                for page in self.window.config.data["pages"]:
                    self.choice.addItem(page["name"], page["id"])
            elif kind == "profile":
                for name in self.window.config.data["profiles"]:
                    self.choice.addItem(name, name)
            else:
                values = {"media": MEDIA, "system": POWER, "audio": ("mic_mute", "output_mute", "volume")}[kind]
                for name in values:
                    self.choice.addItem(name, name)
            index = self.choice.findData(value)
            self.choice.setCurrentIndex(max(0, index))
            self.details_layout.addRow("Value", self.choice)
            if kind == "audio":
                self.level = QSpinBox()
                self.level.setRange(0, 100)
                self.level.setValue(int(self.current.get("level", 50)))
                self.details_layout.addRow("Volume % (volume action)", self.level)
        elif kind == "command":
            self.value.setText(shlex.join(self.current.get("argv", [])))
            self.details_layout.addRow(QLabel("Advanced: explicit arguments, no shell expansion. Confirmed every time it runs."))
            self.details_layout.addRow("Command", self.value)
        elif kind in ("url", "file"):
            self.value.setPlaceholderText("https://example.com" if kind == "url" else "/home/user/path")
            self.details_layout.addRow("URL" if kind == "url" else "Absolute file/folder", self.value)
        elif kind == "macro":
            self.steps = copy.deepcopy(self.current.get("steps", []))
            self.steps_list = QListWidget()
            self.steps_list.setMinimumHeight(160)
            self.details_layout.addRow(self.steps_list)
            row = QWidget()
            buttons = QHBoxLayout(row)
            for text, callback in (("Add", self.add_step), ("Edit", self.edit_step), ("Remove", self.remove_step), ("↑", lambda: self.move_step(-1)), ("↓", lambda: self.move_step(1))):
                buttons.addWidget(button(text, callback))
            self.details_layout.addRow(row)
            self.fill_steps()

    def pick(self):
        picker = AppPicker(self.window)
        if picker.exec():
            self.value.setText(picker.selected["id"])

    def fill_steps(self):
        self.steps_list.clear()
        for step in self.steps:
            self.steps_list.addItem(step["type"] + ": " + str(step.get("value", shlex.join(step.get("argv", [])))) + " · " + str(step.get("delay_ms", 0)) + " ms")

    def add_step(self):
        if len(self.steps) >= 32:
            return
        dialog = ActionDialog(self.window)
        if dialog.exec():
            self.steps.append(dialog.result_action)
            self.fill_steps()

    def edit_step(self):
        index = self.steps_list.currentRow()
        if index >= 0:
            dialog = ActionDialog(self.window, self.steps[index])
            if dialog.exec():
                self.steps[index] = dialog.result_action
                self.fill_steps()

    def remove_step(self):
        index = self.steps_list.currentRow()
        if index >= 0:
            self.steps.pop(index)
            self.fill_steps()

    def move_step(self, direction):
        index = self.steps_list.currentRow()
        target = index + direction
        if index >= 0 and 0 <= target < len(self.steps):
            self.steps[index], self.steps[target] = self.steps[target], self.steps[index]
            self.fill_steps()
            self.steps_list.setCurrentRow(target)

    def action(self):
        kind = self.type.currentText()
        action = {"type": kind, "delay_ms": self.delay.value()}
        if kind == "macro":
            action["steps"] = copy.deepcopy(self.steps)
        elif kind == "command":
            action["argv"] = shlex.split(self.value.text())
        elif kind in ("page", "profile", "system", "media", "audio"):
            action["value"] = self.choice.currentData()
            if kind == "audio" and action["value"] == "volume":
                action["level"] = self.level.value()
        elif kind != "settings":
            action["value"] = self.value.text().strip()
        validate_action(action)
        return action


class ActionDialog(FormDialog):
    def __init__(self, window, action=None):
        super().__init__("Macro step", window)
        self.action_form = ActionForm(window, action, allow_macro=False)
        self.form_layout.addWidget(self.action_form)
        self.buttons.accepted.connect(self.save)

    def save(self):
        try:
            self.result_action = self.action_form.action()
            self.accept()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid action", str(error))


class TileEditor(FormDialog):
    def __init__(self, window, item=None):
        super().__init__("Edit widget" if item else "Add widget", window)
        self.window = window
        self.item = copy.deepcopy(item or tile("button", "New button"))
        form = QFormLayout()
        self.form_layout.addLayout(form)
        self.kind = QComboBox()
        self.kind.addItems(KINDS)
        self.kind.setCurrentText(self.item["kind"])
        self.label = QLineEdit(self.item["label"])
        self.icon_name = QLineEdit(self.item["icon"])
        self.icon_name.setPlaceholderText("System icon name or absolute local icon path")
        self.size = QComboBox()
        self.size.addItems(["1x1", "2x1", "2x2"])
        self.size.setCurrentText(str(self.item["w"]) + "x" + str(self.item["h"]))
        self.target = QComboBox()
        for p in window.config.data["pages"]:
            self.target.addItem(p["name"], p["id"])
        self.target.setCurrentIndex(window.page_index)
        self.position = QSpinBox()
        self.position.setRange(1, 129)
        current = window.current_page()["tiles"]
        self.position.setValue(next((i + 1 for i, t in enumerate(current) if t["id"] == self.item["id"]), len(current) + 1))
        for name, widget in (("Widget", self.kind), ("Label", self.label), ("Icon", self.icon_name), ("Size", self.size), ("Page", self.target), ("Position", self.position)):
            form.addRow(name, widget)
        self.hour24 = QCheckBox("24-hour clock")
        self.hour24.setChecked(self.item["settings"].get("hour24", True))
        self.seconds = QCheckBox("Clock seconds")
        self.seconds.setChecked(self.item["settings"].get("seconds", False))
        self.date = QCheckBox("Show date")
        self.date.setChecked(self.item["settings"].get("date", True))
        for option in (self.hour24, self.seconds, self.date):
            form.addRow(option)
        self.action_form = ActionForm(window, self.item["action"])
        self.form_layout.addWidget(self.action_form)
        self.form_layout.addWidget(QLabel("Action applies to button widgets. Long-press a widget title to edit.\nOrder and size determine grid placement; overflow scrolls vertically."))
        self.buttons.accepted.connect(self.save)

    def save(self):
        try:
            item = copy.deepcopy(self.item)
            item.update(kind=self.kind.currentText(), label=self.label.text().strip() or "Widget", icon=self.icon_name.text().strip())
            item["w"], item["h"] = map(int, self.size.currentText().split("x"))
            item["settings"] = {"hour24": self.hour24.isChecked(), "seconds": self.seconds.isChecked(), "date": self.date.isChecked()}
            item["action"] = self.action_form.action() if item["kind"] == "button" else {"type": "settings"}
            data = copy.deepcopy(self.window.config.data)
            for p in data["pages"]:
                p["tiles"] = [t for t in p["tiles"] if t["id"] != item["id"]]
            target = next(p for p in data["pages"] if p["id"] == self.target.currentData())
            target["tiles"].insert(min(self.position.value() - 1, len(target["tiles"])), item)
            self.window.commit(data)
            self.accept()
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Cannot save widget", str(error))

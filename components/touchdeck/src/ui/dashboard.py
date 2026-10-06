from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QGridLayout
from ui.common import scroll
from ui.widgets import Tile


class Dashboard(QWidget):
    def __init__(self, window):
        super().__init__()
        from PySide6.QtWidgets import QVBoxLayout
        self.window = window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.body = QWidget()
        self.grid = QGridLayout(self.body)
        self.grid.setSpacing(12)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.area = scroll(self.body)
        layout.addWidget(self.area)
        self.tiles = []
        self.columns = 0
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(120)
        self.resize_timer.timeout.connect(self.rebuild)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start()

    def rebuild(self):
        self.window.hold_timer.stop()
        self.window.press_origin = None
        self.window.press_widget = None
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        for row in range(self.grid.rowCount()):
            self.grid.setRowMinimumHeight(row, 0)
            self.grid.setRowStretch(row, 0)
        for column in range(self.grid.columnCount()):
            self.grid.setColumnMinimumWidth(column, 0)
            self.grid.setColumnStretch(column, 0)
        p = self.window.current_page()
        width = max(320, self.area.viewport().width() - 18)
        columns = max(2, min(p["cols"], width // 180))
        self.columns = columns
        height = max(108, (self.area.viewport().height() - 18 - 12 * (p["rows"] - 1)) // p["rows"])
        occupied = set()
        self.tiles = []
        end_row = p["rows"]
        for item in p["tiles"]:
            w, h = min(item["w"], columns), item["h"]
            index = 0
            while True:
                row, column = divmod(index, columns)
                cells = {(r, c) for r in range(row, row + h) for c in range(column, column + w)}
                if column + w <= columns and not occupied & cells:
                    break
                index += 1
            occupied.update(cells)
            widget = Tile(self.window, item)
            widget.setMinimumHeight(height * h + 12 * (h - 1))
            widget.setMinimumWidth(0)
            self.grid.addWidget(widget, row, column, h, w)
            self.tiles.append(widget)
            end_row = max(end_row, row + h)
        for column in range(columns):
            self.grid.setColumnStretch(column, 1)
        for row in range(end_row):
            self.grid.setRowMinimumHeight(row, height)
        self.body.setMinimumHeight(end_row * (height + 12) + 4)

    def refresh(self):
        for widget in self.tiles:
            widget.refresh()

from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QIcon, QPainter, QColor
from PySide6.QtWidgets import QPushButton, QSlider, QStyle, QDialog, QVBoxLayout, QDialogButtonBox, QScrollArea, QWidget

ASSETS = Path(__file__).resolve().parents[2] / "assets"
ICON_THEME = "Dark"
SYMBOLIC_ICONS = {}


def set_icon_theme(theme):
    global ICON_THEME
    if theme != ICON_THEME:
        SYMBOLIC_ICONS.clear()
    ICON_THEME = theme
    QIcon.setFallbackThemeName("breeze" if theme == "Light" else "breeze-dark")


def icon(name, symbolic=False):
    """Keep application/custom artwork intact; tint built-in controls for contrast."""
    if name and Path(name).is_absolute() and Path(name).is_file():
        return QIcon(name)
    key = (name, ICON_THEME)
    if symbolic and key in SYMBOLIC_ICONS:
        return SYMBOLIC_ICONS[key]
    bundled = ASSETS / "icons" / (name + ".svg") if name else ASSETS / "icons/tile.svg"
    fallback = QIcon(str(bundled if bundled.is_file() else ASSETS / "icons/tile.svg"))
    result = QIcon.fromTheme(name or "view-grid", fallback)
    if symbolic:
        pixmap = result.pixmap(48, 48)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor("#202630" if ICON_THEME == "Light" else "#e1e5ed"))
        painter.end()
        result = QIcon(pixmap)
        SYMBOLIC_ICONS[key] = result
    return result


def button(text, callback=None):
    item = QPushButton(text)
    item.setMinimumHeight(48)
    if callback:
        item.clicked.connect(callback)
    return item


class TouchButton(QPushButton):
    held = Signal()

    def __init__(self, text=""):
        super().__init__(text)
        self.setMinimumHeight(48)
        self.setIconSize(QSize(30, 30))
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(650)
        self.timer.timeout.connect(self._hold)
        self.long_press = False
        self.origin = None

    def _hold(self):
        self.long_press = True
        self.setDown(False)
        self.held.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.long_press = False
            self.origin = event.position()
            self.timer.start()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.origin is not None and (event.position() - self.origin).manhattanLength() > 18:
            self.timer.stop()
            self.long_press = True
            self.setDown(False)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.timer.stop()
        if self.long_press:
            self.setDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class TouchSlider(QSlider):
    """Click/tap anywhere on a wide groove; keep normal drag support."""
    def __init__(self, maximum=100):
        super().__init__(Qt.Horizontal)
        self.setRange(0, maximum)
        self.setMinimumHeight(48)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setValue(QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(event.position().x()), max(1, self.width())))
            self.setSliderDown(True)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown():
            self.setValue(QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(event.position().x()), max(1, self.width())))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.isSliderDown():
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


def scroll(widget):
    from PySide6.QtWidgets import QScroller
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    QScroller.grabGesture(area.viewport(), QScroller.TouchGesture)
    return area


class FormDialog(QDialog):
    def __init__(self, title, parent):
        super().__init__(parent)
        self.setWindowTitle(title)
        size = parent.size()
        self.resize(min(760, size.width() - 24), min(650, size.height() - 24))
        layout = QVBoxLayout(self)
        self.body = QWidget()
        self.form_layout = QVBoxLayout(self.body)
        layout.addWidget(scroll(self.body))
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

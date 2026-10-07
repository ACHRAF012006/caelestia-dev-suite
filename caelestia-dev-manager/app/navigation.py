"""Brief navigation animations that leave page selection and input immediate."""
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (QStackedWidget, QLabel, QGraphicsOpacityEffect,
                              QListWidget, QListWidgetItem, QStyledItemDelegate, QStyle)


class NavigationDelegate(QStyledItemDelegate):
    """Labels paint text above the sliding highlight; the view keeps native input."""
    def paint(self, painter, option, index):
        if option.state & QStyle.State_MouseOver:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#2a3447"))
            painter.drawRoundedRect(option.rect.adjusted(0, 3, 0, -3), 6, 6)
            painter.restore()


class AnimatedNavigation(QListWidget):
    """One highlight travels behind the labels, including during rapid switching."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.animations_enabled = True
        self.setItemDelegate(NavigationDelegate(self))
        self.highlight = QLabel(self.viewport())
        self.highlight.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.highlight.setStyleSheet("background: #354260; border: none; border-radius: 6px;")
        self.highlight.hide()
        self.animation = QPropertyAnimation(self.highlight, b"geometry", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.currentRowChanged.connect(self.selection_changed)

    def addItem(self, text):
        item = QListWidgetItem(text)
        item.setSizeHint(QSize(180, 48))
        super().addItem(item)
        label = QLabel(text)
        label.setAttribute(Qt.WA_TransparentForMouseEvents)
        label.setStyleSheet("background: transparent; border: none; padding: 0 12px; color: #e0e5ef;")
        self.setItemWidget(item, label)
        self.highlight.lower()

    def target_rect(self):
        item = self.currentItem()
        return self.visualItemRect(item).adjusted(0, 3, 0, -3) if item else None

    def selection_changed(self, row):
        for index in range(self.count()):
            label = self.itemWidget(self.item(index))
            color = "#eaf0ff" if index == row else "#e0e5ef"
            label.setStyleSheet(f"background: transparent; border: none; padding: 0 12px; color: {color};")
        target = self.target_rect()
        animate = (self.animations_enabled and self.isVisible() and
                   self.highlight.isVisible() and target is not None and target.isValid())
        start = self.highlight.geometry()
        self.animation.stop()
        if target is None or not target.isValid():
            self.highlight.hide()
            return
        self.highlight.show()
        self.highlight.lower()
        if animate:
            self.animation.setStartValue(start)
            self.animation.setEndValue(target)
            self.animation.start()
        else:
            self.highlight.setGeometry(target)

    def stop_transition(self):
        self.animation.stop()
        target = self.target_rect()
        if target is not None and target.isValid():
            self.highlight.setGeometry(target)

    def set_animations_enabled(self, enabled):
        self.animations_enabled = bool(enabled)
        if not enabled: self.stop_transition()

    def showEvent(self, event):
        super().showEvent(event)
        self.selection_changed(self.currentRow())
        self.stop_transition()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "animation"): self.stop_transition()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        if hasattr(self, "animation"): self.stop_transition()

    def hideEvent(self, event):
        self.stop_transition()
        super().hideEvent(event)


class AnimatedStack(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.animations_enabled = True
        self.overlay = QLabel(self)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay.setStyleSheet("background: transparent; border: none; padding: 0;")
        self.overlay.hide()
        effect = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(effect)
        self.animation = QPropertyAnimation(effect, b"opacity", self)
        self.animation.setDuration(140)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.finished.connect(self.stop_transition)

    def stop_transition(self):
        self.animation.stop()
        self.overlay.hide()
        self.overlay.clear()

    def set_animations_enabled(self, enabled):
        self.animations_enabled = bool(enabled)
        if not enabled: self.stop_transition()

    def setCurrentIndex(self, index):
        if index == self.currentIndex() or not 0 <= index < self.count(): return
        self.stop_transition()
        animate = self.animations_enabled and self.isVisible() and self.currentWidget() is not None
        snapshot = self.currentWidget().grab() if animate else None
        super().setCurrentIndex(index)
        if animate and not snapshot.isNull():
            self.overlay.setGeometry(self.rect())
            self.overlay.setPixmap(snapshot)
            self.overlay.show(); self.overlay.raise_()
            self.animation.setStartValue(1.0); self.animation.setEndValue(0.0)
            self.animation.start()

    def resizeEvent(self, event):
        if hasattr(self, "animation"): self.stop_transition()
        super().resizeEvent(event)

    def hideEvent(self, event):
        self.stop_transition()
        super().hideEvent(event)

"""Short page fades without changing page layout or delaying input."""
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QStackedWidget, QLabel, QGraphicsOpacityEffect


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

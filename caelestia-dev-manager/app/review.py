"""Readable confirmations with exact technical plans available on demand."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QDialogButtonBox
from app.editor import CodeEditor


class ReviewDialog(QDialog):
    def __init__(self, parent, title, text, label, extra=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(min(850, parent.width()), min(700, parent.height()))
        layout = QVBoxLayout(self)
        heading = QLabel(title); heading.setObjectName("title")
        heading.setWordWrap(True); heading.setTextFormat(Qt.PlainText)
        layout.addWidget(heading)
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setPlainText(getattr(extra, "summary_text", text))
        self.summary.setObjectName("reviewSummary")
        layout.addWidget(self.summary, 1)
        if extra is not None: layout.addWidget(extra)
        self.details_toggle = QPushButton("Show technical details")
        self.details_toggle.setCheckable(True)
        self.details_toggle.setMinimumHeight(40)
        self.details_toggle.setVisible(extra is not None)
        layout.addWidget(self.details_toggle)
        self.details = CodeEditor(readonly=True)
        self.details.setPlainText(text)
        self.details.setVisible(False)
        layout.addWidget(self.details, 1)
        self.details_toggle.toggled.connect(self.toggle_details)
        controls = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.accept_button = controls.addButton(label, QDialogButtonBox.AcceptRole)
        self.accept_button.setObjectName("primary")
        if extra is not None and hasattr(extra, "plan"):
            def preview(updated, valid):
                self.details.setPlainText(updated)
                self.summary.setPlainText(getattr(extra, "summary_text", updated))
                self.accept_button.setEnabled(valid)
            extra.refresh_preview = preview
            self.accept_button.setEnabled(extra.plan is not None)
        controls.accepted.connect(self.accept); controls.rejected.connect(self.reject)
        layout.addWidget(controls)

    def toggle_details(self, checked):
        self.details.setVisible(checked)
        self.details_toggle.setText("Hide technical details" if checked else "Show technical details")

import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QPlainTextEdit

class Highlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        for pattern, color in [(r'\b(import|from|def|class|return|if|else|while|for|True|False|None|function|property|readonly|signal|false|true)\b', '#b4c4f6'),
                               (r'"[^"\n]*"|\x27[^\x27\n]*\x27', '#a4c7ae'), (r'#.*$|//.*$', '#788397')]:
            fmt = QTextCharFormat(); fmt.setForeground(QColor(color))
            for match in re.finditer(pattern, text): self.setFormat(match.start(), match.end() - match.start(), fmt)

class CodeEditor(QPlainTextEdit):
    def __init__(self, placeholder="", readonly=False):
        super().__init__()
        self.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setPlaceholderText(placeholder)
        self.setReadOnly(readonly)
        self.setTabStopDistance(32)
        self.highlighter = Highlighter(self.document())

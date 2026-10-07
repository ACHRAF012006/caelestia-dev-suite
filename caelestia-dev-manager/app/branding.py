"""Bundled artwork uses literal SVG colors instead of the desktop icon theme."""
from pathlib import Path

from PySide6.QtGui import QIcon

ICON_PATH = Path(__file__).resolve().parent / "assets/icon.svg"


def application_icon():
    return QIcon(str(ICON_PATH))

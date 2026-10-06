import logging
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from models.config import Config
from services.applications import Applications
from services.audio import Audio
from services.media import Media
from services.system_monitor import Monitor
from ui.common import ASSETS
from ui.main_window import MainWindow
from utils.logging import setup


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("touchdeck")
    app.setOrganizationName("TouchDeck")
    QIcon.setFallbackThemeName("breeze-dark")
    app.setWindowIcon(QIcon(str(ASSETS / "icon.svg")))
    try:
        log_path = setup()
        config = Config()
        window = MainWindow(config, Applications(), Audio(), Media(), Monitor(), log_path)
        window.start()
        logging.getLogger("touchdeck").info("TouchDeck 0.1.1 started")
        return app.exec()
    except (OSError, ValueError) as error:
        QMessageBox.critical(None, "TouchDeck cannot start", str(error))
        return 1

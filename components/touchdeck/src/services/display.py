import os
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from utils.paths import atomic_write, checked, directory, root

MARK = "# TouchDeck user-owned autostart v1\n"


def screens():
    return QGuiApplication.screens()


def screen_id(screen):
    return "|".join((screen.name(), screen.manufacturer(), screen.model(), screen.serialNumber()))


def apply(window, config):
    available = screens()
    selected = next((s for s in available if screen_id(s) == config["screen"]), None)
    missing = selected is None
    if missing:
        selected = next((s for s in available if s != QGuiApplication.primaryScreen()), QGuiApplication.primaryScreen())
    mode = config["mode"]
    if missing and selected == QGuiApplication.primaryScreen():
        mode = "Windowed"
    window.hide()
    window.setWindowFlag(Qt.FramelessWindowHint, mode != "Windowed")
    window.winId()
    if selected:
        window.windowHandle().setScreen(selected)
        geometry = selected.availableGeometry()
        window.resize(min(1024, geometry.width()), min(600, geometry.height()))
        window.move(geometry.topLeft())
    if mode == "Fullscreen":
        window.showFullScreen()
    elif mode == "Borderless" and selected:
        window.setGeometry(selected.availableGeometry())
        window.showNormal()
    else:
        window.showNormal()


def autostart_path():
    return checked(root("CONFIG") / "autostart" / "touchdeck-user.desktop")


def autostart_enabled():
    path = autostart_path()
    return path.is_file() and path.read_text(encoding="utf-8").startswith(MARK)


def set_autostart(enabled):
    path = autostart_path()
    if path.exists() and not path.read_text(encoding="utf-8").startswith(MARK):
        raise ValueError("Autostart filename is owned by another application; left unchanged")
    if not enabled:
        if path.exists():
            path.unlink()
        return
    # Match the existing manager's fixed user command destination exactly.
    launcher = checked(Path.home() / ".local/bin/touchdeck")
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise ValueError("Install and enable TouchDeck through Dev Manager before enabling autostart")
    def quote(value):
        return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%") + '"'
    directory(path.parent)
    atomic_write(path, MARK + "[Desktop Entry]\nType=Application\nName=TouchDeck\nExec=" + quote(launcher) +
                 "\nTryExec=" + str(launcher) + "\nTerminal=false\n")

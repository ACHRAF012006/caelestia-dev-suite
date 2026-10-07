"""Brand colors and absolute desktop icon paths survive theme and lifecycle changes."""
import json
from pathlib import Path
import sys

import pytest
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtWidgets import QApplication

from app.branding import ICON_PATH, application_icon
from scripts import install_manager


def test_bundled_icon_keeps_colors_when_system_palette_changes():
    app = QApplication.instance() or QApplication([])
    original_palette = app.palette()
    original_theme = QIcon.themeName()
    try:
        before = application_icon().pixmap(128, 128).toImage()
        palette = QPalette()
        palette.setColor(QPalette.WindowText, QColor("#ff0000"))
        palette.setColor(QPalette.Text, QColor("#00ff00"))
        app.setPalette(palette)
        QIcon.setThemeName("nonexistent-branding-test-theme")
        after = application_icon().pixmap(128, 128).toImage()
        assert not before.isNull() and before == after
        assert before.pixelColor(91, 36).name() == "#e3e9ff"
    finally:
        app.setPalette(original_palette)
        QIcon.setThemeName(original_theme)


def test_manager_logo_is_installed_owned_updated_and_removed(tmp_path, monkeypatch):
    project = tmp_path / "source with spaces"
    (project / "app/assets").mkdir(parents=True)
    source = project / "app/assets/icon.svg"
    source.write_bytes(ICON_PATH.read_bytes())
    home, data, config = (tmp_path / name for name in ("home", "data with spaces", "config"))
    for name, path in (("HOME", home), ("XDG_DATA_HOME", data), ("XDG_CONFIG_HOME", config), ("XDG_STATE_HOME", tmp_path / "state")):
        monkeypatch.setenv(name, str(path))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(install_manager.shutil, "which", lambda tool: "/usr/bin/" + tool if tool in {"python3", "systemctl"} else None)

    def fake_run(command, **kwargs):
        # Installer behavior only: never download dependencies or launch installed code.
        if command[1:3] == ["-m", "venv"]:
            interpreter = Path(command[-1]) / "bin/python"
            interpreter.parent.mkdir(parents=True)
            interpreter.write_text("temporary test interpreter")

    monkeypatch.setattr(install_manager.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["install_manager.py", str(project)])
    install_manager.main()
    icon = data / "caelestia-dev-manager/manager/icon.svg"
    desktop = data / "applications/caelestia-dev-manager.desktop"
    receipt = config / "caelestia-dev-manager/manager-install.json"
    assert icon.read_bytes() == source.read_bytes()
    assert f"Icon={icon}\n" in desktop.read_text()
    assert "Icon=applications-development" not in desktop.read_text()
    assert str(icon) in {f["path"] for f in json.loads(receipt.read_text())["files"]}
    # Upgrade a receipt from before the bundled logo was introduced.
    old = json.loads(receipt.read_text())
    old["files"] = [f for f in old["files"] if f["path"] != str(icon)]
    old["version"] = "0.3.1"
    icon.unlink(); receipt.write_text(json.dumps(old))
    install_manager.main()
    assert icon.read_bytes() == source.read_bytes()
    # An unrelated file and component payload remain outside manager ownership.
    unrelated = data / "caelestia-dev-manager/apps/survivor/user.txt"
    unrelated.parent.mkdir(parents=True); unrelated.write_text("keep")
    monkeypatch.setattr(sys, "argv", ["install_manager.py", str(project), "--uninstall"])
    icon.write_text("user edit")
    with pytest.raises(RuntimeError, match="Modified manager files preserved"):
        install_manager.main()
    assert icon.exists()
    icon.write_bytes(source.read_bytes())
    install_manager.main()
    assert not icon.exists() and not desktop.exists() and not receipt.exists()
    assert unrelated.read_text() == "keep"

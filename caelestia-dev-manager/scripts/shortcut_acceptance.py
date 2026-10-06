"""Launch a shortcut with real KDE KIO, using ONLY temporary source/XDG/desktop paths."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
from backend.codex.package import encode
from backend.manager import Manager
from backend.paths import Paths, atomic_write
from backend.templates import template

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    args = parser.parse_args()
    probe = args.probe.resolve()
    with tempfile.TemporaryDirectory(prefix="cdm-shortcut-acceptance-") as temporary:
        paths = Paths.sandbox(Path(temporary))
        atomic_write(paths.config / "user-dirs.dirs", b'XDG_DESKTOP_DIR="$HOME/Bureau personnalise"\n')
        marker = Path(temporary) / "independent-launch.txt"
        m, files = template("CDM Shortcut Test", "cdm-shortcut-test", "Python Script")
        m["type"] = "standalone-app"; m["desktop"] = {"createShortcut": True}
        files["manifest.json"] = json.dumps(m)
        files["src/main.py"] = "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('independent KDE launch')\n"
        # Exercise native paste/import, checkbox preference and the actual installation dialog.
        from PySide6.QtWidgets import QApplication, QDialog, QPushButton
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt, QTimer
        from app.main import Window
        application = QApplication([])
        manager = Manager(paths, real=False); window = Window(manager); window.show()
        window.nav.setCurrentRow(2); application.processEvents()
        application.clipboard().setText(encode(files, m)); window.paste.setFocus()
        QTest.keyClick(window.paste, Qt.Key_V, Qt.ControlModifier)
        def click(text):
            matches = [b for b in window.findChildren(QPushButton) if b.text() == text and b.isVisible()]
            assert matches, text
            QTest.mouseClick(matches[0], Qt.LeftButton); application.processEvents()
        click("Analyze Code"); assert window.import_shortcut.isChecked()
        assert not paths.source(m["id"]).exists()
        click("Create Component"); reconstructed = manager.read_source(m["id"])
        assert reconstructed.keys() == files.keys()
        assert all(reconstructed[name].strip() == content.strip() for name, content in files.items())
        def accept():
            dialog = application.activeModalWidget(); assert isinstance(dialog, QDialog)
            assert dialog.findChildren(QPushButton)
            dialog.accept()
        QTimer.singleShot(250, accept); click("Install")
        record = manager.installed(m["id"]); shortcut = Path(record["desktop_shortcut"]["path"])
        assert shortcut.read_bytes() == manager.canonical_desktop(m).read_bytes()
        assert shortcut.is_relative_to(Path(temporary)) and shortcut.stat().st_mode & 0o111
        window.close(); application.processEvents()
        # KDE resolves the desktop file and executes its standalone absolute Exec.
        result = subprocess.run([str(probe), "--file", str(shortcut), "--launch"], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline: time.sleep(0.05)
        assert marker.read_text() == "independent KDE launch"
        reopened = Window(Manager(paths, real=False)); reopened.show(); application.processEvents()
        assert reopened.manager.has_desktop_shortcut(m["id"])
        reopened.close(); application.processEvents()
        unrelated = shortcut.parent / "Keep.desktop"; unrelated.write_text("unrelated")
        manager.uninstall(m["id"])
        assert not shortcut.exists() and unrelated.read_text() == "unrelated"
        assert paths.source(m["id"]).is_dir()
        print("PASS: native paste/import/install, KDE KIO shortcut launch after manager window closed, reopen detection, owned-only uninstall; all paths temporary.")

if __name__ == "__main__": main()

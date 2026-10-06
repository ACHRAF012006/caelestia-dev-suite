"""Run with QT_QPA_PLATFORM=offscreen python -B -m unittest discover -s tests.
All writable paths are temporary. No real audio, media, launch or power actions.
"""
import copy
import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace, MethodType

sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtCore import QObject, Signal, Qt, QEvent
from PySide6.QtGui import QIcon
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from models.config import Config, defaults, validate, validate_action
from services.applications import Applications
from services.audio import Audio
from services.media import Media, PLAYER, PATH
from ui.main_window import MainWindow
from ui.editor import TileEditor, ActionDialog
from ui.settings import Settings
from ui.wizard import SetupWizard
from ui.common import icon, set_icon_theme

APP = QApplication.instance() or QApplication([])


class FakeService(QObject):
    changed = Signal(dict)
    completed = Signal(str, bool, str)

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.calls = []
        self.fail = False

    def request(self, operation, value=None, token=""):
        self.calls.append((operation, value))
        self.completed.emit(token, not self.fail, "mock result")

    def selected(self, data):
        return "", {}

    def close(self):
        pass


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="touchdeck-test-")
        self.base = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.base / "config"),
                                          "XDG_STATE_HOME": str(self.base / "state"),
                                          "XDG_DATA_HOME": str(self.base / "data"),
                                          "XDG_DATA_DIRS": str(self.base / "system")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def pump(self, seconds=0.1):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            APP.processEvents()
            time.sleep(0.005)

    def window(self):
        config = Config()
        data = defaults()
        data["first_run"] = False
        config.save(data)
        audio = FakeService({"available": False, "error": "Mock audio unavailable", "outputs": [], "inputs": [], "streams": []})
        media = FakeService({"players": {}, "error": ""})
        monitor = FakeService({"cpu": 15, "ram": 35, "uptime": 1, "upload": 0, "download": 0})
        return MainWindow(config, Applications(), audio, media, monitor, self.base / "state/touchdeck.log")

    def test_config_backup_recovery_undo_and_validation(self):
        config = Config()
        first = defaults()
        config.save(first)
        changed = copy.deepcopy(first)
        changed["pages"][0]["name"] = "Edited"
        config.save(changed)
        config.undo()
        self.assertEqual(config.data["pages"][0]["name"], "Home")
        config.path.write_text("{broken", encoding="utf-8")
        recovered = Config()
        self.assertTrue(recovered.notice)
        self.assertEqual(recovered.data["pages"][0]["name"], "Edited")
        bad = copy.deepcopy(first)
        bad["pages"][0]["tiles"][0]["kind"] = "unsafe-plugin"
        with self.assertRaises(ValueError):
            validate(bad)
        with self.assertRaises(ValueError):
            validate_action({"type": "macro", "steps": [{"type": "macro", "steps": []}]})
        with self.assertRaises(ValueError):
            validate_action({"type": "command", "argv": "hidden shell"})

    def test_desktop_discovery_masks_hidden_and_keeps_names(self):
        base = self.base / "data/applications"
        base.mkdir(parents=True)
        (base / "demo.desktop").write_text("[Desktop Entry]\nType=Application\nName=Demo\nComment=An application\nIcon=demo\nExec=demo %U\n", encoding="utf-8")
        (base / "hidden.desktop").write_text("[Desktop Entry]\nType=Application\nName=Hidden\nHidden=true\nExec=hidden\n", encoding="utf-8")
        apps = Applications()
        self.assertEqual(set(apps.apps), {"demo.desktop"})
        self.assertEqual(apps.apps["demo.desktop"]["description"], "An application")

    def test_ui_resolutions_and_editors(self):
        window = self.window()
        window.show()
        for width, height in ((800, 480), (1024, 600), (1280, 800)):
            window.resize(width, height)
            self.pump(0.2)
            window.dashboard.rebuild()
            self.assertLessEqual(window.dashboard.body.minimumSizeHint().width(), window.dashboard.area.viewport().width())
            self.assertEqual(len(window.dashboard.tiles), 6)
        window.advance(1)
        self.assertEqual(window.current_page()["name"], "Audio")
        window.toggle_edit()
        editor = TileEditor(window)
        editor.label.setText("New clock")
        editor.kind.setCurrentText("clock")
        editor.save()
        self.assertEqual(window.current_page()["tiles"][-1]["label"], "New clock")
        window.undo()
        self.assertEqual(len(window.current_page()["tiles"]), 3)
        settings = Settings(window)
        settings.copy_page()
        settings.save()
        self.assertEqual(len(window.config.data["pages"]), 4)
        wizard = SetupWizard(window)
        wizard.reject()
        self.assertFalse(wizard.result_config()["first_run"])
        window.close()
        self.pump()

    def test_macros_stop_on_failure_and_power_requires_confirmation(self):
        window = self.window()
        window.audio.fail = True
        window.actions.execute({"type": "macro", "steps": [{"type": "audio", "value": "mic_mute"}, {"type": "system", "value": "shutdown"}]})
        self.pump()
        self.assertFalse(window.actions.busy)
        self.assertEqual(window.media.calls, [])
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Cancel):
            window.actions.execute({"type": "system", "value": "shutdown"})
            self.pump()
            window.actions.execute({"type": "command", "argv": ["never-execute-this"]})
            self.pump()
        self.assertEqual(window.media.calls, [])
        self.assertFalse(window.actions.busy)
        window.close()

    def test_audio_request_clamps_volume(self):
        class Device:
            index = 1
            name = "speaker"
        class Info:
            default_sink_name = "speaker"
        class Pulse:
            def sink_list(self): return [Device()]
            def source_list(self): return []
            def sink_input_list(self): return []
            def server_info(self): return Info()
            def volume_set_all_chans(self, target, value): self.value = value
        pulse = Pulse()
        Audio._operate(None, pulse, "volume", {"kind": "output", "level": 9})
        self.assertEqual(pulse.value, 1)

    def test_mpris_seek_uses_track_object_path_and_microseconds(self):
        from dbus_next import MessageType, Variant
        class Bus:
            def __init__(self): self.calls = []
            async def call(self, message):
                self.calls.append(message)
                return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[], error_name=None)
        bus = Bus()
        completed = []
        service = SimpleNamespace(bus=bus, players={"org.mpris.MediaPlayer2.demo": {"CanSeek": True,
                                  "Metadata": {"mpris:trackid": "/demo/track/1"}}},
                                  completed=SimpleNamespace(emit=lambda *args: completed.append(args)))
        service._call = MethodType(Media._call, service)
        asyncio.run(Media._request(service, "media", {"player": "org.mpris.MediaPlayer2.demo", "method": "SetPosition", "position": 45000000}, "seek"))
        self.assertEqual(bus.calls[0].signature, "ox")
        self.assertEqual(bus.calls[0].body, ["/demo/track/1", 45000000])
        self.assertTrue(completed[0][1])
        service.players["org.mpris.MediaPlayer2.demo"]["CanSeek"] = False
        asyncio.run(Media._request(service, "media", {"player": "org.mpris.MediaPlayer2.demo", "method": "SetPosition", "position": 1}, "seek"))
        self.assertEqual(len(bus.calls), 1)
        self.assertFalse(completed[-1][1])

    def test_dynamic_mixer_device_and_stream_controls(self):
        window = self.window()
        device = {"id": 1, "name": "speaker", "label": "Speakers", "volume": .4, "mute": False}
        mic = {"id": 2, "name": "mic", "label": "Microphone", "volume": .7, "mute": True}
        stream = {"id": 10, "key": "browser", "label": "Browser", "volume": .25, "mute": False, "icon": ""}
        window.audio.state.update(available=True, output=device, input=mic, outputs=[device], inputs=[mic], streams=[stream])
        window.advance(1)
        mixer = window.dashboard.tiles[0].content
        self.assertEqual(len(mixer.rows), 3)
        row = mixer.rows[-1][2]
        row.slider.setValue(31)
        row.volume()
        self.assertEqual(window.audio.calls[-1], ("volume", {"kind": "stream", "id": 10, "level": .31}))
        window.audio.state["streams"] = []
        mixer.refresh()
        self.assertEqual(len(mixer.rows), 2)
        window.close()

    def test_fullscreen_bars_touch_menu_edit_and_idle_recovery(self):
        window = self.window()
        window.show()
        window.toggle_fullscreen()
        self.pump()
        self.assertTrue(window.isFullScreen())
        self.assertTrue(window.header.isHidden())
        self.assertTrue(window.quick_area.isHidden())
        self.assertTrue(window.menu_button.isVisible())
        self.assertEqual(window.config.data["mode"], "Fullscreen")
        self.assertTrue(window.config.data["screen"])
        QTest.mouseClick(window.menu_button, Qt.LeftButton)
        self.assertTrue(window.header.isVisible())
        self.assertTrue(window.quick_area.isVisible())
        QTest.mouseClick(window.edit_button, Qt.LeftButton)
        self.assertTrue(window.edit_mode)
        self.assertTrue(window.add_button.isVisible())
        QTest.mouseClick(window.edit_button, Qt.LeftButton)
        self.assertTrue(window.header.isHidden())
        window.advance(1)
        self.assertTrue(window.header.isHidden())
        window.show_controls()
        QTest.mouseClick(window.hide_bars_button, Qt.LeftButton)
        self.assertTrue(window.header.isHidden())
        window.config.data["idle_seconds"] = 1
        window.last_touch = time.monotonic() - 2
        window.refresh()
        self.assertEqual(window.stack.currentIndex(), 1)
        self.assertTrue(window.menu_button.isHidden())
        window.eventFilter(window.idle_clock, QEvent(QEvent.TouchBegin))
        self.assertEqual(window.stack.currentIndex(), 0)
        self.assertTrue(window.header.isHidden())
        self.assertTrue(window.quick_area.isHidden())
        window.config.data["idle_seconds"] = 0
        window.config.data["fullscreen_hide_bars"] = False
        window.update_chrome()
        self.assertTrue(window.header.isVisible())
        window.config.data["quickbar"] = False
        window.update_chrome()
        self.assertTrue(window.quick_area.isHidden())
        QTest.keyClick(window, Qt.Key_F11)
        self.pump()
        self.assertFalse(window.isFullScreen())
        self.assertTrue(window.header.isVisible())
        self.assertTrue(window.quick_area.isHidden())
        window.close()

    def test_volume_expansion_live_streams_and_back_preserves_page(self):
        window = self.window()
        window.show()
        self.pump()
        device = {"id": 1, "name": "speaker", "label": "Speakers", "volume": .4, "mute": False}
        mic = {"id": 2, "name": "mic", "label": "Microphone", "volume": .7, "mute": True}
        streams = [{"id": i, "key": str(i), "label": "Application " + str(i), "volume": .25, "mute": False} for i in range(10, 25)]
        window.audio.state.update(available=True, output=device, input=mic, outputs=[device], inputs=[mic], streams=streams)
        volume = next(t for t in window.dashboard.tiles if t.item["kind"] == "volume")
        QTest.mouseClick(volume.title, Qt.LeftButton)
        self.assertEqual(window.stack.currentIndex(), 2)
        mixer = window.mixer_panel.mixer
        self.assertEqual([r[:2] for r in mixer.rows[:15]], [("stream", i) for i in range(10, 25)])
        for width, height in ((800, 480), (1024, 600), (1280, 800)):
            window.resize(width, height)
            self.pump()
            self.assertLessEqual(mixer.body.minimumSizeHint().width(), mixer.area.viewport().width())
        row = mixer.rows[0][2]
        row.slider.setValue(63)
        row.volume()
        self.assertEqual(window.audio.calls[-1], ("volume", {"kind": "stream", "id": 10, "level": .63}))
        QTest.mouseClick(row.mute, Qt.LeftButton)
        self.assertEqual(window.audio.calls[-1], ("mute", {"kind": "stream", "id": 10}))
        window.audio.state["streams"] = streams[1:]
        window.audio.changed.emit(window.audio.state)
        self.assertNotIn(10, [r[1] for r in mixer.rows if r[0] == "stream"])
        QTest.mouseClick(window.mixer_panel.back, Qt.LeftButton)
        self.assertEqual(window.stack.currentIndex(), 0)
        self.assertEqual(window.current_page()["name"], "Home")
        window.showFullScreen()
        self.pump()
        window.open_mixer()
        window.audio.state.update(available=False, error="Mock audio unavailable", streams=[])
        window.audio.changed.emit(window.audio.state)
        self.assertEqual(mixer.rows, [])
        self.assertEqual(mixer.rows_layout.itemAt(0).widget().text(), "Mock audio unavailable")
        QTest.keyClick(window, Qt.Key_Escape)
        self.pump()
        self.assertEqual(window.stack.currentIndex(), 0)
        self.assertTrue(window.isFullScreen())
        self.assertTrue(window.header.isHidden())
        window.close()

    def test_light_control_icons_have_contrast_and_preserve_custom_art(self):
        def colors(item):
            image = item.pixmap(48, 48).toImage()
            return [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()) if image.pixelColor(x, y).alpha() > 100]
        for theme, light in (("Light", True), ("Dark", False), ("OLED Dark", False)):
            set_icon_theme(theme)
            # Missing KDE themes must still produce recognizable controls.
            with patch.object(QIcon, "fromTheme", side_effect=lambda name, fallback: fallback):
                for name in ("audio-input-microphone", "microphone-sensitivity-muted", "audio-volume-high", "audio-volume-muted", "media-playback-start", "media-playback-pause"):
                    pixels = colors(icon(name, symbolic=True))
                    self.assertTrue(pixels, (theme, name))
                    if light:
                        self.assertTrue(all(max(p.red(), p.green(), p.blue()) < 80 for p in pixels))
                    else:
                        self.assertTrue(all(min(p.red(), p.green(), p.blue()) > 180 for p in pixels))
        custom = self.base / "custom.svg"
        custom.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="#0080ff"/></svg>', encoding="utf-8")
        set_icon_theme("Light")
        self.assertTrue(all(p.blue() > 240 and p.red() < 20 for p in colors(icon(str(custom), symbolic=True))))
        window = self.window()
        window.config.data["theme"] = "Light"
        window.rebuild()
        microphone = next(t for t in window.dashboard.tiles if t.item["kind"] == "microphone")
        self.assertTrue(all(max(p.red(), p.green(), p.blue()) < 80 for p in colors(microphone.title.icon())))
        window.close()

    def test_existing_config_and_fullscreen_preference_persist(self):
        data = defaults()
        data.pop("fullscreen_hide_bars")
        validate(data)
        window = self.window()
        settings = Settings(window)
        self.assertTrue(settings.hide_bars.isChecked())
        settings.hide_bars.setChecked(False)
        settings.save()
        self.assertFalse(Config().data["fullscreen_hide_bars"])
        invalid = copy.deepcopy(data)
        invalid["fullscreen_hide_bars"] = "false"
        with self.assertRaises(ValueError):
            validate(invalid)
        window.close()


if __name__ == "__main__":
    unittest.main()

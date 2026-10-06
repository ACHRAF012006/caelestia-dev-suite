import time
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QComboBox, QSizePolicy
from ui.common import TouchButton, TouchSlider, button, icon, scroll


class VolumeRow(QWidget):
    def __init__(self, window, kind, ident=None):
        super().__init__()
        self.window, self.kind, self.ident = window, kind, ident
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.PlainText)
        layout.addWidget(self.title)
        controls = QHBoxLayout()
        self.mute = button("Mute", self.toggle)
        self.mute.setMinimumWidth(96)
        self.slider = TouchSlider()
        self.percent = QLabel("—")
        self.percent.setMinimumWidth(45)
        self.slider.valueChanged.connect(lambda value: self.percent.setText(str(value) + "%"))
        self.slider.sliderReleased.connect(self.volume)
        controls.addWidget(self.mute)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.percent)
        layout.addLayout(controls)

    def toggle(self):
        self.window.audio.request("mute", {"kind": self.kind, "id": self.ident})

    def volume(self):
        self.window.audio.request("volume", {"kind": self.kind, "id": self.ident, "level": self.slider.value() / 100})

    def refresh(self, state):
        self.setEnabled(state is not None)
        if state:
            self.title.setText(state["label"])
            self.mute.setText("Unmute" if state["mute"] else "Mute")
            app_icon = state.get("icon", "") if self.kind == "stream" else ""
            control_icon = ("microphone-sensitivity-muted" if state["mute"] else "audio-input-microphone") if self.kind == "input" else ("audio-volume-muted" if state["mute"] else "audio-volume-high")
            self.mute.setIcon(icon(app_icon or control_icon, symbolic=not bool(app_icon)))
            self.mute.setToolTip("Muted" if state["mute"] else "Unmuted")
            if not self.slider.isSliderDown():
                self.slider.setValue(round(state["volume"] * 100))
        else:
            self.title.setText("Device unavailable")
            self.percent.setText("—")


class Mixer(QWidget):
    def __init__(self, window, streams_first=False):
        super().__init__()
        self.window = window
        self.streams_first = streams_first
        layout = QVBoxLayout(self)
        self.body = QWidget()
        self.rows_layout = QVBoxLayout(self.body)
        self.area = scroll(self.body)
        layout.addWidget(self.area)
        self.signature = None
        self.rows = []

    def refresh(self):
        state = self.window.audio.state
        signature = (state["available"], tuple((kind, tuple((x["id"], x["label"]) for x in state[kind])) for kind in ("outputs", "inputs", "streams")))
        if signature != self.signature:
            self.signature = signature
            while self.rows_layout.count():
                item = self.rows_layout.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
            self.rows, self.selectors = [], []
            if not state["available"]:
                self.rows_layout.addWidget(QLabel(state.get("error", "Audio unavailable")))
                return
            if self.streams_first:
                self.add_streams(state)
            for kind, collection in (("output", "outputs"), ("input", "inputs")):
                self.rows_layout.addWidget(QLabel("Output device" if kind == "output" else "Microphone device"))
                selector = QComboBox()
                selector.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                for device in state[collection]:
                    selector.addItem(device["label"], device["id"])
                selector.activated.connect(lambda index, k=kind, combo=selector: self.window.audio.request("device", {"kind": k, "id": combo.itemData(index)}))
                self.rows_layout.addWidget(selector)
                self.selectors.append((kind, selector))
                row = VolumeRow(self.window, kind)
                self.rows_layout.addWidget(row)
                self.rows.append((kind, None, row))
            if not self.streams_first:
                self.add_streams(state)
            self.rows_layout.addStretch()
        if not state["available"]:
            return
        for kind, selector in self.selectors:
            device = state.get(kind)
            selector.setCurrentIndex(selector.findData(device["id"]) if device else -1)
        for kind, ident, row in self.rows:
            item = next((x for x in state["streams"] if x["id"] == ident), None) if kind == "stream" else state.get(kind)
            row.refresh(item)


    def add_streams(self, state):
        self.rows_layout.addWidget(QLabel("Active application streams" if state["streams"] else "No application audio streams"))
        for stream in state["streams"]:
            row = VolumeRow(self.window, "stream", stream["id"])
            self.rows_layout.addWidget(row)
            self.rows.append(("stream", stream["id"], row))


class MixerPanel(QWidget):
    """An expanded, live mixer that leaves the user's page layout untouched."""
    def __init__(self, window):
        super().__init__()
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.back = button("‹ Back", window.close_mixer)
        header.addWidget(self.back)
        title = QLabel("Application volumes")
        title.setWordWrap(True)
        header.addWidget(title, 1)
        layout.addLayout(header)
        self.mixer = Mixer(window, streams_first=True)
        layout.addWidget(self.mixer, 1)


class NowPlaying(QWidget):
    def __init__(self, window, size):
        super().__init__()
        self.window, self.size = window, size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.players = QComboBox()
        self.players.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.players.activated.connect(self.select)
        layout.addWidget(self.players)
        information = QHBoxLayout()
        self.art = QLabel()
        self.art.setFixedSize(60 if size == (2, 2) else 40, 60 if size == (2, 2) else 40)
        self.art.setAlignment(Qt.AlignCenter)
        self.track = QLabel("No media playing")
        self.track.setTextFormat(Qt.PlainText)
        self.track.setWordWrap(True)
        information.addWidget(self.art)
        information.addWidget(self.track, 1)
        layout.addLayout(information, 1)
        self.progress = TouchSlider(1000)
        self.progress.sliderReleased.connect(self.seek)
        self.time = QLabel()
        layout.addWidget(self.progress)
        if size == (2, 2):
            layout.addWidget(self.time)
        controls = QHBoxLayout()
        self.controls = {}
        for method, label, name in (("Previous", "Previous", "media-skip-backward"), ("PlayPause", "Play", "media-playback-start"), ("Next", "Next", "media-skip-forward")):
            b = button(label, lambda checked=False, m=method: self.control(m))
            b.setIcon(icon(name, symbolic=True))
            self.controls[method] = b
            controls.addWidget(b)
        layout.addLayout(controls)
        self.art_path = None

    def select(self, index):
        chosen = self.players.itemData(index)
        data = dict(self.window.config.data)
        data["auto_player"], data["player"] = chosen == "", chosen or ""
        try:
            self.window.config.save(data)
        except (OSError, ValueError) as error:
            self.window.toast(str(error))

    def control(self, method):
        player, _ = self.window.media.selected(self.window.config.data)
        self.window.media.request("media", {"player": player, "method": method})

    def seek(self):
        player, props = self.window.media.selected(self.window.config.data)
        length = props.get("Metadata", {}).get("mpris:length", 0)
        self.window.media.request("media", {"player": player, "method": "SetPosition", "position": int(length * self.progress.value() / 1000)})

    def refresh(self):
        config = self.window.config.data
        players = self.window.media.state["players"]
        signature = [("", "Automatic"), *((name, p.get("identity", name)) for name, p in players.items())]
        if [self.players.itemData(i) for i in range(self.players.count())] != [x[0] for x in signature]:
            self.players.clear()
            for name, label in signature:
                self.players.addItem(label, name)
        chosen = "" if config["auto_player"] else config["player"]
        self.players.setCurrentIndex(max(0, self.players.findData(chosen)))
        _, props = self.window.media.selected(config)
        meta = props.get("Metadata", {})
        title = meta.get("xesam:title", "No media playing")
        artists = meta.get("xesam:artist", [])
        artist = ", ".join(str(x) for x in artists) if isinstance(artists, list) else str(artists)
        album = meta.get("xesam:album", "")
        self.track.setText(str(title) + ("\n" + artist if artist else "") + ("\n" + str(album) if album and self.size == (2, 2) else ""))
        playing = props.get("PlaybackStatus") == "Playing"
        self.controls["PlayPause"].setText("Pause" if playing else "Play")
        self.controls["PlayPause"].setIcon(icon("media-playback-pause" if playing else "media-playback-start", symbolic=True))
        for method, control in self.controls.items():
            capability = {"Previous": "CanGoPrevious", "Next": "CanGoNext", "PlayPause": "CanPause" if playing else "CanPlay"}[method]
            control.setEnabled(bool(props.get("CanControl", False) and props.get(capability, False)))
        length = max(0, meta.get("mpris:length", 0))
        position = props.get("Position", 0)
        if playing:
            position += (time.monotonic() - props.get("sampled", time.monotonic())) * 1000000 * props.get("Rate", 1)
        position = max(0, min(length, position))
        if not self.progress.isSliderDown():
            self.progress.setValue(int(position * 1000 / length) if length else 0)
        self.progress.setEnabled(bool(length and props.get("CanSeek", False)))
        def duration(value):
            return str(int(value / 60000000)) + ":" + str(int(value / 1000000) % 60).zfill(2)
        self.time.setText(duration(position) + " / " + duration(length))
        art_url = QUrl(meta.get("mpris:artUrl", ""))
        art_path = art_url.toLocalFile() if art_url.isLocalFile() else ""
        if art_path != self.art_path:
            self.art_path = art_path
            pixmap = QPixmap()
            try:
                if art_path and Path(art_path).stat().st_size < 10 * 1024 * 1024:
                    pixmap.load(art_path)
            except OSError:
                pass
            if pixmap.isNull():
                pixmap = icon("audio-x-generic", symbolic=True).pixmap(self.art.size())
            self.art.setPixmap(pixmap.scaled(self.art.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class Tile(QFrame):
    def __init__(self, window, item):
        super().__init__()
        self.window, self.item = window, item
        self.setObjectName("tile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        self.title = TouchButton(item["label"])
        self.title.held.connect(lambda: window.tile_menu(item, self.title))
        self.title.clicked.connect(self.activate)
        layout.addWidget(self.title)
        kind = item["kind"]
        if kind == "clock" and not window.edit_mode:
            self.title.hide()
        self.content = None
        if kind == "button":
            layout.setStretch(0, 1)
        elif kind == "mixer":
            self.content = Mixer(window)
        elif kind == "media":
            self.content = NowPlaying(window, (item["w"], item["h"]))
            layout.removeWidget(self.title)
            header = QHBoxLayout()
            header.addWidget(self.title, 1)
            self.content.layout().removeWidget(self.content.players)
            header.addWidget(self.content.players, 1)
            layout.addLayout(header)
        elif kind == "volume":
            self.content = VolumeRow(window, "output")
            self.title.setIcon(icon(item["icon"] or "view-fullscreen", symbolic=not bool(item["icon"])))
            self.title.setText(item["label"] + (" · Expand" if item["w"] == 2 else "\nExpand"))
            self.title.setToolTip("Expand to all application volumes")
            self.title.setAccessibleName(item["label"] + ", expand application mixer")
        elif kind == "microphone":
            self.content = TouchButton()
            self.content.clicked.connect(self.activate)
            self.content.held.connect(lambda: window.tile_menu(item, self.content))
        else:
            self.content = QLabel()
            self.content.setTextFormat(Qt.PlainText)
            self.content.setWordWrap(True)
            self.content.setAlignment(Qt.AlignCenter)
        if self.content:
            layout.addWidget(self.content, 1)
            if kind in ("volume", "media", "mixer"):
                self.content.setEnabled(not window.edit_mode)
        self.refresh()

    def activate(self):
        if self.window.edit_mode:
            self.window.edit_tile(self.item)
        elif self.item["kind"] == "button":
            self.window.actions.execute(self.item["action"])
        elif self.item["kind"] == "microphone":
            self.window.audio.request("mute", {"kind": "input"})
        elif self.item["kind"] in ("volume", "mixer"):
            self.window.open_mixer()

    def refresh(self):
        kind, window = self.item["kind"], self.window
        if kind == "button":
            action = self.item["action"]
            app = window.apps.apps.get(action.get("value"), {}) if action["type"] == "launch" else {}
            name = self.item["icon"] or app.get("icon", "")
            self.title.setIcon(icon(name, symbolic=not bool(name)))
            label = self.item["label"]
            if action["type"] == "launch" and not app:
                label += "\nUnavailable"
            elif action["type"] == "audio" and action.get("value") in ("mic_mute", "output_mute"):
                state = window.audio.state.get("input" if action["value"] == "mic_mute" else "output")
                label += "\n" + ("Muted" if state and state["mute"] else "Unmuted" if state else "Unavailable")
            elif action["type"] == "media" and action.get("value") == "PlayPause":
                _, props = window.media.selected(window.config.data)
                label += "\n" + ("Pause" if props.get("PlaybackStatus") == "Playing" else "Play")
            self.title.setText(label)
        elif kind in ("mixer", "media"):
            self.content.refresh()
        elif kind == "volume":
            self.content.refresh(window.audio.state.get("output"))
        elif kind == "microphone":
            state = window.audio.state.get("input")
            text = "Muted" if state and state["mute"] else "Unmuted" if state else "Microphone unavailable"
            self.content.setText(text + ("\n" + state["label"] if state else ""))
            self.title.setIcon(icon(self.item["icon"] or ("microphone-sensitivity-muted" if state and state["mute"] else "audio-input-microphone"), symbolic=not bool(self.item["icon"])))
        elif kind == "clock":
            options = self.item["settings"]
            pattern = "%H:%M" if options.get("hour24", True) else "%I:%M %p"
            if options.get("seconds"):
                pattern = "%H:%M:%S" if options.get("hour24", True) else "%I:%M:%S %p"
            text = datetime.now().strftime(pattern)
            if options.get("date", True):
                text += datetime.now().strftime("\n%A\n%d %B")
            self.content.setText(text)
            self.content.setStyleSheet("font-size: " + ("20" if self.item["w"] == 2 else "16") + "px; background: transparent;")
        elif kind in ("system", "network"):
            state = window.monitor.state
            if not state or state.get("error"):
                self.content.setText(state.get("error", "Gathering statistics…"))
            elif kind == "system":
                text = "CPU %.0f%% · RAM %.0f%%\nDisk %.0f%% · Uptime %.1f h" % (state["cpu"], state["ram"], state.get("disk", 0), state["uptime"])
                if state.get("temperature") is not None:
                    text += "\nCPU %.0f°C" % state["temperature"]
                if state.get("gpu"):
                    text += "\n" + state["gpu"]
                self.content.setText(text)
            else:
                self.content.setText(state.get("connection", "Network") + "\n" + state.get("ip", "") + "\n↓ %.1f KiB/s · ↑ %.1f KiB/s" % (state["download"] / 1024, state["upload"] / 1024))

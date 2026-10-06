"""PipeWire via pipewire-pulse; one worker owns all libpulse calls."""
import copy
import logging
import queue
import threading
import time
from PySide6.QtCore import QObject, Signal


class Audio(QObject):
    changed = Signal(dict)
    completed = Signal(str, bool, str)

    def __init__(self):
        super().__init__()
        self.state = {"available": False, "error": "Connecting to audio…", "outputs": [], "inputs": [], "streams": []}
        self.changed.connect(self._receive)
        self.tasks = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="touchdeck-audio")
        self.thread.start()

    def _receive(self, state):
        if state["available"] != self.state["available"] or self.state.get("error") == "Connecting to audio…":
            logging.getLogger("touchdeck").info("Audio connected" if state["available"] else "Audio unavailable")
        self.state = state

    def request(self, operation, value=None, token=""):
        self.tasks.put((operation, value, token))

    def close(self):
        self.stop_event.set()

    @staticmethod
    def key(item):
        props = item.proplist
        return props.get("application.id") or props.get("application.process.binary") or props.get("application.name") or item.name

    def _snapshot(self, pulse):
        info = pulse.server_info()
        def device(item):
            return {"id": item.index, "name": item.name, "label": item.description or item.name,
                    "volume": min(1.0, item.volume.value_flat), "mute": bool(item.mute)}
        outputs = [device(x) for x in pulse.sink_list()]
        inputs = [device(x) for x in pulse.source_list() if x.monitor_of_sink == 4294967295]
        streams = []
        for item in pulse.sink_input_list():
            streams.append({"id": item.index, "key": self.key(item), "label": item.proplist.get("application.name") or item.name,
                            "icon": item.proplist.get("application.icon_name", ""),
                            "volume": min(1.0, item.volume.value_flat), "mute": bool(item.mute)})
        return {"available": True, "error": "", "outputs": outputs, "inputs": inputs, "streams": streams,
                "output": next((x for x in outputs if x["name"] == info.default_sink_name), None),
                "input": next((x for x in inputs if x["name"] == info.default_source_name), None)}

    def profile(self):
        return {"output": copy.deepcopy(self.state.get("output")), "input": copy.deepcopy(self.state.get("input")),
                "streams": {x["key"]: x["volume"] for x in self.state["streams"]}}

    def _operate(self, pulse, operation, value):
        if operation == "profile":
            missing = []
            for kind, list_method, default_method in (("output", pulse.sink_list, pulse.sink_default_set),
                                                      ("input", pulse.source_list, pulse.source_default_set)):
                saved = value.get(kind)
                if not saved:
                    continue
                target = next((x for x in list_method() if x.name == saved["name"]), None)
                if target:
                    default_method(target)
                    pulse.volume_set_all_chans(target, saved["volume"])
                    pulse.mute(target, saved["mute"])
                else:
                    missing.append(kind)
            for item in pulse.sink_input_list():
                level = value.get("streams", {}).get(self.key(item))
                if level is not None:
                    pulse.volume_set_all_chans(item, level)
            return "Profile applied" + ("; missing " + ", ".join(missing) + " left unchanged" if missing else "")
        kind = value["kind"]
        items = {"output": pulse.sink_list, "input": pulse.source_list, "stream": pulse.sink_input_list}[kind]()
        ident = value.get("id")
        if ident is None:
            info = pulse.server_info()
            name = info.default_sink_name if kind == "output" else info.default_source_name
            target = next((x for x in items if x.name == name), None)
        else:
            target = next((x for x in items if x.index == ident), None)
        if target is None:
            raise ValueError("Audio device or stream is unavailable")
        if operation == "volume":
            pulse.volume_set_all_chans(target, max(0.0, min(1.0, value["level"])))
            return "Volume updated"
        if operation == "mute":
            muted = value.get("mute", not bool(target.mute))
            pulse.mute(target, muted)
            return ("Microphone " if kind == "input" else "Audio ") + ("muted" if muted else "unmuted")
        if operation == "device":
            (pulse.sink_default_set if kind == "output" else pulse.source_default_set)(target)
            return "Default device switched; existing streams keep their routing"
        raise ValueError("Unknown audio operation")

    def _run(self):
        try:
            import pulsectl
        except ImportError:
            self.changed.emit({**self.state, "error": "Audio unavailable: install declared pulsectl dependency"})
            return
        while not self.stop_event.is_set():
            try:
                with pulsectl.Pulse("touchdeck", connect=False) as pulse:
                    pulse.connect(timeout=2)
                    dirty = [True]
                    pulse.event_mask_set("all")
                    pulse.event_callback_set(lambda event: dirty.__setitem__(0, True))
                    last = 0.0
                    while not self.stop_event.is_set():
                        while not self.tasks.empty():
                            operation, value, token = self.tasks.get_nowait()
                            try:
                                message = self._operate(pulse, operation, value)
                                self.completed.emit(token, True, message)
                            except Exception:
                                self.completed.emit(token, False, "Audio action failed; device/stream may have disappeared")
                            dirty[0] = True
                        now = time.monotonic()
                        if (dirty[0] and now - last > 0.10) or now - last > 5:
                            self.changed.emit(self._snapshot(pulse))
                            dirty[0], last = False, now
                        pulse.event_listen(timeout=0.15)
            except Exception:
                self.changed.emit({"available": False, "error": "Audio unavailable: check pipewire-pulse / libpulse", "outputs": [], "inputs": [], "streams": []})
                while not self.tasks.empty():
                    _, _, token = self.tasks.get_nowait()
                    self.completed.emit(token, False, "Audio unavailable")
                self.stop_event.wait(3)

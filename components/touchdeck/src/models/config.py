import copy
import json
import uuid
from utils.paths import atomic_write, checked, config_dir

KINDS = ("button", "clock", "volume", "microphone", "mixer", "media", "system", "network")
ACTION_TYPES = ("launch", "command", "url", "file", "media", "audio", "profile", "system", "page", "macro", "settings")
MEDIA = ("Previous", "Play", "Pause", "PlayPause", "Stop", "Next")
POWER = ("lock", "logout", "suspend", "reboot", "shutdown")


def uid():
    return uuid.uuid4().hex


def tile(kind, label, w=1, h=1, action=None):
    return {"id": uid(), "kind": kind, "label": label, "icon": "", "w": w, "h": h,
            "settings": {}, "action": action or {"type": "settings"}}


def page(name, tiles=None):
    return {"id": uid(), "name": name, "cols": 4, "rows": 3, "tiles": tiles or []}


def preset(name):
    if name == "Audio":
        return page(name, [tile("mixer", "Audio mixer", 2, 2), tile("microphone", "Microphone"),
                           tile("button", "Settings", action={"type": "settings"})])
    if name == "Media":
        return page(name, [tile("media", "Now Playing", 2, 2), tile("volume", "Master volume", 2),
                           tile("clock", "Clock", 2), tile("microphone", "Microphone")])
    if name == "Gaming":
        return page(name, [tile("volume", "Master volume", 2), tile("microphone", "Microphone"),
                           tile("system", "System", 2), tile("media", "Now Playing", 2, 2)])
    return page(name, [tile("clock", "Clock", 2), tile("microphone", "Microphone"),
                       tile("button", "Settings", action={"type": "settings"}),
                       tile("media", "Now Playing", 2, 2), tile("volume", "Master volume", 2),
                       tile("system", "System", 2)])


def defaults():
    return {"schema": 1, "first_run": True, "theme": "Dark", "accent": "#879cba", "quickbar": True,
            "screen": "", "mode": "Windowed", "fullscreen_hide_bars": True, "idle_seconds": 0, "auto_player": True,
            "player": "", "pages": [preset("Home"), preset("Audio"), preset("Media")], "profiles": {}}


def validate_action(action, depth=0):
    if not isinstance(action, dict) or action.get("type") not in ACTION_TYPES or depth > 1:
        raise ValueError("Unknown or nested action")
    kind = action["type"]
    if kind == "macro":
        steps = action.get("steps", [])
        if not isinstance(steps, list) or not 1 <= len(steps) <= 32:
            raise ValueError("Macros require 1–32 steps")
        for step in steps:
            if not isinstance(step, dict) or step.get("type") == "macro":
                raise ValueError("Nested macros are disabled")
            validate_action(step, depth + 1)
    elif kind == "command":
        argv = action.get("argv")
        if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x or "\0" in x for x in argv):
            raise ValueError("Command requires a nonempty argv string array")
    elif kind in ("launch", "url", "file", "page", "profile"):
        if not isinstance(action.get("value"), str) or not action["value"]:
            raise ValueError("Action requires a value")
    elif kind == "media" and action.get("value") not in MEDIA:
        raise ValueError("Unknown media action")
    elif kind == "system" and action.get("value") not in POWER:
        raise ValueError("Unknown system action")
    elif kind == "audio":
        if action.get("value") not in ("mic_mute", "output_mute", "volume"):
            raise ValueError("Unknown audio action")
        if action["value"] == "volume" and (type(action.get("level")) not in (int, float) or not 0 <= action["level"] <= 100):
            raise ValueError("Volume must be 0–100")
    delay = action.get("delay_ms", 0)
    if type(delay) is not int or not 0 <= delay <= 60000:
        raise ValueError("Delay must be 0–60000 ms")


def validate(data):
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unsupported configuration")
    if data.get("theme") not in ("Dark", "OLED Dark", "Light") or data.get("mode") not in ("Windowed", "Borderless", "Fullscreen"):
        raise ValueError("Invalid appearance or display mode")
    import re
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", data.get("accent", "")):
        raise ValueError("Accent requires #RRGGBB")
    for key in ("quickbar", "first_run", "auto_player"):
        if type(data.get(key)) is not bool:
            raise ValueError("Invalid setting: " + key)
    if type(data.get("fullscreen_hide_bars", True)) is not bool:
        raise ValueError("Invalid setting: fullscreen_hide_bars")
    if not all(isinstance(data.get(key), str) for key in ("screen", "player")):
        raise ValueError("Invalid display or player")
    if type(data.get("idle_seconds")) is not int or not 0 <= data["idle_seconds"] <= 86400:
        raise ValueError("Invalid idle timeout")
    pages = data.get("pages")
    if not isinstance(pages, list) or not 1 <= len(pages) <= 32:
        raise ValueError("Keep 1–32 pages")
    identifiers = set()
    for p in pages:
        if not isinstance(p, dict) or not isinstance(p.get("name"), str) or not p["name"]:
            raise ValueError("Page requires a name")
        for key, low, high in (("cols", 2, 6), ("rows", 1, 6)):
            if type(p.get(key)) is not int or not low <= p[key] <= high:
                raise ValueError("Invalid grid")
        if not isinstance(p.get("tiles"), list) or len(p["tiles"]) > 128:
            raise ValueError("Invalid tiles")
        for item in [p, *p["tiles"]]:
            ident = item.get("id") if isinstance(item, dict) else None
            if not isinstance(ident, str) or not ident or ident in identifiers:
                raise ValueError("Invalid or duplicate ID")
            identifiers.add(ident)
        for t in p["tiles"]:
            if t.get("kind") not in KINDS or not all(isinstance(t.get(k), str) for k in ("label", "icon")):
                raise ValueError("Invalid widget")
            if (t.get("w"), t.get("h")) not in ((1, 1), (2, 1), (2, 2)) or not isinstance(t.get("settings"), dict):
                raise ValueError("Invalid widget size/settings")
            validate_action(t.get("action"))
    if not isinstance(data.get("profiles"), dict):
        raise ValueError("Invalid profiles")
    for name, profile in data["profiles"].items():
        if not isinstance(name, str) or not name or not isinstance(profile, dict):
            raise ValueError("Invalid audio profile")
        for key in ("output", "input"):
            item = profile.get(key)
            if item is not None and (not isinstance(item, dict) or not isinstance(item.get("name"), str)
                                    or type(item.get("volume")) not in (int, float)
                                    or not 0 <= item["volume"] <= 1 or type(item.get("mute")) is not bool):
                raise ValueError("Invalid profile device")
        streams = profile.get("streams", {})
        if not isinstance(streams, dict) or any(not isinstance(k, str) or type(v) not in (int, float) or not 0 <= v <= 1 for k, v in streams.items()):
            raise ValueError("Invalid profile stream levels")
    return data


class Config:
    def __init__(self):
        self.path = config_dir() / "config.json"
        self.backup = config_dir() / "config.backup.json"
        self.history = []
        self.notice = ""
        self.data = defaults()
        for path in (self.path, self.backup):
            try:
                checked(path)
                if path.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError("Configuration too large")
                self.data = validate(json.loads(path.read_text(encoding="utf-8")))
                if path == self.backup:
                    self.notice = "Recovered configuration from backup"
                break
            except FileNotFoundError:
                continue
            except (ValueError, OSError, TypeError, KeyError):
                self.notice = "Invalid configuration; recovered backup or safe defaults. Original kept until you save."

    def save(self, data):
        validate(data)
        if self.path.exists():
            try:
                old = checked(self.path).read_text(encoding="utf-8")
                validate(json.loads(old))
                atomic_write(self.backup, old)
            except (ValueError, TypeError, KeyError):
                atomic_write(self.path.with_name("config.rejected.json"), old)
        atomic_write(self.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        self.history.append(copy.deepcopy(self.data))
        self.history = self.history[-20:]
        self.data = copy.deepcopy(data)

    def undo(self):
        if self.history:
            previous = self.history.pop()
            history = self.history[:]
            self.save(previous)
            self.history = history

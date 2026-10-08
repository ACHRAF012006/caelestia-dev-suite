"""Small input, address and private-XDG boundaries; no shell evaluation."""
import ipaddress
import json
import os
from pathlib import Path
import tempfile


class Failure(Exception):
    pass


def text(value, limit=160):
    return "".join(c for c in str(value) if c.isprintable())[:limit]


def local_ip(value):
    if not isinstance(value, str):
        raise Failure("Receiver has an invalid address")
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        raise Failure("Receiver has an invalid address") from None
    networks = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16")
    if ip.version != 4 or not any(ip in ipaddress.ip_network(n) for n in networks):
        raise Failure("Use a private or link-local IPv4 receiver address")
    if str(ip).endswith(".255"):
        raise Failure("Broadcast-like receiver address rejected")
    return str(ip)


def no_links(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise Failure("Invalid component data path")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise Failure("Symlinked component data paths are not supported")
    return path


def private_dir(path):
    path = no_links(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise Failure("Component directory has a different owner")
    path.chmod(0o700)
    return path


class Preferences:
    defaults = {"source": "default", "format": "hls", "latency": "fast", "bitrate": 192, "remember": True,
                "reconnect": False, "last": "", "discovery_timeout": 45, "manual_devices": [], "stream_port": 48200}

    def __init__(self):
        home = Path.home()
        self.directory = private_dir(Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "cast-audio")
        self.path = no_links(self.directory / "settings.json")
        self.notice = ""
        self.values = dict(self.defaults)
        try:
            if self.path.exists():
                if self.path.stat().st_size > 16384:
                    raise ValueError()
                self.values = self.validate(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, Failure):
            self.notice = "Settings could not be read; using defaults. Saving settings replaces the invalid file."
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", os.environ.get("XDG_CACHE_HOME", str(home / ".cache"))))
        self.runtime = private_dir(runtime / "cast-audio")
        # catt supports aliases/default receivers in its own config. Isolate that
        # config so this component always uses only the validated receiver address.
        self.catt_config = private_dir(self.directory / "catt-config")
        self.catt_cache = private_dir(self.runtime / "catt-cache")

    @classmethod
    def validate(cls, value):
        if not isinstance(value, dict) or set(value) - set(cls.defaults):
            raise Failure("Invalid settings")
        result = {**cls.defaults, **value}
        if result["format"] not in ("hls", "mp3"):
            raise Failure("Unsupported streaming mode")
        if result['latency'] not in ('fast', 'balanced'):
            raise Failure('Unsupported latency profile')
        if type(result["bitrate"]) is not int or result["bitrate"] not in (128, 192, 256, 320):
            raise Failure("Unsupported bitrate")
        if type(result["discovery_timeout"]) is not int or not 15 <= result["discovery_timeout"] <= 60:
            raise Failure("Discovery timeout must be 15–60 seconds")
        for key in ("remember", "reconnect"):
            if type(result[key]) is not bool:
                raise Failure("Invalid preference")
        for key in ("source", "last"):
            if not isinstance(result[key], str) or len(result[key]) > 255 or any(not c.isprintable() for c in result[key]):
                raise Failure("Invalid preference")
        if type(result["stream_port"]) is not int or result["stream_port"] != 0 and not 1024 <= result["stream_port"] <= 65535:
            raise Failure("Stream port must be 0 (automatic) or 1024–65535")
        devices = result["manual_devices"]
        if not isinstance(devices, list) or len(devices) > 16:
            raise Failure("Save at most 16 manual receivers")
        checked, seen = [], set()
        for device in devices:
            if not isinstance(device, dict) or set(device) != {"host", "name"}:
                raise Failure("Manual receivers need a name and IPv4 address")
            host = local_ip(device["host"])
            name = device["name"]
            if not isinstance(name, str) or not name.strip() or len(name) > 80 or any(not c.isprintable() for c in name):
                raise Failure("Receiver name must contain 1–80 printable characters")
            if host in seen:
                raise Failure("Manual receiver IP addresses must be unique")
            seen.add(host)
            checked.append({"host": host, "name": name.strip()})
        result["manual_devices"] = checked
        if not result["remember"]:
            result["last"] = ""
            result["reconnect"] = False
        return result

    def save(self, changes):
        values = self.validate({**self.values, **changes})
        no_links(self.path)
        fd, name = tempfile.mkstemp(prefix="settings-", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(values, out, indent=2)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.values = values

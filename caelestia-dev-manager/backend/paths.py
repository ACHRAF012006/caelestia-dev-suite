"""Every filesystem operation passes through constrained, symlink-free paths."""
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

VERSION = "0.3.2"

class SafetyError(ValueError):
    pass

def component_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", value) or len(value) > 64:
        raise SafetyError("ID must be lowercase letters, digits and single hyphens (max 64).")
    if value in {"caelestia", "caelestia-dev-manager", "python", "python3", "bash", "sh", "systemctl", "journalctl",
                 "quickshell", "qs", "qml6", "qml", "kbuildsycoca6", "desktop-file-validate", "kate", "pip", "pip3", "sudo"}:
        raise SafetyError("Reserved component ID")
    return value

def relative(value):
    if not isinstance(value, str) or not value or "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise SafetyError("Invalid relative filename")
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in {"", ".", ".."} for x in value.split("/")) or value.startswith("~"):
        raise SafetyError(f"Unsafe path: {value}")
    if any(x.startswith(".") for x in p.parts) or any(x in {"__pycache__", "node_modules"} for x in p.parts):
        raise SafetyError(f"Hidden/cache paths are not component files: {value}")
    return p

def no_symlinks(path):
    path = Path(path).absolute()
    for p in [path, *path.parents]:
        if p.is_symlink():
            raise SafetyError(f"Symbolic links are not allowed: {p}")
    return path

def inside(root, path):
    root, path = no_symlinks(root), no_symlinks(path)
    if path == root or not path.resolve().is_relative_to(root.resolve()):
        raise SafetyError(f"Path escapes its allowed child location: {path}")
    return path

def digest(data):
    return hashlib.sha256(data).hexdigest()

def atomic_write(path, data, mode=0o644):
    path = no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cdm-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

@dataclass
class Paths:
    project: Path
    home: Path
    data: Path
    config: Path
    state: Path
    bin: Path

    def __post_init__(self):
        for name in ("project", "home", "data", "config", "state", "bin"):
            value = Path(getattr(self, name)).absolute()
            if any(ord(c) < 32 or ord(c) == 127 for c in str(value)): raise SafetyError("Managed roots cannot contain control characters")
            setattr(self, name, value)

    @classmethod
    def default(cls, project=None):
        home = Path.home()
        return cls(Path(project or os.environ.get("CDM_PROJECT", Path(__file__).resolve().parents[1])), home,
                   Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")),
                   Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")),
                   Path(os.environ.get("XDG_STATE_HOME", home / ".local/state")), home / ".local/bin")

    @classmethod
    def sandbox(cls, root):
        root = Path(root).absolute()
        return cls(root / "project", root / "home", root / "data", root / "config", root / "state", root / "bin")

    @property
    def sources(self): return self.project / "plugins"
    @property
    def manager(self): return self.data / "caelestia-dev-manager"
    @property
    def database(self): return self.state / "caelestia-dev-manager/registry.sqlite3"
    @property
    def backups(self): return self.manager / "backups"
    @property
    def shell(self): return self.config / "quickshell/caelestia"

    def source(self, id): return inside(self.sources, self.sources / component_id(id))

    def root(self, manifest):
        id = component_id(manifest["id"])
        if manifest["type"] in {"caelestia-plugin", "qml-component"}:
            return inside(self.config / "caelestia/plugins", self.config / "caelestia/plugins" / id)
        return inside(self.manager / "apps", self.manager / "apps" / id)

    def allowed(self, manifest, path, shortcuts=()):
        path = no_symlinks(path)
        root = self.root(manifest)
        id = component_id(manifest["id"])
        exact = {self.bin / id, self.data / "applications" / (id + ".desktop"),
                 self.config / "systemd/user" / ("cdm-" + id + ".service")}
        if path in exact or (path != root and path.resolve().is_relative_to(root.resolve())):
            return path
        from backend.desktop import approved_shortcut
        if any(approved_shortcut(manifest, path, descriptor) for descriptor in shortcuts): return path
        raise SafetyError(f"Destination not approved for {id}: {path}")

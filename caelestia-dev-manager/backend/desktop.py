"""Read XDG desktop configuration as data; never source shell configuration."""
import re
from pathlib import Path
from backend.paths import SafetyError, no_symlinks, inside

SHORTCUT_TYPES = {"standalone-app", "script"}

def desktop_directory(paths):
    config = no_symlinks(paths.config / "user-dirs.dirs")
    try: text = config.read_text()
    except FileNotFoundError: return None
    values = []
    for line in text.splitlines():
        if not re.match(r"\s*XDG_DESKTOP_DIR\s*=", line): continue
        match = re.fullmatch(r'\s*XDG_DESKTOP_DIR\s*=\s*"((?:\\.|[^"\\])*)"\s*(?:#.*)?', line)
        if not match: raise SafetyError("Invalid XDG_DESKTOP_DIR in user-dirs.dirs; expected a quoted path")
        raw, value, i = match[1], "", 0
        while i < len(raw):
            if raw[i] == "\\":
                if i + 1 == len(raw) or raw[i+1] not in {'$', '`', '"', '\\'}:
                    raise SafetyError("Invalid escape in XDG_DESKTOP_DIR")
                value += raw[i+1]; i += 2
            elif raw[i] == "$":
                token = next((t for t in ("${HOME}", "$HOME") if raw.startswith(t, i)), None)
                if not token or (token == "$HOME" and i+len(token) < len(raw) and (raw[i+len(token)].isalnum() or raw[i+len(token)] == "_")):
                    raise SafetyError("Only $HOME expansion is supported in XDG_DESKTOP_DIR")
                value += str(paths.home); i += len(token)
            elif raw[i] == "`": raise SafetyError("Commands are not permitted in XDG_DESKTOP_DIR")
            else: value += raw[i]; i += 1
        values.append(value)
    if not values: return None
    if len(values) != 1: raise SafetyError("Duplicate XDG_DESKTOP_DIR configuration")
    if not values[0]: return None
    directory = Path(values[0])
    if not directory.is_absolute() or ".." in directory.parts or any(ord(c) < 32 for c in str(directory)):
        raise SafetyError("XDG desktop directory must be an absolute path without traversal")
    directory = no_symlinks(directory)
    if directory.resolve() == paths.home.resolve(): return None  # XDG disabled-directory convention.
    forbidden = {Path("/"), Path("/usr"), Path("/etc"), Path("/var"), Path("/tmp"), paths.config, paths.data, paths.state, paths.bin, paths.manager, paths.sources}
    if directory.resolve() in {p.resolve() for p in forbidden} or any(directory.is_relative_to(p) for p in (Path("/usr"), Path("/etc"))):
        raise SafetyError("XDG desktop directory is a broad or system directory")
    if directory.exists() and not directory.is_dir(): raise SafetyError("XDG desktop location is not a directory")
    return directory

def shortcut_filename(manifest):
    name = re.sub(r'[/\\\x00-\x1f\x7f]', "-", manifest["name"]).strip(" .")
    return (name or manifest["id"]).encode()[:140].decode(errors="ignore") + ".desktop"

def shortcut_descriptor(directory, filename):
    if not isinstance(filename, str) or not filename.endswith(".desktop") or filename.startswith(".") or len(filename.encode()) > 240 or any(c in filename for c in '/\\') or any(ord(c) < 32 or ord(c) == 127 for c in filename):
        raise SafetyError("Desktop shortcut filename must be a safe, non-hidden .desktop basename")
    directory = no_symlinks(Path(directory))
    path = inside(directory, directory / filename)
    return {"directory": str(directory), "filename": filename, "path": str(path)}

def approved_shortcut(manifest, path, descriptor):
    if manifest["type"] not in SHORTCUT_TYPES or not descriptor: return False
    approved = shortcut_descriptor(descriptor["directory"], descriptor["filename"])
    if approved != descriptor: raise SafetyError("Invalid recorded desktop shortcut path")
    return str(path) == approved["path"]

class ShortcutConflict(SafetyError):
    def __init__(self, path, alternate):
        self.path, self.alternate = path, alternate
        super().__init__(f"An unrelated desktop file already exists: {path}\nSuggested safe filename: {alternate}")

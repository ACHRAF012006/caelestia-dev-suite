"""User data only. No changes to installed source or manager ownership."""
import os
import tempfile
from pathlib import Path


def root(kind):
    defaults = {"CONFIG": ".config", "DATA": ".local/share", "STATE": ".local/state"}
    value = Path(os.environ.get("XDG_" + kind + "_HOME", Path.home() / defaults[kind]))
    if not value.is_absolute():
        value = Path.home() / defaults[kind]
    return value


def checked(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise OSError("Refusing symlink path: " + str(part))
    return path


def directory(path):
    path = checked(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def atomic_write(path, text):
    path = checked(path)
    directory(path.parent)
    fd, temp = tempfile.mkstemp(prefix="touchdeck-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        checked(path)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def config_dir():
    return directory(root("CONFIG") / "touchdeck")


def state_dir():
    return directory(root("STATE") / "touchdeck")

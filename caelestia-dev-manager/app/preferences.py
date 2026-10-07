"""Small user preferences, kept separate from component configuration."""
import json
from backend.paths import no_symlinks, atomic_write


def load(paths):
    try:
        settings = json.loads(no_symlinks(paths.config / "caelestia-dev-manager/settings.json").read_text())
        return settings if isinstance(settings, dict) else {}
    except (OSError, ValueError):
        return {}


def save_animations(paths, enabled):
    settings = load(paths)
    settings["animations_enabled"] = bool(enabled)
    atomic_write(paths.config / "caelestia-dev-manager/settings.json", json.dumps(settings, indent=2).encode(), 0o600)

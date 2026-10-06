import os
import re
import shutil
import subprocess
from backend.paths import no_symlinks

def command(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=4).stdout.strip()
    except (OSError, subprocess.SubprocessError): return ""

def detect(paths):
    osinfo = {}
    try:
        for line in open("/etc/os-release"):
            key, sep, value = line.strip().partition("=")
            if sep: osinfo[key] = value.strip('"')
    except OSError: pass
    version = command(["plasmashell", "--version"]).replace("plasmashell ", "")
    def read(path):
        try: return no_symlinks(path).read_text()
        except (OSError, ValueError): return ""
    loader = read(paths.shell / "services/PluginLoader.qml")
    script = read(paths.shell / "scripts/list-plugins.sh")
    supported = all(s in loader for s in ("metadata.json", "Qt.createComponent", 'target: "plugins"')) and "/caelestia/plugins" in script
    active = command(["systemctl", "--user", "is-active", "caelestia-shell.service"]) == "active"
    return {"os": osinfo.get("PRETTY_NAME", "Unknown"), "os_id": osinfo.get("ID", "unknown"),
            "plasma_version": version, "session": os.environ.get("XDG_SESSION_TYPE", "Unknown"),
            "desktop": os.environ.get("XDG_CURRENT_DESKTOP", "Unknown"), "caelestia_running": active,
            "caelestia_commit": read(paths.shell / ".current_commit").strip(),
            "caelestia_version": read(paths.shell / ".current_version").strip(),
            "plugin_supported": supported, "loader_sha256": __import__('hashlib').sha256(loader.encode()).hexdigest(),
            "shell_path": str(paths.shell), "plugin_path": str(paths.config / "caelestia/plugins"),
            "reload_method": "systemctl --user restart caelestia-shell.service (explicit action)",
            "tools": {x: shutil.which(x) for x in ("python3", "bash", "qml6", "quickshell", "systemctl", "kate", "kbuildsycoca6")}}

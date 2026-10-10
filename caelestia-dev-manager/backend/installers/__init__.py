"""Adapters create declarative file plans. They never run component install scripts."""
from dataclasses import dataclass
from pathlib import Path
import json
import shlex
import shutil
import sys
from backend.paths import SafetyError, digest, inside, no_symlinks
from backend.resources import content

@dataclass
class FilePlan:
    path: Path
    data: bytes | None = None
    source: Path | None = None
    mode: int = 0o644
    checksum: str = ""

    def content(self):
        data = no_symlinks(self.source).read_bytes() if self.source else self.data
        if self.checksum and digest(data) != self.checksum: raise SafetyError(f"Source changed since preview: {self.source}")
        return data

    def seal(self):
        self.checksum = digest(self.content())
        return self

def desktop_quote(value):
    # Desktop Exec undergoes both key-value unescaping and Exec token unescaping.
    value = str(value).replace("%", "%%")
    value = value.replace("\\", "\\\\\\\\").replace('"', '\\\\"').replace("`", "\\\\`").replace("$", "\\\\$")
    return '"' + value + '"'

def unit_quote(value):
    value = str(value).replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
    return '"' + value + '"'

class BaseInstaller:
    capabilities = {"install", "update", "uninstall", "backup", "restore"}

    def __init__(self, paths): self.paths = paths

    def command(self, m):
        root = self.paths.root(m)
        deps = m.get("dependencies", {}).get("python", [])
        if deps:
            interpreter = str(root / "_venv/bin/python")
        else:
            interpreter = shutil.which("python3") or sys.executable
        runtimes = {"python": interpreter, "python-pyside6": interpreter,
                    "shell": shutil.which("bash") or "/usr/bin/bash", "qml": shutil.which("qml6") or "/usr/bin/qml6"}
        flags = ["-B"] if m["runtime"] in {"python", "python-pyside6"} else []
        return [runtimes[m["runtime"]], *flags, str(root / m["entrypoint"]), *m.get("args", [])]

    def plan_install(self, m, files, dependencies=None):
        root = self.paths.root(m)
        result = [FilePlan(inside(root, root / path), data=content(value)).seal() for path, value in files.items()]
        if dependencies:
            for source in sorted(dependencies.rglob("*")):
                no_symlinks(source)
                if "__pycache__" in source.relative_to(dependencies).parts or source.suffix == ".pyc": continue
                if source.is_file():
                    target = inside(root, root / "_venv" / source.relative_to(dependencies))
                    result.append(FilePlan(target, source=source, mode=source.stat().st_mode & 0o777).seal())
        return result

    def launcher(self, m):
        return ("#!/bin/sh\n# Managed component launcher; no Dev Manager runtime required.\n" +
                "cd " + shlex.quote(str(self.paths.root(m))) + " || exit 1\n" +
                "exec " + shlex.join(self.command(m)) + "\n").encode()

    def desktop(self, m, enabled=True):
        def value(text): return str(text).replace("\\", "\\\\")
        icon = str(self.paths.root(m) / m["desktop"]["icon"]) if m.get("desktop", {}).get("icon") else "applications-development"
        settings = m.get("desktop", {})
        return ("[Desktop Entry]\nType=Application\n" + f"Name={value(m['name'])}\nComment={value(m.get('description', ''))}\n" +
                f"Exec={desktop_quote(self.paths.bin / m['id'])}\nIcon={value(icon)}\n" +
                f"Terminal={'true' if settings.get('terminal', m['type'] == 'script') else 'false'}\n" +
                f"Categories={settings.get('categories', 'Utility;')}\n" +
                f"StartupNotify={'true' if settings.get('startupNotify', False) else 'false'}\n" +
                f"Hidden={'false' if enabled else 'true'}\n").encode()

class StandaloneAppInstaller(BaseInstaller):
    capabilities = BaseInstaller.capabilities | {"enable", "disable", "launch", "stop", "restart", "logs"}

    def plan_install(self, m, files, dependencies=None):
        result = super().plan_install(m, files, dependencies)
        result += [FilePlan(self.paths.bin / m["id"], self.launcher(m), mode=0o755).seal(),
                   FilePlan(self.paths.data / "applications" / (m["id"] + ".desktop"), self.desktop(m)).seal()]
        return result

class ScriptInstaller(BaseInstaller):
    capabilities = BaseInstaller.capabilities | {"enable", "disable", "launch", "stop", "logs"}
    def plan_install(self, m, files, dependencies=None):
        return super().plan_install(m, files, dependencies) + [FilePlan(self.paths.bin / m["id"], self.launcher(m), mode=0o755).seal()]

class UserServiceInstaller(BaseInstaller):
    capabilities = BaseInstaller.capabilities | {"enable", "disable", "launch", "stop", "restart", "logs"}
    def plan_install(self, m, files, dependencies=None):
        result = super().plan_install(m, files, dependencies)
        unit = self.unit(m)
        result.append(FilePlan(self.paths.config / "systemd/user" / ("cdm-" + m["id"] + ".service"), unit).seal())
        return result

    def unit(self, m):
        unit = ("[Unit]\n" + f"Description={m['name'].replace('%', '%%')}\n\n[Service]\nType=simple\n" +
                "WorkingDirectory=" + str(self.paths.root(m)).replace("%", "%%") + "\n" +
                "ExecStart=" + " ".join(unit_quote(x) for x in self.command(m)) + "\n" +
                "Restart=" + m.get("service", {}).get("restart", "no") + "\nRestartSec=3\n" +
                "NoNewPrivileges=true\n\n[Install]\nWantedBy=default.target\n")
        return unit.encode()

class CaelestiaPluginInstaller(BaseInstaller):
    capabilities = BaseInstaller.capabilities | {"enable", "disable", "logs"}

class KDEIntegrationInstaller(BaseInstaller):
    capabilities = set()
    def plan_install(self, *args, **kwargs): raise SafetyError("No verified KDE integration adapter yet")

def installer(paths, m):
    from backend.capabilities import capabilities
    return capabilities.installer(paths, m)

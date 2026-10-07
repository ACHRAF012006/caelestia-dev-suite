"""User-level installer. Its receipt is separate from all component ownership."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

def no_links(path):
    for p in [path, *path.parents]:
        if p.is_symlink(): raise RuntimeError(f"Refusing symlink: {p}")
    return path

def checksum(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, data, mode=0o644):
    no_links(path).parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".cdm-")
    try:
        with os.fdopen(fd, "w") as stream: stream.write(data)
        os.chmod(tmp, mode); os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    project = args.project.resolve()
    home = Path.home(); data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    base = no_links(data / "caelestia-dev-manager/manager")
    receipt = no_links(config / "caelestia-dev-manager/manager-install.json")
    launcher = no_links(home / ".local/bin/caelestia-dev-manager")
    desktop = no_links(data / "applications/caelestia-dev-manager.desktop")
    old = json.loads(receipt.read_text()) if receipt.exists() else {"files": []}
    def allowed(path):
        path = no_links(Path(path))
        if path in {launcher, desktop} or (path != base and path.is_relative_to(base)): return path
        raise RuntimeError("Unsafe manager receipt path: " + str(path))
    for f in old["files"]: allowed(f["path"])
    if args.uninstall:
        # No purge mode: components, registry, backups and source are intentionally independent.
        modified = [f["path"] for f in old["files"] if allowed(f["path"]).is_file() and checksum(Path(f["path"])) != f["checksum"]]
        if modified: raise RuntimeError("Modified manager files preserved. Resolve before uninstall:\n" + "\n".join(modified[:20]))
        parents = set()
        for f in old["files"]:
            p = allowed(f["path"])
            if p.exists(): p.unlink()
            for parent in p.parents:
                if parent == base or parent.is_relative_to(base): parents.add(parent)
        for p in sorted(parents, key=lambda p: len(p.parts), reverse=True):
            try: no_links(p).rmdir()
            except OSError: pass
        if receipt.exists(): receipt.unlink()
        print("Manager uninstalled. Components, development source, registry and backups remain.")
        return
    osinfo = Path("/etc/os-release").read_text()
    print("CachyOS/Arch detected" if 'ID=cachyos' in osinfo or 'ID=arch' in osinfo or 'ID_LIKE=arch' in osinfo else "Non-Arch environment detected; user-level installation supported")
    for tool in ("python3", "systemctl"):
        if not shutil.which(tool): raise RuntimeError(f"Missing dependency: {tool}; install manually")
    owned = {f["path"] for f in old["files"]}
    for p in (launcher, desktop):
        if p.exists() and str(p) not in owned: raise RuntimeError(f"Existing unowned manager destination: {p}")
    if base.exists() and not receipt.exists(): raise RuntimeError("Existing manager directory lacks a receipt; refusing overwrite")
    if base.exists():
        extra = [p for p in base.rglob("*") if p.is_file() and str(p) not in owned and "__pycache__" not in p.parts]
        if extra: raise RuntimeError("Unowned files in manager install; refusing update")
    # Preserve state and source; only a manager-specific virtualenv receives packages.
    env = base / "venv"
    if not env.exists():
        subprocess.run([sys.executable, "-m", "venv", "--copies", str(env)], check=True)
        if (env / "lib64").is_symlink(): (env / "lib64").unlink()
    try:
        subprocess.run([str(env / "bin/python"), "-m", "pip", "install", "--only-binary=:all:", "PySide6>=6.8,<7", "packaging>=24", "setuptools", "wheel"], check=True)
        subprocess.run([str(env / "bin/python"), "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(project)], check=True)
        subprocess.run([str(env / "bin/python"), "-I", "-B", "-c", "from app.main import Window; from PySide6.QtWidgets import QApplication"], check=True)
        command = "#!/bin/sh\nexec " + shlex.quote(str(env / "bin/python")) + " -I -B -m app.main --project " + shlex.quote(str(project)) + ' "$@"\n'
        write(launcher, command, 0o755)
        # Use the same XDG-compliant Exec quoting as component desktop entries.
        sys.path.insert(0, str(project))
        from backend.installers import desktop_quote
        write(desktop, "[Desktop Entry]\nType=Application\nName=Caelestia Dev Manager\nComment=Create and manage independent KDE and Caelestia components\nExec=" + desktop_quote(launcher) + "\nIcon=applications-development\nTerminal=false\nCategories=Development;\n")
    finally:
        # Persist partial ownership too, so a failed dependency download is recoverable/uninstallable.
        files = []
        for p in sorted(base.rglob("*")):
            if p.is_file() and not p.is_symlink(): files.append({"path": str(p), "checksum": checksum(p)})
        for p in (launcher, desktop):
            if p.exists(): files.append({"path": str(p), "checksum": checksum(p)})
        write(receipt, json.dumps({"version": "0.3.1", "project": str(project), "files": files}, indent=2), 0o600)
    for directory in (data / "caelestia-dev-manager/apps", data / "caelestia-dev-manager/backups", config / "caelestia-dev-manager", Path(os.environ.get("XDG_STATE_HOME", home / ".local/state")) / "caelestia-dev-manager"):
        no_links(directory).mkdir(parents=True, exist_ok=True)
    if shutil.which("desktop-file-validate"): subprocess.run(["desktop-file-validate", str(desktop)], check=True)
    if shutil.which("kbuildsycoca6"): subprocess.run(["kbuildsycoca6", "--noincremental"], check=True)
    print(f"Installed manager: {base}\nCommand: {launcher}\nDesktop entry: {desktop}\nDevelopment repository: {project}")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(str(e), file=sys.stderr); sys.exit(1)

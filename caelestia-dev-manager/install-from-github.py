#!/usr/bin/env python3
"""Download/update the source checkout, then run the user-level manager installer."""
import argparse
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys

REPOSITORY = "https://github.com/ACHRAF012006/caelestia-dev-suite.git"


def no_links(path):
    path = Path(path).absolute()
    for child in (path, *path.parents):
        if child.is_symlink(): raise RuntimeError("Refusing symbolic link: " + str(child))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install Caelestia Dev Manager from GitHub without root privileges")
    parser.add_argument("--directory", type=Path, help="Source checkout (default XDG_DATA_HOME/caelestia-dev-manager/repository)")
    parser.add_argument("--clone-only", action="store_true", help="Fetch source without installing or running its code")
    args = parser.parse_args(argv)
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git is not installed. Install the git package with your system package manager and run this script again. This installer never elevates privileges.")
    if sys.version_info < (3, 11): raise RuntimeError("Python 3.11 or newer is required")
    if not shutil.which("systemctl") and not args.clone_only:
        raise RuntimeError("systemctl is missing. Install the systemd tools before installing the manager.")
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    destination = no_links(args.directory or data / "caelestia-dev-manager/repository")
    def run(*command):
        credential = []
        github_cli = shutil.which("gh")
        if github_cli:
            credential = ["-c", "credential.https://github.com.helper=!" + shlex.quote(github_cli) + " auth git-credential"]
        return subprocess.run([git, "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never",
                               "-c", "protocol.ext.allow=never", *credential, *command], check=True, capture_output=True, text=True, timeout=180).stdout.strip()
    if destination.exists():
        if not (destination / ".git").is_dir():
            raise RuntimeError("The source destination already exists and is not a Git checkout; refusing to overwrite it")
        for child in destination.rglob("*"): no_links(child)
        if run("-C", str(destination), "remote", "get-url", "origin") != REPOSITORY:
            raise RuntimeError("Unexpected repository origin; refusing update")
        if run("-C", str(destination), "status", "--porcelain"):
            raise RuntimeError("The repository has local changes. Save them before updating; this installer will not reset or discard code")
        if run("-C", str(destination), "branch", "--show-current") != "main":
            raise RuntimeError("The source checkout must be on main; refusing to change branches")
        run("-C", str(destination), "fetch", "--no-tags", "origin", "main")
        run("-C", str(destination), "merge", "--ff-only", "origin/main")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        run("clone", "--branch", "main", "--single-branch", "--", REPOSITORY, str(destination))
    for child in destination.rglob("*"): no_links(child)
    manager = no_links(destination / "caelestia-dev-manager")
    installer = no_links(manager / "scripts/install_manager.py")
    if not installer.is_file(): raise RuntimeError("The checkout has no supported manager installer")
    commit = run("-C", str(destination), "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit): raise RuntimeError("Invalid Git commit")
    print("Repository: " + REPOSITORY + "\nCommit: " + commit + "\nSource: " + str(destination), flush=True)
    if args.clone_only:
        print("Source downloaded only. No downloaded code was executed.")
        return 0
    print("Installing the manager in user XDG directories. Components are installed separately through the store.", flush=True)
    subprocess.run([sys.executable, "-B", str(installer), str(manager)], check=True)
    print("Launch: caelestia-dev-manager", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        message = "Git request failed; check your connection and GitHub access." if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(message, file=sys.stderr)
        sys.exit(1)

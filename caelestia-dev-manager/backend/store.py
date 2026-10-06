"""Read a GitHub component catalogue as inert Git blobs, never checked-out code."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import signal
import threading
import time
from datetime import datetime, timezone

from backend.paths import SafetyError, atomic_write, no_symlinks, relative, component_id
from backend.validators import manifest_parse

DEFAULT_REPOSITORY = "https://github.com/ACHRAF012006/caelestia-dev-suite.git"
MAX_COMPONENT_BYTES = 8 * 1024 * 1024
MAX_CATALOG_BYTES = 64 * 1024 * 1024


def source_hash(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def checked_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {"repository", "branch", "check_on_startup"}:
        raise SafetyError("Invalid component store settings")
    if not isinstance(settings["repository"], str) or not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git", settings["repository"]):
        raise SafetyError("Use an HTTPS GitHub repository URL ending in .git, without credentials")
    branch = settings["branch"]
    if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,120}", branch) or any(x in branch for x in ("..", "//", ".lock")) or branch.endswith(("/", ".")):
        raise SafetyError("Invalid repository branch")
    if type(settings["check_on_startup"]) is not bool:
        raise SafetyError("Invalid startup check preference")
    return dict(settings)


def checked_files(files, expected_id=None):
    if not isinstance(files, dict) or not 1 <= len(files) <= 500:
        raise SafetyError("A component must contain 1–500 UTF-8 files")
    total = 0
    for name, value in files.items():
        relative(name)
        if name.split("/")[0] == "_venv" or not isinstance(value, str) or "\0" in value:
            raise SafetyError("Reserved path or non-text component file")
        if any(other.startswith(name + "/") for other in files):
            raise SafetyError("Conflicting component file paths")
        total += len(value.encode("utf-8"))
        if name.endswith(".py"):
            try:
                ast.parse(value, filename=name)
            except (SyntaxError, ValueError) as error:
                raise SafetyError("Invalid Python source: " + name) from error
    if total > MAX_COMPONENT_BYTES:
        raise SafetyError("Component exceeds 8 MiB")
    manifest = manifest_parse(files.get("manifest.json", ""))
    if expected_id is not None and manifest["id"] != expected_id:
        raise SafetyError("Component directory and manifest ID differ")
    if manifest.get("entrypoint") not in files:
        raise SafetyError("Component entrypoint is missing")
    if manifest.get("desktop", {}).get("icon") and manifest["desktop"]["icon"] not in files:
        raise SafetyError("Component icon is missing")
    return manifest


class Store:
    def __init__(self, paths):
        self.paths = paths
        self.settings_path = no_symlinks(paths.config / "caelestia-dev-manager/store.json")
        self.base = no_symlinks(paths.manager / "store")
        self.notice = ""
        self.cancelled = threading.Event()
        defaults = {"repository": DEFAULT_REPOSITORY, "branch": "main", "check_on_startup": True}
        try:
            self.settings = checked_settings(json.loads(self.settings_path.read_text())) if self.settings_path.exists() else defaults
        except (OSError, ValueError, TypeError, KeyError):
            self.settings = defaults
            self.notice = "Invalid store settings; using the default repository"

    def save_settings(self, repository, branch, check_on_startup):
        settings = checked_settings({"repository": repository, "branch": branch, "check_on_startup": check_on_startup})
        atomic_write(self.settings_path, json.dumps(settings, indent=2).encode())
        self.settings = settings

    def key(self):
        return hashlib.sha256((self.settings["repository"] + "\n" + self.settings["branch"]).encode()).hexdigest()[:24]

    def cache_path(self):
        return no_symlinks(self.base / self.key() / "catalog.json")

    def cached(self):
        path = self.cache_path()
        try:
            if not path.exists(): return None
            if path.stat().st_size > MAX_CATALOG_BYTES * 2: raise SafetyError("Oversized catalogue cache")
            catalog = json.loads(path.read_text())
            if catalog["repository"] != self.settings["repository"] or catalog["branch"] != self.settings["branch"]:
                raise SafetyError("Catalogue repository changed")
            if not re.fullmatch(r"[0-9a-f]{40,64}", catalog["commit"]): raise SafetyError("Invalid catalogue commit")
            for entry in catalog["entries"]:
                entry["manifest"] = checked_files(entry["files"], entry["manifest"]["id"])
                entry["hash"] = source_hash(entry["files"])
            return catalog
        except (OSError, ValueError, TypeError, KeyError):
            self.notice = "Store cache unavailable; check the repository to rebuild it"
            return None

    def git(self, *args, cwd=None, timeout=45):
        executable = shutil.which("git")
        if not executable: raise SafetyError("Git is missing. Install Git with your package manager, then Check for Updates.")
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
            env.pop(key, None)
        if self.cancelled.is_set(): raise SafetyError("Repository check cancelled")
        credential = []
        github_cli = shutil.which("gh")
        if github_cli:
            credential = ["-c", "credential.https://github.com.helper=!" + shlex.quote(github_cli) + " auth git-credential"]
        process = subprocess.Popen([executable, "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never",
            "-c", "protocol.ext.allow=never", *credential, *args], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while True:
                if self.cancelled.is_set(): raise SafetyError("Repository check cancelled")
                if time.monotonic() > deadline: raise SafetyError("Repository request timed out. Cached components remain available.")
                try:
                    output, _ = process.communicate(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try: process.communicate(timeout=0.5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
        if process.returncode:
            # No credential-bearing subprocess output is persisted or displayed.
            raise SafetyError("Git repository request failed. Check connectivity, repository/branch and access. Private repositories need Git credentials or an authenticated GitHub CLI.")
        return output

    def scan(self):
        checked_settings(self.settings)
        directory = no_symlinks(self.base / self.key() / "objects.git")
        if not directory.exists():
            directory.parent.mkdir(parents=True, exist_ok=True)
            self.git("init", "--bare", str(directory))
        for path in directory.rglob("*"): no_symlinks(path)
        self.git("fetch", "--depth=1", "--no-tags", self.settings["repository"], "refs/heads/" + self.settings["branch"], cwd=directory)
        commit = self.git("rev-parse", "--verify", "FETCH_HEAD^{commit}", cwd=directory).decode().strip()
        if not re.fullmatch(r"[0-9a-f]{40,64}", commit): raise SafetyError("Invalid Git commit")
        tree = self.git("ls-tree", "-r", "-l", "-z", commit, "--", "components/", cwd=directory)
        if len(tree) > 4 * 1024 * 1024: raise SafetyError("Component catalogue file list is too large")
        groups, issues = {}, []
        for item in tree.split(b"\0"):
            if not item: continue
            info, raw_path = item.split(b"\t", 1)
            mode, kind, object_id, size = info.split()
            try:
                name = raw_path.decode("utf-8")
                prefix, ident, child = name.split("/", 2)
                if ident.startswith("_"): continue  # Developer templates are not store products.
                component_id(ident)
            except (ValueError, UnicodeError):
                issues.append("Skipped an unsafe component path")
                continue
            group = groups.setdefault(ident, {"files": {}, "error": "", "bytes": 0})
            try:
                relative(child)
            except ValueError:
                group["error"] = "Unsafe component file path"
                continue
            if kind != b"blob" or mode not in (b"100644", b"100755") or child.split("/")[0] == "_venv":
                group["error"] = "Symlinks, submodules and dependency payloads are refused"
                continue
            group["bytes"] += int(size)
            if int(size) > MAX_COMPONENT_BYTES or group["bytes"] > MAX_COMPONENT_BYTES or len(group["files"]) >= 500:
                group["error"] = "Component exceeds file/size limits"
                continue
            group["files"][child] = object_id.decode("ascii")
        if sum(g["bytes"] for g in groups.values()) > MAX_CATALOG_BYTES or len(groups) > 128:
            raise SafetyError("Component catalogue is too large")
        entries = []
        for ident, group in sorted(groups.items()):
            try:
                if group["error"]: raise SafetyError(group["error"])
                files = {name: self.git("cat-file", "blob", obj, cwd=directory).decode("utf-8") for name, obj in group["files"].items()}
                manifest = checked_files(files, ident)
                entries.append({"manifest": manifest, "files": files, "hash": source_hash(files)})
            except (ValueError, UnicodeError) as error:
                issues.append(ident + ": " + str(error))
        catalog = {"repository": self.settings["repository"], "branch": self.settings["branch"], "commit": commit,
                   "checked_at": datetime.now(timezone.utc).isoformat(), "entries": entries, "issues": issues}
        atomic_write(self.cache_path(), json.dumps(catalog, ensure_ascii=False).encode())
        return catalog


def describe_entry(manager, entry, repository):
    ident = entry["manifest"]["id"]
    record = manager.registry.get(ident)
    if not record: return "Available to download"
    if not manager.paths.source(ident).exists(): return "Source missing; preserve installed copy"
    local = manager.source_hash(manager.read_source(ident))
    origin = record.get("store_origin", {})
    if local == entry["hash"]:
        installed = record.get("installed") and record.get("installed_source_hash") != local
        return "Downloaded; installed update available" if installed else "Source is current"
    if origin.get("repository") != repository: return "Local component; source differs"
    if origin.get("hash") != local: return "Local edits protected"
    return "Source update available"

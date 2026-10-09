import functools
import fcntl
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from backend.paths import SafetyError, atomic_write, digest, inside, no_symlinks, relative
from backend.validators import manifest_parse, validate
from backend.registry import Registry
from backend.environment import detect
from backend.installers import installer, FilePlan
from backend.backups import Backups, now
from backend.runtime import Runtime
from backend.desktop import SHORTCUT_TYPES, ShortcutConflict, desktop_directory, shortcut_filename, shortcut_descriptor
from backend.dependencies import DependencyError, clean_output, failure_report, python_version, report as dependency_report
from backend import host_integration, system_setup

def locked(method):
    @functools.wraps(method)
    def run(self, *args, **kwargs):
        lockpath = no_symlinks(self.paths.database.parent / "operations.lock")
        with lockpath.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try: return method(self, *args, **kwargs)
            finally: fcntl.flock(lock, fcntl.LOCK_UN)
    return run

class Manager:
    def __init__(self, paths, real=True):
        self.paths = paths
        for root in (paths.sources, paths.manager, paths.database.parent, paths.backups):
            no_symlinks(root).mkdir(parents=True, exist_ok=True)
        self.registry = Registry(paths.database)
        self.backups = Backups(paths)
        self.runtime = Runtime(paths, real)
        self.environment = detect(paths)
        self.journal = paths.database.parent / "pending-operation.json"
        self.discover()

    def ready(self):
        if self.journal.exists(): raise SafetyError("An interrupted operation needs recovery. Open Settings → Recover interrupted operation.")

    def allowed(self, record, path, *shortcuts):
        return self.paths.allowed(record.get("installed_manifest", record["manifest"]), path,
                                  [record.get("desktop_shortcut"), *shortcuts])

    def canonical_desktop(self, m): return self.paths.data / "applications" / (m["id"] + ".desktop")

    def shortcut_target(self, m, record=None, filename=None):
        if m["type"] not in SHORTCUT_TYPES: raise SafetyError("This component cannot have a desktop shortcut")
        existing = (record or {}).get("desktop_shortcut")
        if existing and filename is None:
            descriptor = shortcut_descriptor(existing["directory"], existing["filename"])
        else:
            directory = desktop_directory(self.paths)
            if not directory: raise SafetyError("No XDG desktop directory is configured (or it is disabled). Configure user-dirs.dirs before creating a shortcut.")
            chosen = filename or shortcut_filename(m)
            # Detect symlink conflicts before canonical path checks; offer a separate safe child.
            candidate = directory / chosen
            if candidate.is_symlink():
                raise ShortcutConflict(candidate, self.alternate_shortcut_filename(m, directory))
            descriptor = shortcut_descriptor(directory, chosen)
        path = Path(descriptor["path"])
        if path == self.canonical_desktop(m) or path.is_relative_to(self.paths.root(m)) or path.is_relative_to(self.paths.sources):
            raise SafetyError("The desktop shortcut must be separate from canonical launchers and component source/payloads")
        owner = self.registry.owner(path)
        if owner not in {None, m["id"]} or (path.exists() and owner != m["id"]):
            raise ShortcutConflict(path, self.alternate_shortcut_filename(m, Path(descriptor["directory"])))
        return descriptor

    def alternate_shortcut_filename(self, m, directory):
        stem = shortcut_filename(m)[:-8]
        for i in range(1, 100):
            filename = f"{stem} ({m['id']})" + (f" {i}" if i > 1 else "") + ".desktop"
            candidate = directory / filename
            if not candidate.exists() and not candidate.is_symlink() and not self.registry.owner(candidate): return filename
        raise SafetyError("No unused desktop shortcut filename is available")

    def has_desktop_shortcut(self, id):
        record = self.registry.get(id)
        descriptor = (record or {}).get("desktop_shortcut")
        if not descriptor or not record.get("installed"): return False
        try:
            path = self.allowed(record, Path(descriptor["path"]))
            return path.is_file() and self.registry.owner(path) == id
        except (OSError, ValueError): return False

    def desired_shortcut(self, m, record, override):
        if override is not None:
            if not isinstance(override, bool): raise SafetyError("Shortcut option must be boolean")
            return override
        requested = m.get("desktop", {}).get("createShortcut", False)
        if record and record.get("installed"):
            old_requested = record["installed_manifest"].get("desktop", {}).get("createShortcut", False)
            if requested == old_requested: return record.get("desktop_shortcut_requested", bool(record.get("desktop_shortcut")))
        return requested

    def read_source(self, id):
        source = self.paths.source(id)
        if not source.exists(): raise SafetyError("Development source is missing")
        files = {}
        for p in sorted(source.rglob("*")):
            no_symlinks(p)
            if p.is_file():
                rel = str(p.relative_to(source))
                if any(x.startswith(".") or x in {"__pycache__", "node_modules"} for x in p.relative_to(source).parts): continue
                relative(rel)
                if rel.split("/")[0] == "_venv": raise SafetyError("_venv is reserved for installed dependencies")
                if p.stat().st_size > 8 * 1024 * 1024: raise SafetyError(f"File too large for text source editor: {p}")
                try: files[rel] = p.read_text()
                except UnicodeError: raise SafetyError("Version 0.1 supports UTF-8 text assets only; use SVG icons")
        if sum(len(x.encode()) for x in files.values()) > 16 * 1024 * 1024: raise SafetyError("Source exceeds 16 MiB")
        return files

    def source_hash(self, files):
        return digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())

    def discover(self):
        for p in sorted(self.paths.sources.iterdir()):
            if p.name.startswith("_") or not p.is_dir() or p.is_symlink(): continue
            try:
                m = manifest_parse(no_symlinks(p / "manifest.json").read_text())
                if p.name != m["id"]: raise SafetyError("Source directory must match manifest ID")
                record = self.registry.get(m["id"]) or {"id": m["id"], "installed": False, "enabled": False, "draft": False}
                record.update(manifest=m, source=str(p))
                self.registry.save(record)
            except (OSError, ValueError) as e:
                self.registry.log(p.name, "Source discovery failed: " + str(e))
        self.registry.db.commit()

    @locked
    def create(self, files, draft=False):
        self.ready()
        if len(files) > 500 or sum(len(x.encode()) for x in files.values() if isinstance(x, str)) > 16 * 1024 * 1024:
            raise SafetyError("Source exceeds 500 files or 16 MiB")
        if "manifest.json" not in files: raise SafetyError("manifest.json is required")
        m = manifest_parse(files["manifest.json"])
        result = validate(files, m)
        if not draft and not result["valid"]: raise SafetyError("\n".join(result["errors"]))
        destination = self.paths.source(m["id"])
        if destination.exists() or self.registry.get(m["id"]): raise SafetyError("ID already exists; edit or update the existing component")
        for name, value in files.items():
            relative(name)
            if name.split("/")[0] == "_venv": raise SafetyError("_venv is reserved")
            if not isinstance(value, str): raise SafetyError("Only UTF-8 text source is supported")
            if any(other.startswith(name + "/") for other in files): raise SafetyError("File/directory conflict")
        stage = inside(self.paths.project / "workspace", self.paths.project / "workspace" / ("import-" + uuid.uuid4().hex))
        stage.mkdir(parents=True)
        try:
            for name, value in files.items(): atomic_write(inside(stage, stage / name), value.encode())
            os.rename(stage, destination)
            with self.registry.db:
                self.registry.save({"id": m["id"], "manifest": m, "source": str(destination), "draft": draft,
                                    "installed": False, "enabled": False, "created_at": now()})
                self.registry.log(m["id"], "Saved development source" + (" as draft" if draft else ""))
        finally:
            if stage.exists(): shutil.rmtree(stage)  # Only our newly-created private staging directory.
        return m["id"]

    @locked
    def save_file(self, id, filename, text):
        self.ready()
        target = inside(self.paths.source(id), self.paths.source(id) / relative(filename))
        if filename.split("/")[0] == "_venv": raise SafetyError("Reserved dependency path")
        if filename == "manifest.json":
            m = manifest_parse(text)
            if m["id"] != id: raise SafetyError("Changing a component ID is not supported")
            record = self.registry.get(id)
            if record.get("installed") and m["type"] != record["installed_manifest"]["type"]: raise SafetyError("Uninstall before changing type")
        atomic_write(target, text.encode())
        self.discover()
        with self.registry.db: self.registry.log(id, "Saved source file " + filename)

    @locked
    def remove_file(self, id, filename):
        self.ready()
        if filename == "manifest.json": raise SafetyError("Use Delete Source to remove the project manifest")
        inside(self.paths.source(id), self.paths.source(id) / relative(filename)).unlink()
        with self.registry.db: self.registry.log(id, "Removed source file " + filename)

    def plan_store_download(self, files, repository, commit):
        from backend.store import checked_files, checked_settings
        checked_settings({"repository": repository, "branch": "main", "check_on_startup": True})
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            raise SafetyError("Invalid repository commit")
        m = checked_files(files)
        record = self.registry.get(m["id"])
        exists = self.paths.source(m["id"]).exists()
        current = self.read_source(m["id"]) if exists else None
        before = self.source_hash(current) if current is not None else None
        origin = (record or {}).get("store_origin", {})
        if current is not None and before != self.source_hash(files):
            if origin.get("repository") != repository:
                raise SafetyError("This ID belongs to local source that differs from the store. Preserve it or import under another ID; it will not be overwritten.")
            if origin.get("hash") != before:
                raise SafetyError("Local source has edits since its store download. Back up and resolve those edits before updating.")
        if record and record.get("installed") and m["type"] != record["installed_manifest"]["type"]:
            raise SafetyError("Uninstall before changing component type")
        return {"id": m["id"], "manifest": m, "repository": repository, "commit": commit,
                "hash": self.source_hash(files), "before": before, "record": record,
                "destination": str(self.paths.source(m["id"])), "files": sorted(files),
                "changes": {"added": sorted(set(files) - set(current or {})),
                            "removed": sorted(set(current or {}) - set(files)),
                            "changed": sorted(p for p in files if p in (current or {}) and files[p] != current[p])}}

    @locked
    def download_store_source(self, files, expected):
        """Review source first. Never install, prepare dependencies or start its code."""
        self.ready()
        plan = self.plan_store_download(files, expected["repository"], expected["commit"])
        if plan != expected: raise SafetyError("Source changed since the store preview; review again")
        ident, manifest = plan["id"], plan["manifest"]
        destination = self.paths.source(ident)
        stage = inside(self.paths.project / "workspace", self.paths.project / "workspace" / ("store-" + uuid.uuid4().hex))
        stage.mkdir(parents=True)
        backup = None
        placed = False
        try:
            for name, text in files.items(): atomic_write(inside(stage, stage / name), text.encode())
            if destination.exists():
                backup_root = no_symlinks(self.paths.manager / "source-backups" / uuid.uuid4().hex)
                backup_root.mkdir(parents=True)
                backup = inside(backup_root, backup_root / ident)
                atomic_write(backup_root / "metadata.json", json.dumps({"id": ident, "source": str(destination),
                    "repository": plan["repository"], "commit": plan["commit"], "previous_hash": plan["before"], "date": now()}).encode())
                os.rename(destination, backup)
            os.rename(stage, destination)
            placed = True
            record = plan["record"] or {"id": ident, "installed": False, "enabled": False, "created_at": now()}
            record.update(manifest=manifest, source=str(destination), draft=not validate(files, manifest, self.environment)["valid"],
                          store_origin={"repository": plan["repository"], "commit": plan["commit"], "hash": plan["hash"]})
            with self.registry.db:
                self.registry.save(record)
                self.registry.log(ident, "Downloaded reviewed store source at " + plan["commit"][:12] + ("; previous source: " + str(backup) if backup else ""))
        except Exception:
            if placed: os.rename(destination, stage)
            if backup and backup.exists(): os.rename(backup, destination)
            raise
        finally:
            # Only files we just wrote, followed by empty private directories.
            if stage.exists():
                for name in files:
                    path = inside(stage, stage / name)
                    if path.is_file(): path.unlink()
                for path in sorted(stage.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                    if path.is_dir(): path.rmdir()
                stage.rmdir()
        return ident

    def validation(self, id):
        files = self.read_source(id)
        return validate(files, manifest_parse(files["manifest.json"]), self.environment)

    def prepared_path(self, m):
        key = digest(json.dumps({"python": list(sys.version_info[:2]), "dependencies": m.get("dependencies", {}).get("python", [])}, sort_keys=True).encode())[:16]
        return self.paths.project / "workspace/dependencies" / m["id"] / key / "venv"

    def dependency_status(self, id):
        record = self.registry.get(id)
        if record is None: raise SafetyError("Unknown component")
        m, source_error = record["manifest"], ""
        if self.paths.source(id).exists():
            try:
                current = manifest_parse(self.read_source(id)["manifest.json"])
                if current["id"] != id: raise SafetyError("Manifest ID changed")
                m = current
            except (OSError, ValueError, KeyError) as error:
                source_error = clean_output(str(error))
        target = self.prepared_path(m)
        result = {"component_id": id, "source_manifest_error": source_error,
                  "development": dependency_report(m, target, target.parent / "prepared.json", target.parent / "dependency-error.json")}
        if record.get("installed"):
            installed = record["installed_manifest"]
            result["installed"] = dependency_report(installed, self.paths.root(installed) / "_venv")
        return result

    def dependencies_prepared(self, m):
        target = self.prepared_path(m)
        result = dependency_report(m, target, target.parent / "prepared.json")
        return not result["inspection_error"] and all(x["status"] == "prepared" for x in result["python"]) and (not result["python"] or (target / "bin/python").is_file())

    def plan_system_setup(self, id):
        manifest = manifest_parse(self.read_source(id)["manifest.json"])
        if manifest["id"] != id: raise SafetyError("Manifest ID changed")
        return system_setup.plan(manifest, self.paths)

    @locked
    def prepare_system(self, id, expected):
        self.ready()
        if not self.runtime.real: raise SafetyError("System setup cannot run in sandbox mode")
        system_setup.apply(self.plan_system_setup(id), expected)
        with self.registry.db: self.registry.log(id, "Prepared Cast Audio host packages/firewall through native authentication")

    @locked
    def prepare_dependencies(self, id):
        self.ready()
        files = self.read_source(id)
        m = manifest_parse(files["manifest.json"])
        if m["id"] != id: raise SafetyError("Manifest ID changed")
        deps = m.get("dependencies", {}).get("python", [])
        if not deps: raise SafetyError("No project-local Python dependencies declared")
        if m["runtime"] not in {"python", "python-pyside6", "quickshell"}: raise SafetyError("Python dependencies require Python or a Quickshell sidecar")
        target = no_symlinks(self.prepared_path(m))
        marker = no_symlinks(target.parent / "prepared.json")
        failure = no_symlinks(target.parent / "dependency-error.json")
        if self.dependencies_prepared(m): return str(target)
        if marker.exists(): marker.unlink()
        stage = "environment"
        try:
            # Reuse only checked private staging files; never recursively delete a failed environment.
            if (target / "lib64").is_symlink(): (target / "lib64").unlink()
            for p in target.rglob("*"): no_symlinks(p)
            subprocess.run([shutil.which("python3") or sys.executable, "-m", "venv", "--copies", str(target)], check=True, timeout=90,
                           capture_output=True, text=True)
            # venv creates a redundant lib64 link on Arch; remove the link itself, never its target.
            if (target / "lib64").is_symlink(): (target / "lib64").unlink()
            for p in target.rglob("*"): no_symlinks(p)
            stage = "packages"
            subprocess.run([str(target / "bin/python"), "-m", "pip", "install", "--only-binary=:all:", *deps], check=True, timeout=600,
                           capture_output=True, text=True, env={**os.environ, "PIP_REQUIRE_VIRTUALENV": "true"})
            stage = "verification"
            for p in target.rglob("*"): no_symlinks(p)
            checked = dependency_report(m, target)
            if not all(x["status"] == "prepared" for x in checked["python"]):
                names = ", ".join(x["requirement"] for x in checked["python"] if x["status"] != "prepared")
                raise SafetyError("Installed distribution metadata does not satisfy: " + names)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, SafetyError) as error:
            data = failure_report(m, stage, error)
            data.update(date=now(), python_version=python_version(target), manager_python_version=sys.version.split()[0])
            atomic_write(failure, json.dumps(data, indent=2).encode())
            with self.registry.db: self.registry.log(id, str(DependencyError(data)) + "\n" + data["output"])
            raise DependencyError(data) from error
        atomic_write(marker, json.dumps({"dependencies": deps, "date": now()}).encode())
        if failure.exists(): failure.unlink()
        with self.registry.db: self.registry.log(id, "Prepared isolated Python dependencies (binary wheels only)")
        return str(target)

    def plan_install(self, id, create_shortcut=None, shortcut_filename=None):
        self.ready()
        files = self.read_source(id)
        m = manifest_parse(files["manifest.json"])
        if m["id"] != id: raise SafetyError("Manifest ID changed")
        self.environment = detect(self.paths)
        validation = validate(files, m, self.environment)
        if not validation["valid"]: raise SafetyError("\n".join(validation["errors"]))
        old = self.registry.get(id)
        if old and old.get("installed") and old["installed_manifest"]["type"] != m["type"]: raise SafetyError("Uninstall before changing component type")
        payload = self.paths.root(m)
        if payload.exists() and not (old and old.get("installed_at")) and any(payload.iterdir()):
            raise SafetyError(f"Existing unowned component directory: {payload}")
        dependencies = None
        if m.get("dependencies", {}).get("python"):
            if m["runtime"] not in {"python", "python-pyside6", "quickshell"}: raise SafetyError("Python dependencies require Python or a Quickshell sidecar")
            dependencies = self.prepared_path(m)
            if not self.dependencies_prepared(m): raise SafetyError("Prepare Python dependencies before installation; this is a separate reviewed network operation. Open Dependencies for missing packages or version mismatches.")
        entries = installer(self.paths, m).plan_install(m, files, dependencies)
        host_plan = host_integration.plan(self.paths, m)
        enabled = old.get("enabled") if old and old.get("installed") else host_integration.requested(m) or m["type"] not in {"user-service", "caelestia-plugin", "qml-component"}
        if host_plan and not enabled and host_integration.requested(m):
            host_plan["summary"] = host_plan["summary"].replace("enable the plugin", "preserve its disabled state")
        if not enabled:
            entries = self.disabled_plan(m, entries)
        requested = self.desired_shortcut(m, old, create_shortcut)
        shortcut = None
        canonical = self.canonical_desktop(m)
        if requested and m["type"] not in SHORTCUT_TYPES: raise SafetyError("This component cannot have a desktop shortcut")
        if m["type"] == "script" and (requested or self.registry.owner(canonical) == id):
            entries.append(FilePlan(canonical, installer(self.paths, m).desktop(m, enabled)).seal())
        if requested:
            shortcut = self.shortcut_target(m, old, shortcut_filename)
            canonical_plan = next(x for x in entries if x.path == canonical)
            entries.append(FilePlan(Path(shortcut["path"]), canonical_plan.content(), mode=0o755 if enabled else 0o644).seal())
        if len({str(f.path) for f in entries}) != len(entries): raise SafetyError("Generated installation paths conflict")
        previous = self.registry.files(id)
        previous_by_path = {f["path"]: f for f in previous}
        for item in entries:
            self.paths.allowed(m, item.path, [shortcut])
            owner = self.registry.owner(item.path)
            if owner and owner != id: raise SafetyError(f"Owned by {owner}: {item.path}")
            if item.path.exists() and owner != id: raise SafetyError(f"Refusing to overwrite an unowned file: {item.path}")
        for f in previous:
            path = self.allowed(old, Path(f["path"]))
            if path.exists() and (not path.is_file() or digest(path.read_bytes()) != f["checksum"] or path.stat().st_mode & 0o777 != f["mode"]):
                raise SafetyError(f"Installed file was modified; back it up and resolve it before updating: {path}")
        return {"id": id, "manifest": m, "source_hash": self.source_hash(files), "files": entries,
                "host_integration": host_plan, "enabled": enabled,
                "remove": [f for f in previous if f["path"] not in {str(x.path) for x in entries}],
                "warnings": validation["warnings"], "prepared": dependencies,
                "desktop_shortcut": shortcut, "create_shortcut": requested, "shortcut_filename": shortcut_filename,
                "preview": "\n".join(("REPLACE " if str(x.path) in previous_by_path else "CREATE ") + str(x.path) +
                                      (" [executable]" if x.mode & 0o111 else "") for x in entries) +
                           "\n" + "\n".join("REMOVE " + f["path"] for f in previous if f["path"] not in {str(x.path) for x in entries}) +
                           ("\n\nCAELESTIA KDE INTEGRATION\n" + host_plan["summary"] + "\n" +
                            "\n".join("REVIEW HOST FILE " + str(self.paths.shell / name) + "\nBEFORE\n" + host_plan["before"][name] + "\nAFTER\n" + host_plan["after"][name] for name in host_plan["before"]) if host_plan else "")}

    def disabled_plan(self, m, files):
        result = []
        for f in files:
            if m["type"] in {"caelestia-plugin", "qml-component"} and f.path.name == "metadata.json":
                f = FilePlan(f.path.with_name("metadata.json.disabled"), f.content()).seal()
            elif f.path == self.paths.bin / m["id"]:
                f = FilePlan(f.path, f.content(), mode=0o644).seal()
            elif f.path == self.canonical_desktop(m):
                f = FilePlan(f.path, installer(self.paths, m).desktop(m, False)).seal()
            result.append(f)
        return result

    def transact(self, record, entries, removals, new_record, reason, retain=(), host_plan=None):
        """Backup → durable intent → files → SQLite commit → clear intent. Recoverable on crash."""
        self.ready()
        host_integration.check(self.paths, host_plan)
        m = new_record.get("installed_manifest", new_record["manifest"])
        targets = {str(x.path): {"path": str(x.path)} for x in entries}
        targets.update({f["path"]: f for f in removals})
        for path in targets:
            self.allowed(new_record, Path(path), record.get("desktop_shortcut"))
            owner = self.registry.owner(path)
            if owner not in {None, record["id"]}: raise SafetyError("Ownership collision")
            if Path(path).exists() and owner != record["id"]: raise SafetyError("Refusing an unowned destination")
        old_files = self.registry.files(record["id"])
        backup_record = {**record, "installed_manifest": record.get("installed_manifest", m)}
        # Partial shortcut toggles still get a complete restorable installed snapshot.
        snapshot = {f["path"]: f for f in old_files}
        snapshot.update(targets)
        backup = self.backups.create(backup_record, list(snapshot.values()), reason, [new_record.get("desktop_shortcut")])
        intent = {"backup": backup["backup_id"], "record": record, "ownership": old_files,
                  "operation_id": uuid.uuid4().hex, "phase": "applying", "host_integration": host_plan}
        atomic_write(self.journal, json.dumps(intent).encode(), 0o600)
        try:
            for f in entries: atomic_write(self.allowed(new_record, f.path, record.get("desktop_shortcut")), f.content(), f.mode)
            for f in removals:
                path = self.allowed(record, Path(f["path"]), new_record.get("desktop_shortcut"))
                if path.exists(): path.unlink()
            host_integration.apply(self.paths, host_plan)
            receipt = [*retain, *[{"path": str(f.path), "checksum": f.checksum, "mode": f.mode} for f in entries]]
            new_record["last_operation"] = intent["operation_id"]
            with self.registry.db:
                self.registry.replace_files(record["id"], receipt)
                self.registry.save(new_record)
                self.registry.log(record["id"], reason)
            self.journal.unlink()
            self.prune_empty(m, list(targets))
        except Exception:
            self.registry.db.rollback()
            self._recover()
            raise
        return backup["backup_id"]

    @locked
    def recover(self): return self._recover()

    def _recover(self):
        if not self.journal.exists(): return "No interrupted operation"
        intent = json.loads(no_symlinks(self.journal).read_text())
        current = self.registry.get(intent["record"]["id"])
        if current and current.get("last_operation") == intent["operation_id"]:
            self.journal.unlink()
            return "Committed operation finalized"
        backup = self.backups.read(intent["backup"])
        host_integration.recover(self.paths, intent.get("host_integration"))
        m = backup["record"]["installed_manifest"]
        for f in backup["files"]:
            path = self.paths.allowed(m, Path(f["path"]), [backup["record"].get("desktop_shortcut"), *backup.get("approved_shortcuts", [])])
            if f["exists"]: atomic_write(path, self.backups.content(backup, f), f["mode"])
            elif path.exists(): path.unlink()
        with self.registry.db:
            self.registry.replace_files(intent["record"]["id"], intent["ownership"])
            self.registry.save(intent["record"])
            self.registry.log(intent["record"]["id"], "Recovered interrupted file operation")
        self.journal.unlink()
        self.prune_empty(m, [f["path"] for f in backup["files"]])
        return "Previous installed state recovered"

    def prune_empty(self, m, files):
        root = self.paths.root(m)
        parents = set()
        for path in files:
            p = Path(path).parent
            while p == root or p.is_relative_to(root):
                parents.add(p)
                if p == root: break
                p = p.parent
        for path in sorted(parents, key=lambda x: len(x.parts), reverse=True):
            try: no_symlinks(path).rmdir()
            except OSError: pass

    @locked
    def install(self, id, expected=None, create_shortcut=None, shortcut_filename=None):
        if expected:
            create_shortcut = expected.get("create_shortcut", create_shortcut)
            shortcut_filename = expected.get("shortcut_filename", shortcut_filename)
        plan = self.plan_install(id, create_shortcut, shortcut_filename)
        if expected:
            previous = [(str(x.path), x.checksum, x.mode) for x in expected["files"]]
            current = [(str(x.path), x.checksum, x.mode) for x in plan["files"]]
            if previous != current or expected["source_hash"] != plan["source_hash"] or expected.get("host_integration") != plan.get("host_integration"): raise SafetyError("Installation changed since preview; review a fresh plan")
        record = self.registry.get(id)
        m = plan["manifest"]
        new = {**record, "manifest": m, "installed_manifest": m, "installed": True, "draft": False,
               "enabled": plan["enabled"],
               "installed_version": m["version"], "installed_source_hash": plan["source_hash"],
               "installed_at": record.get("installed_at") or now(), "updated_at": now(), "destination": str(self.paths.root(m)),
               "desktop_shortcut": plan["desktop_shortcut"], "desktop_shortcut_requested": plan["create_shortcut"],
               "reload_required": m["type"] in {"caelestia-plugin", "qml-component"}}
        entries = plan["files"]
        # Services must be stopped while replacing their executable source.
        if m["type"] == "user-service" and record.get("installed"): self.runtime.systemctl("stop", self.runtime.unit(id))
        self.transact(record, entries, plan["remove"], new, "Updated installed version" if record.get("installed") else "Installed component", host_plan=plan["host_integration"])
        if m["type"] == "user-service": self.runtime.systemctl("daemon-reload")
        if m["type"] in SHORTCUT_TYPES: self.runtime.refresh_desktop()
        if host_integration.requested(m) and self.runtime.real:
            self._reload_caelestia()
        return new

    def installed(self, id):
        record = self.registry.get(id)
        if not record or not record.get("installed"): raise SafetyError("Component is not installed")
        return record

    def check_owned_file(self, record, receipt):
        path = self.allowed(record, Path(receipt["path"]))
        if self.registry.owner(path) != record["id"]: raise SafetyError("File is not owned by this component")
        if path.exists() and (not path.is_file() or digest(path.read_bytes()) != receipt["checksum"] or path.stat().st_mode & 0o777 != receipt["mode"]):
            raise SafetyError(f"Modified installed file: {path}. Backup/resolve before replacing or removing it.")
        return path

    def plan_create_desktop_shortcut(self, id, filename=None):
        self.ready()
        record = self.installed(id)
        m = record["installed_manifest"]
        shortcut = self.shortcut_target(m, record, filename)
        if record.get("desktop_shortcut") and record["desktop_shortcut"] != shortcut:
            raise SafetyError("Remove the existing owned shortcut before choosing another location or filename")
        receipts = self.registry.files(id)
        canonical = self.canonical_desktop(m)
        owned_canonical = next((f for f in receipts if f["path"] == str(canonical)), None)
        entries = []
        if owned_canonical:
            path = self.check_owned_file(record, owned_canonical)
            if not path.is_file(): raise SafetyError("Canonical application launcher is missing; repair it with Update first")
            content = path.read_bytes()
        else:
            if m["type"] != "script": raise SafetyError("Canonical application launcher is not owned by this component")
            if canonical.exists() or canonical.is_symlink() or self.registry.owner(canonical): raise SafetyError("Canonical launcher collides with an unrelated file")
            content = installer(self.paths, m).desktop(m, record.get("enabled", False))
            entries.append(FilePlan(canonical, content).seal())
        old_shortcut = next((f for f in receipts if f["path"] == shortcut["path"]), None)
        if old_shortcut: self.check_owned_file(record, old_shortcut)
        entries.append(FilePlan(Path(shortcut["path"]), content, mode=0o755 if record.get("enabled") else 0o644).seal())
        retain = [f for f in receipts if f["path"] not in {str(x.path) for x in entries}]
        return {"record": record, "shortcut": shortcut, "files": entries, "retain": retain,
                "preview": "\n".join(("REPLACE " if self.registry.owner(x.path) == id else "CREATE ") + str(x.path) for x in entries)}

    @locked
    def create_desktop_shortcut(self, id, filename=None, expected=None):
        plan = self.plan_create_desktop_shortcut(id, filename)
        if expected and [(str(x.path), x.checksum, x.mode) for x in expected["files"]] != [(str(x.path), x.checksum, x.mode) for x in plan["files"]]:
            raise SafetyError("Desktop shortcut changed since preview; review a fresh plan")
        record = plan["record"]
        new = {**record, "desktop_shortcut": plan["shortcut"], "desktop_shortcut_requested": True}
        self.transact(record, plan["files"], [], new, "Created desktop shortcut", retain=plan["retain"])
        self.runtime.refresh_desktop()
        return Path(plan["shortcut"]["path"])

    def plan_remove_desktop_shortcut(self, id):
        self.ready()
        record = self.installed(id)
        if record["installed_manifest"]["type"] not in SHORTCUT_TYPES: raise SafetyError("This component cannot have a desktop shortcut")
        descriptor = record.get("desktop_shortcut")
        if not descriptor: raise SafetyError("No manager-owned desktop shortcut is recorded")
        receipt = next((f for f in self.registry.files(id) if f["path"] == descriptor["path"]), None)
        if not receipt: raise SafetyError("Desktop shortcut is not in the component's owned-files database")
        self.check_owned_file(record, receipt)
        return receipt

    @locked
    def remove_desktop_shortcut(self, id):
        receipt = self.plan_remove_desktop_shortcut(id)
        record = self.installed(id)
        new = {**record, "desktop_shortcut": None, "desktop_shortcut_requested": False}
        retain = [f for f in self.registry.files(id) if f["path"] != receipt["path"]]
        self.transact(record, [], [receipt], new, "Removed desktop shortcut; application preserved", retain=retain)

    def check_owned(self, record):
        for f in self.registry.files(record["id"]):
            path = self.allowed(record, Path(f["path"]))
            if path.exists() and (not path.is_file() or digest(path.read_bytes()) != f["checksum"] or path.stat().st_mode & 0o777 != f["mode"]):
                raise SafetyError(f"Modified installed file: {path}. Backup/resolve before removing or replacing it.")

    def plan_uninstall(self, id):
        record = self.installed(id)
        self.check_owned(record)
        host_integration.plan(self.paths, {"id": id})
        return self.registry.files(id)

    @locked
    def uninstall(self, id):
        self.ready()
        record = self.installed(id)
        files = self.plan_uninstall(id)
        m = record["installed_manifest"]
        if m["type"] == "user-service": self.runtime.systemctl("disable", "--now", self.runtime.unit(id))
        elif m["type"] in {"standalone-app", "script"}: self.runtime.stop(record)
        new = {**record, "installed": False, "enabled": False, "uninstalled_at": now(),
               "reload_required": m["type"] in {"caelestia-plugin", "qml-component"}}
        self.transact(record, [], files, new, "Uninstalled owned files; source preserved", host_plan=host_integration.plan(self.paths, {"id": id}))
        if m["type"] == "user-service": self.runtime.systemctl("daemon-reload")
        if m["type"] in SHORTCUT_TYPES: self.runtime.refresh_desktop()
        if host_integration.requested(m) and self.runtime.real:
            self._reload_caelestia()

    @locked
    def set_enabled(self, id, enabled):
        self.ready()
        record = self.installed(id)
        self.check_owned(record)
        m = record["installed_manifest"]
        if enabled == record.get("enabled"): return
        entries, remove = [], []
        for f in self.registry.files(id):
            path = self.allowed(record, Path(f["path"]))
            if not path.exists(): raise SafetyError("Repair missing installed files using Update first")
            item = FilePlan(path, path.read_bytes(), mode=f["mode"]).seal()
            if m["type"] in {"caelestia-plugin", "qml-component"} and path.name in {"metadata.json", "metadata.json.disabled"}:
                item = FilePlan(path.with_name("metadata.json" if enabled else "metadata.json.disabled"), item.content()).seal()
                remove.append(f)
            elif path == self.paths.bin / id: item = FilePlan(path, item.content(), mode=0o755 if enabled else 0o644).seal()
            elif path == self.canonical_desktop(m): item = FilePlan(path, installer(self.paths, m).desktop(m, enabled)).seal()
            elif record.get("desktop_shortcut") and str(path) == record["desktop_shortcut"]["path"]:
                item = FilePlan(path, installer(self.paths, m).desktop(m, enabled), mode=0o755 if enabled else 0o644).seal()
            entries.append(item)
        if m["type"] == "user-service":
            try:
                self.runtime.systemctl("enable" if enabled else "disable", "--now", self.runtime.unit(id))
            except Exception:
                # enable --now can create a symlink before start fails; undo that partial enablement.
                if enabled and not record.get("enabled"):
                    self.runtime.systemctl("disable", self.runtime.unit(id))
                raise
        elif not enabled and m["type"] in {"standalone-app", "script"}: self.runtime.stop(record)
        new = {**record, "enabled": enabled, "reload_required": m["type"] in {"caelestia-plugin", "qml-component"}}
        self.transact(record, entries, remove, new, "Enabled component" if enabled else "Disabled component")
        if m["type"] in SHORTCUT_TYPES: self.runtime.refresh_desktop()
        if host_integration.requested(m) and self.runtime.real:
            self._reload_caelestia()

    @locked
    def backup(self, id):
        record = self.installed(id)
        meta = self.backups.create(record, self.registry.files(id), "Manual backup")
        with self.registry.db: self.registry.log(id, "Created backup " + meta["backup_id"])
        return meta

    def plan_restore(self, backup_id):
        self.ready()
        meta = self.backups.read(backup_id)
        id = meta["component_id"]
        record = self.registry.get(id)
        if not record: raise SafetyError("Restore requires the component registry record")
        if not meta["record"].get("installed"): raise SafetyError("This backup records an uninstalled state; use Uninstall instead")
        self.check_owned(record)
        host_integration.plan(self.paths, meta["record"]["installed_manifest"])
        # Update backups include newly-created destinations marked absent. Only present blobs are restored.
        entries = [FilePlan(Path(f["path"]), self.backups.content(meta, f), mode=f["mode"]).seal() for f in meta["files"] if f["exists"]]
        for f in entries:
            owner = self.registry.owner(f.path)
            if owner not in {None, id} or (f.path.exists() and owner != id): raise SafetyError("Restore would overwrite an unowned file")
        remove = [f for f in self.registry.files(id) if f["path"] not in {str(x.path) for x in entries}]
        return meta, record, entries, remove

    def previous_version_backup(self, id, backups=None):
        record = self.registry.get(id)
        if not record or not record.get("installed"): return None
        for meta in self.backups.list() if backups is None else backups:
            saved = meta["record"]
            if meta["component_id"] != id or not saved.get("installed"): continue
            if (saved.get("installed_source_hash") != record.get("installed_source_hash")
                    or saved.get("installed_version") != record.get("installed_version")):
                return meta
        return None

    @locked
    def restore(self, backup_id):
        meta, record, entries, remove = self.plan_restore(backup_id)
        new = {**meta["record"], "manifest": record["manifest"], "source": record["source"], "restored_at": now()}
        # Source is not restored with the installed payload; keep its current provenance.
        if "store_origin" in record: new["store_origin"] = record["store_origin"]
        else: new.pop("store_origin", None)
        if new["installed_manifest"]["type"] == "user-service": self.runtime.systemctl("stop", self.runtime.unit(record["id"]))
        self.transact(record, entries, remove, new, "Restored backup " + backup_id, host_plan=host_integration.plan(self.paths, new["installed_manifest"]))
        if new["installed_manifest"]["type"] == "user-service": self.runtime.systemctl("daemon-reload")
        if new["installed_manifest"]["type"] in SHORTCUT_TYPES: self.runtime.refresh_desktop()
        if new["installed_manifest"]["type"] in {"caelestia-plugin", "qml-component"}:
            with self.registry.db:
                new["reload_required"] = True
                self.registry.save(new)
        if self.runtime.real and (host_integration.requested(new["installed_manifest"]) or host_integration.requested(record["installed_manifest"])):
            self._reload_caelestia()

    @locked
    def delete_source(self, id, confirmation):
        self.ready()
        if confirmation != id: raise SafetyError("Type the exact component ID to confirm source deletion")
        source = self.paths.source(id)
        self.read_source(id)  # Reject links and special/unreadable source first.
        shutil.rmtree(source)  # Exact validated source project, never installation destinations.
        record = self.registry.get(id)
        record["source_deleted_at"] = now()
        with self.registry.db:
            self.registry.save(record)
            self.registry.log(id, "Deleted development source; installed component preserved")

    def status(self, record):
        result = {**record, "source_exists": self.paths.source(record["id"]).exists(), "missing": [], "modified": [], "pids": [], "source_modified": False}
        result["compatible"] = True
        result["desktop_shortcut_created"] = self.has_desktop_shortcut(record["id"])
        result["desktop_shortcut_state"] = "Created" if result["desktop_shortcut_created"] else "Not Created"
        installed_manifest = record.get("installed_manifest", record["manifest"])
        compat = installed_manifest.get("compatibility", {})
        if compat.get("plasma") and not self.environment.get("plasma_version", "").startswith(compat["plasma"]): result["compatible"] = False
        if compat.get("caelestia_commit") and compat["caelestia_commit"] != self.environment.get("caelestia_commit"): result["compatible"] = False
        try:
            files = self.read_source(record["id"])
            current = manifest_parse(files["manifest.json"])
            result["manifest"] = current
            icon = files.get(current.get("desktop", {}).get("icon") or "assets/icon.svg", "")
            result["icon_svg"] = icon if len(icon.encode()) <= 65536 else ""
            result["source_hash"] = self.source_hash(files)
            result["source_modified"] = bool(record.get("installed") and result["source_hash"] != record.get("installed_source_hash"))
            result["validation"] = validate(files, current, self.environment)
        except (OSError, ValueError, KeyError) as e: result["validation"] = {"valid": False, "errors": [str(e)], "warnings": []}
        for f in self.registry.files(record["id"]):
            try:
                p = self.allowed(record, Path(f["path"]))
                if not p.is_file(): result["missing"].append(str(p))
                elif digest(p.read_bytes()) != f["checksum"] or p.stat().st_mode & 0o777 != f["mode"]: result["modified"].append(str(p))
            except (OSError, ValueError): result["modified"].append(f["path"])
        if record.get("installed"):
            m = record["installed_manifest"]
            if m["type"] == "user-service":
                result["service_state"] = self.runtime.systemctl("is-active", self.runtime.unit(record["id"]))
                result["service_load_state"] = self.runtime.systemctl("show", self.runtime.unit(record["id"]), "--property=LoadState", "--value")
                result["running"] = result["service_state"] == "active"
                result["service"] = self.runtime.unit(record["id"])
                result["enabled"] = self.runtime.systemctl("is-enabled", result["service"]) == "enabled" if self.runtime.real else record.get("enabled")
                pid = self.runtime.systemctl("show", result["service"], "--property=MainPID", "--value")
                if pid.isdigit() and int(pid): result["pids"] = [int(pid)]
            else:
                result["pids"] = self.runtime.processes(record)
                result["running"] = bool(result["pids"])
        else: result["running"] = False
        if record.get("installed") and host_integration.requested(installed_manifest):
            try:
                if not host_integration.receipt_path(self.paths, record["id"]).is_file():
                    raise SafetyError("Host integration receipt is missing")
                host_integration.plan(self.paths, installed_manifest)
                result["host_integration_status"] = "Timer dashboard installed" if record["id"] == "animated-timer" else "Quick Toggles menu installed"
            except (OSError, ValueError) as error:
                result["host_integration_status"] = str(error)
                result["modified"].append("Host integration: " + str(error))
        if result["missing"]: result["status"] = "Missing Files"
        elif result["modified"]: result["status"] = "Broken"
        elif result.get("service_state") == "failed" or result.get("service_load_state") in {"bad-setting", "error", "not-found"}: result["status"] = "Broken"
        elif not result["compatible"]: result["status"] = "Incompatible"
        elif record.get("installed"):
            result["status"] = "Running" if result["running"] else "Enabled" if result["enabled"] else "Disabled"
            if result["source_modified"]: result["status"] += " • Update Available"
            if record.get("reload_required"): result["status"] += " • Reload Required"
        else:
            errors = result["validation"]["errors"]
            missing_dependencies = errors and all(error.startswith("Missing system executable") for error in errors)
            result["status"] = ("Draft" if record.get("draft") else "Ready" if result["validation"]["valid"]
                                else "Missing Dependencies" if missing_dependencies else "Incompatible / Broken")
        return result

    def all_status(self): return [self.status(r) for r in self.registry.all()]

    @locked
    def reload_caelestia(self):
        return self._reload_caelestia()

    def _reload_caelestia(self):
        self.ready()
        if not self.environment.get("plugin_supported"): raise SafetyError("Caelestia integration is unverified")
        self.runtime.systemctl("restart", "caelestia-shell.service")
        with self.registry.db:
            for r in self.registry.all():
                if r.get("reload_required"):
                    r["reload_required"] = False
                    self.registry.save(r)
            self.registry.log(None, "Requested explicit Caelestia shell restart; inspect shell logs for QML errors")

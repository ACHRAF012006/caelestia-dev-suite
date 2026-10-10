import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from backend.paths import VERSION, SafetyError, atomic_write, digest, inside, no_symlinks, component_id, fsync_directory

def now(): return datetime.now(timezone.utc).isoformat()

class Backups:
    def __init__(self, paths): self.paths = paths

    def create(self, record, files, reason, approved_shortcuts=()):
        id = uuid.uuid4().hex
        root = inside(self.paths.backups, self.paths.backups / id)
        root.mkdir(parents=True)
        fsync_directory(root.parent)
        metadata = {"backup_id": id, "component_id": record["id"], "version": record.get("installed_version"),
                    "date": now(), "manager_version": VERSION, "reason": reason, "record": record, "files": [],
                    "approved_shortcuts": [s for s in (record.get("desktop_shortcut"), *approved_shortcuts) if s]}
        manifest = record.get("installed_manifest", record["manifest"])
        for i, f in enumerate(files):
            path = self.paths.allowed(manifest, Path(f["path"]), metadata["approved_shortcuts"])
            item = {"path": str(path), "exists": path.exists(), "blob": str(i)}
            if path.exists():
                if not path.is_file(): raise SafetyError(f"Backup target is not a regular file: {path}")
                data = path.read_bytes()
                atomic_write(root / str(i), data, 0o600)
                item.update(checksum=digest(data), mode=path.stat().st_mode & 0o777)
            metadata["files"].append(item)
        atomic_write(root / "metadata.json", json.dumps(metadata, indent=2).encode(), 0o600)
        return metadata

    def list(self):
        if not self.paths.backups.exists(): return []
        result = []
        for child in self.paths.backups.iterdir():
            if len(child.name) == 32:
                try: result.append(self.read(child.name))
                except (OSError, ValueError): pass
        return sorted(result, key=lambda x: x["date"], reverse=True)

    def catalog(self, checkpoint=lambda: None):
        """Display metadata only; restore/read still verify every owned blob."""
        if not self.paths.backups.exists(): return []
        result = []
        for child in no_symlinks(self.paths.backups).iterdir():
            checkpoint()
            try:
                if len(child.name) != 32 or any(x not in "0123456789abcdef" for x in child.name): continue
                meta = json.loads(no_symlinks(child / "metadata.json").read_text())
                if meta["backup_id"] != child.name or meta["component_id"] != meta["record"]["id"]: continue
                component_id(meta["component_id"])
                if not all(isinstance(meta[key], str) for key in ("date", "reason")): continue
                if meta["version"] is not None and not isinstance(meta["version"], str): continue
                result.append({key: meta[key] for key in ("backup_id", "component_id", "date", "reason", "version", "record")})
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return sorted(result, key=lambda x: x["date"], reverse=True)

    def read(self, id):
        if not isinstance(id, str) or len(id) != 32 or any(x not in "0123456789abcdef" for x in id): raise SafetyError("Invalid backup ID")
        root = inside(self.paths.backups, self.paths.backups / id)
        try:
            metadata = no_symlinks(root / "metadata.json")
            if not metadata.is_file() or metadata.stat().st_size > 32 * 1024 * 1024: raise SafetyError('Missing or oversized backup metadata')
            meta = json.loads(metadata.read_text())
            if meta["backup_id"] != id or meta["component_id"] != meta["record"]["id"]: raise SafetyError("Invalid backup identity")
            component_id(meta['component_id'])
            from backend.validators import manifest_parse
            m = manifest_parse(json.dumps(meta["record"].get("installed_manifest", meta["record"]["manifest"])))
            if m['id'] != meta['component_id']: raise SafetyError('Backup manifest identity mismatch')
            if not isinstance(meta['files'], list) or len(meta['files']) > 100000: raise SafetyError('Invalid backup file count')
            paths, blobs = set(), set()
            for item in meta["files"]:
                self.paths.allowed(m, Path(item["path"]), [meta["record"].get("desktop_shortcut"), *meta.get("approved_shortcuts", [])])
                if not isinstance(item['blob'], str) or not item['blob'].isascii() or not item["blob"].isdigit(): raise SafetyError("Invalid backup blob")
                if item['path'] in paths or item['blob'] in blobs: raise SafetyError('Duplicate backup path/blob')
                paths.add(item['path']); blobs.add(item['blob'])
                if type(item['exists']) is not bool: raise SafetyError('Invalid backup existence flag')
                if item["exists"]:
                    if type(item['mode']) is not int or not 0 <= item['mode'] <= 0o777: raise SafetyError('Invalid backup mode')
                    self.content(meta, item)
            return meta
        except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
            if isinstance(error, SafetyError): raise
            raise SafetyError('Invalid or incomplete backup: ' + str(error)) from error

    def content(self, meta, item):
        data = no_symlinks(self.paths.backups / meta["backup_id"] / item["blob"]).read_bytes()
        if digest(data) != item['checksum']: raise SafetyError('Backup checksum mismatch')
        return data

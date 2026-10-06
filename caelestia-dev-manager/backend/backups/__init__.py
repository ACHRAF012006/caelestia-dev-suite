import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from backend.paths import VERSION, SafetyError, atomic_write, digest, inside, no_symlinks

def now(): return datetime.now(timezone.utc).isoformat()

class Backups:
    def __init__(self, paths): self.paths = paths

    def create(self, record, files, reason, approved_shortcuts=()):
        id = uuid.uuid4().hex
        root = inside(self.paths.backups, self.paths.backups / id)
        root.mkdir(parents=True)
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

    def read(self, id):
        if not isinstance(id, str) or len(id) != 32 or any(x not in "0123456789abcdef" for x in id): raise SafetyError("Invalid backup ID")
        root = inside(self.paths.backups, self.paths.backups / id)
        meta = json.loads(no_symlinks(root / "metadata.json").read_text())
        if meta["backup_id"] != id or meta["component_id"] != meta["record"]["id"]: raise SafetyError("Invalid backup identity")
        m = meta["record"].get("installed_manifest", meta["record"]["manifest"])
        for item in meta["files"]:
            self.paths.allowed(m, Path(item["path"]), [meta["record"].get("desktop_shortcut"), *meta.get("approved_shortcuts", [])])
            if not item["blob"].isdigit(): raise SafetyError("Invalid backup blob")
            if item["exists"]:
                data = no_symlinks(root / item["blob"]).read_bytes()
                if digest(data) != item["checksum"]: raise SafetyError("Backup checksum mismatch")
        return meta

    def content(self, meta, item):
        return no_symlinks(self.paths.backups / meta["backup_id"] / item["blob"]).read_bytes()

"""Read-only UI inspection using a frozen inventory, never SQLite across threads."""
import copy
import threading
from PySide6.QtCore import QThread, Signal
from backend.environment import detect
from backend.runtime import Runtime


class InspectionCancelled(RuntimeError):
    pass


class Inventory:
    def __init__(self, registry, checkpoint):
        self.records = {r["id"]: r for r in registry.all()}
        self.receipts = {ident: registry.files(ident) for ident in self.records}
        self.owners = {f["path"]: ident for ident, files in self.receipts.items() for f in files}
        self.checkpoint = checkpoint

    def get(self, ident): return self.records.get(ident)
    def all(self): return list(self.records.values())
    def owner(self, path): return self.owners.get(str(path))

    def files(self, ident):
        for receipt in self.receipts.get(ident, []):
            self.checkpoint()
            yield receipt


class Inspection(QThread):
    result = Signal(int, dict)
    failed = Signal(int, str)

    def __init__(self, manager, generation, parent=None):
        super().__init__(parent)
        self.generation = generation
        self.cancelled = threading.Event()
        # Capture registry data on its owning thread. Only plain data and paths
        # reach the worker; mutations remain on the real manager's connection.
        self.reader = copy.copy(manager)
        self.reader.registry = Inventory(manager.registry, self.checkpoint)
        self.reader.environment = dict(manager.environment)
        self.reader.runtime = Runtime(manager.paths, manager.runtime.real)
        self.logs = manager.registry.logs()

    def checkpoint(self):
        if self.cancelled.is_set(): raise InspectionCancelled()

    def run(self):
        try:
            self.checkpoint()
            self.reader.environment = detect(self.reader.paths)
            statuses, dependencies = [], {}
            for record in self.reader.registry.all():
                self.checkpoint()
                statuses.append(self.reader.status(record))
                dependencies[record["id"]] = self.reader.dependency_status(record["id"])
            self.checkpoint()
            backups = self.reader.backups.catalog(self.checkpoint)
            self.checkpoint()
            self.result.emit(self.generation, {"statuses": statuses, "dependencies": dependencies,
                             "environment": self.reader.environment, "backups": backups, "logs": self.logs})
        except InspectionCancelled:
            pass
        except Exception as error:
            self.failed.emit(self.generation, str(error))

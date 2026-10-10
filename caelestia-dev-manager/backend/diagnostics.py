"""Read-only diagnostics usable by Qt and CLI. Never initializes or repairs state."""
import importlib.metadata
import json
from pathlib import Path
import platform
import sqlite3
from backend.paths import VERSION, SafetyError, no_symlinks
from backend.database import CURRENT_VERSION
from backend.manager import Manager
from backend.registry import Registry
from backend.runtime import Runtime
from backend.backups import Backups
from backend.environment import detect
from backend.dependencies import clean_output


class ReadRegistry(Registry):
    def __init__(self, path):
        path = no_symlinks(path)
        self.db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        self.db.execute('PRAGMA query_only=ON')

    def history(self, limit=300):
        if self.db.execute('PRAGMA user_version').fetchone()[0] < 2: return []
        return super().history(limit)


def reader(paths, real=True):
    manager = Manager.__new__(Manager)
    manager.paths, manager.registry = paths, ReadRegistry(paths.database)
    manager.backups, manager.runtime = Backups(paths), Runtime(paths, real)
    manager.environment = detect(paths)
    manager.journal = paths.database.parent / 'pending-operation.json'
    return manager


def inspect(paths, context=None, real=True, verify_backups=True):
    def checkpoint():
        if context: context.checkpoint()
    checks = []
    def add(scope, status, detail, component=None):
        checks.append({'scope': scope, 'status': status, 'detail': clean_output(detail), 'component': component})
    result = {'manager_version': VERSION, 'database_schema': None, 'checks': checks, 'components': [],
              'paths': {key: str(getattr(paths, key)) for key in ('project', 'data', 'config', 'state', 'database', 'backups')},
              'system': {'python': platform.python_version(), 'platform': platform.platform()}}
    try: result['system']['qt_binding'] = importlib.metadata.version('PySide6')
    except importlib.metadata.PackageNotFoundError: result['system']['qt_binding'] = 'Unavailable'
    checkpoint()
    if not paths.database.exists():
        add('Database', 'Unknown', 'No registry exists; diagnostics did not create it')
        result['environment'] = detect(paths)
        return result
    manager = None
    try:
        manager = reader(paths, real)
        result['environment'] = manager.environment
        schema = manager.registry.db.execute('PRAGMA user_version').fetchone()[0]
        result['database_schema'] = schema
        integrity = manager.registry.db.execute('PRAGMA quick_check').fetchone()[0]
        add('Database', 'Healthy' if integrity == 'ok' and schema <= CURRENT_VERSION else 'Failed',
            f'Schema {schema} (supported {CURRENT_VERSION}); {integrity}')
        if schema > CURRENT_VERSION: return result
        add('Transaction journal', 'Recovery required' if manager.journal.exists() else 'Healthy',
            'Pending file transaction; use reviewed Settings recovery' if manager.journal.exists() else 'No pending file transaction')
        for record in manager.registry.all():
            checkpoint()
            if context: context.report('Inspecting ' + record['id'])
            try:
                status = manager.status(record)
                result['components'].append(status)
                issues = status['missing'] + status['modified'] + status['validation']['errors']
                add('Component', 'Attention required' if issues else status['status'], '\n'.join(issues) or 'Source and owned payload checks completed', record['id'])
                deps = manager.dependency_status(record['id'])
                for scope in ('development', 'installed'):
                    if scope in deps and not deps[scope]['ready']:
                        add('Dependencies', 'Attention required', scope + ': ' + json.dumps(deps[scope]), record['id'])
            except (OSError, ValueError, KeyError, TypeError) as error: add('Component', 'Failed', str(error), record.get('id'))
        if verify_backups:
            for backup in manager.backups.catalog(checkpoint):
                checkpoint()
                try:
                    manager.backups.read(backup['backup_id'], checkpoint)
                    add('Backup', 'Healthy', backup['backup_id'], backup['component_id'])
                except (OSError, ValueError) as error: add('Backup', 'Failed', str(error), backup['component_id'])
            # Completed catalogue entries omit incomplete/corrupt metadata; report
            # those directories separately, never silently call them healthy.
            if paths.backups.exists():
                known = {b['backup_id'] for b in manager.backups.catalog(checkpoint)}
                for path in no_symlinks(paths.backups).iterdir():
                    if path.name not in known: add('Backup', 'Incomplete', 'Unrecognized/incomplete snapshot: ' + path.name)
        from backend.capabilities import capabilities
        from backend.compatibility import inspect as host_inspect
        for ident, adapter in capabilities.proposals.items():
            checkpoint()
            try:
                receipt, _ = adapter.read_receipt(paths)
                state = host_inspect(paths, ident, receipt['checksums'] if receipt else None)
                add('Caelestia adapter', state['status'], ident + ': ' + state['detail'])
            except (OSError, ValueError) as error: add('Caelestia adapter', 'Host modified', ident + ': ' + str(error))
        from backend.store import Store
        store = Store(paths)
        catalog = store.cached()
        result['store'] = {'cached': bool(catalog), 'commit': (catalog or {}).get('commit'), 'notice': store.notice}
        result['history'] = manager.registry.history()
    except (OSError, sqlite3.Error, ValueError) as error: add('Database', 'Failed', str(error))
    finally:
        if manager is not None: manager.registry.db.close()
    return result

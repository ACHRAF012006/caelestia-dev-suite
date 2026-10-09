"""Versioned UTF-8 persistence, durable replace, last-good backup, one writer."""
import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile

SCHEMA_VERSION = 1
MIGRATIONS = {}  # source version -> pure function returning the next version
DEFAULT_SETTINGS = {'defaultSection': 'both', 'showCompleted': False, 'taskSort': 'manual',
                    'noteSort': 'updated', 'animation': True, 'compact': False, 'confirmDelete': True}


class StorageError(ValueError):
    pass


class UnsupportedSchema(StorageError):
    pass


def empty():
    return {'schemaVersion': SCHEMA_VERSION, 'revision': 0, 'notes': [], 'tasks': [], 'settings': dict(DEFAULT_SETTINGS)}


def migrate(value, target=SCHEMA_VERSION, migrations=None):
    """Never mutate the original; never downgrade an unknown future document."""
    migrations = MIGRATIONS if migrations is None else migrations
    value = copy.deepcopy(value)
    if not isinstance(value, dict) or type(value.get('schemaVersion')) is not int:
        raise StorageError('Missing or invalid storage schemaVersion')
    version = value['schemaVersion']
    if version > target: raise UnsupportedSchema(f'Data schema {version} is newer than supported schema {target}; update the component.')
    while version < target:
        if version not in migrations: raise UnsupportedSchema(f'No migration from schema {version}; original data retained.')
        value = migrations[version](copy.deepcopy(value))
        if not isinstance(value, dict) or value.get('schemaVersion') != version + 1:
            raise StorageError('Migration must advance exactly one schema version')
        version += 1
    return value


def validate_document(value):
    value = migrate(value)
    if type(value.get('revision')) is not int or value['revision'] < 0 or not isinstance(value.get('settings'), dict):
        raise StorageError('Invalid document revision/settings')
    for kind in ('notes', 'tasks'):
        rows = value.get(kind)
        if not isinstance(rows, list): raise StorageError('Invalid ' + kind)
        ids = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in ids:
                raise StorageError('Invalid or duplicate ' + kind + ' ID')
            ids.add(row['id'])
            for key in ('title', 'createdAt', 'updatedAt'):
                if not isinstance(row.get(key), str): raise StorageError('Invalid ' + key)
            if not isinstance(row.get('tags'), list) or any(not isinstance(tag, str) for tag in row['tags']): raise StorageError('Invalid tags')
            if kind == 'notes':
                if not isinstance(row.get('content'), dict) or row['content'].get('format') != 'plain' or not isinstance(row['content'].get('text'), str):
                    raise StorageError('Unsupported note format; original retained')
                if any(type(row.get(key)) is not bool for key in ('pinned', 'archived')): raise StorageError('Invalid note flags')
            else:
                from domain import validate_task
                validate_task(row)
    from domain import validate_settings
    validate_settings(value['settings'])
    value['settings'] = {**DEFAULT_SETTINGS, **value['settings']}
    return value


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise StorageError('Duplicate JSON key: ' + key)
            value[key] = item
        return value
    def constant(value): raise StorageError('Non-finite JSON value: ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)


def encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')


def atomic_replace(path, data):
    fd, name = tempfile.mkstemp(prefix='.save-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(name): os.unlink(name)


class Store:
    """Must remain locked for its lifetime, including before read and migration."""
    def __init__(self, directory=None):
        configured = os.environ.get('XDG_DATA_HOME', '')
        base = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / '.local/share'
        self.directory = Path(directory) if directory is not None else base / 'caelestia-components/notes-tasks'
        for path in (self.directory, *self.directory.parents):
            if path.is_symlink(): raise StorageError('Data directory cannot be a symbolic link')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / 'data.json'
        self.backup = self.directory / 'data.previous.json'
        lockpath = self.directory / 'writer.lock'
        for path in (self.path, self.backup, lockpath):
            if path.is_symlink(): raise StorageError('Data files cannot be symbolic links')
        self.lock = lockpath.open('a')
        os.chmod(lockpath, 0o600)
        try: fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise StorageError('Another Notes & Tasks writer is active; reload after it exits.')
        self.last_bytes = None

    def read(self):
        if not self.path.exists(): return empty()
        if self.path.stat().st_size > 64 * 1024 * 1024: raise StorageError('Oversized data; original retained')
        raw = self.path.read_bytes()
        try:
            value = decode(raw)
            checked = validate_document(value)
        except UnsupportedSchema: raise
        except (ValueError, UnicodeError, TypeError, KeyError) as error:
            raise StorageError('Data is malformed or unsupported; original retained. Inspect data.previous.json before manual recovery.') from error
        self.last_bytes = raw
        return checked

    def save(self, document):
        data = encode(validate_document(document))
        # Compare against the last read/written bytes: protect external edits.
        if self.path.is_symlink() or self.backup.is_symlink(): raise StorageError('Data files cannot be symbolic links')
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.last_bytes: raise StorageError('Data changed outside this writer; reload before saving.')
        if data == self.last_bytes: return False
        if self.last_bytes is not None: atomic_replace(self.backup, self.last_bytes)
        atomic_replace(self.path, data)
        self.last_bytes = data
        return True

    def close(self):
        if not self.lock.closed:
            fcntl.flock(self.lock, fcntl.LOCK_UN); self.lock.close()

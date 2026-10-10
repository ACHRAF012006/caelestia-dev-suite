"""Explicit, transactional SQLite upgrades; legacy unversioned databases are v0."""
import sqlite3
import uuid
from backend.paths import SafetyError, no_symlinks, fsync_directory

CURRENT_VERSION = 2
LEGACY = {
    'components': ('id', 'record'),
    'ownership': ('path', 'component', 'checksum', 'mode'),
    'events': ('time', 'component', 'message'),
}


def version(db): return db.execute('PRAGMA user_version').fetchone()[0]


def migrate(db, path):
    current = version(db)
    if current > CURRENT_VERSION:
        raise SafetyError(f"Database schema {current} is newer than supported {CURRENT_VERSION}; use a newer manager. Database preserved.")
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if current == 0 and tables:
        if tables != set(LEGACY) or any(tuple(r[1] for r in db.execute(f'PRAGMA table_info({table})')) != columns for table, columns in LEGACY.items()):
            raise SafetyError('Unrecognized legacy database structure; preserve the database and inspect it before upgrading.')
    if current == CURRENT_VERSION: return
    if tables:
        directory = no_symlinks(path.parent / 'database-backups')
        directory.mkdir(parents=True, exist_ok=True)
        backup = directory / f'v{current}-{uuid.uuid4().hex}.sqlite3'
        destination = sqlite3.connect(backup)
        try: db.backup(destination)
        finally: destination.close()
        backup.chmod(0o600)
        with backup.open('rb') as stream:
            import os
            os.fsync(stream.fileno())
        fsync_directory(directory)
    try:
        db.execute('BEGIN IMMEDIATE')
        # Reread after the lock: another manager may have just completed migration.
        current = version(db)
        if current > CURRENT_VERSION: raise SafetyError('Database was upgraded by a newer manager')
        if current < 1:
            for statement in (
                'CREATE TABLE IF NOT EXISTS components(id TEXT PRIMARY KEY, record TEXT NOT NULL)',
                'CREATE TABLE IF NOT EXISTS ownership(path TEXT PRIMARY KEY, component TEXT NOT NULL, checksum TEXT NOT NULL, mode INTEGER NOT NULL)',
                'CREATE TABLE IF NOT EXISTS events(time TEXT NOT NULL, component TEXT, message TEXT NOT NULL)',
            ): db.execute(statement)
            db.execute('PRAGMA user_version=1')
        if current < 2:
            db.execute('CREATE TABLE operations(id TEXT PRIMARY KEY, time TEXT NOT NULL, type TEXT NOT NULL, component TEXT, version TEXT, state TEXT NOT NULL, transaction_id TEXT, error_category TEXT)')
            db.execute('CREATE INDEX operations_time ON operations(time)')
            db.execute('CREATE INDEX ownership_component ON ownership(component)')
            db.execute('PRAGMA user_version=2')
        db.commit()
    except Exception as error:
        db.rollback()
        raise SafetyError('Database migration failed; no partial schema was committed. Preserve database/WAL and use database-backups for recovery: ' + str(error)) from error

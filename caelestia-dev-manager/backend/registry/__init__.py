import json
import sqlite3
from backend.paths import no_symlinks, SafetyError

class Registry:
    def __init__(self, path):
        path = no_symlinks(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.log_directory = path.parent / "logs"
        try:
            from backend.database import migrate
            migrate(self.db, path)
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
        except Exception as error:
            self.db.close()
            if isinstance(error, SafetyError): raise
            raise SafetyError('Database cannot be opened safely; preserve it and its WAL before recovery: ' + str(error)) from error

    def get(self, id):
        row = self.db.execute("SELECT record FROM components WHERE id=?", (id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT record FROM components ORDER BY id")]

    def save(self, record):
        self.db.execute("INSERT OR REPLACE INTO components VALUES(?,?)", (record["id"], json.dumps(record)))

    def files(self, id):
        return [{"path": p, "checksum": c, "mode": m} for p, c, m in self.db.execute("SELECT path,checksum,mode FROM ownership WHERE component=? ORDER BY path", (id,))]

    def owner(self, path):
        row = self.db.execute("SELECT component FROM ownership WHERE path=?", (str(path),)).fetchone()
        return row[0] if row else None

    def replace_files(self, id, files):
        self.db.execute("DELETE FROM ownership WHERE component=?", (id,))
        self.db.executemany("INSERT INTO ownership VALUES(?,?,?,?)", [(f["path"], id, f["checksum"], f["mode"]) for f in files])

    def log(self, id, message):
        from datetime import datetime, timezone
        from backend.dependencies import clean_output
        from backend.logging import logger
        logger(self.log_directory).info(clean_output(message))
        self.db.execute("INSERT INTO events VALUES(?,?,?)", (datetime.now(timezone.utc).isoformat(), id, clean_output(message)))
        self.db.execute('DELETE FROM events WHERE rowid NOT IN (SELECT rowid FROM events ORDER BY rowid DESC LIMIT 3000)')

    def logs(self):
        return [" • ".join(str(x or "manager") for x in row) for row in self.db.execute("SELECT * FROM events ORDER BY rowid DESC LIMIT 300")]

    def operation(self, kind, component=None, version=None, state='succeeded', transaction_id=None, error_category=None):
        from backend.backups import now
        import uuid
        self.db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?,?)',
                        (uuid.uuid4().hex, now(), kind, component, version, state, transaction_id, error_category))
        self.db.execute('DELETE FROM operations WHERE id NOT IN (SELECT id FROM operations ORDER BY time DESC LIMIT 3000)')

    def history(self, limit=300):
        columns = ('id', 'time', 'type', 'component', 'version', 'state', 'transaction_id', 'error_category')
        return [dict(zip(columns, row)) for row in self.db.execute('SELECT * FROM operations ORDER BY time DESC LIMIT ?', (min(max(limit, 1), 3000),))]

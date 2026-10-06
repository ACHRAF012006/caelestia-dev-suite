import json
import sqlite3
from backend.paths import no_symlinks

class Registry:
    def __init__(self, path):
        path = no_symlinks(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS components(id TEXT PRIMARY KEY, record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ownership(path TEXT PRIMARY KEY, component TEXT NOT NULL, checksum TEXT NOT NULL, mode INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS events(time TEXT NOT NULL, component TEXT, message TEXT NOT NULL);
        ''')
        self.db.commit()

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
        self.db.execute("INSERT INTO events VALUES(?,?,?)", (datetime.now(timezone.utc).isoformat(), id, message))

    def logs(self):
        return [" • ".join(str(x or "manager") for x in row) for row in self.db.execute("SELECT * FROM events ORDER BY rowid DESC LIMIT 300")]

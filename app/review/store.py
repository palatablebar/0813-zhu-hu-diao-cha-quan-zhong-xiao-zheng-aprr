import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.business import DomainIssue

SCHEMA = """CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, report TEXT NOT NULL, created TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', revision INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '', reviewed TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT NOT NULL, at TEXT NOT NULL,
    revision INTEGER NOT NULL, status TEXT NOT NULL, outcome TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '', blockers TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS attempts_run ON attempts(run, id);"""


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
            db.row_factory = sqlite3.Row
            db.executescript(SCHEMA)
            yield db

    def register(self, run_id, report):
        with self.connect() as db:
            db.execute(
                "INSERT INTO runs(id,report,created) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING",
                (
                    run_id,
                    json.dumps(report, ensure_ascii=False),
                    report["manifest"]["created"],
                ),
            )
        return self.load(run_id)

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise DomainIssue("RUN_NOT_FOUND")
            attempts = [
                dict(item)
                for item in db.execute(
                    "SELECT * FROM attempts WHERE run=? ORDER BY id", (run_id,)
                )
            ]
        result = dict(row)
        result["report"] = json.loads(result["report"])
        for item in attempts:
            item["blockers"] = json.loads(item["blockers"])
        result["attempts"] = attempts
        return result

    def list(self):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,created,status,revision,note FROM runs ORDER BY created DESC,id LIMIT 50"
                )
            ]

    def note_attempt(self, run_id, revision, status, outcome, note, blockers, now):
        with self.connect() as db:
            db.execute(
                "INSERT INTO attempts(run,at,revision,status,outcome,note,blockers)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    now,
                    revision,
                    status,
                    outcome,
                    note,
                    json.dumps(blockers, ensure_ascii=False),
                ),
            )

    def revise(self, run_id, revision, status, note, now):
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE runs SET status=?,note=?,reviewed=?,revision=revision+1 WHERE id=? AND revision=?",
                (status, note, now, run_id, revision),
            )
            if cursor.rowcount != 1:
                raise DomainIssue("STALE_REVIEW")
            db.execute(
                "INSERT INTO attempts(run,at,revision,status,outcome,note,blockers)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    now,
                    revision + 1,
                    status,
                    "COMMITTED",
                    note,
                    "[]",
                ),
            )
        return self.load(run_id)
